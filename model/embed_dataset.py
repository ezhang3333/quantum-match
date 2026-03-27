import json
import cv2
import insightface
import numpy as np

from .settings import PROFILES_PATH, OUT_EMBEDDINGS, OUT_NAMES


def build_database():
    with open(PROFILES_PATH) as f:
        profiles = json.load(f)

    app = insightface.app.FaceAnalysis(name="buffalo_l")
    app.prepare(ctx_id=0, det_size=(320, 320))

    embeddings = []
    names = []
    skipped = []

    for person_id, profile in profiles.items():
        path = profile.get("image_path", "")
        if not path:
            skipped.append(person_id)
            continue

        img = cv2.imread(path)
        if img is None:
            skipped.append(person_id)
            continue

        faces = app.get(img)
        if not faces or faces[0].embedding is None:
            skipped.append(person_id)
            continue

        embeddings.append(faces[0].embedding)
        names.append(profile["name"])
        del img

    if not embeddings:
        print("No embeddings generated")
        return

    np.save(OUT_EMBEDDINGS, np.array(embeddings, dtype=np.float32))
    with open(OUT_NAMES, "w") as f:
        json.dump(names, f, indent=2)

    if skipped:
        print(f"\nSkipped: {skipped}")


if __name__ == "__main__":
    build_database()
