import os

CATEGORIES = ["scientists", "engineers", "entrepreneurs"]

# legacy url
QUANTUM_SCIENTIST_DATABASE_URL = "https://quantumzeitgeist.com/influential-people-in-quantum-computing/"

BASE_URL = "https://perimeterinstitute.ca"
PERIMETER_PEOPLE_URL = "https://perimeterinstitute.ca/people"

_MODEL_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(_MODEL_DIR, "data")
RAW_IMAGES_DIR = os.path.join(DATA_DIR, "raw_images")
PROFILES_PATH = os.path.join(DATA_DIR, "profiles.json")
OUT_EMBEDDINGS = os.path.join(DATA_DIR, "embeddings.npy")
OUT_NAMES = os.path.join(DATA_DIR, "names.json")
CAPTURED_FACE_PATH = os.path.join(DATA_DIR, "captured_face.jpg")

# live camera feed parameters
WARMUP_FRAMES = 10
MIN_DET_SCORE = 0.7
FRAMES_TO_COLLECT = 6
INFERENCE_EVERY_N_FRAMES = 3
