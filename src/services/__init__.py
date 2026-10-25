"""Serviços de integração com o sistema operacional e persistência de preferências."""

from .hotkeys import GlobalHotkeyManager
from .settings import AppSettings
from .startup import StartupManager

__all__ = [
    "AppSettings",
    "GlobalHotkeyManager",
    "StartupManager",
]

