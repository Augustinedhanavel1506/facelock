STYLE_SHEET = """
QWidget { background-color: #050b0d; color: #00d9ff; }
QLabel#title { font-size: 15px; font-weight: bold; letter-spacing: 2px; padding: 8px; }
QLabel#subtitle { color: #3fb8d4; font-size: 11px; }
QListWidget {
    background: rgba(0,20,26,200); color:#cfefff; border:1px solid #00d9ff;
    border-radius:4px; font-family: Consolas; font-size: 12px;
}
QListWidget::item { padding: 6px; }
QListWidget::item:selected { background: rgba(0,120,150,150); }
QPushButton {
    background: rgba(0,40,50,200); color:#00d9ff; border:1px solid #00d9ff;
    border-radius:4px; padding:8px; font-size:12px; letter-spacing:1px;
}
QPushButton:hover { background: rgba(0,90,110,220); }
QPushButton:disabled { color:#2a4a52; border-color:#2a4a52; }
"""
