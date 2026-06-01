import os

CATEGORIES = ["scientists", "engineers", "entrepreneurs"]

# legacy url
QUANTUM_SCIENTIST_DATABASE_URL = "https://quantumzeitgeist.com/influential-people-in-quantum-computing/"

BASE_URL = "https://perimeterinstitute.ca"
PERIMETER_PEOPLE_URL = "https://perimeterinstitute.ca/people"
IQUIST_BASE_URL = "https://iquist.illinois.edu"
IQUIST_PEOPLE_URL = "https://iquist.illinois.edu/people"
QUANTUM_INSIDER_CTO_URL = "https://thequantuminsider.com/2021/08/05/11956/"

_MODEL_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(_MODEL_DIR, "data")
RAW_IMAGES_DIR = os.path.join(DATA_DIR, "raw_images")
PROFILES_PATH = os.path.join(DATA_DIR, "profiles.json")
PROFILE_INFO_PATH = os.path.join(DATA_DIR, "profile_info.json")
OUT_EMBEDDINGS = os.path.join(DATA_DIR, "embeddings.npy")
OUT_NAMES = os.path.join(DATA_DIR, "names.json")
CAPTURED_FACE_PATH = os.path.join(DATA_DIR, "captured_face.jpg")

# live camera feed parameters
WARMUP_FRAMES = 60
MIN_DET_SCORE = 0.7
FRAMES_TO_COLLECT = 6
INFERENCE_EVERY_N_FRAMES = 3
