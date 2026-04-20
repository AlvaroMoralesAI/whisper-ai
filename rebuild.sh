#!/bin/bash
# rebuild.sh — rebuild alias mode + relanzar
set -e
cd "$HOME/whisper-ai"

echo "=== Deteniendo app ==="
pkill -f "whisper-ai.app" 2>/dev/null; sleep 1; echo "OK"

echo "=== Limpiando build anterior ==="
rm -rf build dist

echo "=== Rebuild alias mode ==="
./.venv/bin/python3 setup.py py2app -A 2>&1 | tail -20

echo "=== Copiando bundle ==="
cp -Rf dist/whisper-ai.app "$HOME/Desktop/"
xattr -cr "$HOME/Desktop/whisper-ai.app"
echo "Bundle copiado"

echo "=== Actualizando Info.plist con claves faltantes ==="
PLIST="$HOME/Desktop/whisper-ai.app/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Set :NSAccessibilityUsageDescription 'whisper-ai necesita acceso de Accesibilidad para detectar la tecla de activación y pegar texto.'" "$PLIST" 2>/dev/null \
  || /usr/libexec/PlistBuddy -c "Add :NSAccessibilityUsageDescription string 'whisper-ai necesita acceso de Accesibilidad para detectar la tecla de activación y pegar texto.'" "$PLIST"
/usr/libexec/PlistBuddy -c "Set :NSInputMonitoringUsageDescription 'whisper-ai necesita monitorear el teclado para detectar cuándo pulsas la tecla de dictado.'" "$PLIST" 2>/dev/null \
  || /usr/libexec/PlistBuddy -c "Add :NSInputMonitoringUsageDescription string 'whisper-ai necesita monitorear el teclado para detectar cuándo pulsas la tecla de dictado.'" "$PLIST"
echo "Plist actualizado"

echo "=== Re-grant TCC ==="
tccutil reset Accessibility com.alvaromorales.whisperai 2>/dev/null; echo "Accessibility reset"
tccutil reset ListenEvent com.alvaromorales.whisperai 2>/dev/null; echo "ListenEvent reset"

echo ""
echo "=== Lanzando app ==="
open "$HOME/Desktop/whisper-ai.app"
sleep 2
pgrep -lf whisper-ai && echo "✅ App corriendo" || echo "❌ App no inició"

echo ""
echo "⚠️  IMPORTANTE: Ve a System Settings → Privacy → Accessibility e Input Monitoring"
echo "    y activa whisper-ai si no está activado."
