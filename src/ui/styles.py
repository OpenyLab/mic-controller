"""Sistema de temas (Escuro e Claro) e folhas de estilo QSS modernas."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThemePalette:
    """Paleta de cores semânticas da interface."""

    is_dark: bool
    bg_primary: str
    bg_secondary: str
    bg_card: str
    bg_card_hover: str
    bg_card_muted: str
    bg_input: str
    border_subtle: str
    border_active: str
    border_muted: str
    text_primary: str
    text_secondary: str
    text_muted: str
    accent: str
    accent_hover: str
    accent_soft: str
    success: str
    success_soft: str
    danger: str
    danger_soft: str
    warning: str
    warning_soft: str
    slider_groove: str


DARK_PALETTE = ThemePalette(
    is_dark=True,
    bg_primary="#0B1120",
    bg_secondary="#111827",
    bg_card="#1E293B",
    bg_card_hover="#243247",
    bg_card_muted="#172030",
    bg_input="#0F172A",
    border_subtle="#334155",
    border_active="#10B981",
    border_muted="#EF4444",
    text_primary="#F8FAFC",
    text_secondary="#94A3B8",
    text_muted="#64748B",
    accent="#3B82F6",
    accent_hover="#2563EB",
    accent_soft="#1E3A8A",
    success="#10B981",
    success_soft="#064E3B",
    danger="#EF4444",
    danger_soft="#7F1D1D",
    warning="#F59E0B",
    warning_soft="#78350F",
    slider_groove="#334155",
)

LIGHT_PALETTE = ThemePalette(
    is_dark=False,
    bg_primary="#F1F5F9",
    bg_secondary="#FFFFFF",
    bg_card="#FFFFFF",
    bg_card_hover="#F8FAFC",
    bg_card_muted="#F8FAFC",
    bg_input="#F1F5F9",
    border_subtle="#CBD5E1",
    border_active="#10B981",
    border_muted="#EF4444",
    text_primary="#0F172A",
    text_secondary="#475569",
    text_muted="#94A3B8",
    accent="#2563EB",
    accent_hover="#1D4ED8",
    accent_soft="#DBEAFE",
    success="#059669",
    success_soft="#D1FAE5",
    danger="#DC2626",
    danger_soft="#FEE2E2",
    warning="#D97706",
    warning_soft="#FEF3C7",
    slider_groove="#CBD5E1",
)


def get_palette(dark: bool = True) -> ThemePalette:
    """Retorna a paleta correspondente ao modo escuro ou claro."""
    return DARK_PALETTE if dark else LIGHT_PALETTE


def build_stylesheet(p: ThemePalette) -> str:
    """Constrói a folha de estilos QSS global da aplicação."""
    return f"""
    QMainWindow, QDialog {{
        background-color: {p.bg_primary};
        color: {p.text_primary};
        font-family: "Segoe UI", "Inter", system-ui, sans-serif;
        font-size: 13px;
    }}

    QWidget {{
        color: {p.text_primary};
        font-family: "Segoe UI", "Inter", system-ui, sans-serif;
    }}

    QLabel {{
        background: transparent;
    }}

    /* Cabeçalho superior */
    QFrame#HeaderBar {{
        background-color: {p.bg_secondary};
        border-bottom: 1px solid {p.border_subtle};
    }}

    /* Barra de busca e filtros */
    QFrame#FilterBar {{
        background-color: {p.bg_primary};
    }}

    QLineEdit#SearchInput {{
        background-color: {p.bg_card};
        color: {p.text_primary};
        border: 1px solid {p.border_subtle};
        border-radius: 8px;
        padding: 7px 12px;
        font-size: 13px;
        selection-background-color: {p.accent};
    }}

    QLineEdit#SearchInput:focus {{
        border: 1px solid {p.accent};
    }}

    /* Área de rolagem */
    QScrollArea#CardsScrollArea {{
        background-color: transparent;
        border: none;
    }}

    QWidget#CardsContainer {{
        background-color: transparent;
    }}

    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 4px 2px 4px 2px;
    }}

    QScrollBar::handle:vertical {{
        background: {p.border_subtle};
        min-height: 30px;
        border-radius: 3px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: {p.text_muted};
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}

    /* Botões padrão da barra superior */
    QPushButton#ToolbarButton {{
        background-color: {p.bg_card};
        color: {p.text_primary};
        border: 1px solid {p.border_subtle};
        border-radius: 8px;
        padding: 6px 12px;
        font-weight: 600;
        font-size: 12px;
    }}

    QPushButton#ToolbarButton:hover {{
        background-color: {p.bg_card_hover};
        border-color: {p.accent};
    }}

    QPushButton#ToolbarButton:pressed {{
        background-color: {p.bg_input};
    }}

    QPushButton#PrimaryButton {{
        background-color: {p.accent};
        color: #FFFFFF;
        border: none;
        border-radius: 8px;
        padding: 7px 14px;
        font-weight: 600;
        font-size: 12px;
    }}

    QPushButton#PrimaryButton:hover {{
        background-color: {p.accent_hover};
    }}

    /* Botões rápidos de porcentagem e ações secundárias no cartão */
    QPushButton#PresetButton {{
        background-color: {p.bg_input};
        color: {p.text_secondary};
        border: 1px solid {p.border_subtle};
        border-radius: 6px;
        padding: 3px 8px;
        font-size: 11px;
        font-weight: 600;
    }}

    QPushButton#PresetButton:hover {{
        color: {p.text_primary};
        border-color: {p.accent};
        background-color: {p.bg_card_hover};
    }}

    QPushButton#PresetButton:disabled {{
        color: {p.text_muted};
        border-color: transparent;
    }}

    /* Slider de volume */
    QSlider::groove:horizontal {{
        height: 6px;
        background: {p.slider_groove};
        border-radius: 3px;
    }}

    QSlider::sub-page:horizontal {{
        background: {p.accent};
        border-radius: 3px;
    }}

    QSlider::sub-page:horizontal:disabled {{
        background: {p.text_muted};
        border-radius: 3px;
    }}

    QSlider::handle:horizontal {{
        background: #FFFFFF;
        border: 2px solid {p.accent};
        width: 16px;
        height: 16px;
        margin: -6px 0;
        border-radius: 9px;
    }}

    QSlider::handle:horizontal:hover {{
        background: {p.accent};
        border: 2px solid #FFFFFF;
    }}

    QSlider::handle:horizontal:disabled {{
        background: {p.border_subtle};
        border: 2px solid {p.text_muted};
    }}

    /* CheckBox */
    QCheckBox {{
        spacing: 8px;
        color: {p.text_secondary};
        font-size: 12px;
        font-weight: 500;
    }}

    QCheckBox:hover {{
        color: {p.text_primary};
    }}

    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border-radius: 4px;
        border: 1px solid {p.border_subtle};
        background: {p.bg_card};
    }}

    QCheckBox::indicator:checked {{
        background: {p.accent};
        border-color: {p.accent};
    }}

    QToolTip {{
        background-color: {p.bg_secondary};
        color: {p.text_primary};
        border: 1px solid {p.border_subtle};
        padding: 6px 8px;
        border-radius: 6px;
    }}
    """

