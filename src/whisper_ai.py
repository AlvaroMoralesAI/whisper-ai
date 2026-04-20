"""whisper-ai — dictado por voz estilo Wispr Flow para macOS."""

from __future__ import annotations

import io
import json
import math
import os
import random
import subprocess
import sys

# py2app's __boot__ sets SSL_CERT_FILE to a fake path; override with certifi's bundle
try:
    import certifi
    _ca = certifi.where()
    if os.path.exists(_ca):
        os.environ["SSL_CERT_FILE"] = _ca
        os.environ["REQUESTS_CA_BUNDLE"] = _ca
        os.environ.pop("SSL_CERT_DIR", None)
except ImportError:
    pass
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
MENUBAR_ICON_CACHE = Path.home() / ".whisper_ai_menubar.png"
SAMPLE_RATE = 16000
CHANNELS = 1
MIN_DURATION = 0.3
MAX_HISTORY = 10

# caps_lock y fn no funcionan con pynput en macOS → se migran a alt_r
LEGACY_HOTKEY_MAP = {
    "left_alt":  "Key.alt_l",
    "right_alt": "Key.alt_r",
    "alt_any":   "Key.alt_r",
    "ctrl":      "Key.ctrl_l",
    "cmd":       "Key.cmd_l",
    "shift":     "Key.shift_l",
    "caps_lock": "Key.alt_r",
    "fn":        "Key.alt_r",
}

LANGUAGES = {
    "auto": None, "es": "es", "en": "en",
    "fr": "fr", "de": "de", "it": "it", "pt": "pt",
}

PROVIDERS = ["groq", "openai", "deepgram", "assemblyai"]


# ---------- Key serialization ----------

def serialize_key(key) -> str:
    try:
        return f"Key.{key.name}"
    except AttributeError:
        if getattr(key, "char", None):
            return f"char.{key.char}"
        return f"vk.{key.vk}"


def deserialize_key(key_str: str):
    if key_str.startswith("Key."):
        name = key_str[4:]
        try:
            return getattr(keyboard.Key, name)
        except AttributeError:
            return None
    if key_str.startswith("char."):
        return keyboard.KeyCode.from_char(key_str[5:])
    if key_str.startswith("vk."):
        try:
            return keyboard.KeyCode.from_vk(int(key_str[3:]))
        except (ValueError, TypeError):
            return None
    return None


def key_display_name(key_str: str) -> str:
    """Human-readable name for the serialized key."""
    names = {
        "Key.alt_r": "⌥ Option derecho",
        "Key.alt_l": "⌥ Option izquierdo",
        "Key.ctrl_l": "⌃ Control izquierdo",
        "Key.ctrl_r": "⌃ Control derecho",
        "Key.cmd_l": "⌘ Cmd izquierdo",
        "Key.cmd_r": "⌘ Cmd derecho",
        "Key.shift_l": "⇧ Shift izquierdo",
        "Key.shift_r": "⇧ Shift derecho",
        "Key.f1": "F1", "Key.f2": "F2", "Key.f3": "F3", "Key.f4": "F4",
        "Key.f5": "F5", "Key.f6": "F6", "Key.f7": "F7", "Key.f8": "F8",
    }
    if key_str in names:
        return names[key_str]
    if key_str.startswith("char."):
        return key_str[5:].upper()
    return key_str


# ---------- Config ----------

@dataclass
class Config:
    provider: str = "groq"
    api_keys: dict = field(default_factory=dict)
    language: str = "auto"
    hotkey: str = "Key.alt_r"
    recording_mode: str = "hold"  # "hold" | "toggle"
    ai_formatting: bool = True
    history: list = field(default_factory=list)

    @classmethod
    def load(cls) -> "Config":
        if not CONFIG_PATH.exists():
            c = cls()
            c.save()
            return c
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            c = cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
            # Migrate legacy hotkey format
            if c.hotkey in LEGACY_HOTKEY_MAP:
                c.hotkey = LEGACY_HOTKEY_MAP[c.hotkey]
                c.save()
            return c
        except (json.JSONDecodeError, TypeError):
            return cls()

    def save(self) -> None:
        CONFIG_PATH.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")
        os.chmod(CONFIG_PATH, 0o600)


