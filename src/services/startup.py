"""Gerenciador de inicialização automática com o Windows via Registro (HKCU)."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Tuple

logger = logging.getLogger(__name__)

RUN_REGISTRY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_REGISTRY_NAME = "MicControllerApp"


class StartupManager:
    """Controla o registro do aplicativo para iniciar automaticamente junto ao Windows."""

    @staticmethod
    def _build_launch_command(start_minimized: bool = True) -> str:
        """Constrói o comando de execução adequado para script Python ou executável congelado."""
        if getattr(sys, "frozen", False):
            exe_path = Path(sys.executable).resolve()
            cmd = f'"{exe_path}"'
        else:
            python_exe = Path(sys.executable).resolve()
            # Prefere pythonw.exe para não abrir console ao iniciar com o Windows
            pythonw = python_exe.with_name("pythonw.exe")
            interpreter = pythonw if pythonw.exists() else python_exe
            project_root = Path(__file__).resolve().parents[2]
            entry_script = project_root / "__main__.py"
            cmd = f'"{interpreter}" "{entry_script}"'

        if start_minimized:
            cmd += " --minimized"
        return cmd

    @classmethod
    def is_enabled(cls) -> bool:
        """Verifica se a inicialização automática está ativa no Registro do Windows."""
        if sys.platform != "win32":
            return False
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                RUN_REGISTRY_PATH,
                0,
                winreg.KEY_READ,
            ) as key:
                value, _ = winreg.QueryValueEx(key, APP_REGISTRY_NAME)
                return bool(value)
        except FileNotFoundError:
            return False
        except OSError as exc:
            logger.debug("Erro ao consultar chave de inicialização no Registro: %s", exc)
            return False

    @classmethod
    def set_enabled(
        cls,
        enabled: bool,
        start_minimized: bool = True,
    ) -> Tuple[bool, str]:
        """Ativa ou desativa a inicialização automática com o Windows."""
        if sys.platform != "win32":
            return False, "Inicialização automática disponível apenas no Windows."

        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                RUN_REGISTRY_PATH,
                0,
                winreg.KEY_SET_VALUE | winreg.KEY_READ,
            ) as key:
                if enabled:
                    command = cls._build_launch_command(start_minimized=start_minimized)
                    winreg.SetValueEx(
                        key,
                        APP_REGISTRY_NAME,
                        0,
                        winreg.REG_SZ,
                        command,
                    )
                    return True, "Inicialização automática com o Windows ativada."
                else:
                    try:
                        winreg.DeleteValue(key, APP_REGISTRY_NAME)
                    except FileNotFoundError:
                        pass
                    return True, "Inicialização automática com o Windows desativada."
        except OSError as exc:
            logger.error("Falha ao alterar Registro de inicialização: %s", exc)
            return (
                False,
                f"Não foi possível modificar o Registro do Windows: {exc}",
            )

