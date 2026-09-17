import sys
import time

from PyQt6.QtCore import Qt, QObject, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
from PyQt6.QtWidgets import (
    QApplication, QSystemTrayIcon, QMenu, QMessageBox, QInputDialog, QLineEdit
)

from facelock import config, settings
from facelock.face_engine import FaceEngine, set_pin, has_pin
from facelock.overlay import LockOverlay
from facelock.enroll_dialog import EnrollDialog
from facelock.profiles_dialog import ProfilesDialog
from facelock.log_dialog import AccessLogDialog
from facelock.presence import PresenceThread
from facelock.idle import get_idle_seconds
from facelock.power_settings import get_display_timeout_seconds
from facelock.startup import is_startup_enabled, enable_startup, disable_startup

# How much earlier than Windows' own "turn off display" timeout FaceLock
# should step in, so it reliably takes over before the screen goes dark.
IDLE_LOCK_LEAD_SECONDS = 15
MIN_IDLE_LOCK_SECONDS = 30
DISPLAY_TIMEOUT_CACHE_SECONDS = 60


def make_tray_icon() -> QIcon:
    pix = QPixmap(64, 64)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QColor(0, 217, 255))
    p.setBrush(QColor(4, 14, 18))
    p.drawEllipse(4, 4, 56, 56)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(0, 217, 255))
    p.drawEllipse(24, 24, 16, 16)
    p.end()
    return QIcon(pix)


class HotkeyBridge(QObject):
    trigger = pyqtSignal()


class FaceLockApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        self.settings = settings.load()
        self.engine = FaceEngine()
        self.overlay = LockOverlay(self.engine, self.settings)
        self.overlay.unlocked.connect(self._on_unlocked)
        self.overlay.suspicious_activity.connect(self._on_suspicious_activity)
        self.enroll_dialog = None
        self.presence_thread = None
        self._display_timeout_cache = None
        self._display_timeout_cache_time = 0.0

        self.bridge = HotkeyBridge()
        self.bridge.trigger.connect(self.show_lock)

        self.tray = QSystemTrayIcon(make_tray_icon())
        self.tray.setToolTip("FaceLock — J.A.R.V.I.S. face authentication")
        self._build_menu()
        self.tray.show()

        self._register_hotkey()

        self.idle_timer = QTimer()
        self.idle_timer.timeout.connect(self._check_idle)
        self.idle_timer.start(5000)

        self._sync_presence_thread()

    def _build_menu(self):
        menu = QMenu()
        lock_action = menu.addAction(f"Lock Now  ({config.GLOBAL_HOTKEY})")
        lock_action.triggered.connect(self.show_lock)
        enroll_action = menu.addAction("Enroll / Re-scan Face...")
        enroll_action.triggered.connect(self.open_enroll)
        profiles_action = menu.addAction("Manage Profiles...")
        profiles_action.triggered.connect(self.open_profiles)
        pin_action = menu.addAction("Set Backup PIN...")
        pin_action.triggered.connect(self.set_pin_dialog)
        log_action = menu.addAction("View Access Log...")
        log_action.triggered.connect(self.open_log)
        menu.addSeparator()

        self.idle_action = menu.addAction("Auto-lock when idle (synced to screen timeout)")
        self.idle_action.setCheckable(True)
        self.idle_action.setChecked(self.settings["idle_lock_enabled"])
        self.idle_action.triggered.connect(self.toggle_idle_lock)

        wm = self.settings["walkaway_lock_minutes"]
        self.walkaway_action = menu.addAction(f"Auto-lock when you leave ({wm} min, webcam)")
        self.walkaway_action.setCheckable(True)
        self.walkaway_action.setChecked(self.settings["walkaway_lock_enabled"])
        self.walkaway_action.triggered.connect(self.toggle_walkaway_lock)

        self.voice_action = menu.addAction("Voice feedback")
        self.voice_action.setCheckable(True)
        self.voice_action.setChecked(self.settings["voice_enabled"])
        self.voice_action.triggered.connect(self.toggle_voice)
        menu.addSeparator()

        self.startup_action = menu.addAction("Start with Windows")
        self.startup_action.setCheckable(True)
        self.startup_action.setChecked(is_startup_enabled())
        self.startup_action.triggered.connect(self.toggle_startup)
        menu.addSeparator()

        quit_action = menu.addAction("Exit")
        quit_action.triggered.connect(self.quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_lock()

    def _register_hotkey(self):
        try:
            import keyboard
            keyboard.add_hotkey(config.GLOBAL_HOTKEY, lambda: self.bridge.trigger.emit())
        except Exception as e:
            print(f"[FaceLock] Global hotkey unavailable ({e}); use the tray menu to lock instead.")

    # ---- locking / unlocking -------------------------------------------

    def show_lock(self):
        if not self.engine.is_enrolled() and not has_pin():
            self.tray.showMessage(
                "FaceLock", "Enroll a face first from the tray menu.",
                QSystemTrayIcon.MessageIcon.Warning, 4000,
            )
            self.open_enroll()
            return
        if self.presence_thread and self.presence_thread.isRunning():
            self.presence_thread.stop()
        self.overlay.showFullScreen()

    def _on_unlocked(self):
        self.tray.showMessage("FaceLock", "Access granted.", QSystemTrayIcon.MessageIcon.Information, 2000)
        self._sync_presence_thread()

    def _on_suspicious_activity(self, count):
        self.tray.showMessage(
            "FaceLock — Warning",
            f"{count} failed unlock attempts just now. A snapshot was saved to the access log.",
            QSystemTrayIcon.MessageIcon.Warning, 6000,
        )

    # ---- idle / walk-away auto-lock -------------------------------------

    def _effective_idle_threshold_seconds(self):
        """Prefer syncing to Windows' own "turn off display after" timeout
        (minus a lead time) so FaceLock takes over just before the screen
        would go dark. Falls back to the fixed setting if that can't be
        read (e.g. the user set display timeout to "Never")."""
        now = time.time()
        if now - self._display_timeout_cache_time > DISPLAY_TIMEOUT_CACHE_SECONDS:
            self._display_timeout_cache = get_display_timeout_seconds()
            self._display_timeout_cache_time = now
        if self._display_timeout_cache:
            return max(MIN_IDLE_LOCK_SECONDS, self._display_timeout_cache - IDLE_LOCK_LEAD_SECONDS)
        return self.settings["idle_lock_minutes"] * 60

    def _check_idle(self):
        if not self.settings.get("idle_lock_enabled") or self.overlay.isVisible():
            return
        if get_idle_seconds() >= self._effective_idle_threshold_seconds():
            self.show_lock()

    def _sync_presence_thread(self):
        should_run = self.settings.get("walkaway_lock_enabled") and not self.overlay.isVisible()
        running = self.presence_thread is not None and self.presence_thread.isRunning()
        if should_run and not running:
            self.presence_thread = PresenceThread(self.engine, self.settings["walkaway_lock_minutes"])
            self.presence_thread.face_absent_too_long.connect(self._on_walkaway_detected)
            self.presence_thread.start()
        elif not should_run and running:
            self.presence_thread.stop()

    def _on_walkaway_detected(self):
        self.show_lock()

    # ---- dialogs ----------------------------------------------------------

    def open_enroll(self):
        if self.enroll_dialog is not None and self.enroll_dialog.isVisible():
            self.enroll_dialog.raise_()
            return
        self.enroll_dialog = EnrollDialog(self.engine)
        self.enroll_dialog.finished_enrolling.connect(
            lambda: self.tray.showMessage(
                "FaceLock", "Face enrolled successfully.", QSystemTrayIcon.MessageIcon.Information, 3000
            )
        )
        self.enroll_dialog.show()

    def open_profiles(self):
        ProfilesDialog(self.engine).exec()

    def open_log(self):
        AccessLogDialog().exec()

    def set_pin_dialog(self):
        pin, ok = QInputDialog.getText(None, "Set Backup PIN", "New PIN:", QLineEdit.EchoMode.Password)
        if not ok:
            return
        if len(pin) < 4:
            QMessageBox.warning(None, "Too short", "PIN must be at least 4 characters.")
            return
        set_pin(pin)
        self.tray.showMessage("FaceLock", "PIN updated.", QSystemTrayIcon.MessageIcon.Information, 2000)

    # ---- toggles ----------------------------------------------------------

    def toggle_idle_lock(self, checked):
        self.settings["idle_lock_enabled"] = checked
        settings.save(self.settings)

    def toggle_walkaway_lock(self, checked):
        self.settings["walkaway_lock_enabled"] = checked
        settings.save(self.settings)
        self._sync_presence_thread()

    def toggle_voice(self, checked):
        self.settings["voice_enabled"] = checked
        settings.save(self.settings)

    def toggle_startup(self, checked):
        if checked:
            enable_startup()
        else:
            disable_startup()

    # ---- lifecycle ----------------------------------------------------------

    def quit(self):
        try:
            import keyboard
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass
        if self.overlay.camera_thread.isRunning():
            self.overlay.camera_thread.stop()
        if self.presence_thread and self.presence_thread.isRunning():
            self.presence_thread.stop()
        self.app.quit()

    def run(self):
        if not self.engine.is_enrolled():
            QTimer.singleShot(300, self.open_enroll)
        sys.exit(self.app.exec())


if __name__ == "__main__":
    FaceLockApp().run()
