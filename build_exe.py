"""Script automatizado de build para empacotar o Gerenciador de Microfones em .exe.

Uso:
    python build_exe.py
    python build_exe.py --clean
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
ASSETS_DIR = PROJECT_ROOT / "assets"
ICON_PATH = ASSETS_DIR / "app_icon.ico"
SPEC_PATH = PROJECT_ROOT / "MicController.spec"
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"


def generate_app_icon() -> Path:
    """Gera o arquivo de ícone (.ico) em alta resolução para o executável Windows."""
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    from PySide6.QtGui import QGuiApplication

    from src.ui.icons import create_mic_pixmap

    app = QGuiApplication.instance() or QGuiApplication([])
    pixmap = create_mic_pixmap(
        size=256,
        active=True,
        available=True,
        fg_color="#FFFFFF",
        bg_color="#2563EB",
    )
    saved = pixmap.save(str(ICON_PATH), "ICO")
    if not saved or not ICON_PATH.exists():
        raise RuntimeError(f"Falha ao salvar o ícone do executável em {ICON_PATH}")

    _ = app
    print(f"[1/3] Ícone do aplicativo gerado em: {ICON_PATH}")
    return ICON_PATH


def ensure_pyinstaller_installed() -> None:
    """Verifica se o PyInstaller está instalado no ambiente atual."""
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("[!] PyInstaller não encontrado. Instalando automaticamente...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "pyinstaller>=6.0.0"]
        )


def build_executable(clean: bool = False) -> Path:
    """Executa o PyInstaller utilizando o arquivo MicController.spec."""
    if clean:
        for folder in (BUILD_DIR, DIST_DIR):
            if folder.exists():
                print(f"[*] Limpando diretório antigo: {folder}")
                shutil.rmtree(folder, ignore_errors=True)

    ensure_pyinstaller_installed()
    generate_app_icon()

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        str(SPEC_PATH),
    ]
    print(f"[2/3] Empacotando aplicativo com PyInstaller...")
    subprocess.check_call(cmd, cwd=str(PROJECT_ROOT))

    exe_path = DIST_DIR / "MicController.exe"
    if not exe_path.exists():
        raise FileNotFoundError(
            f"O executável esperado não foi encontrado em {exe_path}"
        )

    size_mb = exe_path.stat().st_size / (1024 * 1024)
    print("\n" + "=" * 60)
    print(f"[3/3] BUILD CONCLUÍDO COM SUCESSO!")
    print(f"Executável gerado: {exe_path}")
    print(f"Tamanho final:     {size_mb:.2f} MB")
    print("=" * 60)
    return exe_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gera o executável standalone MicController.exe para Windows."
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove as pastas build/ e dist/ antes de iniciar o empacotamento",
    )
    args = parser.parse_args()

    try:
        build_executable(clean=args.clean)
        return 0
    except Exception as exc:
        print(f"\n[ERRO NO BUILD] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
