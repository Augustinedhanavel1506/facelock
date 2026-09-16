import re

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QMessageBox
)

from . import config
from .face_engine import FaceEngine, set_pin
from .camera import CameraThread
from .hud_widget import HudWidget
from .dialog_style import STYLE_SHEET as BASE_STYLE

STYLE_SHEET = BASE_STYLE + """
QLabel#title { font-size: 18px; font-weight: bold; letter-spacing: 3px; padding: 12px; }
QLineEdit {
    background: rgba(0,20,26,200); color:#00d9ff; border:1px solid #00d9ff;
    border-radius:4px; padding:8px; font-size:14px;
}
QPushButton { padding:10px; }
"""


class EnrollDialog(QWidget):
    finished_enrolling = pyqtSignal()

    def __init__(self, engine: FaceEngine):
        super().__init__()
        self.engine = engine
        self.setWindowTitle("FaceLock — Enrollment")
        self.setFixedSize(640, 780)
        self.setStyleSheet(STYLE_SHEET)

        self._name = None
        self._sample_idx = 0
        self._latest_frame = None
        self._latest_detections = []
        self.camera_thread = None
        self._capture_timer = QTimer(self)
        self._capture_timer.timeout.connect(self._maybe_capture)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_name_page())
        self.stack.addWidget(self._build_capture_page())
        self.stack.addWidget(self._build_pin_page())

        layout = QVBoxLayout(self)
        title = QLabel("J.A.R.V.I.S.  //  FACE ENROLLMENT")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        layout.addWidget(self.stack)

    # ---- page 1: name -------------------------------------------------

    def _build_name_page(self):
        page = QWidget()
        v = QVBoxLayout(page)
        v.addStretch()
        label = QLabel("Enter a name to identify this face profile:")
        label.setObjectName("subtitle")
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. TONY")
        begin_btn = QPushButton("BEGIN FACIAL SCAN")
        begin_btn.clicked.connect(self._start_capture)
        v.addWidget(label)
        v.addWidget(self.name_input)
        v.addSpacing(20)
        v.addWidget(begin_btn)
        v.addStretch()
        return page

    def _start_capture(self):
        raw = self.name_input.text().strip()
        name = re.sub(r"[^A-Za-z0-9_-]", "", raw)
        if not name:
            QMessageBox.warning(self, "Name required", "Please enter a valid name (letters/numbers).")
            return
        self._name = name
        self._sample_idx = 0
        self.stack.setCurrentIndex(1)
        self.camera_thread = CameraThread(self.engine)
        self.camera_thread.frame_ready.connect(self._on_frame)
        self.camera_thread.start()
        self._capture_timer.start(180)

    # ---- page 2: capture ----------------------------------------------

    def _build_capture_page(self):
        page = QWidget()
        v = QVBoxLayout(page)
        self.hud = HudWidget()
        self.hud.setFixedHeight(560)
        self.hud.set_state("scanning", "LOOK AT THE CAMERA", "Slowly turn your head slightly while we scan", progress=0)
        v.addWidget(self.hud)
        return page

    def _on_frame(self, qimage, detections, frame):
        self.hud.set_frame(qimage)
        self._latest_frame = frame
        self._latest_detections = detections

        progress = min(1.0, self._sample_idx / config.SAMPLES_PER_ENROLLMENT)
        if detections:
            self.hud.set_state("scanning", f"CAPTURING  {self._sample_idx}/{config.SAMPLES_PER_ENROLLMENT}",
                                "Slowly turn your head slightly...", progress=progress)
        else:
            self.hud.set_state("no_face", "NO FACE DETECTED", "Center yourself in the frame", progress=progress)

    def _maybe_capture(self):
        if not self._latest_detections or self._latest_frame is None:
            return
        best = max(self._latest_detections, key=lambda d: d.rect[2] * d.rect[3])
        self.engine.enroll_capture_embedding(self._name, self._latest_frame, best.face_row)
        self._sample_idx += 1

        if self._sample_idx >= config.SAMPLES_PER_ENROLLMENT:
            self._capture_timer.stop()
            self.camera_thread.stop()
            self.hud.set_state("granted", "SAVING PROFILE...", "", progress=1.0)
            self.engine.save_profiles()
            self.stack.setCurrentIndex(2)

    # ---- page 3: PIN ----------------------------------------------------

    def _build_pin_page(self):
        page = QWidget()
        v = QVBoxLayout(page)
        v.addStretch()
        label = QLabel("Set a backup PIN (used if the camera can't recognize you):")
        label.setObjectName("subtitle")
        self.pin1 = QLineEdit()
        self.pin1.setEchoMode(QLineEdit.EchoMode.Password)
        self.pin1.setPlaceholderText("PIN")
        self.pin2 = QLineEdit()
        self.pin2.setEchoMode(QLineEdit.EchoMode.Password)
        self.pin2.setPlaceholderText("CONFIRM PIN")

        row = QHBoxLayout()
        finish_btn = QPushButton("SAVE PIN & FINISH")
        finish_btn.clicked.connect(self._save_pin_and_finish)
        skip_btn = QPushButton("SKIP")
        skip_btn.clicked.connect(self._finish)
        row.addWidget(finish_btn)
        row.addWidget(skip_btn)

        v.addWidget(label)
        v.addWidget(self.pin1)
        v.addWidget(self.pin2)
        v.addSpacing(20)
        v.addLayout(row)
        v.addStretch()
        return page

    def _save_pin_and_finish(self):
        p1, p2 = self.pin1.text(), self.pin2.text()
        if len(p1) < 4:
            QMessageBox.warning(self, "PIN too short", "Use at least 4 digits/characters.")
            return
        if p1 != p2:
            QMessageBox.warning(self, "Mismatch", "PINs do not match.")
            return
        set_pin(p1)
        self._finish()

    def _finish(self):
        self.finished_enrolling.emit()
        self.close()

    def closeEvent(self, event):
        if self.camera_thread and self.camera_thread.isRunning():
            self.camera_thread.stop()
        super().closeEvent(event)
