## BullBearBroker

### Requisitos previos

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/) (Docker Desktop ya lo incluye)
- Opcional: `make` si prefieres ejecutar comandos abreviados
- Python 3.11 si deseas ejecutar el backend sin contenedores. Instala las
  dependencias con `pip install -r backend/requirements.txt` (incluye Plotly,
  APScheduler, Celery y python-telegram-bot para gráficos, programación y
  notificaciones).

### Variables de entorno

Crea un archivo `.env` en la raíz del proyecto para compartirlo entre el backend y el worker de alertas. Como referencia mínima:

```env
# Autenticación y sesiones
BULLBEARBROKER_SECRET_KEY="coloca_aquí_una_clave_aleatoria_segura"
# BULLBEARBROKER_JWT_ALGORITHM="HS256"  # opcional

# Base de datos (Supabase)
DATABASE_URL="postgresql://usuario:password@db.<proyecto>.supabase.co:5432/postgres?sslmode=require"

# Servicios internos
REDIS_URL="redis://redis:6379/0"

# Claves para proveedores externos (habilitan funcionalidades avanzadas)
ALPHA_VANTAGE_API_KEY=
TWELVEDATA_API_KEY=
COINGECKO_API_KEY=
COINMARKETCAP_API_KEY=
NEWSAPI_API_KEY=
CRYPTOPANIC_API_KEY=
FINFEED_API_KEY=
MEDIASTACK_API_KEY=
HUGGINGFACE_API_KEY=
HUGGINGFACE_SENTIMENT_MODEL="distilbert-base-uncased-finetuned-sst-2-english"
MISTRAL_API_KEY=
TELEGRAM_BOT_TOKEN=
TELEGRAM_DEFAULT_CHAT_ID=
# Variables opcionales para inferencia local
# OLLAMA_HOST=http://localhost:11434
# OLLAMA_MODEL=llama3
```

> 💡 Genera una clave segura ejecutando `python -c "import secrets; print(secrets.token_urlsafe(64))"`.

Si `BULLBEARBROKER_SECRET_KEY` no está definida, el backend generará una clave aleatoria en cada arranque y se invalidarán los tokens previos.

#### Variables destacadas

- **DATABASE_URL**: Debe apuntar al clúster de Supabase (PostgreSQL gestionado). El formato recomendado es el que proporciona Supabase con `sslmode=require` para garantizar conexiones seguras.
- **Backend y alert-worker**: requieren `BULLBEARBROKER_SECRET_KEY`, `DATABASE_URL` y `REDIS_URL` para operar.
- **Mercados**: `ALPHA_VANTAGE_API_KEY`, `TWELVEDATA_API_KEY`, `COINGECKO_API_KEY` y `COINMARKETCAP_API_KEY` habilitan los distintos proveedores de precios.
- **Noticias**: `NEWSAPI_API_KEY`, `CRYPTOPANIC_API_KEY`, `FINFEED_API_KEY` y `MEDIASTACK_API_KEY` enriquecen los listados.
- **IA y notificaciones**: `HUGGINGFACE_API_KEY`, `HUGGINGFACE_SENTIMENT_MODEL`, `MISTRAL_API_KEY`, `TELEGRAM_BOT_TOKEN` y `TELEGRAM_DEFAULT_CHAT_ID` son usados por los servicios de sentimiento, generación y alertas.

### Ejecución con Docker Compose

