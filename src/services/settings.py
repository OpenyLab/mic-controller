"""Gerenciamento persistente de configurações do aplicativo via QSettings."""

from __future__ import annotations

from PySide6.QtCore import QSettings


class AppSettings:
    """Encapsula as preferências do usuário salvas no Registro/INI do sistema."""

    ORGANIZATION = "OpenYLab"
    APPLICATION = "MicController"

    def __init__(self) -> None:
        self._store = QSettings(self.ORGANIZATION, self.APPLICATION)

    @property
    def dark_theme(self) -> bool:
        return str(self._store.value("ui/dark_theme", "true")).lower() == "true"

    @dark_theme.setter
    def dark_theme(self, value: bool) -> None:
        self._store.setValue("ui/dark_theme", "true" if value else "false")

    @property
    def show_inactive_devices(self) -> bool:
        return str(self._store.value("audio/show_inactive", "false")).lower() == "true"

    @show_inactive_devices.setter
    def show_inactive_devices(self, value: bool) -> None:
        self._store.setValue("audio/show_inactive", "true" if value else "false")

    @property
    def minimize_to_tray(self) -> bool:
        return str(self._store.value("system/minimize_to_tray", "true")).lower() == "true"

    @minimize_to_tray.setter
    def minimize_to_tray(self, value: bool) -> None:
        self._store.setValue("system/minimize_to_tray", "true" if value else "false")

    @property
    def start_minimized(self) -> bool:
        return str(self._store.value("system/start_minimized", "false")).lower() == "true"

    @start_minimized.setter
    def start_minimized(self, value: bool) -> None:
        self._store.setValue("system/start_minimized", "true" if value else "false")

    @property
    def show_notifications(self) -> bool:
        return str(self._store.value("ui/show_notifications", "true")).lower() == "true"

    @show_notifications.setter
    def show_notifications(self, value: bool) -> None:
        self._store.setValue("ui/show_notifications", "true" if value else "false")

    @property
    def global_hotkey_enabled(self) -> bool:
        return str(self._store.value("hotkey/enabled", "true")).lower() == "true"

    @global_hotkey_enabled.setter
    def global_hotkey_enabled(self, value: bool) -> None:
        self._store.setValue("hotkey/enabled", "true" if value else "false")

    @property
    def global_hotkey_chord(self) -> str:
        return str(self._store.value("hotkey/chord", "Ctrl+Shift+M"))

    @global_hotkey_chord.setter
    def global_hotkey_chord(self, value: str) -> None:
        self._store.setValue("hotkey/chord", value.strip() or "Ctrl+Shift+M")

