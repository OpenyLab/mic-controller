"""Diálogo de configurações do aplicativo (Inicialização, Bandeja, Atalhos e Diagnóstico)."""

from __future__ import annotations

import os
import subprocess
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.services.settings import AppSettings
from src.services.startup import StartupManager
from src.ui.styles import ThemePalette


class SettingsDialog(QDialog):
    """Janela modal para gerenciar preferências do sistema, bandeja e atalho global."""

    def __init__(
        self,
        settings: AppSettings,
        palette: ThemePalette,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.settings = settings
        self.palette = palette
        self.status_message: str = ""

        self.setWindowTitle("Configurações — Gerenciador de Microfones")
        self.setModal(True)
        self.setMinimumWidth(480)
        self._build_ui()

    def _build_ui(self) -> None:
        p = self.palette
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(16)

        title = QLabel("Configurações e Integração com o Windows")
        title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {p.text_primary};")
        layout.addWidget(title)

        # --- Seção 1: Sistema e Bandeja ---
        sys_card = self._create_section_frame("Comportamento do Sistema")
        sys_layout = QVBoxLayout(sys_card)
        sys_layout.setContentsMargins(14, 14, 14, 14)
        sys_layout.setSpacing(10)

        self._chk_startup = QCheckBox("Iniciar automaticamente junto com o Windows")
        self._chk_startup.setChecked(StartupManager.is_enabled())
        sys_layout.addWidget(self._chk_startup)

        self._chk_start_minimized = QCheckBox("Iniciar minimizado na bandeja do sistema")
        self._chk_start_minimized.setChecked(self.settings.start_minimized)
        sys_layout.addWidget(self._chk_start_minimized)

        self._chk_minimize_tray = QCheckBox(
            "Minimizar para a bandeja do sistema ao fechar a janela"
        )
        self._chk_minimize_tray.setChecked(self.settings.minimize_to_tray)
        sys_layout.addWidget(self._chk_minimize_tray)

        self._chk_notifications = QCheckBox(
            "Exibir notificações discretas ao alterar volume ou estado do microfone"
        )
        self._chk_notifications.setChecked(self.settings.show_notifications)
        sys_layout.addWidget(self._chk_notifications)

        layout.addWidget(sys_card)

        # --- Seção 2: Atalho Global de Teclado ---
        hk_card = self._create_section_frame(
            "Atalho Global de Teclado (Alternar Microfone Padrão)"
        )
        hk_layout = QVBoxLayout(hk_card)
        hk_layout.setContentsMargins(14, 14, 14, 14)
        hk_layout.setSpacing(10)

        self._chk_hotkey = QCheckBox(
            "Habilitar atalho global para ativar/desativar o microfone padrão"
        )
        self._chk_hotkey.setChecked(self.settings.global_hotkey_enabled)
        hk_layout.addWidget(self._chk_hotkey)

        chord_row = QHBoxLayout()
        chord_label = QLabel("Combinação de teclas:")
        chord_label.setStyleSheet(f"color: {p.text_secondary}; font-size: 12px;")
        chord_row.addWidget(chord_label)

        self._txt_chord = QLineEdit(self.settings.global_hotkey_chord)
        self._txt_chord.setObjectName("SearchInput")
        self._txt_chord.setPlaceholderText("Ex: Ctrl+Shift+M ou Ctrl+Alt+M")
        chord_row.addWidget(self._txt_chord, stretch=1)

        reset_hk_btn = QPushButton("Padrão")
        reset_hk_btn.setObjectName("PresetButton")
        reset_hk_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_hk_btn.clicked.connect(lambda: self._txt_chord.setText("Ctrl+Shift+M"))
        chord_row.addWidget(reset_hk_btn)

        hk_layout.addLayout(chord_row)

        hk_hint = QLabel(
            "Dica: Use modificadores (Ctrl, Shift, Alt) + uma letra ou tecla F1–F12."
        )
        hk_hint.setStyleSheet(f"color: {p.text_muted}; font-size: 11px;")
        hk_layout.addWidget(hk_hint)

        layout.addWidget(hk_card)

        # --- Seção 3: Utilitários do Windows para Solução de Problemas ---
        tools_card = self._create_section_frame("Diagnóstico e Atalhos do Windows")
        tools_layout = QHBoxLayout(tools_card)
        tools_layout.setContentsMargins(14, 12, 14, 12)
        tools_layout.setSpacing(10)

        btn_mmsys = QPushButton("Painel de Som (mmsys.cpl)")
        btn_mmsys.setObjectName("ToolbarButton")
        btn_mmsys.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_mmsys.clicked.connect(self._open_windows_sound_panel)
        tools_layout.addWidget(btn_mmsys)

        btn_privacy = QPushButton("Privacidade do Microfone")
        btn_privacy.setObjectName("ToolbarButton")
        btn_privacy.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_privacy.clicked.connect(self._open_windows_mic_privacy)
        tools_layout.addWidget(btn_privacy)

        layout.addWidget(tools_card)

        # --- Rodapé: Cancelar / Salvar ---
        footer = QHBoxLayout()
        footer.addStretch(1)

        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setObjectName("ToolbarButton")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        footer.addWidget(cancel_btn)

        save_btn = QPushButton("Salvar Alterações")
        save_btn.setObjectName("PrimaryButton")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self._on_save)
        footer.addWidget(save_btn)

        layout.addLayout(footer)

    def _create_section_frame(self, heading: str) -> QFrame:
        p = self.palette
        frame = QFrame(self)
        frame.setStyleSheet(
            f"""
            QFrame {{
                background-color: {p.bg_card};
                border: 1px solid {p.border_subtle};
                border-radius: 10px;
            }}
            """
        )
        return frame

    @staticmethod
    def _open_windows_sound_panel() -> None:
        try:
            subprocess.Popen(["control", "mmsys.cpl,,1"], shell=False)
        except Exception:
            pass

    @staticmethod
    def _open_windows_mic_privacy() -> None:
        try:
            os.startfile("ms-settings:privacy-microphone")  # type: ignore[attr-defined]
        except Exception:
            pass

    def _on_save(self) -> None:
        self.settings.start_minimized = self._chk_start_minimized.isChecked()
        self.settings.minimize_to_tray = self._chk_minimize_tray.isChecked()
        self.settings.show_notifications = self._chk_notifications.isChecked()
        self.settings.global_hotkey_enabled = self._chk_hotkey.isChecked()
        self.settings.global_hotkey_chord = (
            self._txt_chord.text().strip() or "Ctrl+Shift+M"
        )

        want_startup = self._chk_startup.isChecked()
        if want_startup != StartupManager.is_enabled():
            ok, msg = StartupManager.set_enabled(
                want_startup,
                start_minimized=self.settings.start_minimized,
            )
            if not ok:
                self.status_message = msg

        self.accept()

