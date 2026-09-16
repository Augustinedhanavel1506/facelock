from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QListWidgetItem, QPushButton, QLabel
from PyQt6.QtGui import QColor

from .access_log import read_recent
from .dialog_style import STYLE_SHEET


class AccessLogDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("FaceLock — Access Log")
        self.setFixedSize(460, 520)
        self.setStyleSheet(STYLE_SHEET)

        layout = QVBoxLayout(self)
        title = QLabel("RECENT LOCK / UNLOCK ACTIVITY")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)
        self._load()

        close_btn = QPushButton("CLOSE")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

    def _load(self):
        entries = read_recent(150)
        if not entries:
            self.list_widget.addItem("No activity recorded yet.")
            return
        for e in entries:
            granted = e.get("event") == "granted"
            mark = "GRANTED" if granted else "DENIED "
            who = e.get("name") or "unknown"
            method = e.get("method") or "?"
            item = QListWidgetItem(f"{e.get('time', '?')}   {mark}   {who}   [{method}]")
            item.setForeground(QColor(72, 255, 168) if granted else QColor(255, 61, 61))
            self.list_widget.addItem(item)
