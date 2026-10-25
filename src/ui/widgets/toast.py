"""Componente de notificação discreta flutuante (Toast / Snackbar)."""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer
from PySide6.QtWidgets import QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QWidget


class ToastOverlay(QFrame):
    """Notificação flutuante discreta exibida na parte inferior da janela principal."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("ToastOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.hide()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(10)

        self._dot_label = QLabel("●")
        self._dot_label.setStyleSheet("font-size: 13px; font-weight: bold;")
        layout.addWidget(self._dot_label)

        self._text_label = QLabel("")
        self._text_label.setStyleSheet("font-size: 12px; font-weight: 600; color: #F8FAFC;")
        layout.addWidget(self._text_label)

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)

        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._fade_anim.setDuration(220)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_anim.finished.connect(self._on_fade_finished)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade_out)

        self._fading_out = False

    def show_toast(
        self,
        message: str,
        kind: str = "info",
        duration_ms: int = 2400,
    ) -> None:
        """Exibe uma notificação discreta (`kind`: 'success', 'warning', 'error', 'info')."""
        colors = {
            "success": ("#10B981", "#064E3B", "#0F172A"),
            "error": ("#EF4444", "#7F1D1D", "#0F172A"),
            "warning": ("#F59E0B", "#78350F", "#0F172A"),
            "info": ("#3B82F6", "#1E3A8A", "#0F172A"),
        }
        dot_color, border_color, bg_color = colors.get(kind, colors["info"])

        self.setStyleSheet(
            f"""
            QFrame#ToastOverlay {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 10px;
            }}
            """
        )
        self._dot_label.setStyleSheet(
            f"font-size: 13px; font-weight: bold; color: {dot_color};"
        )
        self._text_label.setText(message)
        self.adjustSize()
        self.reposition()

        self._fading_out = False
        self._fade_anim.stop()
        self._opacity_effect.setOpacity(0.96)
        self.show()
        self.raise_()
        self._timer.start(duration_ms)

    def reposition(self) -> None:
        """Centraliza horizontalmente na parte inferior do widget pai."""
        parent = self.parentWidget()
        if parent is None:
            return
        self.adjustSize()
        x = max(16, (parent.width() - self.width()) // 2)
        y = max(16, parent.height() - self.height() - 22)
        self.move(x, y)

    def _fade_out(self) -> None:
        self._fading_out = True
        self._fade_anim.stop()
        self._fade_anim.setStartValue(self._opacity_effect.opacity())
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.start()

    def _on_fade_finished(self) -> None:
        if self._fading_out:
            self.hide()

