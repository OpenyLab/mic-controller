"""Ponto de entrada principal do aplicativo Gerenciador de Microfones."""

from __future__ import annotations

import argparse
import ctypes
import logging
import sys
import warnings

# Suprime aviso de IntFlag do comtypes em versões recentes do Python (3.14+/3.15+)
warnings.filterwarnings(
    "ignore",
    message=r".*You are running 'comtypes' on Python.*",
    category=FutureWarning,
)

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from src import __app_display_name__, __app_name__, __version__
from src.audio.controller import AudioController
from src.services.settings import AppSettings
from src.ui.main_window import MainWindow


def configure_logging() -> None:
    """Configura o sistema de logs da aplicação."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def set_windows_app_id() -> None:
    """Define o AppUserModelID no Windows para agrupar ícone na barra de tarefas."""
    if sys.platform == "win32":
        try:
            app_id = f"OpenYLab.{__app_name__}.Desktop.{__version__}"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        except Exception:
            pass


def run_cli_list(include_inactive: bool = True) -> int:
    """Lista os microfones detectados no terminal (modo diagnóstico)."""
    controller = AudioController(include_inactive=include_inactive)
    devices = controller.list_microphones(include_inactive=include_inactive)
    print(f"=== {__app_display_name__} v{__version__} ===")
    print(f"Total de dispositivos detectados: {len(devices)}\n")
    for idx, dev in enumerate(devices, start=1):
        flags = []
        if dev.is_default_console:
            flags.append("PADRÃO DO SISTEMA")
        if dev.is_default_communications:
            flags.append("PADRÃO COMUNICAÇÃO")
        flag_str = f" [{' | '.join(flags)}]" if flags else ""
        state_str = (
            "ATIVO"
            if dev.is_enabled
            else ("DESATIVADO (MUDO)" if dev.is_available else dev.hardware_state.label_pt)
        )
        print(
            f"{idx}. {dev.display_title} ({dev.display_subtitle}){flag_str}\n"
            f"   Estado: {state_str} | Volume: {dev.volume_percent}% "
            f"| Ganho: {dev.volume_db if dev.volume_db is not None else 'N/A'} dB"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    """Inicializa e executa a aplicação desktop."""
    parser = argparse.ArgumentParser(
        prog=__app_name__,
        description="Gerenciador de Microfones para Windows 10 e Windows 11",
    )
    parser.add_argument(
        "--minimized",
        action="store_true",
        help="Inicia o aplicativo minimizado na bandeja do sistema",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Lista os dispositivos de microfone detectados no console e encerra",
    )
    args = parser.parse_args(argv)

    configure_logging()
    set_windows_app_id()

    if args.list:
        return run_cli_list(include_inactive=True)

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    app.setApplicationDisplayName(__app_display_name__)
    app.setApplicationVersion(__version__)
    app.setQuitOnLastWindowClosed(False)

    settings = AppSettings()
    start_min = bool(args.minimized or settings.start_minimized)

    window = MainWindow(start_minimized=start_min)
    _ = window  # Mantém referência viva durante o loop de eventos

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

