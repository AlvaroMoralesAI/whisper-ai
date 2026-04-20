# 🛡 Whisper-AI: Instrucciones Específicas de Proyecto (Project Skill)

Esta "skill" es una capa de seguridad y auditoría en tiempo de desarrollo específica UNÍCAMENTE para este repositorio interactuando con Inteligencias Artificiales. Al leer este archivo, estás obligado a cumplir estrictamente los siguientes parámetros antes de modificar o crear nuevo código:

## 1. Auditoría de Seguridad & Secretos (CRÍTICO)
- **Fuga de Credenciales:** Nunca expongas tu API Key de Groq ni ningún otro token hardcodeado en el código fuente (`src/whisper_ai.py`) o en `.json` que sean subidos al repositorio.
- **Git Push Protection:** Si vas a ejecutar un comando `git commit` o `git push`, verifica proactivamente usando herramientas como `git diff` que no se ha filtrado ningún secreto. Archivos temporales generados con claves deben ir al `.gitignore`.
- **Acceso Local:** El historial de la aplicación debe guardarse **solamente en la máquina local del usuario** (actualmente en `~/.whisper_ai.json`) con permisos de lectura/escritura restrictivos (`0o600`).

## 2. Estándares y Formateo del Código (Clean Code)
- **Modularidad:** Si introduces una nueva funcionalidad, no rompas ni sobrecargues la clase principal del overlay (CoreGraphics / PyObjC). Evalúa extraer funcionalidades pesadas a métodos separados.
- **Rendimiento UI vs Background:** Recuerda que las actualizaciones al `NSWindow` en macOS **SOLO** pueden invocarse en el hilo principal utilizando `PyObjCTools.AppHelper.callAfter()`. Violaciones a esta regla provocarán errores de Segfault.
- **Python Types:** Todo código nuevo de backend debe mantener el tipado estático opcional (`Union`, `Optional`, `List`) según lo dicta `typing`.

## 3. Revisión Funcional (Bugs & Documentación)
- Tras implementar código, realiza una revisión de estado de error (Error Handling Exception catching). Groq API, mic recording (pynput, sounddevice) son fuentes comunes de excepciones asíncronas. Ninguna función de dictado debe frenar el hilo si ocurre un error HTTP 400.
- Si se añaden nuevas funcionalidades o flujos para nuevos desarrolladores, asegúrate obligatoriamente de registrar el cambio en el archivo `SESSION_BRIEF.md` (Contexto Técnico) o en `README.md` (Entorno y Setup de Antigravity).

*Ejecuta estos chequeos de forma implícita y automática en todas tus respuestas y procesos dentro de esta carpeta.*
