import sys
import os

# Agregar venv al path
VENV = os.path.expanduser("~/whisper-ai/.venv/lib/python3.14/site-packages")
sys.path.insert(0, VENV)

# Cambiar al directorio del proyecto
os.chdir(os.path.expanduser("~/whisper-ai"))

# Importar y correr la app
exec(open(os.path.expanduser("~/whisper-ai/src/whisper_ai.py")).read())
