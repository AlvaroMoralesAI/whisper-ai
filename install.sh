#!/bin/bash
set -e

echo "🚀 Iniciando instalación de Whisper AI..."

# Revisa si estamos en el directorio correcto
if [ ! -f "setup.py" ]; then
    echo "❌ Error: Ejecuta este script desde la carpeta del proyecto whisper-ai."
    exit 1
fi

echo "📦 Creando entorno virtual e instalando dependencias..."
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt

echo "🏗 Compilando la app nativa para macOS..."
# Construye la app en modo desarrollo local usando alias mode (-A)
python3 setup.py py2app -A

echo "📂 Copiando Whisper AI al Escritorio..."
rm -rf ~/Desktop/whisper-ai.app
cp -R dist/whisper-ai.app ~/Desktop/

echo "🔓 Configurando permisos de Gatekeeper..."
xattr -cr ~/Desktop/whisper-ai.app

echo "♻️ Reseteando permisos locales de Accesibilidad..."
tccutil reset Accessibility com.alvaromorales.whisperai || true
tccutil reset ListenEvent com.alvaromorales.whisperai || true

echo "==============================================="
echo "✅ Instalación completada con éxito."
echo "==============================================="
echo "👉 Abre la app desde el escritorio: ~/Desktop/whisper-ai.app"
echo "👉 IMPORTANTE: Requerirá permisos de Accesibilidad y Control de Teclado."
echo "👉 Configura tu API Key (Groq) desde el icono de la F en la barra de menú arriba."
