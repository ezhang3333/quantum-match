# This file is meant only to be able to see if our raspberry pi can actually read the Logitech C270 camera and output a result

import os
import cv2
import time
import insightface
import numpy as np
from model.settings import CAPTURED_FACE_PATH, WARMUP_FRAMES, MIN_DET_SCORE, FRAMES_TO_COLLECT, INFERENCE_EVERY_N_FRAMES
from model.face_match import load_database, find_top_matches

RASPBERRY_PI_LOGITECH_CAMERA = '/dev/video0'

app = insightface.app.FaceAnalysis(name="buffalo_l")
app.prepare(ctx_id=0, det_size=(320, 320))

db_embeddings, db_names = load_database()

cap = cv2.VideoCapture(RASPBERRY_PI_LOGITECH_CAMERA, cv2.CAP_V4L2)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
cap.set(cv2.CAP_PROP_FPS, 30)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
time.sleep(2)

if not cap.isOpened():
    raise RuntimeError("Could not open webcam")

frame_count = 0
collected_embeddings = []
best_frame = None
best_face = None
inference_frame_counter = 0

print("Warming up camera...")
for i in range(WARMUP_FRAMES):
    ret, frame = cap.read()
    if ret:
        cv2.imwrite("live_test.jpg", frame)
        print(f"  Warmup frame {i+1}/{WARMUP_FRAMES} saved to live_test.jpg")

print("Collecting face embeddings...")
while True:
    ret, frame = cap.read()
    if not ret:
        break

    if inference_frame_counter % INFERENCE_EVERY_N_FRAMES == 0:
        faces = app.get(frame)
        for face in faces:
            if face.embedding is None or face.det_score < MIN_DET_SCORE:
                continue
            collected_embeddings.append(face.embedding)
            best_frame = frame.copy()
            best_face = face
            print(f"  Collected {len(collected_embeddings)}/{FRAMES_TO_COLLECT}")

    inference_frame_counter += 1

    if len(collected_embeddings) >= FRAMES_TO_COLLECT:
        avg_embedding = np.mean(collected_embeddings, axis=0)
        matches = find_top_matches(avg_embedding, db_embeddings, db_names, n=3)

        print("\nTop matches:")
        for i, (name, score) in enumerate(matches, 1):
            print(f"  {i}. {name} ({score:.3f})")

        if best_face is not None:
            x1, y1, x2, y2 = [int(v) for v in best_face.bbox]
            face_crop = best_frame[y1:y2, x1:x2]
            cv2.imwrite(CAPTURED_FACE_PATH, face_crop)
            print(f"Captured face saved to: {CAPTURED_FACE_PATH}")
        break

cap.release()