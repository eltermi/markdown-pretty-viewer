#!/usr/bin/env bash
set -euo pipefail

APP_NAME="Markdown Pretty Viewer"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 no está instalado o no está en el PATH."
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "Creando entorno virtual .venv..."
  python3 -m venv .venv
fi

source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

rm -rf build dist
pyinstaller MarkdownPrettyViewer-macOS.spec --clean --noconfirm

echo ""
echo "App generada: dist/${APP_NAME}.app"
echo "Puedes abrirla con doble clic desde Finder."
