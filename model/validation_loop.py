"""Validation override: when VALIDATE_NAME is set, the camera loop still pulls
real webcam frames for the live preview and the thumbs-up detector, but the
frame fed into FaceCollector is replaced with a noisy version of a known DB
image. End result: the kiosk runs exactly like production, except the match
shown is whatever the model picks for the noisy reference face.
"""

from __future__ import annotations

import os
from pathlib import Path

import cv2
import numpy as np


NOISE_LEVELS = {
    "mild": {"sigma": 10.0, "jpeg_quality": 70},
    "harsh": {"sigma": 25.0, "jpeg_quality": 30},
}


def _add_gaussian_noise(img: np.ndarray, sigma: float) -> np.ndarray:
    noise = np.zeros_like(img, dtype=np.int16)
    cv2.randn(noise, 0, sigma)
    return np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)


def _jpeg_round_trip(img: np.ndarray, quality: int) -> np.ndarray:
    ok, enc = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, int(quality)])
    if not ok:
        return img
    decoded = cv2.imdecode(enc, cv2.IMREAD_COLOR)
    return decoded if decoded is not None else img


def load_validation_frame(raw_images_dir: Path) -> np.ndarray | None:
    """Reads VALIDATE_NAME from env, looks up the matching JPG in raw_images_dir,
    applies VALIDATE_NOISE noise, and returns the final BGR frame to feed the
    face model. Returns None if validation isn't enabled or the file is missing."""
    name = os.environ.get("VALIDATE_NAME", "").strip()
    if not name:
        return None

    candidates = [
        raw_images_dir / f"{name}.jpg",
        raw_images_dir / f"{name.replace('_', ' ')}.jpg",
        raw_images_dir / f"{name.replace(' ', '_')}.jpg",
    ]
    path = next((c for c in candidates if c.exists()), None)
    if path is None:
        print(f"[validation] no image found for VALIDATE_NAME={name!r} in {raw_images_dir}")
        return None

    img = cv2.imread(str(path))
    if img is None:
        print(f"[validation] cv2.imread failed for {path}")
        return None

    level = os.environ.get("VALIDATE_NOISE", "harsh").lower()
    cfg = NOISE_LEVELS.get(level, NOISE_LEVELS["harsh"])
    noisy = _add_gaussian_noise(img, cfg["sigma"])
    noisy = _jpeg_round_trip(noisy, cfg["jpeg_quality"])

    print(f"[validation] feeding noisy {path.name} (level={level}) to face model")
    return noisy
