@echo off
setlocal enabledelayedexpansion

set APP_NAME=Markdown Pretty Viewer
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Error: Python no esta instalado o no esta en el PATH.
    exit /b 1
)

if not exist .venv (
    echo Creando entorno virtual .venv...
    python -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

pyinstaller MarkdownPrettyViewer-Windows.spec --clean --noconfirm

echo.
echo App generada: dist\%APP_NAME%\%APP_NAME%.exe
echo Puedes abrir el .exe con doble clic.
