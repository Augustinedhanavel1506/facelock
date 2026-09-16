import time
import cv2
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage

from . import config
from .face_engine import FaceEngine


class Detection:
    __slots__ = ("face_row", "rect", "name", "confidence", "matched")

    def __init__(self, face_row, name, confidence, matched):
        self.face_row = face_row
        self.rect = tuple(int(v) for v in face_row[:4])
        self.name = name
        self.confidence = confidence
        self.matched = matched


class CameraThread(QThread):
    """Continuously grabs webcam frames, runs face detection/recognition,
    and emits results to the GUI thread. Never touches Qt widgets directly."""

    frame_ready = pyqtSignal(QImage, list, object)  # display image, [Detection], raw_bgr_frame

    def __init__(self, engine: FaceEngine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self._running = False
        self._cap = None

    def run(self):
        self._running = True
        self._cap = cv2.VideoCapture(config.CAMERA_INDEX, cv2.CAP_DSHOW)
        if not self._cap.isOpened():
            self._cap = cv2.VideoCapture(config.CAMERA_INDEX)

        while self._running:
            ok, frame = self._cap.read()
            if not ok:
                time.sleep(0.05)
                continue

            frame = cv2.flip(frame, 1)
            faces = self.engine.detect_faces(frame)

            detections = []
            for face_row in faces:
                name, confidence = (None, None)
                matched = False
                if self.engine.is_enrolled():
                    name, confidence = self.engine.predict(frame, face_row)
                    matched = confidence is not None and confidence > config.MATCH_THRESHOLD
                detections.append(Detection(face_row, name, confidence, matched))

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888).copy()

            self.frame_ready.emit(qimg, detections, frame)

        if self._cap is not None:
            self._cap.release()

    def stop(self):
        self._running = False
        self.wait(2000)
