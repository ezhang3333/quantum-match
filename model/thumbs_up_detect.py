import math
import time

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


# -----------------------------
# Config
# -----------------------------
CAMERA_ID = 0
WIDTH = 1280
HEIGHT = 720

MODEL_PATH = "hand_landmarker.task"

MIN_HAND_DETECTION_CONFIDENCE = 0.6
MIN_HAND_PRESENCE_CONFIDENCE = 0.6
MIN_TRACKING_CONFIDENCE = 0.6

THUMBS_UP_HOLD_TIME = 0.35


# -----------------------------
# Landmark indices
# -----------------------------
WRIST = 0

THUMB_CMC = 1
THUMB_MCP = 2
THUMB_IP = 3
THUMB_TIP = 4

INDEX_MCP = 5
INDEX_PIP = 6
INDEX_DIP = 7
INDEX_TIP = 8

MIDDLE_MCP = 9
MIDDLE_PIP = 10
MIDDLE_DIP = 11
MIDDLE_TIP = 12

RING_MCP = 13
RING_PIP = 14
RING_DIP = 15
RING_TIP = 16

PINKY_MCP = 17
PINKY_PIP = 18
PINKY_DIP = 19
PINKY_TIP = 20


# -----------------------------
# MediaPipe setup
# -----------------------------
def create_landmarker():
    base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
    options = vision.HandLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.VIDEO,
        num_hands=1,
        min_hand_detection_confidence=MIN_HAND_DETECTION_CONFIDENCE,
        min_hand_presence_confidence=MIN_HAND_PRESENCE_CONFIDENCE,
        min_tracking_confidence=MIN_TRACKING_CONFIDENCE,
    )
    return vision.HandLandmarker.create_from_options(options)


# -----------------------------
# Gesture helpers
# -----------------------------
def finger_curled(lms, tip_idx, pip_idx):
    return lms[tip_idx].y > lms[pip_idx].y


def thumb_up(lms):
    return (lms[THUMB_TIP].y < lms[THUMB_IP].y < lms[THUMB_MCP].y)


def thumb_far_from_hand(lms):
    thumb_tip = lms[THUMB_TIP]
    index_mcp = lms[INDEX_MCP]
    wrist = lms[WRIST]

    thumb_to_index = math.hypot(thumb_tip.x - index_mcp.x, thumb_tip.y - index_mcp.y)
    wrist_to_index = math.hypot(wrist.x - index_mcp.x, wrist.y - index_mcp.y)

    if wrist_to_index < 1e-6:
        return False

    return thumb_to_index > 0.45 * wrist_to_index


def is_thumbs_up(lms):
    thumb_ok = thumb_up(lms) and thumb_far_from_hand(lms)

    index_curled = finger_curled(lms, INDEX_TIP, INDEX_PIP)
    middle_curled = finger_curled(lms, MIDDLE_TIP, MIDDLE_PIP)
    ring_curled = finger_curled(lms, RING_TIP, RING_PIP)
    pinky_curled = finger_curled(lms, PINKY_TIP, PINKY_PIP)

    curled_count = sum([index_curled, middle_curled, ring_curled, pinky_curled])

    return thumb_ok and curled_count >= 3


def draw_status(frame, text, color):
    cv2.rectangle(frame, (0, 0), (frame.shape[1], 80), (20, 20, 20), -1)
    cv2.putText(
        frame,
        text,
        (20, 50),
        cv2.FONT_HERSHEY_DUPLEX,
        1.2,
        color,
        3,
    )


# -----------------------------
# Reusable detector for the server
# -----------------------------
class ThumbsUpDetector:
    def __init__(self, hold_time: float = THUMBS_UP_HOLD_TIME):
        self.hold_time = hold_time
        self.landmarker = create_landmarker()
        self._started_at: float | None = None
        self._last_ts_ms = 0

    def reset(self):
        self._started_at = None

    def process_frame(self, frame, ts_ms: int | None = None) -> bool:
        """Run one inference on a BGR frame. Returns True once the user has held
        a thumbs-up for `hold_time` seconds."""
        if ts_ms is None:
            ts_ms = int(time.monotonic() * 1000)
        ts_ms = max(ts_ms, self._last_ts_ms + 1)
        self._last_ts_ms = ts_ms

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        result = self.landmarker.detect_for_video(mp_image, ts_ms)

        thumbs_up_now = False
        if result.hand_landmarks and len(result.hand_landmarks) > 0:
            thumbs_up_now = is_thumbs_up(result.hand_landmarks[0])

        now = time.time()
        if thumbs_up_now:
            if self._started_at is None:
                self._started_at = now
            elif now - self._started_at >= self.hold_time:
                return True
        else:
            self._started_at = None

        return False


# -----------------------------
# Standalone entry (for solo testing)
# -----------------------------
def main():
    cap = cv2.VideoCapture(CAMERA_ID, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, 30)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    if not cap.isOpened():
        print("ERROR: Could not open camera.")
        return

    detector = ThumbsUpDetector()
    detected = False

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("ERROR: Failed to read frame.")
                break

            frame = cv2.flip(frame, 1)
            frame = cv2.resize(frame, (WIDTH, HEIGHT))

            detected = detector.process_frame(frame)

            if detected:
                draw_status(frame, "CONFIRMED", (0, 255, 120))
                cv2.putText(
                    frame,
                    "THUMBS UP DETECTED",
                    (WIDTH // 2 - 230, HEIGHT // 2),
                    cv2.FONT_HERSHEY_TRIPLEX,
                    1.2,
                    (0, 255, 120),
                    3,
                )
                print("THUMBS_UP_DETECTED", flush=True)
                cv2.imshow("Thumbs Up Detector", frame)
                cv2.waitKey(1000)
                break
            elif detector._started_at is not None:
                draw_status(frame, "THUMBS UP", (0, 220, 255))
            else:
                draw_status(frame, "WAITING", (200, 200, 200))

            cv2.imshow("Thumbs Up Detector", frame)
            key = cv2.waitKey(1) & 0xFF

            if key == 27 or key == ord("q"):
                break

    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
