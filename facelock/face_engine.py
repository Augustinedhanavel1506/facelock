import hashlib
import secrets

import cv2
import numpy as np

from . import config


class FaceEngine:
    """Face detection (YuNet) + face recognition (SFace embeddings).

    Unlike LBPH histograms, SFace produces a numeric "fingerprint" per face
    that generalizes to rejecting people who were never enrolled -- important
    since we typically only ever enroll one or two identities and need the
    model to actively discriminate against everyone else, not just memorize
    a single texture pattern.
    """

    def __init__(self):
        self.detector = cv2.FaceDetectorYN_create(
            config.YUNET_MODEL_PATH, "", (320, 320),
            score_threshold=0.85, nms_threshold=0.3, top_k=10,
        )
        self.recognizer = cv2.FaceRecognizerSF_create(config.SFACE_MODEL_PATH, "")
        self.profiles = {}  # name -> list[np.ndarray] of embeddings
        self._load()

    def _load(self):
        if config.EMBEDDINGS_PATH.exists():
            with np.load(config.EMBEDDINGS_PATH, allow_pickle=False) as data:
                self.profiles = {
                    name: [data[name][i] for i in range(data[name].shape[0])]
                    for name in data.files
                }

    def is_enrolled(self) -> bool:
        return bool(self.profiles)

    def detect_faces(self, frame):
        h, w = frame.shape[:2]
        self.detector.setInputSize((w, h))
        _, faces = self.detector.detect(frame)
        return faces if faces is not None else np.empty((0, 15), dtype=np.float32)

    def embed(self, frame, face_row):
        aligned = self.recognizer.alignCrop(frame, face_row)
        return self.recognizer.feature(aligned)

    def predict(self, frame, face_row):
        """Returns (best_name, best_similarity) or (None, None) if nothing enrolled."""
        if not self.profiles:
            return None, None
        feature = self.embed(frame, face_row)
        best_name, best_score = None, -1.0
        for name, embeddings in self.profiles.items():
            for emb in embeddings:
                score = self.recognizer.match(feature, emb, cv2.FaceRecognizerSF_FR_COSINE)
                if score > best_score:
                    best_score, best_name = score, name
        return best_name, best_score

    def enroll_capture_embedding(self, name: str, frame, face_row):
        feature = self.embed(frame, face_row)
        self.profiles.setdefault(name, []).append(feature)

    def delete_profile(self, name: str):
        self.profiles.pop(name, None)

    def save_profiles(self):
        if not self.profiles:
            if config.EMBEDDINGS_PATH.exists():
                config.EMBEDDINGS_PATH.unlink()
            return
        arrays = {name: np.stack(embs) for name, embs in self.profiles.items()}
        np.savez(config.EMBEDDINGS_PATH, **arrays)


# ---- PIN fallback (in case the camera / recognition isn't usable) ----

def set_pin(pin: str):
    salt = secrets.token_hex(16)
    digest = hashlib.sha256((salt + pin).encode()).hexdigest()
    config.PIN_PATH.write_text(f"{salt}:{digest}")


def verify_pin(pin: str) -> bool:
    if not config.PIN_PATH.exists():
        return False
    salt, digest = config.PIN_PATH.read_text().strip().split(":")
    return hashlib.sha256((salt + pin).encode()).hexdigest() == digest


def has_pin() -> bool:
    return config.PIN_PATH.exists()
