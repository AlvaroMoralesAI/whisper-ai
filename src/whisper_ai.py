"""whisper-ai — dictado por voz estilo Whisperflow para macOS.

Doble-tap en la tecla configurada → graba → suelta → transcribe → pega en la app activa.
"""

from __future__ import annotations

import io
import json
import os
import shlex
import subprocess
import sys
import threading
import time
import wave
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import numpy as np
import rumps
import sounddevice as sd
from pynput import keyboard


APP_NAME = "whisper-ai"
CONFIG_PATH = Path.home() / ".whisper_ai.json"
SAMPLE_RATE = 16000
CHANNELS = 1
DOUBLE_TAP_WINDOW = 0.4
MIN_DURATION = 0.3
MAX_HISTORY = 10

HOTKEY_MAP = {
    "right_alt": keyboard.Key.alt_r,
    "left_alt": keyboard.Key.alt_l,
    "ctrl": keyboard.Key.ctrl,
    "cmd": keyboard.Key.cmd,
}

LANGUAGES = {
    "auto": None,
    "es": "es",
    "en": "en",
    "fr": "fr",
    "de": "de",
    "it": "it",
    "pt": "pt",
}

PROVIDERS = ["groq", "openai", "deepgram", "assemblyai"]


# ---------- Config ----------

@dataclass
class Config:
    provider: str = "groq"
    api_keys: dict = field(default_factory=dict)
    language: str = "auto"
    hotkey: str = "right_alt"
    history: list = field(default_factory=list)

    @classmethod
    def load(cls) -> "Config":
        if not CONFIG_PATH.exists():
            c = cls()
            c.save()
            return c
        try:
            data = json.loads(CONFIG_PATH.read_text())
            return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        except (json.JSONDecodeError, TypeError):
            return cls()

    def save(self) -> None:
        CONFIG_PATH.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False))
        os.chmod(CONFIG_PATH, 0o600)


# ---------- Transcribers ----------

class Transcriber:
    name = "base"

    def __init__(self, api_key: str, language: Optional[str]):
        self.api_key = api_key
        self.language = language

    def transcribe(self, wav_bytes: bytes) -> str:
        raise NotImplementedError


class GroqTranscriber(Transcriber):
    name = "groq"

    def transcribe(self, wav_bytes: bytes) -> str:
        from groq import Groq
        client = Groq(api_key=self.api_key)
        kwargs = {"model": "whisper-large-v3", "file": ("audio.wav", wav_bytes)}
        if self.language:
            kwargs["language"] = self.language
        r = client.audio.transcriptions.create(**kwargs)
        return r.text.strip()


class OpenAITranscriber(Transcriber):
    name = "openai"

    def transcribe(self, wav_bytes: bytes) -> str:
        from openai import OpenAI
        client = OpenAI(api_key=self.api_key)
        kwargs = {"model": "whisper-1", "file": ("audio.wav", wav_bytes)}
        if self.language:
            kwargs["language"] = self.language
        r = client.audio.transcriptions.create(**kwargs)
        return r.text.strip()


class DeepgramTranscriber(Transcriber):
    name = "deepgram"

    def transcribe(self, wav_bytes: bytes) -> str:
        from deepgram import DeepgramClient, PrerecordedOptions
        client = DeepgramClient(self.api_key)
        opts = PrerecordedOptions(model="nova-2", smart_format=True,
                                  language=self.language or "multi")
        r = client.listen.rest.v("1").transcribe_file({"buffer": wav_bytes}, opts)
        return r.results.channels[0].alternatives[0].transcript.strip()


class AssemblyAITranscriber(Transcriber):
    name = "assemblyai"

    def transcribe(self, wav_bytes: bytes) -> str:
        import assemblyai as aai
        aai.settings.api_key = self.api_key
        transcriber = aai.Transcriber()
        cfg = aai.TranscriptionConfig(language_code=self.language) if self.language else None
        transcript = transcriber.transcribe(wav_bytes, config=cfg)
        return (transcript.text or "").strip()


TRANSCRIBERS = {
    "groq": GroqTranscriber,
    "openai": OpenAITranscriber,
    "deepgram": DeepgramTranscriber,
    "assemblyai": AssemblyAITranscriber,
}


# ---------- Audio ----------

class Recorder:
    def __init__(self):
        self.frames: list[np.ndarray] = []
        self.stream: Optional[sd.InputStream] = None
        self._lock = threading.Lock()

    def start(self) -> None:
        with self._lock:
            self.frames = []
            self.stream = sd.InputStream(
                samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="int16",
                callback=self._callback,
            )
            self.stream.start()

    def _callback(self, indata, frames, time_info, status):
        self.frames.append(indata.copy())

    def stop(self) -> Optional[bytes]:
        with self._lock:
            if self.stream is None:
                return None
            self.stream.stop()
            self.stream.close()
            self.stream = None
            if not self.frames:
                return None
            audio = np.concatenate(self.frames, axis=0)
            duration = len(audio) / SAMPLE_RATE
            if duration < MIN_DURATION:
                return None
            rms = float(np.sqrt(np.mean(audio.astype(np.float32) ** 2)))
            if rms < 2:
                return None
            buf = io.BytesIO()
            with wave.open(buf, "wb") as w:
                w.setnchannels(CHANNELS)
                w.setsampwidth(2)
                w.setframerate(SAMPLE_RATE)
                w.writeframes(audio.tobytes())
            return buf.getvalue()


# ---------- Output ----------

def copy_and_paste(text: str) -> None:
    subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=False)
    # Pequeña pausa para que el clipboard se actualice
    time.sleep(0.05)
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    script = 'tell application "System Events" to keystroke "v" using command down'
    subprocess.run(["osascript", "-e", script], check=False)
    _ = escaped  # reservado por si se quiere usar keystroke directo en el futuro


