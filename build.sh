#!/usr/bin/env bash
# Empaqueta whisper-ai como .app con PyInstaller.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt pyinstaller

rm -rf build dist

pyinstaller \
  --name whisper-ai \
  --windowed \
  --osx-bundle-identifier com.alvaromorales.whisperai \
  src/whisper_ai.py

echo "✓ App: dist/whisper-ai.app"
