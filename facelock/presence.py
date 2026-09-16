import time
import cv2
from PyQt6.QtCore import QThread, pyqtSignal

from . import config


class PresenceThread(QThread):
    """Lightweight background check (~0.5 fps) for whether a face is in
    frame at all -- no recognition, just presence -- so we can auto-lock
    shortly after you physically walk away, independent of keyboard/mouse
    idle time. Only runs while the lock overlay itself isn't showing."""

    face_absent_too_long = pyqtSignal()

    def __init__(self, engine, absence_minutes: float, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.absence_seconds = absence_minutes * 60
        self._running = False

    def run(self):
        self._running = True
        cap = cv2.VideoCapture(config.CAMERA_INDEX, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(config.CAMERA_INDEX)

        last_seen = time.time()
        alerted = False
        while self._running:
            ok, frame = cap.read()
            if ok:
                faces = self.engine.detect_faces(frame)
                if len(faces):
                    last_seen = time.time()
                    alerted = False
                elif not alerted and time.time() - last_seen > self.absence_seconds:
                    alerted = True
                    self.face_absent_too_long.emit()
            for _ in range(20):
                if not self._running:
                    break
                time.sleep(0.1)

        cap.release()

    def stop(self):
        self._running = False
        self.wait(3000)
