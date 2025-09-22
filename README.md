## BullBearBroker

### Configuración de entorno

La API utiliza JWT para autenticar a los usuarios. Define una clave secreta fuerte antes de ejecutar el backend creando un archivo `.env` en la raíz del proyecto (o configurando las variables de entorno en tu plataforma de despliegue) con el siguiente contenido:

```env
BULLBEARBROKER_SECRET_KEY="coloca_aquí_una_clave_aleatoria_segura"
# Opcional: BULLBEARBROKER_JWT_ALGORITHM="HS256"
```

> 💡 Puedes generar una cadena segura ejecutando en tu terminal `python -c "import secrets; print(secrets.token_urlsafe(64))"`.

Si la clave no está definida, el backend generará automáticamente una de un solo uso al iniciarse, lo cual es útil para desarrollo pero invalidará los tokens emitidos previamente tras cada reinicio.

#### Variables de entorno adicionales

Los nuevos servicios requieren configurar claves opcionales para integraciones externas:

| Variable | Descripción |
| --- | --- |
| `TWELVEDATA_API_KEY` | Necesaria para datos de divisas y series temporales forex. |
| `REDIS_URL` | Dirección del backend Redis utilizado por el planificador de alertas (por defecto `redis://localhost:6379/0`). |
| `ALERT_EVALUATION_INTERVAL` | Intervalo en segundos para evaluar alertas (por defecto `60`). |
| `HUGGINGFACE_API_TOKEN` | Token de inferencia para el modelo de sentimiento en HuggingFace. |
| `HUGGINGFACE_MODEL` | Modelo a utilizar (por defecto `ProsusAI/finbert`). |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | Opcionales para notificaciones vía Telegram. |

> Para ejecutar el planificador necesitas una instancia de Redis disponible. En desarrollo puedes levantarla con `docker run -p 6379:6379 redis:7`.

Las tareas programadas evaluarán las alertas activas y notificarán a través del WebSocket `/ws/alerts` y, si está configurado, mediante Telegram.

### Ejecución local

1. Instala las dependencias con `npm install`.
2. Para levantar el frontend estático, ejecuta `npm run start` y accede a [http://localhost:8080](http://localhost:8080).
3. En otra terminal, inicia el backend con `npm run backend`, lo que lanza el servidor FastAPI en [http://localhost:8000](http://localhost:8000).

Detén cada proceso con `Ctrl+C` cuando termines.
