"""Barra de nível de entrada de áudio em tempo real (VU / Peak Meter)."""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget


class AudioLevelMeter(QWidget):
    """Exibe visualmente a intensidade de captação do microfone em tempo real."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(8)
        self._level = 0.0
        self._active = True
        self._track_color = QColor("#0F172A")

    def sizeHint(self) -> QSize:
        return QSize(180, 8)

    def set_track_color(self, color: str) -> None:
        self._track_color = QColor(color)
        self.update()

    def set_active(self, active: bool) -> None:
        if self._active != active:
            self._active = active
            if not active:
                self._level = 0.0
            self.update()

    def set_level(self, level: float) -> None:
        """Atualiza o nível com decaimento suave para evitar oscilações bruscas."""
        clamped = max(0.0, min(1.0, float(level))) if self._active else 0.0
        if clamped >= self._level:
            new_level = clamped
        else:
            # Decaimento suave quando o som diminui
            new_level = max(clamped, self._level * 0.72)
            if new_level < 0.008:
                new_level = 0.0

        if abs(new_level - self._level) > 0.004 or (new_level == 0.0 and self._level != 0.0):
            self._level = new_level
            self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w = float(self.width())
        h = float(self.height())
        r = h / 2.0

        # Trilha de fundo
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._track_color)
        painter.drawRoundedRect(QRectF(0.0, 0.0, w, h), r, r)

        # Barra preenchida proporcional ao pico de áudio
        if self._active and self._level > 0.005:
            # Aplica curva de sensibilidade perceptual (raiz quadrada) para voz humana
            visual_ratio = min(1.0, self._level ** 0.62)
            fill_w = max(h, w * visual_ratio)

            grad = QLinearGradient(0.0, 0.0, w, 0.0)
            grad.setColorAt(0.0, QColor("#10B981"))   # Verde (normal)
            grad.setColorAt(0.72, QColor("#F59E0B"))  # Âmbar (alto)
            grad.setColorAt(1.0, QColor("#EF4444"))   # Vermelho (clipping)

            painter.setBrush(grad)
            painter.drawRoundedRect(QRectF(0.0, 0.0, fill_w, h), r, r)

        painter.end()