# ---------- Transcribers ----------

class Transcriber:
    def __init__(self, api_key: str, language: Optional[str]):
        self.api_key = api_key
        self.language = language

    def transcribe(self, wav_bytes: bytes) -> str:
        raise NotImplementedError


class GroqTranscriber(Transcriber):
    def transcribe(self, wav_bytes: bytes) -> str:
        from groq import Groq
        client = Groq(api_key=self.api_key)
        kwargs: dict = {"model": "whisper-large-v3", "file": ("audio.wav", wav_bytes)}
        if self.language:
            kwargs["language"] = self.language
        return client.audio.transcriptions.create(**kwargs).text.strip()


class OpenAITranscriber(Transcriber):
    def transcribe(self, wav_bytes: bytes) -> str:
        from openai import OpenAI
        client = OpenAI(api_key=self.api_key)
        kwargs: dict = {"model": "whisper-1", "file": ("audio.wav", wav_bytes)}
        if self.language:
            kwargs["language"] = self.language
        return client.audio.transcriptions.create(**kwargs).text.strip()


class DeepgramTranscriber(Transcriber):
    def transcribe(self, wav_bytes: bytes) -> str:
        from deepgram import DeepgramClient, PrerecordedOptions
        client = DeepgramClient(self.api_key)
        opts = PrerecordedOptions(model="nova-2", smart_format=True,
                                  language=self.language or "multi")
        r = client.listen.rest.v("1").transcribe_file({"buffer": wav_bytes}, opts)
        return r.results.channels[0].alternatives[0].transcript.strip()


class AssemblyAITranscriber(Transcriber):
    def transcribe(self, wav_bytes: bytes) -> str:
        import assemblyai as aai
        aai.settings.api_key = self.api_key
        cfg = aai.TranscriptionConfig(language_code=self.language) if self.language else None
        return (aai.Transcriber().transcribe(wav_bytes, config=cfg).text or "").strip()


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

    def _callback(self, indata, _frames, _time_info, _status):
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
            if len(audio) / SAMPLE_RATE < MIN_DURATION:
                return None
            if float(np.sqrt(np.mean(audio.astype(np.float32) ** 2))) < 2:
                return None
            buf = io.BytesIO()
            with wave.open(buf, "wb") as w:
                w.setnchannels(CHANNELS)
                w.setsampwidth(2)
                w.setframerate(SAMPLE_RATE)
                w.writeframes(audio.tobytes())
            return buf.getvalue()

    def get_current_volume(self) -> float:
        with self._lock:
            if not self.frames:
                return 0.0
            last_frame = self.frames[-1]
            if len(last_frame) == 0:
                return 0.0
            # RMS amplitude calc, mapped roughly between 0.0 and 1.0
            rms = np.sqrt(np.mean(last_frame.astype(np.float32) ** 2))
            vol = min(rms / 1000.0, 1.0)
            return float(vol)


# ---------- Output ----------

