"""Cartão individual de controle de microfone (MicrophoneCard)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from src.models.microphone import DeviceHardwareState, MicrophoneDevice
from src.ui.icons import create_mic_pixmap, create_volume_pixmap
from src.ui.styles import ThemePalette
from src.ui.widgets.level_meter import AudioLevelMeter
from src.ui.widgets.toggle_switch import ToggleSwitch


class MicrophoneCard(QFrame):
    """Cartão visual moderno para exibir e controlar um dispositivo de microfone."""

    # Sinais emitidos pelas interações do usuário
    toggle_requested = Signal(str, bool)             # (device_id, enabled)
    volume_changed = Signal(str, int, bool)          # (device_id, percent, is_final)
    set_default_requested = Signal(str)              # (device_id)
    hardware_visibility_requested = Signal(str, bool)  # (device_id, visible)

    def __init__(
        self,
        device: MicrophoneDevice,
        palette: ThemePalette,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.device = device
        self._palette = palette
        self._is_dragging_slider = False
        self.setObjectName("MicrophoneCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._build_ui()
        self.update_from_model(device, palette)

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(18, 16, 18, 16)
        root_layout.setSpacing(12)

        # --- Linha 1: Avatar + Nome/Badges + Botão/Switch de Ativação ---
        top_row = QHBoxLayout()
        top_row.setSpacing(14)

        self._avatar_label = QLabel()
        self._avatar_label.setFixedSize(46, 46)
        top_row.addWidget(self._avatar_label, alignment=Qt.AlignmentFlag.AlignTop)

        # Coluna central: Nome + Badges + Subtítulo
        info_col = QVBoxLayout()
        info_col.setSpacing(4)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)

        self._name_label = QLabel()
        self._name_label.setStyleSheet("font-size: 16px; font-weight: 700;")
        title_row.addWidget(self._name_label)

        self._default_badge = QLabel("★ PADRÃO DO SISTEMA")
        self._default_badge.setVisible(False)
        title_row.addWidget(self._default_badge)

        self._comm_badge = QLabel("● COMUNICAÇÃO")
        self._comm_badge.setVisible(False)
        title_row.addWidget(self._comm_badge)

        self._status_badge = QLabel()
        title_row.addWidget(self._status_badge)

        title_row.addStretch(1)
        info_col.addLayout(title_row)

        self._subtitle_label = QLabel()
        self._subtitle_label.setStyleSheet("font-size: 12px;")
        info_col.addWidget(self._subtitle_label)

        top_row.addLayout(info_col, stretch=1)

        # Coluna direita: Botão de ação explícito + Interruptor (ToggleSwitch)
        controls_col = QHBoxLayout()
        controls_col.setSpacing(10)

        self._hw_enable_btn = QPushButton("Habilitar no Windows")
        self._hw_enable_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hw_enable_btn.setToolTip(
            "Este dispositivo está desabilitado no Painel de Controle de Som do Windows.\n"
            "Clique para tentar reabilitá-lo no sistema."
        )
        self._hw_enable_btn.clicked.connect(self._on_hw_enable_clicked)
        self._hw_enable_btn.setVisible(False)
        controls_col.addWidget(self._hw_enable_btn)

        self._toggle_btn = QPushButton()
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.setMinimumWidth(112)
        self._toggle_btn.clicked.connect(self._on_toggle_button_clicked)
        controls_col.addWidget(self._toggle_btn)

        self._switch = ToggleSwitch(self)
        self._switch.setToolTip("Interruptor para ativar ou desativar este microfone")
        self._switch.clicked.connect(self._on_switch_clicked)
        controls_col.addWidget(self._switch)

        top_row.addLayout(controls_col)
        root_layout.addLayout(top_row)

        # --- Linha 2: Controle Deslizante de Volume + Porcentagem + Ganho dB ---
        vol_container = QWidget()
        vol_layout = QHBoxLayout(vol_container)
        vol_layout.setContentsMargins(0, 4, 0, 0)
        vol_layout.setSpacing(12)

        self._vol_icon_btn = QPushButton()
        self._vol_icon_btn.setFixedSize(28, 28)
        self._vol_icon_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._vol_icon_btn.setFlat(True)
        self._vol_icon_btn.setToolTip("Clique para alternar entre Ativo e Silenciado")
        self._vol_icon_btn.clicked.connect(self._on_toggle_button_clicked)
        vol_layout.addWidget(self._vol_icon_btn)

        vol_title = QLabel("Volume:")
        vol_title.setStyleSheet("font-size: 12px; font-weight: 600;")
        vol_layout.addWidget(vol_title)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 100)
        self._slider.setSingleStep(1)
        self._slider.setPageStep(5)
        self._slider.setCursor(Qt.CursorShape.PointingHandCursor)
        self._slider.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self._slider.sliderPressed.connect(self._on_slider_pressed)
        self._slider.sliderReleased.connect(self._on_slider_released)
        self._slider.valueChanged.connect(self._on_slider_value_changed)
        vol_layout.addWidget(self._slider, stretch=1)

        self._percent_label = QLabel("100%")
        self._percent_label.setMinimumWidth(52)
        self._percent_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self._percent_label.setStyleSheet("font-size: 15px; font-weight: 700;")
        vol_layout.addWidget(self._percent_label)

        self._db_label = QLabel("")
        self._db_label.setMinimumWidth(68)
        self._db_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self._db_label.setStyleSheet("font-size: 11px;")
        vol_layout.addWidget(self._db_label)

        root_layout.addWidget(vol_container)

        # --- Linha 3: Medidor de Nível em Tempo Real + Botões Rápidos + Definir Padrão ---
        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 2, 0, 0)
        bottom_row.setSpacing(8)

        meter_label = QLabel("Sinal:")
        meter_label.setStyleSheet("font-size: 11px; font-weight: 600;")
        bottom_row.addWidget(meter_label)

        self._level_meter = AudioLevelMeter(self)
        self._level_meter.setFixedWidth(150)
        self._level_meter.setToolTip("Nível de entrada de áudio em tempo real")
        bottom_row.addWidget(self._level_meter)

        bottom_row.addSpacing(8)

        # Botões rápidos de volume (0%, 25%, 50%, 75%, 100%)
        self._preset_buttons: list[QPushButton] = []
        for preset in (0, 25, 50, 75, 100):
            btn = QPushButton(f"{preset}%")
            btn.setObjectName("PresetButton")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, val=preset: self._on_preset_clicked(val))
            bottom_row.addWidget(btn)
            self._preset_buttons.append(btn)

        bottom_row.addStretch(1)

        self._set_default_btn = QPushButton("★ Definir como Padrão")
        self._set_default_btn.setObjectName("PresetButton")
        self._set_default_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._set_default_btn.setToolTip(
            "Define este microfone como dispositivo de captura padrão do Windows"
        )
        self._set_default_btn.clicked.connect(
            lambda: self.set_default_requested.emit(self.device.id)
        )
        bottom_row.addWidget(self._set_default_btn)

        root_layout.addLayout(bottom_row)

        # --- Linha 4 (Opcional): Aviso de erro ou limitação do driver ---
        self._warning_label = QLabel()
        self._warning_label.setWordWrap(True)
        self._warning_label.setVisible(False)
        root_layout.addWidget(self._warning_label)

    def _on_toggle_button_clicked(self) -> None:
        if not self.device.is_available:
            return
        target_enabled = not self.device.is_enabled
        self.toggle_requested.emit(self.device.id, target_enabled)

    def _on_switch_clicked(self, checked: bool) -> None:
        if not self.device.is_available:
            return
        self.toggle_requested.emit(self.device.id, bool(checked))

    def _on_hw_enable_clicked(self) -> None:
        self.hardware_visibility_requested.emit(self.device.id, True)

    def _on_slider_pressed(self) -> None:
        self._is_dragging_slider = True

    def _on_slider_released(self) -> None:
        self._is_dragging_slider = False
        val = self._slider.value()
        self._percent_label.setText(f"{val}%")
        self.volume_changed.emit(self.device.id, val, True)

    def _on_slider_value_changed(self, value: int) -> None:
        self._percent_label.setText(f"{value}%")
        self._update_volume_icon(value, self.device.is_muted)
        # Atualiza o volume do dispositivo em tempo real durante o arraste
        self.volume_changed.emit(self.device.id, value, not self._is_dragging_slider)

    def _on_preset_clicked(self, preset_value: int) -> None:
        if not self.device.is_available or not self.device.supports_volume:
            return
        was_blocked = self._slider.blockSignals(True)
        self._slider.setValue(preset_value)
        self._slider.blockSignals(was_blocked)
        self._percent_label.setText(f"{preset_value}%")
        self._update_volume_icon(preset_value, self.device.is_muted)
        self.volume_changed.emit(self.device.id, preset_value, True)

    def _update_volume_icon(self, volume_percent: int, muted: bool) -> None:
        color = (
            self._palette.danger
            if muted or not self.device.is_available
            else self._palette.text_secondary
        )
        pix = create_volume_pixmap(
            size=20,
            volume_percent=volume_percent,
            muted=muted or not self.device.is_available,
            color=color,
        )
        self._vol_icon_btn.setIcon(pix)

    def update_peak_level(self, level: float) -> None:
        """Atualiza o medidor de nível de entrada em tempo real."""
        self.device.peak_level = level
        self._level_meter.set_active(self.device.is_enabled)
        self._level_meter.set_level(level)

    def update_from_model(
        self,
        device: MicrophoneDevice,
        palette: ThemePalette | None = None,
    ) -> None:
        """Sincroniza todos os controles visuais do cartão com o estado real do sistema."""
        self.device = device
        if palette is not None:
            self._palette = palette
        p = self._palette

        is_avail = device.is_available
        is_enabled = device.is_enabled

        # Borda lateral e estilo do cartão conforme estado
        if not is_avail:
            border_color = p.border_subtle
            card_bg = p.bg_card_muted
            avatar_bg = p.border_subtle
        elif is_enabled:
            border_color = p.border_active if device.is_default_console else p.border_subtle
            card_bg = p.bg_card
            avatar_bg = p.success
        else:
            border_color = p.border_muted
            card_bg = p.bg_card
            avatar_bg = p.danger

        self.setStyleSheet(
            f"""
            QFrame#MicrophoneCard {{
                background-color: {card_bg};
                border: 1px solid {border_color};
                border-radius: 12px;
            }}
            QFrame#MicrophoneCard:hover {{
                background-color: {p.bg_card_hover};
            }}
            """
        )

        # Avatar do microfone
        self._avatar_label.setPixmap(
            create_mic_pixmap(
                size=46,
                active=is_enabled,
                available=is_avail,
                fg_color="#FFFFFF",
                bg_color=avatar_bg,
            )
        )

        # Textos principais
        self._name_label.setText(device.display_title)
        self._name_label.setStyleSheet(
            f"font-size: 16px; font-weight: 700; color: {p.text_primary};"
        )
        self._subtitle_label.setText(device.display_subtitle)
        self._subtitle_label.setStyleSheet(
            f"font-size: 12px; color: {p.text_secondary};"
        )

        # Badge Padrão do Sistema
        self._default_badge.setVisible(device.is_default_console)
        self._default_badge.setStyleSheet(
            f"""
            background-color: {p.accent_soft};
            color: {"#93C5FD" if p.is_dark else p.accent};
            border: 1px solid {p.accent};
            border-radius: 5px;
            padding: 2px 7px;
            font-size: 10px;
            font-weight: 700;
            """
        )

        # Badge Padrão de Comunicação (exibido se for padrão de comunicação)
        show_comm = device.is_default_communications and not device.is_default_console
        self._comm_badge.setVisible(show_comm)
        if show_comm:
            self._comm_badge.setStyleSheet(
                f"""
                background-color: {p.bg_input};
                color: {p.text_secondary};
                border: 1px solid {p.border_subtle};
                border-radius: 5px;
                padding: 2px 7px;
                font-size: 10px;
                font-weight: 700;
                """
            )

        # Badge de Estado (ATIVO / DESATIVADO / DESCONECTADO)
        if not is_avail:
            badge_bg = p.warning_soft
            badge_fg = "#FCD34D" if p.is_dark else p.warning
            badge_border = p.warning
            badge_text = f"● {device.hardware_state.label_pt.upper()}"
        elif is_enabled:
            badge_bg = p.success_soft
            badge_fg = "#6EE7B7" if p.is_dark else p.success
            badge_border = p.success
            badge_text = "● ATIVO (CAPTURANDO)"
        else:
            badge_bg = p.danger_soft
            badge_fg = "#FCA5A5" if p.is_dark else p.danger
            badge_border = p.danger
            badge_text = "● DESATIVADO (MUDO)"

        self._status_badge.setText(badge_text)
        self._status_badge.setStyleSheet(
            f"""
            background-color: {badge_bg};
            color: {badge_fg};
            border: 1px solid {badge_border};
            border-radius: 5px;
            padding: 2px 8px;
            font-size: 10px;
            font-weight: 700;
            """
        )

        # Botão de habilitar no Windows para endpoints desabilitados
        is_hw_disabled = device.hardware_state == DeviceHardwareState.DISABLED
        self._hw_enable_btn.setVisible(is_hw_disabled)
        if is_hw_disabled:
            self._hw_enable_btn.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {p.accent};
                    color: #FFFFFF;
                    border: none;
                    border-radius: 7px;
                    padding: 6px 12px;
                    font-size: 12px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background-color: {p.accent_hover};
                }}
                """
            )

        # Botão e interruptor de Ativar/Desativar
        can_mute = is_avail and device.supports_mute
        self._toggle_btn.setEnabled(can_mute)
        self._switch.setEnabled(can_mute)
        self._switch.set_colors(p.success, p.danger if is_avail else p.border_subtle)
        self._switch.setCheckedSilent(is_enabled)

        if not is_avail:
            self._toggle_btn.setText("Indisponível")
            self._toggle_btn.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {p.bg_input};
                    color: {p.text_muted};
                    border: 1px solid {p.border_subtle};
                    border-radius: 8px;
                    padding: 6px 12px;
                    font-weight: 600;
                }}
                """
            )
        elif is_enabled:
            self._toggle_btn.setText("Desativar")
            self._toggle_btn.setToolTip("Clique para silenciar (desativar) este microfone")
            self._toggle_btn.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {p.bg_input};
                    color: {p.text_primary};
                    border: 1px solid {p.border_subtle};
                    border-radius: 8px;
                    padding: 6px 12px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background-color: {p.danger_soft};
                    border-color: {p.danger};
                    color: {"#FCA5A5" if p.is_dark else p.danger};
                }}
                """
            )
        else:
            self._toggle_btn.setText("Ativar Microfone")
            self._toggle_btn.setToolTip("Clique para ativar a captura deste microfone")
            self._toggle_btn.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {p.success};
                    color: #FFFFFF;
                    border: none;
                    border-radius: 8px;
                    padding: 6px 12px;
                    font-weight: 700;
                }}
                QPushButton:hover {{
                    background-color: #059669;
                }}
                """
            )

        # Slider e rótulos de volume (não sobrescreve se o usuário estiver arrastando)
        can_vol = is_avail and device.supports_volume
        self._slider.setEnabled(can_vol)
        for btn in self._preset_buttons:
            btn.setEnabled(can_vol)

        if not self._is_dragging_slider:
            was_blocked = self._slider.blockSignals(True)
            self._slider.setValue(device.volume_percent)
            self._slider.blockSignals(was_blocked)
            self._percent_label.setText(f"{device.volume_percent}%")

        self._percent_label.setStyleSheet(
            f"font-size: 15px; font-weight: 700; color: "
            f"{p.text_primary if is_avail else p.text_muted};"
        )

        if is_avail and device.volume_db is not None:
            sign = "+" if device.volume_db > 0 else ""
            self._db_label.setText(f"({sign}{device.volume_db:.1f} dB)")
        else:
            self._db_label.setText("(— dB)")
        self._db_label.setStyleSheet(f"font-size: 11px; color: {p.text_muted};")

        self._update_volume_icon(device.volume_percent, device.is_muted)

        # Medidor de sinal
        self._level_meter.set_track_color(p.bg_input)
        self._level_meter.set_active(is_enabled)
        self._level_meter.set_level(device.peak_level)

        # Botão Definir como Padrão
        self._set_default_btn.setVisible(is_avail and not device.is_default_console)

        # Mensagem de aviso/erro do dispositivo
        if device.error_message:
            self._warning_label.setText(f"⚠ {device.error_message}")
            self._warning_label.setStyleSheet(
                f"color: {p.warning}; font-size: 11px; font-weight: 600; padding-top: 4px;"
            )
            self._warning_label.setVisible(True)
        else:
            self._warning_label.setVisible(False)

