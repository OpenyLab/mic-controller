"""Gerenciador de atalhos globais de teclado usando a API nativa Win32 (RegisterHotKey)."""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
import sys
from typing import Dict, Optional, Tuple

from PySide6.QtCore import QAbstractNativeEventFilter, QByteArray, QCoreApplication, QObject, Signal

logger = logging.getLogger(__name__)

WM_HOTKEY = 0x0312

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

VIRTUAL_KEYS: Dict[str, int] = {
    **{chr(c): c for c in range(ord("A"), ord("Z") + 1)},
    **{chr(c): c for c in range(ord("0"), ord("9") + 1)},
    **{f"F{i}": 0x6F + i for i in range(1, 13)},
    "SPACE": 0x20,
    "PAUSE": 0x13,
    "INSERT": 0x2D,
    "DELETE": 0x2E,
    "HOME": 0x24,
    "END": 0x23,
    "PGUP": 0x21,
    "PGDN": 0x22,
}


class _Win32HotkeyEventFilter(QAbstractNativeEventFilter):
    """Filtro nativo de mensagens do Windows para capturar eventos WM_HOTKEY."""

    def __init__(self, hotkey_id: int, callback) -> None:
        super().__init__()
        self._hotkey_id = hotkey_id
        self._callback = callback

    def nativeEventFilter(
        self,
        event_type: QByteArray | bytes,
        message: int,
    ) -> Tuple[bool, int]:
        try:
            evt_str = (
                bytes(event_type).decode("ascii", errors="ignore")
                if not isinstance(event_type, str)
                else event_type
            )
            if "windows_" in evt_str:
                msg = ctypes.wintypes.MSG.from_address(int(message))
                if msg.message == WM_HOTKEY and msg.wParam == self._hotkey_id:
                    self._callback()
                    return True, 0
        except Exception as exc:
            logger.debug("Erro ao processar evento nativo WM_HOTKEY: %s", exc)
        return False, 0


class GlobalHotkeyManager(QObject):
    """Registra e monitora atalhos globais de teclado no Windows."""

    activated = Signal()

    HOTKEY_ID = 0xA11C

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._registered = False
        self._current_chord = ""
        self._filter = _Win32HotkeyEventFilter(self.HOTKEY_ID, self._on_hotkey_triggered)
        app = QCoreApplication.instance()
        if app is not None:
            app.installNativeEventFilter(self._filter)

    def _on_hotkey_triggered(self) -> None:
        self.activated.emit()

    @staticmethod
    def parse_chord(chord: str) -> Optional[Tuple[int, int]]:
        """Converte uma string como 'Ctrl+Shift+M' em (modifiers, virtual_key)."""
        if not chord or not chord.strip():
            return None

        parts = [p.strip().upper() for p in chord.split("+") if p.strip()]
        if not parts:
            return None

        modifiers = MOD_NOREPEAT
        vk_code: Optional[int] = None

        for token in parts:
            if token in ("CTRL", "CONTROL"):
                modifiers |= MOD_CONTROL
            elif token == "SHIFT":
                modifiers |= MOD_SHIFT
            elif token == "ALT":
                modifiers |= MOD_ALT
            elif token in ("WIN", "META", "SUPER"):
                modifiers |= MOD_WIN
            elif token in VIRTUAL_KEYS:
                vk_code = VIRTUAL_KEYS[token]
            else:
                return None

        if vk_code is None:
            return None
        return modifiers, vk_code

    def register_hotkey(self, chord: str) -> Tuple[bool, str]:
        """Registra o atalho global no Windows."""
        self.unregister_hotkey()

        if sys.platform != "win32":
            return False, "Atalhos globais nativos suportados apenas no Windows."

        parsed = self.parse_chord(chord)
        if parsed is None:
            return (
                False,
                f"Combinação de teclas inválida: '{chord}'. Exemplo válido: Ctrl+Shift+M",
            )

        modifiers, vk_code = parsed
        try:
            ok = bool(
                ctypes.windll.user32.RegisterHotKey(
                    None,
                    self.HOTKEY_ID,
                    modifiers,
                    vk_code,
                )
            )
            if ok:
                self._registered = True
                self._current_chord = chord
                return True, f"Atalho global '{chord}' registrado com sucesso."
            else:
                return (
                    False,
                    f"Não foi possível registrar o atalho '{chord}' "
                    "(pode já estar em uso por outro aplicativo).",
                )
        except Exception as exc:
            return False, f"Erro ao registrar atalho global: {exc}"

    def unregister_hotkey(self) -> None:
        """Remove o registro do atalho global atual, se houver."""
        if self._registered and sys.platform == "win32":
            try:
                ctypes.windll.user32.UnregisterHotKey(None, self.HOTKEY_ID)
            except Exception:
                pass
        self._registered = False
        self._current_chord = ""

    @property
    def is_registered(self) -> bool:
        return self._registered

    @property
    def current_chord(self) -> str:
        return self._current_chord

