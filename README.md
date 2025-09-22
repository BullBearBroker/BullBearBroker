## BullBearBroker

### Configuración de entorno

La API utiliza JWT para autenticar a los usuarios. Define una clave secreta fuerte antes de ejecutar el backend creando un archivo `.env` en la raíz del proyecto (o configurando las variables de entorno en tu plataforma de despliegue) con el siguiente contenido:

```env
BULLBEARBROKER_SECRET_KEY="coloca_aquí_una_clave_aleatoria_segura"
# Opcional: BULLBEARBROKER_JWT_ALGORITHM="HS256"
# Opcional: BULLBEARBROKER_REDIS_URL="redis://localhost:6379/0"
# Opcional: CRYPTO_PRICE_CACHE_TTL="60"               # segundos
# Opcional: CRYPTO_HTTP_TIMEOUT="10"                  # segundos
# Opcional: CRYPTO_HTTP_RETRIES="2"
# Opcional: CRYPTO_HTTP_BACKOFF_BASE="0.5"            # segundos
```

Si defines `BULLBEARBROKER_REDIS_URL`, instala la dependencia opcional `redis` para habilitar la caché asíncrona (por ejemplo, `pip install redis`).

> 💡 Puedes generar una cadena segura ejecutando en tu terminal `python -c "import secrets; print(secrets.token_urlsafe(64))"`.

Si la clave no está definida, el backend generará automáticamente una de un solo uso al iniciarse, lo cual es útil para desarrollo pero invalidará los tokens emitidos previamente tras cada reinicio.

### Ejecución local

1. Instala las dependencias con `npm install`.
2. Para levantar el frontend estático, ejecuta `npm run start` y accede a [http://localhost:8080](http://localhost:8080).
3. En otra terminal, inicia el backend con `npm run backend`, lo que lanza el servidor FastAPI en [http://localhost:8000](http://localhost:8000).

Detén cada proceso con `Ctrl+C` cuando termines.
