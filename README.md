# Office Music Connect

Aplicación web para controlar YouTube Music desde la LAN de la oficina. El backend vive en la mini PC anfitriona y mantiene aislada una instancia dedicada de Chrome.

## Estado

MVP implementado: salud, autenticación por token, estado del reproductor, play/pause, anterior/siguiente, volumen básico, barra de progreso con búsqueda de posición, búsqueda con adaptador reemplazable, cola persistente en SQLite, WebSocket y UI responsive.

Al pulsar **Reproducir** en un resultado, el tema se reproduce inmediatamente sin agregarse a la cola. **Siguiente** reproduce y retira el primer tema encolado; si la cola está vacía, usa el control siguiente de YouTube Music.

La **Lista para Siguiente** se usa únicamente al pulsar **Siguiente**. Al finalizar una canción, YouTube Music conserva su comportamiento de reproducción automática y la lista no se consume.

El volumen seleccionado desde la interfaz se vuelve a aplicar si YouTube Music lo cambia mientras el backend está en ejecución. Tras reiniciar el backend, selecciona el nivel deseado nuevamente.

## Requisitos

- Windows 11
- Python 3.12 64-bit probado
- Google Chrome
- Google Chrome (el backend inicia la instancia dedicada con CDP en loopback)
- YouTube Music Premium iniciado manualmente en el perfil dedicado

No instalar nada en la mini PC hasta autorizar el despliegue.

## Desarrollo

Desde Git Bash en Windows, ejecuta `bash start.sh`. En el primer inicio crea `.venv` e instala las dependencias si faltan. Si no existe `.env`, crea una copia de `.env.example`; configura `APP_ACCESS_TOKEN` y `APP_SECRET_KEY` antes de volver a iniciar.

```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m playwright install chromium
Copy-Item .env.example .env
```

Edite `.env` y sustituya `APP_ACCESS_TOKEN` y `APP_SECRET_KEY` por valores aleatorios. Puede generar un token con:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Al iniciar el backend, se inicia automáticamente un Chrome dedicado con dos pestañas:

- La pestaña principal, configurada en la aplicación (por defecto `https://example.com/`).
- `https://music.youtube.com/`

La instancia usa `./chrome-profile`, inicia en pantalla completa y mantiene la pestaña principal configurada en primer plano mientras YouTube Music reproduce en segundo plano. CDP solo escucha en `127.0.0.1:9222`. El Chrome preexistente no se cierra ni se automatiza. Si CDP ya está disponible, el servicio reutiliza esa instancia y abre únicamente las páginas faltantes.

El enlace de la pestaña principal se puede cambiar desde el engranaje de **Configuración** y queda guardado en SQLite. También se puede establecer inicialmente con `MAIN_TAB_URL` en `.env` (por defecto `https://example.com/`). Otras opciones: `CHROME_AUTO_LAUNCH=true`, `CHROME_USER_DATA_DIR`, `CHROME_CDP_URL` y `CHROME_MUSIC_URL`. Para deshabilitar el inicio de Chrome, establezca `CHROME_AUTO_LAUNCH=false`. Si Chrome no está en la ruta habitual, indique su ejecutable con `CHROME_EXECUTABLE`.

No ejecute manualmente otro Chrome con el perfil `chrome-profile` a la vez. Inicie el backend y autentique YouTube Music manualmente la primera vez.

Si se necesita iniciar el perfil manualmente, use este comando únicamente tras detener el backend:

```powershell
& "$env:ProgramFiles\Google\Chrome\Application\chrome.exe" `
  --remote-debugging-address=127.0.0.1 `
  --remote-debugging-port=9222 `
  --user-data-dir="$PWD\chrome-profile" `
  "https://example.com/" `
  "https://music.youtube.com/"
```

Inicie el servicio:

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Abra `http://127.0.0.1:8080` y use el mismo token configurado en `.env`.

## Pruebas

```powershell
python -m pytest -q
```

Las pruebas deben pasar antes de iniciar cualquier despliegue. La búsqueda usa `ytmusicapi`, una integración comunitaria reemplazable; no descarga ni retransmite audio.

## Seguridad

- CDP se conecta únicamente a `127.0.0.1:9222`.
- Las rutas de control exigen Bearer token.
- El WebSocket exige `?token=...`.
- No abra el puerto CDP en el firewall.
- Configure el firewall del puerto HTTP para permitir solo la subred LAN autorizada.

## Recuperación

Si Chrome reinicia o YouTube Music pierde la sesión, el backend conserva la cola SQLite y marca el reproductor desconectado. Reinicie el Chrome dedicado y vuelva a iniciar sesión manualmente en YouTube Music. Consulte los logs de consola y reintente la conexión desde la interfaz.
