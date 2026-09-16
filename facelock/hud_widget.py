import math
from datetime import datetime

from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath, QFont, QRadialGradient, QLinearGradient
from PyQt6.QtWidgets import QWidget

from . import config

CYAN = QColor(*config.COLOR_PRIMARY)
CYAN_DIM = QColor(*config.COLOR_PRIMARY_DIM)
GOLD = QColor(*config.COLOR_ACCENT_GOLD)
DANGER = QColor(*config.COLOR_DANGER)
SUCCESS = QColor(*config.COLOR_SUCCESS)

STATE_COLORS = {
    "init": CYAN_DIM,
    "no_face": CYAN_DIM,
    "scanning": CYAN,
    "unrecognized": DANGER,
    "granted": SUCCESS,
    "denied": DANGER,
}


class HudWidget(QWidget):
    """Paints the full Iron-Man / J.A.R.V.I.S.-style HUD: rotating arc-reactor
    viewport with the live camera feed, scan rings, HUD brackets and readouts."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.image = None
        self.state = "init"
        self.status_text = "INITIALIZING"
        self.sub_text = ""
        self.progress = 0.0
        self.person_name = None

        self._t = 0.0
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._tick)
        self._anim_timer.start(33)

    def _tick(self):
        self._t += 0.033
        self.update()

    def set_frame(self, qimage):
        self.image = qimage
        self.update()

    def set_state(self, state, status_text="", sub_text="", progress=None, person_name=None):
        self.state = state
        self.status_text = status_text
        self.sub_text = sub_text
        if progress is not None:
            self.progress = progress
        self.person_name = person_name

    # ------------------------------------------------------------------

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2

        self._draw_background(p, w, h)
        self._draw_grid(p, w, h)
        self._draw_corner_brackets(p, w, h)
        self._draw_readouts(p, w, h)

        radius = min(w, h) * 0.20
        color = STATE_COLORS.get(self.state, CYAN)

        self._draw_camera_circle(p, cx, cy, radius)
        self._draw_glow_rings(p, cx, cy, radius, color)
        self._draw_rotating_ring(p, cx, cy, radius)
        self._draw_progress_arc(p, cx, cy, radius, color)
        self._draw_status_text(p, w, h, cx, cy, radius, color)

        p.end()

    # ------------------------------------------------------------------

    def _draw_background(self, p, w, h):
        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0, QColor(6, 14, 18))
        grad.setColorAt(1, QColor(2, 4, 6))
        p.fillRect(0, 0, w, h, QBrush(grad))

    def _draw_grid(self, p, w, h):
        pen = QPen(QColor(CYAN.red(), CYAN.green(), CYAN.blue(), 14))
        pen.setWidth(1)
        p.setPen(pen)
        step = 46
        for x in range(0, w, step):
            p.drawLine(x, 0, x, h)
        for y in range(0, h, step):
            p.drawLine(0, y, w, y)

    def _draw_corner_brackets(self, p, w, h):
        pen = QPen(CYAN, 3)
        p.setPen(pen)
        m, ln = 28, 46
        corners = [
            ((m, m), (1, 0), (0, 1)),
            ((w - m, m), (-1, 0), (0, 1)),
            ((m, h - m), (1, 0), (0, -1)),
            ((w - m, h - m), (-1, 0), (0, -1)),
        ]
        for (x, y), dx, dy in corners:
            p.drawLine(int(x), int(y), int(x + dx[0] * ln), int(y + dy[1] * 0))
            p.drawLine(int(x), int(y), int(x + dx[0] * ln), int(y))
            p.drawLine(int(x), int(y), int(x), int(y + dy[1] * ln))

    def _draw_readouts(self, p, w, h):
        mono = QFont("Consolas", 10)
        mono.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 110)
        p.setFont(mono)
        p.setPen(QPen(CYAN_DIM))

        p.drawText(40, 60, "J.A.R.V.I.S.  //  FACIAL AUTHENTICATION")
        p.drawText(40, 78, "SYS.STATUS: " + self.state.upper())

        now = datetime.now().strftime("%H:%M:%S")
        p.drawText(w - 160, 60, now)
        p.drawText(w - 160, 78, datetime.now().strftime("%d.%m.%Y"))

        # fake scrolling data ticks bottom bar for flavor
        p.setPen(QPen(QColor(CYAN.red(), CYAN.green(), CYAN.blue(), 90)))
        wave = "".join("█" if (i + int(self._t * 6)) % 5 == 0 else "·" for i in range(60))
        p.drawText(40, h - 34, wave)

    def _draw_camera_circle(self, p, cx, cy, radius):
        clip_path = QPainterPath()
        clip_path.addEllipse(QPointF(cx, cy), radius, radius)
        p.save()
        p.setClipPath(clip_path)

        if self.image is not None and not self.image.isNull():
            iw, ih = self.image.width(), self.image.height()
            side = min(iw, ih)
            src = QRectF((iw - side) / 2, (ih - side) / 2, side, side)
            dst = QRectF(cx - radius, cy - radius, radius * 2, radius * 2)
            p.drawImage(dst, self.image, src)
            # cyan tint overlay for HUD look
            p.fillRect(int(cx - radius), int(cy - radius), int(radius * 2), int(radius * 2),
                       QColor(0, 60, 80, 55))
        else:
            p.fillRect(int(cx - radius), int(cy - radius), int(radius * 2), int(radius * 2),
                       QColor(4, 10, 12))
            p.setPen(QPen(CYAN_DIM))
            p.drawText(QRectF(cx - radius, cy - radius, radius * 2, radius * 2),
                       Qt.AlignmentFlag.AlignCenter, "NO SIGNAL")

        p.restore()

    def _draw_glow_rings(self, p, cx, cy, radius, color):
        for i in range(3):
            phase = self._t * 1.6 + i * 2.1
            pulse = (math.sin(phase) + 1) / 2
            r = radius * (1.08 + i * 0.12 + pulse * 0.03)
            alpha = int(70 - i * 18)
            pen = QPen(QColor(color.red(), color.green(), color.blue(), max(alpha, 0)))
            pen.setWidth(2)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, cy), r, r)

    def _draw_rotating_ring(self, p, cx, cy, radius):
        p.save()
        p.translate(cx, cy)
        angle = (self._t * 45) % 360
        p.rotate(angle)
        pen = QPen(CYAN, 2, Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        r = radius * 1.22
        p.drawEllipse(QPointF(0, 0), r, r)
        p.restore()

        p.save()
        p.translate(cx, cy)
        p.rotate(-angle * 0.6)
        pen2 = QPen(GOLD, 1, Qt.PenStyle.DotLine)
        p.setPen(pen2)
        r2 = radius * 1.34
        p.drawEllipse(QPointF(0, 0), r2, r2)
        p.restore()

    def _draw_progress_arc(self, p, cx, cy, radius, color):
        pen = QPen(color, 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        rect = QRectF(cx - radius * 1.1, cy - radius * 1.1, radius * 2.2, radius * 2.2)
        span = int(-self.progress * 360 * 16)
        p.drawArc(rect, 90 * 16, span)

    def _draw_status_text(self, p, w, h, cx, cy, radius, color):
        font = QFont("Consolas", 20, QFont.Weight.Bold)
        font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 120)
        p.setFont(font)

        text_y = cy + radius * 1.6
        glow = QColor(color.red(), color.green(), color.blue(), 90)
        p.setPen(glow)
        for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            p.drawText(QRectF(0 + ox, text_y + oy, w + ox, 40), Qt.AlignmentFlag.AlignCenter, self.status_text)
        p.setPen(color)
        p.drawText(QRectF(0, text_y, w, 40), Qt.AlignmentFlag.AlignCenter, self.status_text)

        if self.sub_text:
            font2 = QFont("Consolas", 11)
            p.setFont(font2)
            p.setPen(CYAN_DIM)
            p.drawText(QRectF(0, text_y + 34, w, 30), Qt.AlignmentFlag.AlignCenter, self.sub_text)
