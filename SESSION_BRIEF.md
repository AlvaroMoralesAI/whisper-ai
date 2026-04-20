# Handoff — whisper-ai nueva sesión

## Contexto del proyecto
Estoy construyendo **whisper-ai**, mi propia herramienta de dictado por voz estilo Whisperflow para macOS.
Inspiración: https://www.whisperflow.app

**Estado actual:**
- App macOS menu bar en Python (rumps + pynput + sounddevice + Groq) ✅
- Bundle: `~/Desktop/whisper-ai.app` (py2app, **alias mode**)
- Código fuente: `~/whisper-ai/src/whisper_ai.py`
- Icono: F morada/chrome visible en la barra de menú ✅
- Hotkey: Option derecho (`Key.alt_r`) ✅ FUNCIONANDO
- Provider: Groq con API key configurada ✅
- Transcripción + pegado automático ✅
- Historial de últimas 10 transcripciones en menú ✅
- Selector de modo de grabación: "Mantener pulsado (Hold)" y "Toggle" ✅
- UI Nativa tipo cápsula flotante estilo Wispr Flow en CoreGraphics con neón y cristal oscuro ✅
- NO subido a GitHub aún

## Mejoras de Sesión Actual (Premium UI & Toggle)
1. **Toggle Mode:** Implementada lógica en `_on_press` y `_on_release` para soportar tanto mantener la tecla pulsada como pulsar-para-grabar / pulsar-para-detener.
2. **AppKit UI Injection:** Se sobrepasaron las limitaciones de hilos de macOS usando `PyObjCTools.AppHelper.callAfter()` para poder instanciar una ventana `NSWindow` pura flotante con nivel "Floating".
3. **Efecto Premium Neón:** Se reemplazó el flat-design inicial por CoreGraphics puros, incluyendo un `NSVisualEffectMaterialDark`, un `NSShadow` agresivo para efecto neón (`#ac3aff` blur 10) y degradados reales a 60fps basados en el RMS del micrófono (`math.sqrt`).
- Cero consumo de CPU en inactividad: el timer y la UI se destruyen completamente cuando no se está grabando.

## Bugs resueltos en sesiones anteriores

### Bug 1 — SSL (py2app)
**Síntoma:** Sonido de error al soltar Option, sin transcripción, sin historial.
**Causa:** py2app's `__boot__.py` setea `SSL_CERT_FILE` a una ruta falsa antes que el código. `os.environ.setdefault` no sobreescribía → SSL fallaba → excepción → nada.
**Fix aplicado** en `whisper_ai.py` líneas 11-20:
```python
try:
    import certifi
    _ca = certifi.where()
    if os.path.exists(_ca):
        os.environ["SSL_CERT_FILE"] = _ca
        os.environ["REQUESTS_CA_BUNDLE"] = _ca
        os.environ.pop("SSL_CERT_DIR", None)
except ImportError:
    pass
```

### Bug 2 — Permisos Accessibility / Input Monitoring (pynput)
**Síntoma:** Pulsar Option no hacía nada. El listener de pynput arrancaba (is_alive=True) pero no recibía eventos.
**Causa:** macOS TCC no había concedido permiso de Accessibility ni Input Monitoring a whisper-ai.app. El mensaje de pynput era: `"This process is not trusted! Input event monitoring will not be possible"`.
**Fix:** 
1. Añadir `NSAccessibilityUsageDescription` y `NSInputMonitoringUsageDescription` al `setup.py` (plist)
2. `tccutil reset Accessibility com.alvaromorales.whisperai`
3. `tccutil reset ListenEvent com.alvaromorales.whisperai`
4. Activar manualmente en System Settings → Privacy → Accessibility + Input Monitoring

### Bug 3 — Encoding al pegar (caracteres corruptos)
**Síntoma:** Transcripción correcta en historial pero al pegar salía `¬øqu√©` en vez de `¿qué`.
**Causa:** `pbcopy` recibe bytes UTF-8 raw pero algunas apps (Cursor, VS Code, Terminal) los reinterpretan en Mac Roman.
**Fix aplicado** en `copy_and_paste()` — usar `NSPasteboard` directamente (PyObjC nativo):
```python
from AppKit import NSPasteboard, NSPasteboardTypeString
pb = NSPasteboard.generalPasteboard()
pb.clearContents()
pb.setString_forType_(text, NSPasteboardTypeString)
```

## Lecciones críticas (NO repetir)
- **py2app siempre** para menu bar apps macOS (nunca bash launcher + exec python)
- Proyecto en `~/whisper-ai/` no en `~/Desktop/` (TCC de macOS)
- `arch -arm64` en launchers Apple Silicon
- `libportaudio.dylib` en `frameworks` del setup.py si usa sounddevice
- **Clipboard UTF-8:** usar siempre `NSPasteboard`, nunca `pbcopy` con bytes — Mac Roman vs UTF-8
- **Permisos TCC:** el bundle necesita `NSAccessibilityUsageDescription` + `NSInputMonitoringUsageDescription` en el plist o macOS nunca pedirá los permisos

## Historial de transcripciones
- Se guardan los **últimos 10** en `~/.whisper_ai.json` (constante `MAX_HISTORY = 10`)
- Cola FIFO: el más nuevo al principio, el más antiguo se descarta
- **No es permanente** — si quieres log ilimitado hay que añadir escritura a archivo aparte

## Archivos clave
```
~/whisper-ai/
├── src/whisper_ai.py          ← código principal (~558 líneas)
├── setup.py                   ← py2app config (con NSAccessibility + NSInputMonitoring keys)
├── assets/AppIcon.icns        ← icono F morada
├── .venv/                     ← Python 3.14 + deps
├── build.sh                   ← build helper
├── rebuild.sh                 ← rebuild limpio + relanzar (creado sesión 2026-04-20)
└── requirements.txt

~/.whisper_ai.json             ← config: hotkey, provider, api_keys, history
~/Desktop/whisper-ai.app       ← bundle activo (alias mode → apunta a src/)
```

## Cómo hacer rebuild
```bash
cd ~/whisper-ai
pkill -f whisper-ai.app
rm -rf build dist
./.venv/bin/python3 setup.py py2app -A
cp -Rf dist/whisper-ai.app ~/Desktop/
xattr -cr ~/Desktop/whisper-ai.app
tccutil reset Accessibility com.alvaromorales.whisperai
tccutil reset ListenEvent com.alvaromorales.whisperai
open ~/Desktop/whisper-ai.app
# → Ir a System Settings > Privacy > Accessibility + Input Monitoring y activar
```

## Features pendientes / ideas
- Log permanente de todas las transcripciones (archivo de texto o SQLite)
- Ampliar MAX_HISTORY si se desea más de 10 en el menú
- Subir a GitHub
