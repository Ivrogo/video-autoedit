# video-autoedit

Edición de video automatizada: subes un video crudo a una carpeta de **Google Drive** desde cualquier dispositivo y, sin tocar nada más, aparece editado en otra carpeta de Drive. El procesamiento corre gratis en **GitHub Actions** — no depende de ningún PC encendido.

> Este repositorio solo contiene código. Los videos nunca pasan por GitHub: viajan directamente entre Google Drive y el runner efímero que los procesa. Las credenciales viven cifradas en GitHub Secrets.

## Qué hace el pipeline

1. **Corta los silencios**: detecta pausas de más de 0.5 s y las elimina (con un poco de aire a cada lado para que no suene robótico).
2. **Transcribe** el audio con Whisper (faster-whisper, español).
3. **Genera subtítulos** (`.srt` y quemados en el video con estilo configurable).
4. **Masteriza el audio**: filtro highpass, EQ de presencia, compresión y normalización a -14 LUFS.
5. **Corrige el color** (ajuste suave de contraste/saturación, o tu propio LUT `.cube`).

Todo configurable en [config.yaml](config.yaml).

## Flujo con Google Drive

```
[Tu móvil/PC] --sube el crudo--> Drive: AutoEdit/01_Raw
                                        |
                     GitHub Actions (cada 30 min, o lanzado a mano)
                                        |
        video editado + .srt + transcripción --> AutoEdit/03_Editados
        el crudo se archiva                  --> AutoEdit/04_Procesados
        si algo falla: crudo + error.log     --> AutoEdit/05_Errores
```

Las carpetas se crean solas la primera vez. `02_Procesando` es interna (marca qué video está siendo procesado para que dos runs no se pisen).

**Tiempos**: los runners son CPU-only; un video de 30–60 min tarda 1–2 h en procesarse. Cuenta con que el resultado aparece en Drive entre 1 y 3 horas después de subirlo.

## Uso local (opcional)

```
py -3.12 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m autoedit process mi_video.mp4
```

El resultado queda en `output/mi_video/final.mp4`. Con GPU NVIDIA, pon `model: large-v3` en `config.yaml` (la detección CUDA→CPU es automática).

También puedes vaciar la cola de Drive desde local: `python -m autoedit drive-run`.

## Setup inicial (una sola vez)

### 1. Credenciales de Google Drive (~10 min)

1. Entra en [Google Cloud Console](https://console.cloud.google.com) y crea un proyecto (p. ej. `autoedit`).
2. **APIs y servicios → Biblioteca** → habilita **Google Drive API**.
3. **Pantalla de consentimiento OAuth** → tipo *Externo* → añade tu propio email como usuario de prueba.
4. **Credenciales → Crear credenciales → ID de cliente de OAuth** → tipo *Aplicación de escritorio* → descarga el JSON y guárdalo como `credentials.json` en la raíz del proyecto (está en `.gitignore`, nunca se sube).
5. Ejecuta `py -3.12 scripts/get_refresh_token.py` → se abre el navegador, autorizas con tu cuenta, y el script imprime los tres valores para los secrets.

### 2. GitHub Secrets

```
gh secret set GDRIVE_CLIENT_ID --body "<valor>"
gh secret set GDRIVE_CLIENT_SECRET --body "<valor>"
gh secret set GDRIVE_REFRESH_TOKEN --body "<valor>"
```

### 3. Probar

Sube un video a `AutoEdit/01_Raw` en Drive y lanza el workflow a mano:

```
gh workflow run "Procesar videos de Drive"
gh run watch
```

## Limitaciones conocidas

- El cron de Actions puede retrasarse unos minutos, y **GitHub desactiva los crons tras 60 días sin actividad en el repo** (un commit cualquiera lo reactiva).
- Los runners tienen ~14 GB de disco: crudos de más de ~8 GB pueden no caber.
- Usar Actions para procesado intensivo de media es una zona gris de la política de GitHub para repos públicos. Si algún día fuera un problema, el mismo código corre en cualquier máquina con `python -m autoedit drive-run` (por ejemplo, en cron de una VM o de tu PC).

## Tests

```
pip install pytest
pytest
```

Para una prueba end-to-end local sin grabar nada: `powershell -ExecutionPolicy Bypass -File scripts\make_test_clip.ps1` genera `test_clip.mp4` con voz sintética en español y pausas largas.
