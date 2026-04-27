from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from face_match import find_top_matches
from thumbs_up_detect import ThumbsUpDetector
from validation_loop import load_validation_frame

import json
import time
import queue
import asyncio
import threading
from pathlib import Path
from contextlib import asynccontextmanager

import cv2
import numpy as np
import insightface

# config globals
WARMUP_FRAMES = 60
MIN_DET_SCORE = 0.7
FRAMES_TO_COLLECT = 6
INFERENCE_EVERY_N_FRAMES = 3
LOGITECH_RASP_CAMERA_IDX = '/dev/video0'
LOCAL_CAMERA_IDX = 0

FRAME_WIDTH = 1280
FRAME_HEIGHT = 720
STREAM_WIDTH = 640
STREAM_HEIGHT = 360
THUMBS_WIDTH = 320
THUMBS_HEIGHT = 180
FACE_WIDTH = 640
FACE_HEIGHT = 360

REPO_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = REPO_ROOT / "display" / "frontend" / "dist" / "frontend" / "browser"
RAW_IMAGES_DIR = REPO_ROOT / "model" / "data" / "raw_images"

DB_DIR = REPO_ROOT / "model" / "data"
DB_EMBEDDINGS_PATH = DB_DIR / "embeddings.npy"
DB_NAMES_PATH = DB_DIR / "names.json"
DB_PROFILES_PATH = DB_DIR / "profiles.json"

event_queue: queue.Queue = queue.Queue()
# Latest JPEG frame from camera_loop; broadcast_event always sends the newest
# and discards any frame that arrived while the previous one was in flight.
latest_frame: bytes | None = None
frame_lock = threading.Lock()
active_websocket: WebSocket | None = None

# Mutated only by the WebSocket handler (single writer); read by camera_loop.
current_state: str = "idle"

thumbs_detector: ThumbsUpDetector | None = None
face_collector = None  # type: FaceCollector | None

# When VALIDATE_NAME is set, this holds a noisy version of the named DB image.
# camera_loop substitutes it for the live webcam frame in the face-inference
# step only — webcam preview + thumbs-up detection still use the real frame.
validation_frame: np.ndarray | None = None


def resize_frame(frame: np.ndarray, width: int, height: int) -> np.ndarray:
    if frame.shape[1] == width and frame.shape[0] == height:
        return frame
    return cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)


class FaceCollector:
    """Collects FRAMES_TO_COLLECT face embeddings, averages them, and emits a
    match_result event with profile metadata enriched from profiles.json."""

    def __init__(self, db_embeddings: np.ndarray, db_names: list[str], profiles: dict):
        self.face_model = insightface.app.FaceAnalysis(name="buffalo_l")
        self.face_model.prepare(ctx_id=0, det_size=(320, 320))
        self.db_embeddings = db_embeddings
        self.db_names = db_names
        self.profiles = profiles
        self.collected: list[np.ndarray] = []
        self._frame_count = 0

    def reset(self):
        self.collected = []
        self._frame_count = 0

    def _enrich(self, name: str, score: float) -> dict:
        profile = self.profiles.get(name, {})
        return {
            "name": name,
            "similarity": float(score),
            "role": profile.get("role", ""),
            "position": profile.get("position", ""),
            "research_areas": profile.get("research_areas", []),
            "image_url": f"/images/{name}.jpg",
            "profile_url": profile.get("profile_url", ""),
        }

    def process_frame(self, frame) -> dict | None:
        self._frame_count += 1
        if self._frame_count % INFERENCE_EVERY_N_FRAMES != 0:
            return None

        frame = resize_frame(frame, FACE_WIDTH, FACE_HEIGHT)
        faces = self.face_model.get(frame)

        if len(faces) != 1:
            return {
                "type": "face_error",
                "reason": "no_face" if len(faces) == 0 else "multiple_faces",
                "count": len(faces),
            }

        face = faces[0]
        if face.det_score <= MIN_DET_SCORE or face.embedding is None:
            return None

        self.collected.append(face.embedding)

        if len(self.collected) < FRAMES_TO_COLLECT:
            return {
                "type": "collecting",
                "progress": len(self.collected),
                "total": FRAMES_TO_COLLECT,
            }

        avg_embedding = np.mean(self.collected, axis=0)
        self.collected = []

        if len(self.db_embeddings) == 0:
            return {"type": "match_result", "matches": []}

        raw = find_top_matches(avg_embedding, self.db_embeddings, self.db_names, n=3)
        return {
            "type": "match_result",
            "matches": [self._enrich(name, score) for name, score in raw],
        }


