import math
import time
from collections import deque

import cv2

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QWidget, QLabel, QLineEdit, QApplication

from . import config
from . import access_log
from . import voice
from .face_engine import verify_pin, has_pin
from .camera import CameraThread
from .hud_widget import HudWidget


class LockOverlay(QWidget):
    """Full-screen always-on-top J.A.R.V.I.S.-style lock. Face-match or PIN
    dismisses it; it never touches Windows' own login/lock screen."""

    unlocked = pyqtSignal()
    suspicious_activity = pyqtSignal(int)  # failed-attempt count this session

    def __init__(self, engine, settings: dict):
        super().__init__()
        self.engine = engine
        self.settings = settings

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        screen_geo = QApplication.primaryScreen().geometry()
        self.setGeometry(screen_geo)

        self.hud = HudWidget(self)
        self.hud.setGeometry(self.rect())

        self.pin_hint = QLabel("PRESS  P  TO USE YOUR PIN INSTEAD", self)
        self.pin_hint.setStyleSheet("color:#3fb8d4; letter-spacing:2px;")
        self.pin_hint.setFont(QFont("Consolas", 10))
        self.pin_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.pin_input = QLineEdit(self)
        self.pin_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pin_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pin_input.setPlaceholderText("ENTER PIN")
        self.pin_input.setFixedWidth(220)
        self.pin_input.setStyleSheet(
            "background: rgba(0,20,26,200); color:#00d9ff; border:1px solid #00d9ff;"
            "border-radius: 4px; padding:6px; font-size:14px;"
        )
        self.pin_input.hide()
        self.pin_input.returnPressed.connect(self._check_pin)

        self.camera_thread = CameraThread(engine)
        self.camera_thread.frame_ready.connect(self._on_frame)

        self._reset_state()

    # ------------------------------------------------------------------

    def _reset_state(self):
        self._match_count = 0
        self._last_face_seen = time.time()
        self._first_mismatch_time = None
        self._unrecognized_logged = False
        self._granted = False
        self._landmark_history = deque(maxlen=config.LIVENESS_HISTORY_LEN)
        self._failed_attempts = 0
        self._last_frame = None
        self.hud.set_state("init", "INITIALIZING CAMERA...", "", progress=0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.hud.setGeometry(self.rect())
        self.pin_hint.setGeometry(0, self.height() - 70, self.width(), 24)
        self.pin_input.move((self.width() - self.pin_input.width()) // 2, self.height() - 110)

    def showEvent(self, event):
        super().showEvent(event)
        self._reset_state()
        self.pin_input.hide()
        self.pin_input.clear()
        if has_pin():
            self.pin_hint.show()
        else:
            self.pin_hint.hide()
        if not self.camera_thread.isRunning():
            self.camera_thread.start()
        self.activateWindow()
        self.raise_()

    def hideEvent(self, event):
        super().hideEvent(event)
        if self.camera_thread.isRunning():
            self.camera_thread.stop()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_P and has_pin():
            self.pin_input.show()
            self.pin_input.setFocus()
        elif event.key() == Qt.Key.Key_Escape:
            self.pin_input.hide()
            self.setFocus()
        # No other key closes the overlay -- this is a deliberate lock.

    # ------------------------------------------------------------------

    def _progress(self):
        return min(1.0, self._match_count / config.CONSEC_MATCHES_REQUIRED)

    def _record_failure(self, frame=None):
        self._failed_attempts += 1
        if self._failed_attempts >= config.SUSPICIOUS_ATTEMPT_THRESHOLD:
            if frame is not None:
                snap_path = config.FAILED_ATTEMPTS_DIR / f"{int(time.time())}.jpg"
                try:
                    cv2.imwrite(str(snap_path), frame)
                except cv2.error:
                    pass
            self.suspicious_activity.emit(self._failed_attempts)

    def _liveness_ok(self) -> bool:
        if len(self._landmark_history) < 8:
            return False
        pts = list(self._landmark_history)
        total = sum(
            math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1])
            for i in range(1, len(pts))
        )
        return total >= config.LIVENESS_MIN_MOVEMENT_PX

    def _on_frame(self, qimage, detections, frame):
        self.hud.set_frame(qimage)
        self._last_frame = frame
        if self._granted:
            return

        if not detections:
            self._match_count = max(0, self._match_count - config.MISS_DECAY)
            self._first_mismatch_time = None
            self._unrecognized_logged = False
            elapsed_no_face = time.time() - self._last_face_seen
            if elapsed_no_face > config.NO_FACE_TIMEOUT_SECS:
                self.hud.set_state("no_face", "NO FACE DETECTED",
                                    "Center yourself in front of the camera", progress=self._progress())
            else:
                self.hud.set_state("scanning", "SCANNING...", "", progress=self._progress())
            return

        self._last_face_seen = time.time()
        best = max(detections, key=lambda d: d.rect[2] * d.rect[3])

        if best.matched:
            self._match_count += 2
            self._first_mismatch_time = None
            self._unrecognized_logged = False
            row = best.face_row
            self._landmark_history.append(((row[4] + row[6]) / 2, (row[5] + row[7]) / 2))

            if self._match_count >= config.CONSEC_MATCHES_REQUIRED:
                if self._liveness_ok():
                    access_log.log_event("granted", name=best.name, method="face")
                    self._grant(best.name)
                    return
                self.hud.set_state(
                    "scanning", f"IDENTIFYING: {best.name.upper()}",
                    "Move your head slightly to verify liveness...",
                    progress=1.0, person_name=best.name,
                )
            else:
                self.hud.set_state(
                    "scanning", f"IDENTIFYING: {best.name.upper()}",
                    f"similarity {max(0, best.confidence) * 100:.0f}%",
                    progress=self._progress(), person_name=best.name,
                )
        else:
            self._match_count = max(0, self._match_count - config.MISS_DECAY)
            if self._first_mismatch_time is None:
                self._first_mismatch_time = time.time()
            elapsed = time.time() - self._first_mismatch_time
            if elapsed > config.UNRECOGNIZED_TIMEOUT_SECS:
                hint = " or your PIN (press P)" if has_pin() else ""
                self.hud.set_state("unrecognized", "IDENTITY NOT RECOGNIZED",
                                    f"Try again{hint}", progress=self._progress())
                if not self._unrecognized_logged:
                    self._unrecognized_logged = True
                    access_log.log_event("denied", name=best.name, method="face")
                    self._record_failure(frame)
            else:
                self.hud.set_state("scanning", "SCANNING...", "", progress=self._progress())

    def _grant(self, name):
        self._granted = True
        self.hud.set_state("granted", "ACCESS GRANTED", f"WELCOME BACK, {name.upper()}", progress=1.0)
        if self.settings.get("voice_enabled", True):
            voice.speak(f"Access granted. Welcome back, {name}.")
        QTimer.singleShot(1100, self._finish_unlock)

    def _finish_unlock(self):
        self.hide()
        self.unlocked.emit()

    def _check_pin(self):
        pin = self.pin_input.text()
        self.pin_input.clear()
        if verify_pin(pin):
            access_log.log_event("granted", name="OPERATOR", method="pin")
            self._grant("OPERATOR")
        else:
            access_log.log_event("denied", method="pin")
            self._record_failure(getattr(self, "_last_frame", None))
            self.hud.set_state("denied", "INCORRECT PIN", "Try again", progress=0)