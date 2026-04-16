import argparse
import gc
import sys
import time
from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# Hand landmark indices from MediaPipe Hands / Hand Landmarker
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


@dataclass
class DetectorConfig:
    model_path: str
    camera_id: int = 0
    width: int = 640
    height: int = 480
    min_hand_detection_confidence: float = 0.65
    min_hand_presence_confidence: float = 0.65
    min_tracking_confidence: float = 0.60
    num_hands: int = 2
    poll_hz: float = 12.0
    fists_hold_s: float = 0.25
    open_hold_s: float = 0.18
    max_transition_s: float = 1.20
    cooldown_s: float = 2.00
    outward_delta_x: float = 0.03
    outward_delta_y: float = 0.08
    debug: bool = False


class QuantumBloomDetector:
    def __init__(self, config: DetectorConfig):
        self.cfg = config
        self.state = "idle"
        self.fists_started_at: Optional[float] = None
        self.open_started_at: Optional[float] = None
        self.cooldown_until: float = 0.0
        self.baseline_distance: Optional[float] = None
        self.triggered = False

    @staticmethod
    def _finger_extended(lms, tip: int, pip: int, mcp: int) -> bool:
        # Normalized image coordinates: smaller y is higher on image.
        # For most front-facing palms, extended fingers have tip above PIP and MCP.
        return (lms[tip].y < lms[pip].y) and (lms[pip].y < lms[mcp].y)

    @staticmethod
    def _thumb_extended(lms, handedness: str) -> bool:
        # Thumb is trickier because it extends mostly sideways.
        # For a palm facing camera, thumb tip tends to sit laterally away from IP/MCP.
        if handedness == "Left":
            return lms[THUMB_TIP].x > lms[THUMB_IP].x > lms[THUMB_MCP].x
        return lms[THUMB_TIP].x < lms[THUMB_IP].x < lms[THUMB_MCP].x

    def _is_open_palm(self, lms, handedness: str) -> bool:
        straight_count = 0
        straight_count += int(self._thumb_extended(lms, handedness))
        straight_count += int(self._finger_extended(lms, INDEX_TIP, INDEX_PIP, INDEX_MCP))
        straight_count += int(self._finger_extended(lms, MIDDLE_TIP, MIDDLE_PIP, MIDDLE_MCP))
        straight_count += int(self._finger_extended(lms, RING_TIP, RING_PIP, RING_MCP))
        straight_count += int(self._finger_extended(lms, PINKY_TIP, PINKY_PIP, PINKY_MCP))
        return straight_count >= 4

    def _is_fist(self, lms, handedness: str) -> bool:
        curled_count = 0
        curled_count += int(not self._thumb_extended(lms, handedness))
        curled_count += int(lms[INDEX_TIP].y > lms[INDEX_PIP].y)
        curled_count += int(lms[MIDDLE_TIP].y > lms[MIDDLE_PIP].y)
        curled_count += int(lms[RING_TIP].y > lms[RING_PIP].y)
        curled_count += int(lms[PINKY_TIP].y > lms[PINKY_PIP].y)
        return curled_count >= 4

    @staticmethod
    def _palm_center(lms) -> Tuple[float, float]:
        xs = [lms[WRIST].x, lms[INDEX_MCP].x, lms[MIDDLE_MCP].x, lms[RING_MCP].x, lms[PINKY_MCP].x]
        ys = [lms[WRIST].y, lms[INDEX_MCP].y, lms[MIDDLE_MCP].y, lms[RING_MCP].y, lms[PINKY_MCP].y]
        return (sum(xs) / len(xs), sum(ys) / len(ys))

    @staticmethod
    def _distance(a: Tuple[float, float], b: Tuple[float, float]) -> float:
        dx = a[0] - b[0]
        dy = a[1] - b[1]
        return (dx * dx + dy * dy) ** 0.5

    def _parse_hands(self, result):
        hands = {}
        if not result.hand_landmarks or not result.handedness:
            return hands

        for i, lms in enumerate(result.hand_landmarks):
            if i >= len(result.handedness) or not result.handedness[i]:
                continue
            label = result.handedness[i][0].category_name
            hands[label] = {
                "landmarks": lms,
                "fist": self._is_fist(lms, label),
                "open": self._is_open_palm(lms, label),
                "center": self._palm_center(lms),
            }
        return hands

    def update(self, result, now_s: float) -> bool:
        self.triggered = False

        if now_s < self.cooldown_until:
            return False

        hands = self._parse_hands(result)
        left = hands.get("Left")
        right = hands.get("Right")

        if not left or not right:
            self._reset_to_idle()
            return False

        both_fists = left["fist"] and right["fist"]
        both_open = left["open"] and right["open"]
        current_distance = self._distance(left["center"], right["center"])
        vertical_ok = abs(left["center"][1] - right["center"][1]) <= self.cfg.outward_delta_y

        if self.state == "idle":
            if both_fists:
                if self.fists_started_at is None:
                    self.fists_started_at = now_s
                    self.baseline_distance = current_distance
                elif now_s - self.fists_started_at >= self.cfg.fists_hold_s:
                    self.state = "armed"
            else:
                self.fists_started_at = None
                self.baseline_distance = None
            return False

        if self.state == "armed":
            if now_s - (self.fists_started_at or now_s) > self.cfg.max_transition_s:
                self._reset_to_idle()
                return False

            if both_open and vertical_ok:
                outward_ok = True
                if self.baseline_distance is not None:
                    outward_ok = current_distance >= self.baseline_distance + self.cfg.outward_delta_x

                if outward_ok:
                    if self.open_started_at is None:
                        self.open_started_at = now_s
                    elif now_s - self.open_started_at >= self.cfg.open_hold_s:
                        self.triggered = True
                        self.cooldown_until = now_s + self.cfg.cooldown_s
                        self._reset_to_idle()
                        return True
                else:
                    self.open_started_at = None
            else:
                self.open_started_at = None
                if not both_fists and (self.fists_started_at is not None):
                    # User abandoned the gesture.
                    if now_s - self.fists_started_at > self.cfg.max_transition_s:
                        self._reset_to_idle()
            return False

        self._reset_to_idle()
        return False

    def _reset_to_idle(self):
        self.state = "idle"
        self.fists_started_at = None
        self.open_started_at = None
        self.baseline_distance = None


