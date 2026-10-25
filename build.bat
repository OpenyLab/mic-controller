@echo off
chcp 65001 >nul
setlocal

echo ============================================================
echo   Gerador de Executavel (.exe) - Gerenciador de Microfones
echo ============================================================
echo.

cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

echo [*] Usando interpretador: %PYTHON_EXE%
"%PYTHON_EXE%" build_exe.py --clean

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERRO] Falha durante a geracao do executavel.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo [OK] O arquivo executavel esta pronto em: dist\MicController.exe
if "%1"=="" pause
