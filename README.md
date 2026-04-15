# whisper-ai

App de dictado por voz para macOS estilo Whisperflow. Doble-tap en una tecla, habla, suelta, y el texto se pega automáticamente en la app activa.

## Features

- 🎙 Doble-tap para grabar (Right Alt por defecto)
- 🧠 4 proveedores: **Groq** (gratis), OpenAI, Deepgram, AssemblyAI
- 🌍 Idiomas: es / en / fr / de / it / pt / auto
- 🔊 Feedback sonoro (Tink al empezar, Pop al terminar)
- 📋 Auto-paste en la app activa
- 🕐 Historial de las últimas 10 transcripciones
- 🍎 Icono en menu bar

## Requisitos

- macOS 11+
- Python 3.11+
- Permisos de **Accesibilidad** y **Micrófono** para Terminal/iTerm

## Instalación

```bash
git clone https://github.com/AlvaroMoralesAI/whisper-ai.git
cd whisper-ai
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python src/whisper_ai.py
```

Verás el icono 🎙 en la barra de menú.

## Configuración

1. Click en el icono → **Set API key…** y pega tu key del provider activo.
2. Elige provider desde **Change provider** (por defecto Groq).
3. Elige idioma y hotkey si quieres cambiarlos.

### Dónde obtener API keys

| Provider   | URL                            | Coste              |
|------------|--------------------------------|--------------------|
| Groq       | https://console.groq.com       | Gratis (generoso)  |
| OpenAI     | https://platform.openai.com    | De pago            |
| Deepgram   | https://console.deepgram.com   | Free tier          |
| AssemblyAI | https://app.assemblyai.com     | Free tier          |

## Uso

1. Doble-tap **Right Alt** (configurable).
2. Mantén la tecla pulsada mientras hablas.
3. Suelta → transcribe → auto-paste en la app activa.

## Config

`~/.whisper_ai.json` (permisos `0o600`). Contiene provider, keys, idioma, hotkey e historial.

## Licencia

MIT © 2026 Álvaro Morales