def create_landmarker(model_path: str, cfg: DetectorConfig):
    base_options = python.BaseOptions(model_asset_path=model_path)
    options = vision.HandLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.VIDEO,
        num_hands=cfg.num_hands,
        min_hand_detection_confidence=cfg.min_hand_detection_confidence,
        min_hand_presence_confidence=cfg.min_hand_presence_confidence,
        min_tracking_confidence=cfg.min_tracking_confidence,
    )
    return vision.HandLandmarker.create_from_options(options)


def parse_args() -> DetectorConfig:
    parser = argparse.ArgumentParser(description="Detect a two-hand quantum bloom gesture.")
    parser.add_argument("--model", type=str, default="hand_landmarker.task")
    parser.add_argument("--camera-id", type=int, default=0)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--poll-hz", type=float, default=12.0)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    return DetectorConfig(
        model_path=args.model,
        camera_id=args.camera_id,
        width=args.width,
        height=args.height,
        poll_hz=args.poll_hz,
        debug=args.debug,
    )


def main() -> int:
    cfg = parse_args()

    cap = cv2.VideoCapture(cfg.camera_id)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.height)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    if not cap.isOpened():
        print("ERROR: Could not open camera.", file=sys.stderr)
        return 1

    detector = QuantumBloomDetector(cfg)
    sleep_s = max(0.0, 1.0 / cfg.poll_hz)
    triggered = False

    try:
        with create_landmarker(cfg.model_path, cfg) as landmarker:
            while True:
                ok, frame = cap.read()
                if not ok:
                    print("ERROR: Failed to read camera frame.", file=sys.stderr)
                    return 1

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                timestamp_ms = int(time.monotonic() * 1000)
                result = landmarker.detect_for_video(mp_image, timestamp_ms)

                now_s = time.monotonic()
                triggered = detector.update(result, now_s)

                if cfg.debug:
                    status = detector.state
                    text = "TRIGGERED" if triggered else status.upper()
                    cv2.putText(frame, text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
                    cv2.imshow("quantum_bloom_debug", frame)
                    key = cv2.waitKey(1) & 0xFF
                    if key == 27 or key == ord("q"):
                        break
                else:
                    # No GUI window in normal mode; keeps memory and CPU lower.
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break

                if triggered:
                    print("QUANTUM_BLOOM_DETECTED", flush=True)
                    break

                if sleep_s:
                    time.sleep(sleep_s)
    finally:
        cap.release()
        cv2.destroyAllWindows()
        gc.collect()

    return 0 if triggered else 2


if __name__ == "__main__":
    raise SystemExit(main())
