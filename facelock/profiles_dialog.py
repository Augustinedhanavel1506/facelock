from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton, QLabel, QMessageBox
)

from .face_engine import FaceEngine
from .dialog_style import STYLE_SHEET


class ProfilesDialog(QDialog):
    def __init__(self, engine: FaceEngine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.setWindowTitle("FaceLock — Manage Profiles")
        self.setFixedSize(380, 440)
        self.setStyleSheet(STYLE_SHEET)

        layout = QVBoxLayout(self)
        title = QLabel("ENROLLED FACE PROFILES")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)
        self._refresh()

        row = QHBoxLayout()
        delete_btn = QPushButton("DELETE SELECTED")
        delete_btn.clicked.connect(self._delete_selected)
        close_btn = QPushButton("CLOSE")
        close_btn.clicked.connect(self.close)
        row.addWidget(delete_btn)
        row.addWidget(close_btn)
        layout.addLayout(row)

    def _refresh(self):
        self.list_widget.clear()
        if not self.engine.profiles:
            self.list_widget.addItem("No profiles enrolled yet.")
            return
        for name in sorted(self.engine.profiles.keys()):
            count = len(self.engine.profiles[name])
            self.list_widget.addItem(f"{name}   ({count} samples)")

    def _delete_selected(self):
        item = self.list_widget.currentItem()
        if not item or not self.engine.profiles:
            return
        name = item.text().split()[0]
        confirm = QMessageBox.question(
            self, "Delete profile", f"Remove the face profile '{name}'? This can't be undone.",
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.engine.delete_profile(name)
            self.engine.save_profiles()
            self._refresh()
