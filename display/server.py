from __future__ import annotations

import json
import os
import time
import base64
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import cv2
import insightface
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

try:
    from .face_match import find_top_matches
except ImportError:
    from face_match import find_top_matches


MIN_DET_SCORE = 0.7
FRAMES_TO_COLLECT = 6
FACE_WIDTH = 640
FACE_HEIGHT = 360
VALID_CATEGORIES = {"scientist", "engineer", "entrepreneur"}

REPO_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = REPO_ROOT / "display" / "frontend" / "dist" / "frontend" / "browser"
RAW_IMAGES_DIR = REPO_ROOT / "model" / "data" / "raw_images"

DB_DIR = REPO_ROOT / "model" / "data"
DB_EMBEDDINGS_PATH = DB_DIR / "embeddings.npy"
DB_NAMES_PATH = DB_DIR / "names.json"
DB_PROFILES_PATH = DB_DIR / "profiles.json"


class MatchProfile(BaseModel):
    name: str
    similarity: float
    role: str
    position: str
    research_areas: list[str]
    image_url: str
    profile_url: str
    summary: str
    category: str


class FaceError(BaseModel):
    reason: Literal["no_face", "multiple_faces", "no_match"]
    count: int


class MatchResponse(BaseModel):
    matches: list[MatchProfile] = []
    error: FaceError | None = None


class MatchRequest(BaseModel):
    category: Literal["scientist", "engineer", "entrepreneur"]
    frames: list[str]


def resize_frame(frame: np.ndarray, width: int, height: int) -> np.ndarray:
    if frame.shape[1] == width and frame.shape[0] == height:
        return frame
    return cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)


def decode_image(data: bytes) -> np.ndarray:
    arr = np.frombuffer(data, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("invalid image")
    return frame


def decode_data_url_image(value: str) -> np.ndarray:
    if "," in value:
        _, value = value.split(",", 1)
    try:
        data = base64.b64decode(value, validate=True)
    except ValueError as exc:
        raise ValueError("invalid base64 image") from exc
    return decode_image(data)


class FaceMatcher:
    def __init__(
        self,
        db_embeddings: np.ndarray,
        db_names: list[str],
        profiles: dict,
        category_masks: dict[str, np.ndarray],
    ):
        self.face_model = insightface.app.FaceAnalysis(name="buffalo_l")
        self.face_model.prepare(ctx_id=0, det_size=(320, 320))
        self.db_embeddings = db_embeddings
        self.db_names = db_names
        self.profiles = profiles
        self.category_masks = category_masks

    def _enrich(self, name: str, score: float) -> MatchProfile:
        profile = self.profiles.get(name, {})
        return MatchProfile(
            name=name,
            similarity=float(score),
            role=profile.get("role", ""),
            position=profile.get("position", ""),
            research_areas=profile.get("research_areas", []),
            image_url=f"/images/{name}.jpg",
            profile_url=profile.get("profile_url", ""),
            summary=profile.get("summary", ""),
            category=profile.get("category", ""),
        )

    def extract_embedding(self, frame: np.ndarray) -> tuple[np.ndarray | None, FaceError | None]:
        frame = resize_frame(frame, FACE_WIDTH, FACE_HEIGHT)
        faces = self.face_model.get(frame)

        if len(faces) != 1:
            reason: Literal["no_face", "multiple_faces"] = "no_face" if len(faces) == 0 else "multiple_faces"
            return None, FaceError(reason=reason, count=len(faces))

        face = faces[0]
        if face.det_score <= MIN_DET_SCORE or face.embedding is None:
            return None, None

        return face.embedding, None

    def match_frames(self, frames: list[np.ndarray], category: str | None) -> MatchResponse:
        embeddings: list[np.ndarray] = []
        saw_multiple_faces = False

        for frame in frames:
            embedding, error = self.extract_embedding(frame)
            if error is not None:
                saw_multiple_faces = saw_multiple_faces or error.reason == "multiple_faces"
                continue
            if embedding is not None:
                embeddings.append(embedding)
                if len(embeddings) >= FRAMES_TO_COLLECT:
                    break

        if len(embeddings) < FRAMES_TO_COLLECT:
            return MatchResponse(
                error=FaceError(
                    reason="multiple_faces" if saw_multiple_faces else "no_face",
                    count=2 if saw_multiple_faces else 0,
                )
            )

        if len(self.db_embeddings) == 0:
            return MatchResponse(error=FaceError(reason="no_match", count=0))

        avg_embedding = np.mean(embeddings, axis=0)
        emb_subset = self.db_embeddings
        names_subset = self.db_names

        if category and category in self.category_masks:
            mask = self.category_masks[category]
            emb_subset = self.db_embeddings[mask]
            names_subset = [name for name, include in zip(self.db_names, mask) if include]

        if len(emb_subset) == 0:
            return MatchResponse(error=FaceError(reason="no_match", count=0))

        raw = find_top_matches(avg_embedding, emb_subset, names_subset, n=3)
        matches = [self._enrich(name, score) for name, score in raw]
        if not matches:
            return MatchResponse(error=FaceError(reason="no_match", count=0))
        return MatchResponse(matches=matches)


def load_face_database() -> tuple[np.ndarray, list[str], dict, dict[str, np.ndarray]]:
    if not (DB_EMBEDDINGS_PATH.exists() and DB_NAMES_PATH.exists()):
        print(f"WARN: face DB not found at {DB_DIR}; matching will return no_match.")
        return np.zeros((0, 512), dtype=np.float32), [], {}, {}

    embeddings = np.load(DB_EMBEDDINGS_PATH)
    with open(DB_NAMES_PATH, "r", encoding="utf-8") as f:
        names = json.load(f)

    profiles: dict = {}
    if DB_PROFILES_PATH.exists():
        with open(DB_PROFILES_PATH, "r", encoding="utf-8") as f:
            profiles = json.load(f)

    masks: dict[str, np.ndarray] = {}
    for cat in VALID_CATEGORIES:
        masks[cat] = np.array(
            [profiles.get(name, {}).get("category") == cat for name in names],
            dtype=bool,
        )

    mask_counts = {cat: int(mask.sum()) for cat, mask in masks.items()}
    print(f"Loaded face DB: {len(names)} identities, {len(profiles)} profiles. Categories: {mask_counts}")
    return embeddings, names, profiles, masks


matcher: FaceMatcher | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global matcher
    started = time.perf_counter()
    db_embeddings, db_names, profiles, category_masks = load_face_database()
    matcher = FaceMatcher(db_embeddings, db_names, profiles, category_masks)
    print(f"Face matcher initialized in {time.perf_counter() - started:.2f}s")
    yield


app = FastAPI(title="Quantum Mirror Web API", lifespan=lifespan)

default_origins = [
    "http://localhost:4200",
    "http://127.0.0.1:4200",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
configured_origins = [
    origin.strip()
    for origin in os.environ.get("QM_CORS_ORIGINS", "").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=configured_origins or default_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"ok": matcher is not None}


@app.post("/api/match", response_model=MatchResponse)
async def match_faces(request: MatchRequest):
    if matcher is None:
        raise HTTPException(status_code=503, detail="Face matcher is still starting")
    if len(request.frames) < FRAMES_TO_COLLECT:
        raise HTTPException(status_code=400, detail=f"At least {FRAMES_TO_COLLECT} frames are required")

    decoded_frames: list[np.ndarray] = []
    for index, frame in enumerate(request.frames):
        try:
            decoded_frames.append(decode_data_url_image(frame))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid image frame at index {index}") from exc

    return matcher.match_frames(decoded_frames, request.category)


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
