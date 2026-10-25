"""Janela principal do aplicativo Gerenciador de Microfones."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QResizeEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QPushButton,
    QScrollArea,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from src import __app_display_name__, __version__
from src.audio.controller import AudioController
from src.audio.monitor import AudioDeviceMonitor
from src.models.microphone import MicrophoneDevice, OperationResult
from src.services.hotkeys import GlobalHotkeyManager
from src.services.settings import AppSettings
from src.ui.icons import create_app_icon, create_mic_pixmap
from src.ui.styles import ThemePalette, build_stylesheet, get_palette
from src.ui.widgets.mic_card import MicrophoneCard
from src.ui.widgets.settings_dialog import SettingsDialog
from src.ui.widgets.toast import ToastOverlay

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Janela principal moderna para visualização e controle individual de microfones."""

    def __init__(self, start_minimized: bool = False) -> None:
        super().__init__()
        self.settings = AppSettings()
        self.palette: ThemePalette = get_palette(dark=self.settings.dark_theme)
        self.controller = AudioController(
            include_inactive=self.settings.show_inactive_devices
        )

        self._devices: List[MicrophoneDevice] = []
        self._cards_by_id: Dict[str, MicrophoneCard] = {}
        self._ordered_card_ids: List[str] = []
        self._force_quit = False

        self.setWindowTitle(f"{__app_display_name__} v{__version__}")
        self.setMinimumSize(780, 560)
        self.resize(880, 680)
        self.setWindowIcon(create_app_icon(active=True))

        self._build_ui()
        self._apply_theme()
        self._setup_tray_icon()
        self._setup_global_hotkey()
        self._setup_monitor_thread()

        if start_minimized and QSystemTrayIcon.isSystemTrayAvailable():
            QTimer.singleShot(100, self.hide)
        else:
            self.show()

    def _build_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- 1. Barra de Cabeçalho ---
        self._header_frame = QFrame()
        self._header_frame.setObjectName("HeaderBar")
        header_layout = QHBoxLayout(self._header_frame)
        header_layout.setContentsMargins(24, 16, 24, 16)
        header_layout.setSpacing(14)

        self._header_logo = QLabel()
        self._header_logo.setFixedSize(40, 40)
        header_layout.addWidget(self._header_logo)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)

        self._app_title_label = QLabel(__app_display_name__)
        self._app_title_label.setStyleSheet("font-size: 18px; font-weight: 800;")
        title_col.addWidget(self._app_title_label)

        self._summary_label = QLabel("Detectando interfaces de microfone...")
        self._summary_label.setStyleSheet("font-size: 12px;")
        title_col.addWidget(self._summary_label)

        header_layout.addLayout(title_col, stretch=1)

        # Botões de ação global
        self._btn_enable_all = QPushButton("Ativar Todos")
        self._btn_enable_all.setObjectName("ToolbarButton")
        self._btn_enable_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_enable_all.setToolTip("Ativa (desmuta) todos os microfones conectados")
        self._btn_enable_all.clicked.connect(lambda: self._set_all_devices_enabled(True))
        header_layout.addWidget(self._btn_enable_all)

        self._btn_disable_all = QPushButton("Desativar Todos")
        self._btn_disable_all.setObjectName("ToolbarButton")
        self._btn_disable_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_disable_all.setToolTip(
            "Desativa (silencia) todos os microfones conectados"
        )
        self._btn_disable_all.clicked.connect(
            lambda: self._set_all_devices_enabled(False)
        )
        header_layout.addWidget(self._btn_disable_all)

        self._btn_refresh = QPushButton("↻ Atualizar")
        self._btn_refresh.setObjectName("ToolbarButton")
        self._btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_refresh.setToolTip("Recarrega imediatamente a lista de dispositivos")
        self._btn_refresh.clicked.connect(self._on_manual_refresh)
        header_layout.addWidget(self._btn_refresh)

        self._btn_theme = QPushButton()
        self._btn_theme.setObjectName("ToolbarButton")
        self._btn_theme.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_theme.setToolTip("Alternar entre tema escuro e tema claro")
        self._btn_theme.clicked.connect(self._on_toggle_theme)
        header_layout.addWidget(self._btn_theme)

        self._btn_settings = QPushButton("⚙ Configurações")
        self._btn_settings.setObjectName("ToolbarButton")
        self._btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_settings.clicked.connect(self._open_settings_dialog)
        header_layout.addWidget(self._btn_settings)

        main_layout.addWidget(self._header_frame)

        # --- 2. Barra de Busca e Filtros ---
        self._filter_frame = QFrame()
        self._filter_frame.setObjectName("FilterBar")
        filter_layout = QHBoxLayout(self._filter_frame)
        filter_layout.setContentsMargins(24, 14, 24, 8)
        filter_layout.setSpacing(14)

        self._search_input = QLineEdit()
        self._search_input.setObjectName("SearchInput")
        self._search_input.setPlaceholderText(
            "🔍 Filtrar microfones por nome, adaptador ou ID..."
        )
        self._search_input.setClearButtonEnabled(True)
        self._search_input.textChanged.connect(self._apply_search_filter)
        filter_layout.addWidget(self._search_input, stretch=1)

        self._chk_inactive = QCheckBox("Mostrar desabilitados / desconectados")
        self._chk_inactive.setChecked(self.settings.show_inactive_devices)
        self._chk_inactive.toggled.connect(self._on_toggle_show_inactive)
        filter_layout.addWidget(self._chk_inactive)

        self._hotkey_badge = QLabel()
        filter_layout.addWidget(self._hotkey_badge)

        main_layout.addWidget(self._filter_frame)

        # --- 3. Banner de Alerta / Erro (Oculto por padrão) ---
        self._error_banner = QFrame()
        self._error_banner.setVisible(False)
        err_layout = QHBoxLayout(self._error_banner)
        err_layout.setContentsMargins(16, 10, 16, 10)
        err_layout.setSpacing(12)

        self._error_label = QLabel()
        self._error_label.setWordWrap(True)
        err_layout.addWidget(self._error_label, stretch=1)

        close_err_btn = QPushButton("✕")
        close_err_btn.setFixedSize(24, 24)
        close_err_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_err_btn.setFlat(True)
        close_err_btn.clicked.connect(lambda: self._error_banner.setVisible(False))
        err_layout.addWidget(close_err_btn)

        banner_wrapper = QHBoxLayout()
        banner_wrapper.setContentsMargins(24, 4, 24, 4)
        banner_wrapper.addWidget(self._error_banner)
        main_layout.addLayout(banner_wrapper)

        # --- 4. Área Rolável de Cartões de Microfone ---
        self._scroll_area = QScrollArea()
        self._scroll_area.setObjectName("CardsScrollArea")
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self._cards_container = QWidget()
        self._cards_container.setObjectName("CardsContainer")
        self._cards_layout = QVBoxLayout(self._cards_container)
        self._cards_layout.setContentsMargins(24, 8, 24, 28)
        self._cards_layout.setSpacing(12)

        # Estado vazio (quando nenhum dispositivo corresponde ao filtro)
        self._empty_label = QLabel()
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setWordWrap(True)
        self._empty_label.setMinimumHeight(180)
        self._empty_label.setVisible(False)
        self._cards_layout.addWidget(self._empty_label)

        self._cards_layout.addStretch(1)
        self._scroll_area.setWidget(self._cards_container)
        main_layout.addWidget(self._scroll_area, stretch=1)

        # --- 5. Toast Overlay Flutuante ---
        self._toast = ToastOverlay(self)

    def _apply_theme(self) -> None:
        p = self.palette
        self.setStyleSheet(build_stylesheet(p))
        self._btn_theme.setText("☀ Claro" if p.is_dark else "🌙 Escuro")

        self._header_logo.setPixmap(
            create_mic_pixmap(
                size=40,
                active=True,
                available=True,
                fg_color="#FFFFFF",
                bg_color=p.accent,
            )
        )
        self._app_title_label.setStyleSheet(
            f"font-size: 18px; font-weight: 800; color: {p.text_primary};"
        )
        self._summary_label.setStyleSheet(
            f"font-size: 12px; color: {p.text_secondary};"
        )
        self._empty_label.setStyleSheet(
            f"font-size: 14px; font-weight: 600; color: {p.text_muted}; padding: 32px;"
        )
        self._error_banner.setStyleSheet(
            f"""
            QFrame {{
                background-color: {p.danger_soft};
                border: 1px solid {p.danger};
                border-radius: 8px;
            }}
            QLabel {{
                color: {"#FECACA" if p.is_dark else p.danger};
                font-size: 12px;
                font-weight: 600;
                border: none;
            }}
            QPushButton {{
                color: {"#FECACA" if p.is_dark else p.danger};
                font-weight: bold;
                border: none;
            }}
            """
        )
        self._update_hotkey_badge()

        for card in self._cards_by_id.values():
            card.update_from_model(card.device, p)

    def _update_hotkey_badge(self) -> None:
        p = self.palette
        if self.settings.global_hotkey_enabled:
            chord = self.settings.global_hotkey_chord
            self._hotkey_badge.setText(f"⌨ {chord}")
            self._hotkey_badge.setToolTip(
                f"Atalho global ativo ({chord}) para alternar o microfone padrão"
            )
            self._hotkey_badge.setStyleSheet(
                f"""
                background-color: {p.bg_card};
                color: {p.text_secondary};
                border: 1px solid {p.border_subtle};
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 11px;
                font-weight: 600;
                """
            )
            self._hotkey_badge.setVisible(True)
        else:
            self._hotkey_badge.setVisible(False)

    def _setup_tray_icon(self) -> None:
        """Configura o ícone e menu de contexto na bandeja do sistema (System Tray)."""
        self._tray_icon = QSystemTrayIcon(self)
        self._tray_icon.setIcon(create_app_icon(active=True))
        self._tray_icon.setToolTip(__app_display_name__)

        tray_menu = QMenu(self)

        act_open = QAction("Abrir Gerenciador de Microfones", self)
        act_open.triggered.connect(self._restore_from_tray)
        tray_menu.addAction(act_open)

        tray_menu.addSeparator()

        self._act_tray_toggle_default = QAction(
            "Alternar Microfone Padrão (Ativar/Desativar)", self
        )
        self._act_tray_toggle_default.triggered.connect(
            self._on_toggle_default_microphone
        )
        tray_menu.addAction(self._act_tray_toggle_default)

        act_enable_all = QAction("Ativar Todos os Microfones", self)
        act_enable_all.triggered.connect(lambda: self._set_all_devices_enabled(True))
        tray_menu.addAction(act_enable_all)

        act_disable_all = QAction("Desativar Todos os Microfones", self)
        act_disable_all.triggered.connect(lambda: self._set_all_devices_enabled(False))
        tray_menu.addAction(act_disable_all)

        tray_menu.addSeparator()

        act_quit = QAction("Sair Completamente", self)
        act_quit.triggered.connect(self._quit_application)
        tray_menu.addAction(act_quit)

        self._tray_icon.setContextMenu(tray_menu)
        self._tray_icon.activated.connect(self._on_tray_activated)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self._tray_icon.show()

    def _setup_global_hotkey(self) -> None:
        self._hotkey_mgr = GlobalHotkeyManager(self)
        self._hotkey_mgr.activated.connect(self._on_toggle_default_microphone)
        self._apply_hotkey_settings()

    def _apply_hotkey_settings(self) -> None:
        if self.settings.global_hotkey_enabled:
            ok, msg = self._hotkey_mgr.register_hotkey(
                self.settings.global_hotkey_chord
            )
            if not ok:
                logger.warning(msg)
        else:
            self._hotkey_mgr.unregister_hotkey()
        self._update_hotkey_badge()

    def _setup_monitor_thread(self) -> None:
        self._monitor = AudioDeviceMonitor(
            include_inactive=self.settings.show_inactive_devices,
            sync_interval_ms=750,
            meter_interval_ms=80,
            parent=self,
        )
        self._monitor.devices_updated.connect(self._on_devices_updated)
        self._monitor.levels_updated.connect(self._on_levels_updated)
        self._monitor.topology_event_detected.connect(self._on_topology_notification)
        self._monitor.monitor_error.connect(self._on_monitor_error)
        self._monitor.start()

    # --- Handlers de Monitoramento e Sincronização ---

    def _on_devices_updated(self, devices: List[MicrophoneDevice]) -> None:
        self._devices = devices
        new_ids = [d.id for d in devices]

        # Se a lista ou ordem mudou, reconstrói o layout dos cartões preservando instâncias
        if new_ids != self._ordered_card_ids:
            # Remove cartões de dispositivos que não estão mais na lista
            removed_ids = set(self._cards_by_id.keys()) - set(new_ids)
            for rem_id in removed_ids:
                card = self._cards_by_id.pop(rem_id)
                self._cards_layout.removeWidget(card)
                card.deleteLater()

            # Reordena/cria os cartões
            for idx, dev in enumerate(devices):
                card = self._cards_by_id.get(dev.id)
                if card is None:
                    card = MicrophoneCard(dev, self.palette, self._cards_container)
                    card.toggle_requested.connect(self._on_card_toggle_requested)
                    card.volume_changed.connect(self._on_card_volume_changed)
                    card.set_default_requested.connect(self._on_card_set_default)
                    card.hardware_visibility_requested.connect(
                        self._on_card_hw_visibility
                    )
                    self._cards_by_id[dev.id] = card
                else:
                    card.update_from_model(dev, self.palette)

                self._cards_layout.insertWidget(idx, card)

            self._ordered_card_ids = new_ids
        else:
            # Apenas atualiza cada cartão existente sem recriar widgets
            for dev in devices:
                card = self._cards_by_id.get(dev.id)
                if card is not None:
                    card.update_from_model(dev, self.palette)

        self._apply_search_filter()
        self._update_header_summary()
        self._update_tray_state()

    def _on_levels_updated(self, levels: Dict[str, float]) -> None:
        for dev_id, peak in levels.items():
            card = self._cards_by_id.get(dev_id)
            if card is not None:
                card.update_peak_level(peak)

    def _on_topology_notification(self, text: str) -> None:
        self._notify(text, kind="info")

    def _on_monitor_error(self, error_text: str) -> None:
        self._show_error_banner(f"Erro ao sincronizar dispositivos de áudio: {error_text}")

    # --- Ações Individuais e Globais nos Microfones ---

    def _on_card_toggle_requested(self, device_id: str, enabled: bool) -> None:
        self._monitor.notify_user_interaction(device_id, hold_seconds=0.8)
        result = self.controller.set_device_enabled(device_id, enabled)
        self._handle_operation_result(result, show_toast_on_success=True)

    def _on_card_volume_changed(
        self,
        device_id: str,
        volume_percent: int,
        is_final: bool,
    ) -> None:
        self._monitor.notify_user_interaction(device_id, hold_seconds=0.6)
        result = self.controller.set_device_volume(device_id, volume_percent)
        # Mostra notificação discreta apenas quando o usuário solta o slider ou clica em preset
        self._handle_operation_result(result, show_toast_on_success=is_final)

    def _on_card_set_default(self, device_id: str) -> None:
        result = self.controller.set_default_device(
            device_id, include_communications=True
        )
        self._handle_operation_result(result, show_toast_on_success=True)
        self._monitor.request_refresh()

    def _on_card_hw_visibility(self, device_id: str, visible: bool) -> None:
        result = self.controller.set_endpoint_hardware_visibility(device_id, visible)
        self._handle_operation_result(result, show_toast_on_success=True)
        self._monitor.request_refresh()

    def _set_all_devices_enabled(self, enabled: bool) -> None:
        available_devs = [d for d in self._devices if d.is_available]
        if not available_devs:
            self._notify("Nenhum microfone conectado disponível.", kind="warning")
            return

        changed_count = 0
        errors: List[str] = []
        for dev in available_devs:
            self._monitor.notify_user_interaction(dev.id, hold_seconds=0.8)
            res = self.controller.set_device_enabled(dev.id, enabled)
            if res.success:
                changed_count += 1
            else:
                errors.append(res.message)

        self._monitor.request_refresh()
        action_word = "ativados" if enabled else "desativados (silenciados)"
        if errors:
            self._show_error_banner(" | ".join(errors[:2]))
        if changed_count > 0:
            self._notify(
                f"{changed_count} microfone(s) {action_word}.",
                kind="success" if enabled else "warning",
            )

    def _on_toggle_default_microphone(self) -> None:
        """Alterna o estado de ativação do microfone padrão (acionado pela bandeja ou atalho global)."""
        default_dev = next(
            (d for d in self._devices if d.is_default_console and d.is_available),
            None,
        )
        if default_dev is None:
            default_dev = next((d for d in self._devices if d.is_available), None)

        if default_dev is None:
            self._notify("Nenhum microfone conectado para alternar.", kind="error")
            return

        res = self.controller.toggle_device_enabled(default_dev.id)
        self._handle_operation_result(res, show_toast_on_success=True)
        self._monitor.request_refresh()

        # Se a janela estiver oculta na bandeja, exibe notificação nativa discreta
        if not self.isVisible() and res.success and res.device is not None:
            state_str = "ATIVO" if res.device.is_enabled else "DESATIVADO (MUDO)"
            self._tray_icon.showMessage(
                __app_display_name__,
                f"{res.device.display_title}: {state_str}",
                QSystemTrayIcon.MessageIcon.Information,
                1800,
            )

    def _handle_operation_result(
        self,
        result: OperationResult,
        show_toast_on_success: bool = True,
    ) -> None:
        if result.device is not None:
            card = self._cards_by_id.get(result.device_id)
            if card is not None:
                card.update_from_model(result.device, self.palette)
            # Atualiza também na lista em memória
            for i, d in enumerate(self._devices):
                if d.id == result.device_id:
                    self._devices[i] = result.device
                    break
            self._update_header_summary()
            self._update_tray_state()

        if not result.success:
            self._show_error_banner(result.message)
            self._notify(result.message, kind="error")
        elif show_toast_on_success:
            self._notify(result.message, kind="success")

    # --- UI Helpers, Busca, Resumo e Bandeja ---

    def _apply_search_filter(self) -> None:
        query = self._search_input.text().strip().lower()
        visible_count = 0

        for dev in self._devices:
            card = self._cards_by_id.get(dev.id)
            if card is None:
                continue
            searchable = (
                f"{dev.display_title} {dev.adapter_name} {dev.short_id} "
                f"{dev.hardware_state.label_pt}"
            ).lower()
            matches = (not query) or (query in searchable)
            card.setVisible(matches)
            if matches:
                visible_count += 1

        if not self._devices:
            self._empty_label.setText(
                "Nenhum dispositivo de entrada de áudio ativo foi encontrado no sistema.\n"
                "Conecte um microfone ou marque a opção 'Mostrar desabilitados / desconectados'."
            )
            self._empty_label.setVisible(True)
        elif visible_count == 0:
            self._empty_label.setText(
                f"Nenhum microfone encontrado para a busca '{self._search_input.text()}'."
            )
            self._empty_label.setVisible(True)
        else:
            self._empty_label.setVisible(False)

    def _update_header_summary(self) -> None:
        connected = [d for d in self._devices if d.is_available]
        enabled_list = [d for d in connected if d.is_enabled]
        default_dev = next((d for d in connected if d.is_default_console), None)

        summary = (
            f"{len(enabled_list)} ativo(s) de {len(connected)} conectado(s)"
        )
        if default_dev is not None:
            def_state = "Ativo" if default_dev.is_enabled else "Mudo"
            summary += (
                f"  •  Padrão: {default_dev.display_title} "
                f"({default_dev.volume_percent}% — {def_state})"
            )
        self._summary_label.setText(summary)

    def _update_tray_state(self) -> None:
        connected = [d for d in self._devices if d.is_available]
        default_dev = next(
            (d for d in connected if d.is_default_console),
            connected[0] if connected else None,
        )
        is_active = default_dev.is_enabled if default_dev is not None else False
        icon = create_app_icon(active=is_active)
        self._tray_icon.setIcon(icon)
        self.setWindowIcon(icon)

        if default_dev is not None:
            status = "ATIVO" if default_dev.is_enabled else "DESATIVADO"
            self._tray_icon.setToolTip(
                f"{__app_display_name__}\n"
                f"Padrão: {default_dev.display_title} ({default_dev.volume_percent}%) — {status}"
            )

    def _notify(self, message: str, kind: str = "info") -> None:
        if self.settings.show_notifications:
            self._toast.show_toast(message, kind=kind)

    def _show_error_banner(self, message: str) -> None:
        self._error_label.setText(f"⚠ {message}")
        self._error_banner.setVisible(True)

    def _on_manual_refresh(self) -> None:
        self._monitor.request_refresh()
        self._notify("Lista de microfones atualizada.", kind="info")

    def _on_toggle_show_inactive(self, checked: bool) -> None:
        self.settings.show_inactive_devices = checked
        self.controller.include_inactive = checked
        self._monitor.set_include_inactive(checked)

    def _on_toggle_theme(self) -> None:
        new_dark = not self.palette.is_dark
        self.settings.dark_theme = new_dark
        self.palette = get_palette(dark=new_dark)
        self._apply_theme()

    def _open_settings_dialog(self) -> None:
        dlg = SettingsDialog(self.settings, self.palette, self)
        if dlg.exec() == SettingsDialog.DialogCode.Accepted:
            self._apply_hotkey_settings()
            if dlg.status_message:
                self._show_error_banner(dlg.status_message)
            else:
                self._notify("Configurações salvas com sucesso.", kind="success")

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._restore_from_tray()

    def _restore_from_tray(self) -> None:
        self._monitor.set_meters_enabled(True)
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _quit_application(self) -> None:
        self._force_quit = True
        self.close()

    # --- Eventos do Ciclo de Vida da Janela ---

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if hasattr(self, "_toast") and self._toast.isVisible():
            self._toast.reposition()

    def closeEvent(self, event: QCloseEvent) -> None:
        if (
            not self._force_quit
            and self.settings.minimize_to_tray
            and QSystemTrayIcon.isSystemTrayAvailable()
        ):
            event.ignore()
            self._monitor.set_meters_enabled(False)
            self.hide()
            if self.settings.show_notifications:
                self._tray_icon.showMessage(
                    __app_display_name__,
                    "O aplicativo continua em execução na bandeja do sistema.",
                    QSystemTrayIcon.MessageIcon.Information,
                    2000,
                )
            return

        self._hotkey_mgr.unregister_hotkey()
        self._monitor.stop()
        self._tray_icon.hide()
        event.accept()
        QApplication.quit()

