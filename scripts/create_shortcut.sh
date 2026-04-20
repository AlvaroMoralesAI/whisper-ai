#!/usr/bin/env bash
# Crea un acceso directo .app en el Escritorio con icono personalizado.
# Uso: bash create_shortcut.sh [ruta_al_icono.png]
set -euo pipefail

APP_NAME="whisper-ai"
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DESKTOP="$HOME/Desktop"
APP_PATH="$DESKTOP/${APP_NAME}.app"
ICON_SRC="${1:-$SCRIPT_DIR/assets/icon.png}"

# ---- Crear bundle .app ----
mkdir -p "$APP_PATH/Contents/MacOS"
mkdir -p "$APP_PATH/Contents/Resources"

# Script lanzador
cat > "$APP_PATH/Contents/MacOS/${APP_NAME}" << 'LAUNCHER'
#!/usr/bin/env bash
APP_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
PROJECT="$(dirname "$(dirname "$APP_DIR")")"
VENV="$PROJECT/.venv/bin/activate"
SCRIPT="$PROJECT/src/whisper_ai.py"

if [ ! -f "$VENV" ]; then
  osascript -e 'display alert "whisper-ai" message "Primero ejecuta: pip install -r requirements.txt en el directorio del proyecto."'
  exit 1
fi
source "$VENV"
exec python "$SCRIPT"
LAUNCHER
chmod +x "$APP_PATH/Contents/MacOS/${APP_NAME}"

# Info.plist
cat > "$APP_PATH/Contents/Info.plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>         <string>${APP_NAME}</string>
  <key>CFBundleIdentifier</key>   <string>com.alvaromorales.whisperai</string>
  <key>CFBundleVersion</key>      <string>0.1.0</string>
  <key>CFBundleIconFile</key>     <string>AppIcon</string>
  <key>LSUIElement</key>          <true/>
  <key>NSMicrophoneUsageDescription</key>
    <string>whisper-ai necesita acceso al micrófono para grabar voz.</string>
  <key>NSAppleEventsUsageDescription</key>
    <string>whisper-ai usa AppleScript para pegar el texto transcrito.</string>
</dict>
</plist>
PLIST

# ---- Convertir PNG → ICNS ----
if [ -f "$ICON_SRC" ]; then
  ICONSET=$(mktemp -d /tmp/AppIcon.XXXXXX.iconset)
  for SIZE in 16 32 64 128 256 512; do
    sips -z $SIZE $SIZE "$ICON_SRC" --out "$ICONSET/icon_${SIZE}x${SIZE}.png" &>/dev/null
    DOUBLE=$((SIZE * 2))
    sips -z $DOUBLE $DOUBLE "$ICON_SRC" --out "$ICONSET/icon_${SIZE}x${SIZE}@2x.png" &>/dev/null
  done
  iconutil -c icns "$ICONSET" -o "$APP_PATH/Contents/Resources/AppIcon.icns"
  rm -rf "$ICONSET"
  echo "✓ Icono aplicado"
else
  echo "⚠️  Icono no encontrado en: $ICON_SRC"
  echo "   Pasa la ruta como argumento: bash create_shortcut.sh /ruta/icono.png"
fi

echo "✓ Acceso directo creado: $APP_PATH"
touch "$APP_PATH"  # refresca Finder
