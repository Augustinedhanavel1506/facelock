import os
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
FROZEN = getattr(sys, "frozen", False)

# Read-only bundled assets: inside the PyInstaller temp extraction dir when
# packaged as an .exe, otherwise the assets/ folder next to the source.
ASSETS_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR)) / "assets"

# Writable per-user data: always a stable AppData location, independent of
# where the .exe/script happens to run from (a onefile .exe's own folder
# isn't reliably writable, and its temp extraction dir is wiped every run).
DATA_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "FaceLock"
EMBEDDINGS_PATH = DATA_DIR / "face_profiles.npz"
PIN_PATH = DATA_DIR / "pin.hash"
FAILED_ATTEMPTS_DIR = DATA_DIR / "failed_attempts"

DATA_DIR.mkdir(parents=True, exist_ok=True)
FAILED_ATTEMPTS_DIR.mkdir(exist_ok=True)

YUNET_MODEL_PATH = str(ASSETS_DIR / "face_detection_yunet_2023mar.onnx")
SFACE_MODEL_PATH = str(ASSETS_DIR / "face_recognition_sface_2021dec.onnx")

CAMERA_INDEX = 0

# SFace cosine similarity: higher = more similar (roughly 0..1). OpenCV's own
# benchmark recommends 0.363 as the genuine/impostor boundary; we go stricter
# since we're rejecting *specific* other people, not just any random face.
MATCH_THRESHOLD = 0.45
CONSEC_MATCHES_REQUIRED = 18
MISS_DECAY = 1
NO_FACE_TIMEOUT_SECS = 4.0
UNRECOGNIZED_TIMEOUT_SECS = 3.5

SAMPLES_PER_ENROLLMENT = 35

GLOBAL_HOTKEY = "ctrl+alt+l"

# Liveness (anti-photo-spoof): require the eye-midpoint to have drifted at
# least this many cumulative pixels across the matched-frame window before
# granting -- a rigid printed photo held in place won't naturally show this,
# real heads/hands always have some micro-movement. Not foolproof, but raises
# the bar well above "hold up a photo."
LIVENESS_MIN_MOVEMENT_PX = 7.0
LIVENESS_HISTORY_LEN = 30

# How many "unrecognized" events in one lock session before we warn the user.
SUSPICIOUS_ATTEMPT_THRESHOLD = 2

# Iron Man / J.A.R.V.I.S. HUD palette
COLOR_BG = "#020608"
COLOR_PRIMARY = (0, 217, 255)      # cyan - BGR-agnostic, used as RGB tuple
COLOR_PRIMARY_DIM = (0, 120, 150)
COLOR_ACCENT_GOLD = (255, 176, 46)
COLOR_DANGER = (255, 61, 61)
COLOR_SUCCESS = (72, 255, 168)
