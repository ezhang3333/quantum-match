import numpy as np

def find_top_matches(live_embedding, db_embeddings, db_names, n=3):
    """
    Find the top-N most similar faces in the database to the live embedding
    """
    live_norm = live_embedding / (np.linalg.norm(live_embedding) + 1e-10)
    db_norms = db_embeddings / (np.linalg.norm(db_embeddings, axis=1, keepdims=True) + 1e-10)

    scores = db_norms @ live_norm
    top_indices = np.argsort(scores)[::-1][:n]

    return [(db_names[i], float(scores[i])) for i in top_indices]