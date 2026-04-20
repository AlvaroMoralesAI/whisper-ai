# Whisper AI ✨

Una aplicación nativa de dictado por voz para macOS super premium con formateo automático generativo por Inteligencia Artificial (LLaMA).

## Características
- **Zero lag:** Transcripción sub-segundo con Whisper Large v3 (vía Groq).
- **Inteligencia Pura:** Pule y formatea tus audios automáticamente con `LLaMA-3.3 70B`. Limpia muletillas, estructura enumeraciones en listas e inserta signos de puntuación perfectos.
- **Overlay Premium:** Animaciones reales a 60fps renderizadas directo al Metal de Mac usando API CoreGraphics. Píldora de cristal oscuro con brillo neón reactivo a tu voz.
- **Inyección directa:** Simula teclado nativo. Pega el texto donde sea que esté tu cursor de texto en cualquier aplicación.
- **Modos de Grabación:** Selecciona interactuar "Manteniendo presionado" (Hold) o modo de toque único "Toggle" para dictar sin manos.

## Instalación en 1-Click (Para el equipo)

1. **Clona o descarga** este repositorio (haz click en *Code > Download ZIP* si no usas git y descomprímelo).
2. Abre la app `Terminal`, navega a la carpeta descargada (`cd ~/Downloads/whisper-ai-main`) y ejecuta el instalador automatizado:

```bash
chmod +x install.sh
./install.sh
```

### Configuración post-instalación:
1. Abre **whisper-ai** en tu Escritorio (`~/Desktop/whisper-ai.app`).
2. macOS te pedirá permisos de **Accesibilidad** e **Input Monitoring** (necesarios para que reciba la pulsación de la tecla y emita las letras como teclado virtual). Entra en `System Settings` y otorga los dos permisos a la app.
3. Toca el logo de la aplicación en la barra superior del menú de tu Mac (arriba a la derecha).
4. Ve a **"Set API key…"** y pega tu clave personal de la plataforma Groq.

¡Listo! Presiona tu tecla de activación (por defecto `Option derecho`) y experimenta.