def copy_and_paste(text: str) -> None:
    # Use NSPasteboard directly — handles Unicode natively (no Mac Roman encoding issues)
    try:
        from AppKit import NSPasteboard, NSPasteboardTypeString
        pb = NSPasteboard.generalPasteboard()
        pb.clearContents()
        pb.setString_forType_(text, NSPasteboardTypeString)
    except Exception:
        # Fallback: pbcopy with explicit UTF-8
        subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=False)
    time.sleep(0.15)
    try:
        from Quartz import (
            CGEventCreateKeyboardEvent, CGEventPost, CGEventSetFlags,
            kCGHIDEventTap, kCGEventFlagMaskCommand,
        )
        V_KEYCODE = 9
        down = CGEventCreateKeyboardEvent(None, V_KEYCODE, True)
        CGEventSetFlags(down, kCGEventFlagMaskCommand)
        up = CGEventCreateKeyboardEvent(None, V_KEYCODE, False)
        CGEventSetFlags(up, kCGEventFlagMaskCommand)
        CGEventPost(kCGHIDEventTap, down)
        time.sleep(0.02)
        CGEventPost(kCGHIDEventTap, up)
    except Exception as e:
        print(f"[paste] Quartz fallo, fallback pynput: {e}")
        ctrl = keyboard.Controller()
        ctrl.press(keyboard.Key.cmd)
        time.sleep(0.02)
        ctrl.press('v')
        time.sleep(0.02)
        ctrl.release('v')
        time.sleep(0.02)
        ctrl.release(keyboard.Key.cmd)


