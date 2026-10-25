"""Renderizador de ícones vetoriais em tempo de execução via QPainter.

Elimina dependência de arquivos de imagem externos e garante nitidez em monitores High-DPI.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap


def create_mic_pixmap(
    size: int = 44,
    active: bool = True,
    available: bool = True,
    fg_color: str = "#FFFFFF",
    bg_color: str = "#10B981",
) -> QPixmap:
    """Desenha um avatar circular com ícone vetorial de microfone (ativo ou cortado/mudo)."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    # Fundo circular suave
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(bg_color))
    painter.drawEllipse(QRectF(1.0, 1.0, size - 2.0, size - 2.0))

    pen = QPen(QColor(fg_color))
    pen.setWidthF(max(1.8, size * 0.055))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    cx = size / 2.0
    cy = size / 2.0

    # Cápsula do microfone
    cap_w = size * 0.22
    cap_h = size * 0.34
    cap_rect = QRectF(cx - cap_w / 2.0, cy - cap_h * 0.68, cap_w, cap_h)
    painter.drawRoundedRect(cap_rect, cap_w / 2.0, cap_w / 2.0)

    # Arco de suporte (U)
    arc_w = size * 0.38
    arc_h = size * 0.34
    arc_rect = QRectF(cx - arc_w / 2.0, cy - arc_h * 0.45, arc_w, arc_h)
    painter.drawArc(arc_rect, 180 * 16, 180 * 16)

    # Haste vertical e base
    stem_top = arc_rect.bottom()
    stem_bottom = cy + size * 0.28
    painter.drawLine(QPointF(cx, stem_top), QPointF(cx, stem_bottom))

    base_half = size * 0.13
    painter.drawLine(
        QPointF(cx - base_half, stem_bottom),
        QPointF(cx + base_half, stem_bottom),
    )

    # Se estiver desativado (mudo) ou indisponível, desenha linha diagonal de corte
    if not active or not available:
        slash_pen = QPen(QColor(fg_color))
        slash_pen.setWidthF(max(2.2, size * 0.065))
        slash_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(slash_pen)
        offset = size * 0.24
        painter.drawLine(
            QPointF(cx - offset, cy - offset),
            QPointF(cx + offset, cy + offset),
        )

    painter.end()
    return pixmap


def create_app_icon(active: bool = True) -> QIcon:
    """Cria o ícone da janela e da bandeja do sistema (System Tray)."""
    bg = "#10B981" if active else "#EF4444"
    pix = create_mic_pixmap(
        size=64,
        active=active,
        available=True,
        fg_color="#FFFFFF",
        bg_color=bg,
    )
    return QIcon(pix)


def create_volume_pixmap(
    size: int = 20,
    volume_percent: int = 100,
    muted: bool = False,
    color: str = "#94A3B8",
) -> QPixmap:
    """Desenha um ícone compacto de alto-falante/ganho proporcional ao nível de volume."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    pen = QPen(QColor(color))
    pen.setWidthF(1.7)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(QColor(color))

    # Cone do alto-falante/ganho
    path = QPainterPath()
    path.moveTo(size * 0.18, size * 0.38)
    path.lineTo(size * 0.34, size * 0.38)
    path.lineTo(size * 0.54, size * 0.20)
    path.lineTo(size * 0.54, size * 0.80)
    path.lineTo(size * 0.34, size * 0.62)
    path.lineTo(size * 0.18, size * 0.62)
    path.closeSubpath()
    painter.drawPath(path)

    painter.setBrush(Qt.BrushStyle.NoBrush)
    if muted or volume_percent == 0:
        painter.drawLine(
            QPointF(size * 0.66, size * 0.36),
            QPointF(size * 0.86, size * 0.64),
        )
        painter.drawLine(
            QPointF(size * 0.86, size * 0.36),
            QPointF(size * 0.66, size * 0.64),
        )
    else:
        if volume_percent > 5:
            arc1 = QRectF(size * 0.46, size * 0.30, size * 0.28, size * 0.40)
            painter.drawArc(arc1, -45 * 16, 90 * 16)
        if volume_percent >= 55:
            arc2 = QRectF(size * 0.40, size * 0.16, size * 0.48, size * 0.68)
            painter.drawArc(arc2, -45 * 16, 90 * 16)

    painter.end()
    return pixmap