def load_face_database() -> tuple[np.ndarray, list[str], dict]:
    if not (DB_EMBEDDINGS_PATH.exists() and DB_NAMES_PATH.exists()):
        print(f"WARN: face DB not found at {DB_DIR}; matching will return empty.")
        return np.zeros((0, 512), dtype=np.float32), [], {}

    embeddings = np.load(DB_EMBEDDINGS_PATH)
    with open(DB_NAMES_PATH, "r", encoding="utf-8") as f:
        names = json.load(f)

    profiles: dict = {}
    if DB_PROFILES_PATH.exists():
        with open(DB_PROFILES_PATH, "r", encoding="utf-8") as f:
            profiles = json.load(f)

    print(f"Loaded face DB: {len(names)} identities, {len(profiles)} profiles.")
    return embeddings, names, profiles


def camera_loop():
    # switch this with raspberry pi camera index when testing through raspberry pi
    cap = cv2.VideoCapture(LOCAL_CAMERA_IDX, cv2.CAP_V4L2)
    # MJPG lets USB 2.0 cams actually hit 30fps at 720p; YUYV is bandwidth-capped to ~5fps.
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, 30)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    if not cap.isOpened():
        raise RuntimeError("Could not open webcam")

    # Per-stage timing accumulators (ms), flushed to stdout every PERF_LOG_EVERY frames.
    PERF_LOG_EVERY = 30
    perf = {"read": 0.0, "gesture": 0.0, "face": 0.0, "encode": 0.0, "enqueue": 0.0, "total": 0.0}
    perf_frames = 0
    perf_state_counts: dict[str, int] = {}

    while True:
        loop_t0 = time.perf_counter()

        t0 = time.perf_counter()
        ret, frame = cap.read()
        read_ms = (time.perf_counter() - t0) * 1000.0
        if not ret:
            continue

        frame = cv2.flip(frame, 1)

        ts_ms = int(time.monotonic() * 1000)
        state = current_state

        gesture_ms = 0.0
        face_ms = 0.0

        if state == "idle" and thumbs_detector is not None:
            t0 = time.perf_counter()
            thumbs_frame = resize_frame(frame, THUMBS_WIDTH, THUMBS_HEIGHT)
            triggered = thumbs_detector.process_frame(thumbs_frame, ts_ms)
            gesture_ms = (time.perf_counter() - t0) * 1000.0
            if triggered:
                event_queue.put({"type": "thumbs_up_detected"})
                thumbs_detector.reset()
        elif state == "camera" and face_collector is not None:
            face_input = validation_frame if validation_frame is not None else frame
            t0 = time.perf_counter()
            event = face_collector.process_frame(face_input)
            face_ms = (time.perf_counter() - t0) * 1000.0
            if event is not None:
                event_queue.put(event)

        t0 = time.perf_counter()
        stream_frame = resize_frame(frame, STREAM_WIDTH, STREAM_HEIGHT)
        ok, buffer = cv2.imencode('.jpg', stream_frame, [cv2.IMWRITE_JPEG_QUALITY, 55])
        encode_ms = (time.perf_counter() - t0) * 1000.0

        enqueue_ms = 0.0
        if ok:
            t0 = time.perf_counter()
            global latest_frame
            with frame_lock:
                latest_frame = buffer.tobytes()
            enqueue_ms = (time.perf_counter() - t0) * 1000.0

        total_ms = (time.perf_counter() - loop_t0) * 1000.0

        perf["read"] += read_ms
        perf["gesture"] += gesture_ms
        perf["face"] += face_ms
        perf["encode"] += encode_ms
        perf["enqueue"] += enqueue_ms
        perf["total"] += total_ms
        perf_frames += 1
        perf_state_counts[state] = perf_state_counts.get(state, 0) + 1

        if perf_frames >= PERF_LOG_EVERY:
            avg = {k: v / perf_frames for k, v in perf.items()}
            fps = 1000.0 / avg["total"] if avg["total"] > 0 else 0.0
            qsize = event_queue.qsize()
            print(
                f"[perf] n={perf_frames} states={perf_state_counts} "
                f"read={avg['read']:.1f} gesture={avg['gesture']:.1f} "
                f"face={avg['face']:.1f} encode={avg['encode']:.1f} "
                f"enqueue={avg['enqueue']:.1f} total={avg['total']:.1f}ms "
                f"(~{fps:.1f} fps)  qsize={qsize}",
                flush=True,
            )
            for k in perf:
                perf[k] = 0.0
            perf_frames = 0
            perf_state_counts = {}


