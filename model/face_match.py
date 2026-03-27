import json
import os

import numpy as np

from .settings import OUT_EMBEDDINGS, OUT_NAMES


def load_database():
    """
    Load precomputed embeddings and names from disk
    This function should only be called once at startup
    with results kept in memory (embeddings.npy)
    """
    if not os.path.exists(OUT_EMBEDDINGS) or not os.path.exists(OUT_NAMES):
        raise FileNotFoundError(
            "Embedding database not found. Run model/embed_dataset.py first."
        )
    embeddings = np.load(OUT_EMBEDDINGS)
    with open(OUT_NAMES) as f:
        names = json.load(f)
    return embeddings, names


def find_top_matches(live_embedding, db_embeddings, db_names, n=3):
    """
    Find the top-N most similar faces in the database to the live embedding
    """
    live_norm = live_embedding / (np.linalg.norm(live_embedding) + 1e-10)
    db_norms = db_embeddings / (np.linalg.norm(db_embeddings, axis=1, keepdims=True) + 1e-10)

    scores = db_norms @ live_norm
    top_indices = np.argsort(scores)[::-1][:n]

    return [(db_names[i], float(scores[i])) for i in top_indices]