def play_sound(name: str) -> None:
    subprocess.Popen(
        ["afplay", f"/System/Library/Sounds/{name}.aiff"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


# ---------- Overlay Visual ----------

def _hex_to_nscolor(hex_str: str, alpha: float = 1.0):
    from AppKit import NSColor
    hex_str = hex_str.lstrip('#')
    r = int(hex_str[0:2], 16) / 255.0
    g = int(hex_str[2:4], 16) / 255.0
    b = int(hex_str[4:6], 16) / 255.0
    return NSColor.colorWithRed_green_blue_alpha_(r, g, b, alpha)


class OverlayView:
    def __init__(self, recorder: Recorder):
        from AppKit import (
            NSWindow, NSBackingStoreBuffered, NSColor, NSRect, NSPoint, NSSize,
            NSBorderlessWindowMask, NSFloatingWindowLevel, NSVisualEffectView,
            NSVisualEffectMaterialDark, NSVisualEffectBlendingModeBehindWindow,
            NSView, NSBezierPath, NSTimer, NSRunLoop, NSDefaultRunLoopMode,
            NSScreen
        )
        import objc
        self.recorder = recorder
        self.bars = [0.1] * 12
        
        # NSView class for drawing
        class RecordingVisualizerView(NSView):
            parent = None
            def drawRect_(self, dirtyRect):
                from AppKit import NSGradient, NSShadow, NSGraphicsContext
                if not self.parent: return
                NSColor.clearColor().set()
                NSBezierPath.fillRect_(dirtyRect)
                
                bounds = self.bounds()
                
                # Dark glossy background base
                base_path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                    bounds, bounds.size.height / 2, bounds.size.height / 2
                )
                # Pure black but translucent to let dark glass shine
                _hex_to_nscolor("000000", 0.6).setFill()
                base_path.fill()
                
                # Draw a glassy highlight gradient across the very top 
                glass_gradient = NSGradient.alloc().initWithStartingColor_endingColor_(
                    _hex_to_nscolor("ffffff", 0.15),
                    _hex_to_nscolor("ffffff", 0.0)
                )
                highlight_rect = NSRect(NSPoint(0, bounds.size.height / 2), NSSize(bounds.size.width, bounds.size.height / 2))
                glass_gradient.drawInRect_angle_(highlight_rect, -90.0)

                # Outer border stroke (Sharp glass rim)
                _hex_to_nscolor("ffffff", 0.20).setStroke()
                base_path.setLineWidth_(1.0)
                base_path.stroke()
                
                # Setup glow shadow for the purple bars (Intense Neon effect)
                context = NSGraphicsContext.currentContext()
                context.saveGraphicsState()
                
                glow = NSShadow.alloc().init()
                glow.setShadowColor_(_hex_to_nscolor("ac3aff", 1.0)) # Extreme purple neon glow
                glow.setShadowBlurRadius_(10.0) # Huge blur for neon diffusion
                glow.setShadowOffset_(NSSize(0, 0))
                glow.set()
                
                # Draw bars
                bar_width = 4
                spacing = 4
                total_width = (bar_width * 12) + (spacing * 11)
                
                start_x = (bounds.size.width - total_width) / 2
                center_y = bounds.size.height / 2
                
                # Lighter purple to pure white core gradient (Neon tube)
                bar_grad = NSGradient.alloc().initWithStartingColor_endingColor_(
                    _hex_to_nscolor("922efa", 1.0),
                    _hex_to_nscolor("e6ccff", 1.0)
                )
                
                for i, amp in enumerate(self.parent.bars):
                    height = max(4.0, amp * 20.0)
                    rect = NSRect(
                        NSPoint(start_x + i * (bar_width + spacing), center_y - height / 2),
                        NSSize(bar_width, height)
                    )
                    path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(rect, 2, 2)
                    
                    bar_grad.drawInBezierPath_angle_(path, 90.0)
                
                context.restoreGraphicsState()
        
        self.VisualizerClass = RecordingVisualizerView

        # Setup window
        screen_frame = NSScreen.mainScreen().frame()
        width, height = 130, 44
        x = (screen_frame.size.width - width) / 2
        y = 120 # Bottom padding
        
        frame = NSRect(NSPoint(x, y), NSSize(width, height))
        self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            frame, NSBorderlessWindowMask, NSBackingStoreBuffered, False
        )
        self.window.setLevel_(NSFloatingWindowLevel)
        self.window.setOpaque_(False)
        self.window.setBackgroundColor_(NSColor.clearColor())
        self.window.setHasShadow_(True)
        self.window.setIgnoresMouseEvents_(True)
        
        # Frosted glass background
        from AppKit import NSVisualEffectMaterialDark
        self.effect_view = NSVisualEffectView.alloc().initWithFrame_(frame)
        self.effect_view.setMaterial_(NSVisualEffectMaterialDark)
        self.effect_view.setBlendingMode_(NSVisualEffectBlendingModeBehindWindow)
        self.effect_view.setState_(1) # Active
        self.effect_view.setWantsLayer_(True)
        self.effect_view.layer().setCornerRadius_(height / 2)
        self.effect_view.layer().setMasksToBounds_(True)
        
        # Audio visualizer view
        self.viz_view = self.VisualizerClass.alloc().initWithFrame_(NSRect(NSPoint(0,0), NSSize(width, height)))
        self.viz_view.parent = self
        self.effect_view.addSubview_(self.viz_view)
        self.window.setContentView_(self.effect_view)
        
        self.timer = None

    def _update_anim(self, _timer):
        vol = self.recorder.get_current_volume()
        # Smooth drop off (60fps)
        for i in range(12):
            target = min(1.0, max(0.1, vol * random.uniform(0.6, 1.4)))
            self.bars[i] = self.bars[i] * 0.82 + target * 0.18
        self.viz_view.setNeedsDisplay_(True)

    def show(self):
        from AppKit import NSTimer, NSRunLoop, NSDefaultRunLoopMode
        self.window.makeKeyAndOrderFront_(None)
        def block(t):
            self._update_anim(t)
        self.timer = NSTimer.scheduledTimerWithTimeInterval_repeats_block_(
            0.016, True, block
        )
        NSRunLoop.mainRunLoop().addTimer_forMode_(self.timer, NSDefaultRunLoopMode)
        
    def hide(self):
        if self.timer:
            self.timer.invalidate()
            self.timer = None
        self.window.orderOut_(None)


# ---------- Icon ----------

def _get_menubar_icon() -> Optional[str]:
    if MENUBAR_ICON_CACHE.exists():
        return str(MENUBAR_ICON_CACHE)
    # Buscar AppIcon.icns relativo al source o al bundle
    candidates = [
        Path(__file__).parent.parent / "assets" / "AppIcon.icns",
        Path(sys.executable).parent.parent / "Resources" / "AppIcon.icns",
    ]
    for icns in candidates:
        if icns.exists():
            result = subprocess.run(
                ["sips", "-s", "format", "png",
                 "--resampleHeightWidth", "36", "36",
                 str(icns), "--out", str(MENUBAR_ICON_CACHE)],
                capture_output=True,
            )
            if result.returncode == 0 and MENUBAR_ICON_CACHE.exists():
                return str(MENUBAR_ICON_CACHE)
    return None