1. Construye e inicia los servicios (`backend`, `alert-worker`, `redis` y `frontend`):

   ```bash
   docker compose up --build
   ```

   - El backend expone la API en [http://localhost:8000](http://localhost:8000).
   - El `alert-worker` comparte la imagen del backend y procesa alertas en segundo plano.
   - `redis` actúa como broker para colas y caché.
   - El `frontend` estático queda disponible en [http://localhost:3000](http://localhost:3000).

   > ℹ️ Ambos servicios de Python leerán `DATABASE_URL` desde `.env` para conectarse al PostgreSQL gestionado por Supabase. No se despliega una base de datos local en este `docker-compose`.

2. Cuando termines, detén los servicios con:

   ```bash
   docker compose down
   ```

   Para limpiar completamente los volúmenes de datos (por ejemplo, reiniciar la base de datos), ejecuta `docker compose down -v`.

#### Atajos con `make`

Si cuentas con `make`, el proyecto incluye un `Makefile` con los siguientes atajos:

- `make build` – equivalente a `docker compose up --build`
- `make up` – levanta los servicios ya construidos
- `make down` – detiene los contenedores
- `make clean` – elimina contenedores, redes y volúmenes asociados
- `make logs` – muestra los logs combinados de los servicios

### Migraciones de base de datos

El backend utiliza [Alembic](https://alembic.sqlalchemy.org/) para gestionar los cambios de esquema. Cada vez que actualices el código asegúrate de aplicar las migraciones más recientes con:

```bash
docker compose run --rm backend alembic upgrade head
```

> Si ejecutas el backend fuera de Docker, asegúrate de que `DATABASE_URL` apunte al clúster de Supabase (o a la instancia de PostgreSQL equivalente) antes de lanzar `alembic upgrade head`.

#### Ejemplos de llamadas HTTP

A continuación se muestran ejemplos rápidos usando `curl` con la API levantada en `http://localhost:8000`:

- Registro de usuario:

  ```bash
  curl -X POST http://localhost:8000/api/auth/register \
    -H "Content-Type: application/json" \
    -d '{"email":"alice@example.com","password":"secreto123"}'
  ```

  Respuesta abreviada:

  ```json
  {
    "message": "Usuario registrado exitosamente",
    "token": "<jwt>",
    "user": { "id": "...", "email": "alice@example.com" }
  }
  ```

- Precio de Bitcoin:

  ```bash
  curl http://localhost:8000/crypto/BTC
  ```

  ```json
  {
    "symbol": "BTC",
    "type": "crypto",
    "price": 62000.42,
    "source": "CryptoService + Binance"
  }
  ```

- Precio de la acción de Apple:

  ```bash
  curl http://localhost:8000/stock/AAPL
  ```

- Cotización EUR/USD:

  ```bash
  curl http://localhost:8000/forex/EURUSD
  ```

- Noticias de criptomonedas:

  ```bash
  curl http://localhost:8000/news/crypto
  ```

- Listado de alertas (requiere token JWT):

  ```bash
  curl http://localhost:8000/alerts \
    -H "Authorization: Bearer <jwt>"
  ```

  ```json
  [
    { "id": "...", "asset": "BTC", "condition": "above", "value": 65000.0 }
  ]
  ```

### Desarrollo sin Docker

Los scripts de `npm` siguen disponibles para desarrollo local sin contenedores:

1. Instala las dependencias del frontend con `npm install`.
2. Levanta el frontend estático con `npm run start` y accede a [http://localhost:8080](http://localhost:8080).
3. Inicia el backend con `npm run backend` (lanza Uvicorn en [http://localhost:8000](http://localhost:8000)).

Detén cada proceso con `Ctrl+C` cuando termines.

### Nuevas capacidades del mercado

- **Pares FX y materias primas**: `forex_service` reutiliza Twelve Data y Yahoo Finance
  con caché en memoria para entregar cotizaciones rápidas a través de `/forex/{pair}`.
- **Sentimiento de mercado**: `sentiment_service` fusiona el índice Fear & Greed de Alternative.me
  con análisis de sentimiento de HuggingFace disponible en `/api/market/sentiment/{symbol}`.
- **Gráficos dinámicos**: la ruta `/api/market/chart/{symbol}` genera imágenes PNG en base64
  mediante Plotly y soporta parámetros de intervalo y rango.
- **Alertas automatizadas**: `alert_service` usa APScheduler para evaluar condiciones de precio y
  notificar vía WebSocket y Telegram. El worker dedicado corre con Docker Compose (`alert-worker`).

### Añadir nuevas fuentes de datos

Las integraciones de precios y noticias están desacopladas mediante servicios especializados.
Para conectar una nueva fuente:

1. **Crea o actualiza un servicio** con un método `get_price` (o equivalente) que devuelva los
   datos normalizados. Puedes inspirarte en `backend/services/crypto_service.py` y
   `backend/services/stock_service.py`.
2. **Inyecta la dependencia** en `MarketService` pasando el servicio en el constructor o
   registrándolo dentro de la clase si debe ser la fuente por defecto.
3. **Gestiona la caché** reutilizando `utils.cache.CacheClient` para evitar llamadas repetidas.
4. **Actualiza los helpers del mercado** (`get_crypto_price`, `get_stock_price`, `get_news`) para que
   deleguen en la nueva fuente y añade la clave necesaria en `.env`.

De forma similar, las nuevas APIs de noticias pueden integrarse creando un método auxiliar que
devuelva la estructura `{title, url, source, published_at, summary}` y registrándolo como fallback
antes de la lectura RSS.
