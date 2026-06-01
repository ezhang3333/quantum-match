import os
import cv2
import insightface
import numpy as np
from model.settings import CAPTURED_FACE_PATH, WARMUP_FRAMES, MIN_DET_SCORE, FRAMES_TO_COLLECT, INFERENCE_EVERY_N_FRAMES
from model.face_match import load_database, find_top_matches

# these could change per OS and computer
LOCAL_CAMERA_INDEX = 0
RASPBERRY_PI_LOGITECH_CAMERA = '/dev/video0'
LOGTIECH_CAMERA_INDEX = 1

app = insightface.app.FaceAnalysis(name="buffalo_l")
app.prepare(ctx_id=0, det_size=(320, 320))

db_embeddings, db_names = load_database()

cap = cv2.VideoCapture(RASPBERRY_PI_LOGITECH_CAMERA, cv2.CAP_V4L2)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
cap.set(cv2.CAP_PROP_FPS, 30)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

if not cap.isOpened():
    raise RuntimeError("Could not open webcam")

frame_count = 0
collected_embeddings = []
best_frame = None
best_face = None
last_bbox = None
inference_frame_counter = 0

while True:
    ret, frame = cap.read()
    if not ret:
        break

    display = frame.copy()

    if frame_count < WARMUP_FRAMES:
        remaining = WARMUP_FRAMES - frame_count
        cv2.putText(display, f"Warming up... {remaining}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 200, 255), 2)
        cv2.imshow("Face Similarity", display)
        frame_count += 1
        if cv2.waitKey(1) & 0xFF == 27:
            break
        continue

    # Run inference every N frames to keep display smooth
    if inference_frame_counter % INFERENCE_EVERY_N_FRAMES == 0:
        faces = app.get(frame)
        for face in faces:
            if face.embedding is None or face.det_score < MIN_DET_SCORE:
                continue
            last_bbox = [int(v) for v in face.bbox]
            collected_embeddings.append(face.embedding)
            best_frame = frame.copy()
            best_face = face

    if last_bbox:
        x1, y1, x2, y2 = last_bbox
        cv2.rectangle(display, (x1, y1), (x2, y2), (0, 255, 0), 2)

    collected = len(collected_embeddings)
    cv2.putText(display, f"Collecting: {collected}/{FRAMES_TO_COLLECT}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 200, 255), 2)
    cv2.imshow("Face Similarity", display)
    frame_count += 1
    inference_frame_counter += 1

    if collected >= FRAMES_TO_COLLECT:
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

    # ESC key will cancel
    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()
