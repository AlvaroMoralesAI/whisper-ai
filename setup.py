"""py2app setup para whisper-ai — bundle nativo macOS."""
from setuptools import setup

import os
SOUNDDEVICE_DATA = os.path.join(
    os.path.dirname(__file__), ".venv/lib/python3.14/site-packages/_sounddevice_data"
)

APP = ["src/whisper_ai.py"]
DATA_FILES = [("_sounddevice_data/portaudio-binaries",
               [os.path.join(SOUNDDEVICE_DATA, "portaudio-binaries/libportaudio.dylib")])]
OPTIONS = {
    "argv_emulation": False,
    "iconfile": "assets/AppIcon.icns",
    "plist": {
        "CFBundleName": "whisper-ai",
        "CFBundleDisplayName": "whisper-ai",
        "CFBundleIdentifier": "com.alvaromorales.whisperai",
        "CFBundleVersion": "0.1.0",
        "CFBundleShortVersionString": "0.1.0",
        "LSUIElement": True,
        "NSHighResolutionCapable": True,
        "NSMicrophoneUsageDescription":
            "whisper-ai necesita acceso al micrófono para grabar y transcribir tu voz.",
        "NSAppleEventsUsageDescription":
            "whisper-ai necesita enviar eventos para pegar el texto transcrito.",
        "NSAccessibilityUsageDescription":
            "whisper-ai necesita acceso de Accesibilidad para detectar la tecla de activación y pegar texto.",
        "NSInputMonitoringUsageDescription":
            "whisper-ai necesita monitorear el teclado para detectar cuándo pulsas la tecla de dictado.",
    },
    "packages": ["rumps", "pynput", "numpy", "groq", "openai"],
    "frameworks": [os.path.join(SOUNDDEVICE_DATA, "portaudio-binaries/libportaudio.dylib")],
    "includes": ["io", "wave", "json", "subprocess", "threading", "dataclasses"],
    "excludes": ["tkinter", "PyQt5", "PyQt6", "PySide2", "PySide6"],
}

setup(
    app=APP,
    name="whisper-ai",
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