async def broadcast_event():
    global latest_frame
    while True:
        try:
            # Drain all pending JSON events first so status never lags frames.
            while True:
                try:
                    event = event_queue.get_nowait()
                except queue.Empty:
                    break
                if active_websocket is not None:
                    await active_websocket.send_json(event)

            # Then grab + clear the newest frame; any older frame has already
            # been overwritten by camera_loop, which is exactly what we want.
            frame_to_send: bytes | None = None
            with frame_lock:
                if latest_frame is not None:
                    frame_to_send = latest_frame
                    latest_frame = None

            if frame_to_send is not None and active_websocket is not None:
                await active_websocket.send_bytes(frame_to_send)
        except Exception as exc:
            print(f"broadcast_event: {exc}")
        await asyncio.sleep(0.01)


def _apply_state_change(new_state: str):
    """Reset the detector for the state we're entering, then update current_state.
    Reset before the swap so camera_loop never sees a stale detector."""
    global current_state
    if new_state == "idle" and thumbs_detector is not None:
        thumbs_detector.reset()
    elif new_state == "camera" and face_collector is not None:
        face_collector.reset()
    current_state = new_state


@asynccontextmanager
async def lifespan(app: FastAPI):
    global thumbs_detector, face_collector
    db_embeddings, db_names, profiles = load_face_database()
    face_collector = FaceCollector(db_embeddings, db_names, profiles)
    thumbs_detector = ThumbsUpDetector()

    global validation_frame
    validation_frame = load_validation_frame(RAW_IMAGES_DIR)

    threading.Thread(target=camera_loop, daemon=True).start()
    asyncio.create_task(broadcast_event())
    yield


app = FastAPI(title="Quantum Mirror", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",
        "http://localhost:5000",
        "http://127.0.0.1:5000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.websocket("/ws/camera")
async def websocket_camera(websocket: WebSocket):
    global active_websocket
    await websocket.accept()
    active_websocket = websocket
    try:
        while True:
            msg = await websocket.receive_json()
            if not isinstance(msg, dict):
                continue
            if msg.get("type") == "state_change":
                new_state = msg.get("state")
                if new_state in ("idle", "camera", "output"):
                    _apply_state_change(new_state)
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        print(f"websocket_camera: {exc}")
    finally:
        if active_websocket is websocket:
            active_websocket = None


if RAW_IMAGES_DIR.exists():
    app.mount("/images", StaticFiles(directory=str(RAW_IMAGES_DIR)), name="images")
else:
    print(f"WARN: {RAW_IMAGES_DIR} not found; /images route disabled.")

_media_dir = DIST_DIR / "media"
if _media_dir.exists():
    app.mount("/media", StaticFiles(directory=str(_media_dir)), name="media")
else:
    print(f"WARN: {_media_dir} not found; /media route disabled (run `ng build` first).")


@app.get("/")
async def root():
    return FileResponse(str(DIST_DIR / "index.html"))


@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    file_path = DIST_DIR / full_path
    if file_path.is_file():
        return FileResponse(str(file_path))
    return FileResponse(str(DIST_DIR / "index.html"))