def play_sound(name: str) -> None:
    path = f"/System/Library/Sounds/{name}.aiff"
    subprocess.Popen(["afplay", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ---------- App ----------

class WhisperAIApp(rumps.App):
    def __init__(self):
        super().__init__(APP_NAME, title="🎙")
        self.config = Config.load()
        self.recorder = Recorder()
        self.recording = False
        self._last_tap = 0.0
        self._build_menu()
        self._start_listener()

    # ----- menu -----
    def _build_menu(self):
        self.menu.clear()
        self.menu = [
            rumps.MenuItem(f"Provider: {self.config.provider}", callback=None),
            self._provider_menu(),
            self._language_menu(),
            self._hotkey_menu(),
            None,
            self._history_menu(),
            None,
            rumps.MenuItem("Set API key…", callback=self.on_set_api_key),
            rumps.MenuItem("Open config file", callback=self.on_open_config),
        ]

    def _provider_menu(self):
        m = rumps.MenuItem("Change provider")
        for p in PROVIDERS:
            item = rumps.MenuItem(
                f"{'✓ ' if p == self.config.provider else '   '}{p}",
                callback=lambda s, p=p: self.on_pick_provider(p),
            )
            m.add(item)
        return m

    def _language_menu(self):
        m = rumps.MenuItem("Language")
        for code in LANGUAGES:
            item = rumps.MenuItem(
                f"{'✓ ' if code == self.config.language else '   '}{code}",
                callback=lambda s, c=code: self.on_pick_language(c),
            )
            m.add(item)
        return m

    def _hotkey_menu(self):
        m = rumps.MenuItem("Hotkey")
        for key in HOTKEY_MAP:
            item = rumps.MenuItem(
                f"{'✓ ' if key == self.config.hotkey else '   '}{key}",
                callback=lambda s, k=key: self.on_pick_hotkey(k),
            )
            m.add(item)
        return m

    def _history_menu(self):
        m = rumps.MenuItem("History")
        if not self.config.history:
            m.add(rumps.MenuItem("(empty)", callback=None))
        else:
            for i, text in enumerate(self.config.history):
                preview = (text[:50] + "…") if len(text) > 50 else text
                m.add(rumps.MenuItem(
                    f"{i+1}. {preview}",
                    callback=lambda s, t=text: self.on_pick_history(t),
                ))
        return m

    def on_pick_provider(self, p):
        self.config.provider = p
        self.config.save()
        self._build_menu()

    def on_pick_language(self, code):
        self.config.language = code
        self.config.save()
        self._build_menu()

    def on_pick_hotkey(self, key):
        self.config.hotkey = key
        self.config.save()
        self._build_menu()
        self._start_listener()

    def on_pick_history(self, text):
        subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=False)
        rumps.notification(APP_NAME, "Copied to clipboard", text[:80])

    def on_set_api_key(self, _):
        window = rumps.Window(
            message=f"API key for {self.config.provider}",
            title="whisper-ai",
            default_text=self.config.api_keys.get(self.config.provider, ""),
            ok="Save", cancel="Cancel", dimensions=(320, 24),
        )
        resp = window.run()
        if resp.clicked and resp.text.strip():
            self.config.api_keys[self.config.provider] = resp.text.strip()
            self.config.save()
            rumps.notification(APP_NAME, "Saved", f"Key for {self.config.provider}")

    def on_open_config(self, _):
        subprocess.run(["open", str(CONFIG_PATH)], check=False)

    # ----- listener -----
    def _start_listener(self):
        if hasattr(self, "_listener") and self._listener:
            self._listener.stop()
        target = HOTKEY_MAP[self.config.hotkey]
        self._target_key = target
        self._listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        self._listener.start()

    def _matches(self, key) -> bool:
        return key == self._target_key

    def _on_press(self, key):
        if not self._matches(key):
            return
        if self.recording:
            return
        now = time.time()
        if now - self._last_tap < DOUBLE_TAP_WINDOW:
            self._last_tap = 0.0
            self._start_recording()
        else:
            self._last_tap = now

    def _on_release(self, key):
        if not self._matches(key):
            return
        if self.recording:
            self._stop_and_transcribe()

    # ----- recording -----
    def _start_recording(self):
        self.recording = True
        self.title = "🔴"
        play_sound("Tink")
        try:
            self.recorder.start()
        except Exception as e:
            self.recording = False
            self.title = "🎙"
            rumps.notification(APP_NAME, "Mic error", str(e))

    def _stop_and_transcribe(self):
        self.title = "⏳"
        wav = self.recorder.stop()
        self.recording = False
        if not wav:
            self.title = "🎙"
            play_sound("Basso")
            return
        threading.Thread(target=self._transcribe_and_paste, args=(wav,), daemon=True).start()

    def _transcribe_and_paste(self, wav: bytes):
        try:
            provider = self.config.provider
            key = self.config.api_keys.get(provider)
            if not key:
                rumps.notification(APP_NAME, "No API key", f"Set one for {provider}")
                self.title = "🎙"
                play_sound("Basso")
                return
            lang = LANGUAGES.get(self.config.language)
            cls = TRANSCRIBERS[provider]
            text = cls(key, lang).transcribe(wav)
            if not text:
                play_sound("Basso")
                self.title = "🎙"
                return
            copy_and_paste(text)
            self.config.history.insert(0, text)
            self.config.history = self.config.history[:MAX_HISTORY]
            self.config.save()
            self._build_menu()
            play_sound("Pop")
        except Exception as e:
            rumps.notification(APP_NAME, "Transcription error", str(e)[:160])
            play_sound("Basso")
        finally:
            self.title = "🎙"


def main():
    WhisperAIApp().run()


if __name__ == "__main__":
    main()
