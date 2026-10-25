"""Interruptor moderno animado (Toggle Switch) estilo Windows 11 Fluent."""

from __future__ import annotations

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import QAbstractButton


class ToggleSwitch(QAbstractButton):
    """Interruptor deslizante animado para ativar/desativar um microfone."""

    def __init__(
        self,
        parent=None,
        active_color: str = "#10B981",
        inactive_color: str = "#475569",
        thumb_color: str = "#FFFFFF",
    ) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(48, 26)

        self._active_color = QColor(active_color)
        self._inactive_color = QColor(inactive_color)
        self._thumb_color = QColor(thumb_color)
        self._offset = 1.0 if self.isChecked() else 0.0

        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def sizeHint(self) -> QSize:
        return QSize(48, 26)

    def get_offset(self) -> float:
        return self._offset

    def set_offset(self, value: float) -> None:
        self._offset = float(value)
        self.update()

    offset = Property(float, get_offset, set_offset)

    def set_colors(self, active_color: str, inactive_color: str) -> None:
        self._active_color = QColor(active_color)
        self._inactive_color = QColor(inactive_color)
        self.update()

    def setCheckedSilent(self, checked: bool) -> None:
        """Atualiza o estado visual sem emitir sinais redundantes."""
        if self.isChecked() == checked:
            self._offset = 1.0 if checked else 0.0
            self.update()
            return
        was_blocked = self.blockSignals(True)
        self.setChecked(checked)
        self.blockSignals(was_blocked)
        self._anim.stop()
        self._offset = 1.0 if checked else 0.0
        self.update()

    def nextCheckState(self) -> None:
        super().nextCheckState()
        self._animate_to(1.0 if self.isChecked() else 0.0)

    def _animate_to(self, target: float) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._offset)
        self._anim.setEndValue(target)
        self._anim.start()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        super().mouseReleaseEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w = float(self.width())
        h = float(self.height())
        radius = h / 2.0

        if not self.isEnabled():
            painter.setOpacity(0.45)

        # Interpola cor da trilha entre inativo e ativo
        t = max(0.0, min(1.0, self._offset))
        r = int(self._inactive_color.red() * (1.0 - t) + self._active_color.red() * t)
        g = int(self._inactive_color.green() * (1.0 - t) + self._active_color.green() * t)
        b = int(self._inactive_color.blue() * (1.0 - t) + self._active_color.blue() * t)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(r, g, b))
        painter.drawRoundedRect(QRectF(0.0, 0.0, w, h), radius, radius)

        # Círculo interno (thumb)
        margin = 3.0
        thumb_d = h - 2.0 * margin
        min_x = margin
        max_x = w - margin - thumb_d
        thumb_x = min_x + (max_x - min_x) * t

        painter.setBrush(self._thumb_color)
        painter.drawEllipse(QRectF(thumb_x, margin, thumb_d, thumb_d))
        painter.end()