# ---------- App ----------

class WhisperAIApp(rumps.App):
    def __init__(self):
        icon_path = _get_menubar_icon()
        super().__init__(APP_NAME, icon=icon_path, title=None, quit_button=None)
        self.config = Config.load()
        self.recorder = Recorder()
        self.overlay = None
        self.recording = False
        self._listener: Optional[keyboard.Listener] = None
        self._capture_mode = False
        self._capture_lock = threading.Lock()
        self._build_menu()
        
        # Init overlay in main thread after app started
        @rumps.timer(1)
        def init_overlay(_):
            if not self.overlay:
                try:
                    self.overlay = OverlayView(self.recorder)
                except Exception as e:
                    print(f"Failed to init overlay: {e}", file=sys.stderr)
        
        threading.Thread(target=self._start_listener, daemon=True).start()

    # ----- menu -----

    def _build_menu(self):
        hotkey_label = key_display_name(self.config.hotkey)
        mode_label = "🔁 Modo: Toggle" if self.config.recording_mode == "toggle" else "⏱  Modo: Mantener pulsado"
        ai_label = "✨ Limpieza IA: ON" if self.config.ai_formatting else "✨ Limpieza IA: OFF"
        self.menu.clear()
        self.menu = [
            rumps.MenuItem(f"Provider: {self.config.provider}", callback=None),
            self._provider_menu(),
            self._language_menu(),
            None,
            rumps.MenuItem(f"Hotkey: {hotkey_label}", callback=None),
            rumps.MenuItem("⌨  Asignar tecla…", callback=self.on_capture_hotkey),
            rumps.MenuItem(mode_label, callback=self.on_toggle_mode),
            rumps.MenuItem(ai_label, callback=self.on_toggle_ai_formatting),
            None,
            self._history_menu(),
            None,
            rumps.MenuItem("Set API key…", callback=self.on_set_api_key),
            rumps.MenuItem("Open config file", callback=self.on_open_config),
            None,
            rumps.MenuItem("Quit", callback=self.on_quit),
        ]

    def _provider_menu(self):
        m = rumps.MenuItem("Cambiar provider")
        for p in PROVIDERS:
            m.add(rumps.MenuItem(
                f"{'✓ ' if p == self.config.provider else '   '}{p}",
                callback=lambda s, p=p: self._set_provider(p),
            ))
        return m

    def _language_menu(self):
        m = rumps.MenuItem("Idioma")
        for code in LANGUAGES:
            m.add(rumps.MenuItem(
                f"{'✓ ' if code == self.config.language else '   '}{code}",
                callback=lambda s, c=code: self._set_language(c),
            ))
        return m

    def _history_menu(self):
        m = rumps.MenuItem("Historial")
        if not self.config.history:
            m.add(rumps.MenuItem("(vacío)", callback=None))
        else:
            for i, text in enumerate(self.config.history):
                preview = (text[:50] + "…") if len(text) > 50 else text
                m.add(rumps.MenuItem(
                    f"{i + 1}. {preview}",
                    callback=lambda s, t=text: self._paste_history(t),
                ))
        return m

    def _set_provider(self, p):
        self.config.provider = p
        self.config.save()
        self._build_menu()

    def _set_language(self, code):
        self.config.language = code
        self.config.save()
        self._build_menu()

    def _paste_history(self, text):
        subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=False)
        rumps.notification(APP_NAME, "Copiado al portapapeles", text[:80])

    def on_set_api_key(self, _):
        window = rumps.Window(
            message=f"API key para {self.config.provider}",
            title="whisper-ai",
            default_text=self.config.api_keys.get(self.config.provider, ""),
            ok="Guardar", cancel="Cancelar", dimensions=(320, 24),
        )
        resp = window.run()
        if resp.clicked and resp.text.strip():
            self.config.api_keys[self.config.provider] = resp.text.strip()
            self.config.save()
            rumps.notification(APP_NAME, "Guardado", f"API key para {self.config.provider}")

    def on_open_config(self, _):
        subprocess.run(["open", str(CONFIG_PATH)], check=False)

    def on_toggle_mode(self, _):
        if self.config.recording_mode == "hold":
            self.config.recording_mode = "toggle"
            rumps.notification(APP_NAME, "Modo Toggle activado",
                               "Un tap para empezar, otro tap para parar y transcribir.")
        else:
            self.config.recording_mode = "hold"
            rumps.notification(APP_NAME, "Modo Hold activado",
                               "Mantén pulsada la tecla para grabar, suéltala para transcribir.")
        self.config.save()
        self._build_menu()

    def on_toggle_ai_formatting(self, _):
        self.config.ai_formatting = not self.config.ai_formatting
        self.config.save()
        status = "ENCENDIDO" if self.config.ai_formatting else "APAGADO"
        rumps.notification(APP_NAME, "Limpieza Inteligente IA", f"Formato automático: {status}")
        self._build_menu()

    def on_quit(self, _):
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass
        rumps.quit_application()

    # ----- hotkey capture -----

    def on_capture_hotkey(self, _):
        with self._capture_lock:
            if self._capture_mode:
                return
            self._capture_mode = True
        self.title = "⌨"
        rumps.notification(
            APP_NAME,
            "Asignar tecla",
            "Pulsa la tecla que quieres usar para grabar…",
        )

    def _finish_capture(self, key):
        with self._capture_lock:
            self._capture_mode = False
        key_str = serialize_key(key)
        self.config.hotkey = key_str
        self.config.save()
        self.title = None
        self._build_menu()
        rumps.notification(APP_NAME, "Tecla asignada", key_display_name(key_str))
        # Reiniciar listener con la nueva tecla
        threading.Thread(target=self._start_listener, daemon=True).start()

    # ----- listener -----

    def _start_listener(self):
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass
        try:
            self._listener = keyboard.Listener(
                on_press=self._on_press,
                on_release=self._on_release,
            )
            self._listener.start()
        except Exception as e:
            print(f"[whisper-ai] Listener error: {e}", file=sys.stderr)
            rumps.notification(
                APP_NAME,
                "Sin permiso de Accesibilidad",
                "Ajustes → Privacidad → Accesibilidad → añadir whisper-ai.app",
            )

    def _matches(self, key) -> bool:
        target = deserialize_key(self.config.hotkey)
        if target is None:
            return False
        return key == target

    def _on_press(self, key):
        # Capture mode: save this key as the new hotkey
        if self._capture_mode:
            self._finish_capture(key)
            return

        if not self._matches(key):
            return

        if self.config.recording_mode == "toggle":
            # Toggle: first press starts, second press stops
            if self.recording:
                self._stop_and_transcribe()
            else:
                self._start_recording()
        else:
            # Hold: press starts recording
            if not self.recording:
                self._start_recording()

    def _on_release(self, key):
        if self._capture_mode:
            return
        if self.config.recording_mode == "toggle":
            return  # In toggle mode, release does nothing
        if not self._matches(key):
            return
        if self.recording:
            self._stop_and_transcribe()

    # ----- recording -----

    def _start_recording(self):
        self.recording = True
        self.title = "🔴"
        play_sound("Submarine")
        try:
            self.recorder.start()
            # Must call UI methods on main thread
            if self.overlay:
                from PyObjCTools import AppHelper
                AppHelper.callAfter(self.overlay.show)
        except Exception as e:
            self.recording = False
            self.title = None
            if self.overlay:
                from PyObjCTools import AppHelper
                AppHelper.callAfter(self.overlay.hide)
            rumps.notification(APP_NAME, "Error micrófono", str(e))

    def _stop_and_transcribe(self):
        self.title = "⏳"
        play_sound("Bottle")
        
        if self.overlay:
            from PyObjCTools import AppHelper
            AppHelper.callAfter(self.overlay.hide)
            
        wav = self.recorder.stop()
        self.recording = False
        if not wav:
            self.title = None
            play_sound("Basso")
            return
        threading.Thread(target=self._transcribe_and_paste, args=(wav,), daemon=True).start()

    def _transcribe_and_paste(self, wav: bytes):
        log = Path.home() / ".whisper_ai_debug.log"
        def _log(msg):
            try:
                with log.open("a", encoding="utf-8") as f:
                    f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
            except Exception:
                pass
        try:
            _log(f"wav bytes={len(wav)}")
            provider = self.config.provider
            key = self.config.api_keys.get(provider)
            if not key:
                _log(f"NO KEY for {provider}")
                rumps.notification(APP_NAME, "Sin API key", f"Configura la key para {provider}")
                play_sound("Basso")
                return
            lang = LANGUAGES.get(self.config.language)
            _log(f"calling transcribe provider={provider} lang={lang}")
            text = TRANSCRIBERS[provider](key, lang).transcribe(wav)
            _log(f"got text: {text!r}")
            if not text:
                play_sound("Basso")
                return
            
            # --- AI Formatting / Post-Processing ---
            if getattr(self.config, "ai_formatting", False) and text:
                _log("Starting AI formatting")
                sys_prompt = (
                    "Eres un asistente de corrección de dictado de voz y notas. Tu objetivo es limpiar y estructurar "
                    "el texto dictado por el usuario sin alterar el significado, la voz natural o la intención original.\n\n"
                    "Reglas estrictas:\n"
                    "1. Elimina muletillas (eh, um, o sea, pues, etc), repeticiones o tartamudeos propios del habla oral.\n"
                    "2. Aplica puntuación, comas y mayúsculas de manera perfecta.\n"
                    "3. Si detectas que el usuario está **enumerando elementos** o dando una serie de instrucciones "
                    "('primero tal', 'después esto', 'por último lo otro'), formatéalo automáticamente como una lista "
                    "limpia con viñetas (- ) o números, añadiendo saltos de línea para que quede muy legible y bien espaciado.\n"
                    "4. Jamás des confirmaciones, saludos ni comentarios como 'Aquí tienes el texto' ni marques con markdown "
                    "innecesario. Devuelve ÚNICAMENTE el texto final."
                )
                try:
                    if provider == "groq":
                        from groq import Groq
                        client = Groq(api_key=key)
                        response = client.chat.completions.create(
                            model="llama-3.3-70b-versatile",
                            messages=[
                                {"role": "system", "content": sys_prompt},
                                {"role": "user", "content": text}
                            ],
                            temperature=0.1,
                            max_tokens=2048,
                        )
                        text = response.choices[0].message.content.strip()
                    elif provider == "openai":
                        import openai
                        client = openai.OpenAI(api_key=key)
                        response = client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[
                                {"role": "system", "content": sys_prompt},
                                {"role": "user", "content": text}
                            ],
                            temperature=0.1,
                        )
                        text = response.choices[0].message.content.strip()
                    _log(f"formatted text: {text!r}")
                except Exception as ex:
                    _log(f"AI formatting failed: {ex}")
                    # Falls back to raw text quietly
            # ----------------------------------------
            
            copy_and_paste(text)
            _log("paste ok")
            self.config.history = ([text] + self.config.history)[:MAX_HISTORY]
            self.config.save()
            self._build_menu()
            play_sound("Pop")
        except Exception as e:
            import traceback
            _log(f"EXC: {e}\n{traceback.format_exc()}")
            rumps.notification(APP_NAME, "Error transcripción", str(e)[:160])
            play_sound("Basso")
        finally:
            self.title = None


def main():
    WhisperAIApp().run()


if __name__ == "__main__":
    main()
