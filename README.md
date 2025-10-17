# BullBearBroker

![Tests](https://github.com/bullbearbroker/bullbearbroker/actions/workflows/tests.yml/badge.svg)

BullBearBroker es una plataforma de análisis financiero asistido por IA. Combina datos de
mercados tradicionales y cripto con módulos de noticias, alertas y un chatbot
especializado para acompañar decisiones de trading en tiempo real.

## Visión del proyecto

- **Asistente integral** para traders minoristas que quieran monitorear acciones,
  criptomonedas y pares de divisas desde un único panel.
- **Alertas inteligentes** con disparadores personalizables y notificaciones en
  tiempo real (web, Telegram y Discord).
- **Contexto enriquecido** mediante noticias, análisis de sentimiento y modelos
  de lenguaje que ayuden a interpretar la información del mercado.
- **Roadmap abierto** orientado a extender la plataforma con módulos de IA
  avanzados, nuevas fuentes de datos y experiencias conversacionales.

## Estructura de carpetas

```text
.
├── backend/                # API FastAPI, servicios y modelos SQLAlchemy
├── frontend/               # Frontend Next.js + Tailwind + SWR
├── docker-compose.yml      # Orquestación de stack completo (backend, frontend, DB, Redis)
├── Dockerfile              # Imagen del backend (FastAPI + Uvicorn)
├── Makefile                # Atajos para Docker Compose y pruebas
├── .env.sample             # Variables de entorno mínimas
└── backend/tests/          # Suite de pruebas (autenticación, alertas, servicios...)
```

## Variables de entorno

El archivo [.env.sample](./.env.sample) lista los valores mínimos para correr el
stack en local. Copia el archivo y ajusta los secretos antes de iniciar los
servicios:

```bash
cp .env.sample .env
```

Campos destacados:

- **SECRET_KEY / ACCESS_TOKEN_SECRET / REFRESH_TOKEN_SECRET**: claves para firmar
  JWT y sesiones.
- **DATABASE_URL**: apunta por defecto al contenedor de PostgreSQL lanzado vía
  Docker Compose (`postgresql+psycopg2://bullbear:bullbear@db:5432/bullbear`).
- **REDIS_URL**: requerido para rate limiting y futuras colas de tareas.
- **LOGIN_IP_LIMIT_TIMES / LOGIN_IP_LIMIT_SECONDS**: controlan el límite suave por IP
  para `/api/auth/login`.
- **BULLBEAR_DEFAULT_USER / PASSWORD**: credenciales sembradas automáticamente para pruebas.
- **NEXT_PUBLIC_API_URL**: URL base que consume el frontend (en Docker se
  resuelve a `http://backend:8000`).
- **PUSH_VAPID_PUBLIC_KEY / PUSH_VAPID_PRIVATE_KEY**: claves VAPID usadas para
  firmar notificaciones web push desde el backend. Genera un par con
  `npx web-push generate-vapid-keys` y compártelas con el frontend.
- **NEXT_PUBLIC_PUSH_VAPID_PUBLIC_KEY**: clave pública expuesta al navegador
  para registrar la suscripción push mediante el Service Worker.
- **AI_PROVIDER_KEYS**: configura `MISTRAL_API_KEY` o `HUGGINGFACE_API_KEY` para
  habilitar respuestas del asistente con persistencia de historial.

## Puesta en marcha con Docker Compose

1. Genera tu archivo `.env` como se describe arriba.
2. Construye y levanta los contenedores en segundo plano:

   ```bash
   make up           # equivalente a docker compose up -d
   ```

   Servicios incluidos:

   - **db**: PostgreSQL 15 con persistencia en `postgres_data`.
   - **redis**: Redis 7 para rate limiting y caching.
   - **backend**: API FastAPI sirviendo en [http://localhost:8000](http://localhost:8000).
   - **frontend**: Next.js Dev Server disponible en [http://localhost:3000](http://localhost:3000).

3. Sigue los logs combinados cuando lo necesites:

   ```bash
   make logs
   ```

4. Detén y limpia los recursos cuando termines:

   ```bash
   make down         # detiene contenedores
   make clean        # detiene y borra volúmenes/orphans
   ```

## Configuración manual (sin Docker)

1. **Backend**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install -r backend/requirements.txt
   export $(grep -v '^#' .env | xargs)
   uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
   ```

   Configurá las variables manualmente si preferís otro enfoque.

2. **Frontend**
   ```bash
   cd frontend
   npm install
   npm run dev -- --hostname 0.0.0.0 --port 3000
   ```

Asegúrate de tener PostgreSQL y Redis ejecutándose en tu entorno local y que las
variables de entorno apunten a esas instancias.

### Perfil staging con Docker Compose

El `docker-compose.yml` define dos perfiles:

- `default`: entorno de desarrollo con recarga en caliente (`make up`).
- `staging`: entorno de pruebas realistas con builds optimizados.

Para levantar el perfil staging:

```bash
make up-staging       # Levanta backend, frontend, db y redis en modo staging
make down-staging     # Detiene únicamente los servicios del perfil staging
```

En staging el frontend ejecuta `npm start` (Next.js compilado) y el backend
utiliza Uvicorn sin `--reload`, reutilizando los contenedores de PostgreSQL y
Redis con volúmenes persistentes.

## Entornos de ejecución

| Variable `ENV` | Comportamiento | Cómo levantar |
| -------------- | -------------- | ------------- |
| `local`        | El backend crea las tablas automáticamente (`Base.metadata.create_all`) y siembra el usuario por defecto. Ideal para desarrollo rápido. | `make up-local` (equivalente a `docker compose --env-file .env.local up -d --build`). |
| `staging` / `prod` | La base de datos **no** se crea automáticamente: se espera que las migraciones de Alembic estén aplicadas. | `make up-staging` (staging) o configura tus variables y ejecuta `docker compose --profile staging up -d`. |

Cuando trabajes fuera de `local` debes aplicar las migraciones manualmente:

```bash
make migrate          # docker compose exec backend alembic upgrade head
```

💡 Recomendación: tras cada despliegue en staging/prod ejecuta `make migrate` (o el comando equivalente en tu pipeline) antes de exponer la API. Esto garantiza que el esquema coincida con la última versión del código.

## Testing

Desde la raíz del repositorio podés lanzar las suites de manera unificada con
los scripts de `pnpm`:

```bash
pnpm test:frontend       # Jest modo desarrollo con watch inteligente
pnpm test:frontend:list  # Lista los tests detectados por Jest
pnpm test:backend        # Pytest completo para el backend
pnpm test:backend:cov    # Pytest con cobertura para backend
```

Si preferís orquestar todo en un solo paso, mantenemos el objetivo clásico:

```bash
make test
```

- Backend: `python -m pytest backend/tests`
- Frontend: `npm --prefix frontend run test:dev`

- Cobertura en CI: `npm --prefix frontend run test:ci`

> ℹ️ **Cobertura en Jest**: los tests del frontend mantienen umbrales globales.
> Usa `npm --prefix frontend run test:ci` para validar cobertura estricta en CI.
> Durante el desarrollo utiliza `npm --prefix frontend run test:dev` para
> ejecutar suites filtradas sin fallos por cobertura.

### Smoke manual de la API

Cuando necesites validar rápidamente el flujo básico de autenticación y alertas
sin montar un entorno completo de pruebas, podés ejecutar esta secuencia de
`curl` desde una shell (`bash`/`zsh`). Asume el backend corriendo en
`http://127.0.0.1:8000`.

```bash
# Registrar un usuario
curl -s -X POST http://127.0.0.1:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@test.com","password":"demo1234"}' | jq

# Login y captura del token JWT
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@test.com","password":"demo1234"}' | jq -r .access_token)
echo "TOKEN=${TOKEN:0:20}..."

# Crear una alerta en el formato nuevo
curl -s -X POST http://127.0.0.1:8000/api/alerts \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"asset":"AAPL","channel":"push","conditions":[{"field":"price","op":">","value":150}]}' | jq

# Listar las alertas del usuario
curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/alerts | jq

# Simular una suscripción push (endpoint ficticio)
curl -s -X POST http://127.0.0.1:8000/api/push/subscribe \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"endpoint":"https://example.com/push/cli","keys":{"auth":"auth-key","p256dh":"p256dh-key"}}' | jq
```

## Logging estructurado

El backend utiliza utilidades basadas en `structlog` definidas en
[`backend/core/logging_config.py`](backend/core/logging_config.py). La función
`log_event` encapsula la escritura de eventos estructurados y añade
metadatos consistentes:

- `service`: servicio o módulo que emite el log (por ejemplo, `alerts`).
- `event`: descripción corta y accionable del evento.
- `timestamp`: ISO 8601 en UTC generado automáticamente.
- `error`: campo opcional para adjuntar mensajes de excepción o trazas.

Podés enlazar contexto adicional mediante kwargs (`user_id`, `payload`, etc.).
El logger serializa el evento como JSON, lo que facilita enviarlo a sistemas de
observabilidad sin parseos adicionales.

## Observabilidad (logs y métricas)

- **Logging estructurado**: el backend utiliza `structlog` con salida JSON. Ajusta
  el nivel con `BULLBEAR_LOG_LEVEL` (`INFO`, `DEBUG`, etc.).
- **Métricas Prometheus**: la API expone `/metrics` con histogramas de latencia y
  contadores por endpoint listos para ser scrapeados por Prometheus/Grafana.

## Chat persistente y notificaciones push

- Las conversaciones del asistente se guardan por usuario y sesión. El endpoint
  `POST /ai/chat` crea sesiones automáticamente y `GET /ai/history/{session_id}`
  devuelve el historial para hidratar el chat en el frontend.
- El frontend conserva el `session_id` en `localStorage` y revalida el historial
  con SWR al montar el componente de chat, garantizando continuidad tras
  recargas o nuevos inicios de sesión.
- El Service Worker (`frontend/public/sw.js`) gestiona la recepción de
  notificaciones push. El hook `usePushNotifications` registra la suscripción
  usando la clave VAPID pública y expone el estado al dashboard.
- Para emitir pruebas de push, usa `POST /push/subscribe` en el backend y la
  utilidad `backend/services/push_service.py` para despachar mensajes mediante
  `pywebpush`. Cuando `pywebpush` no está instalado, el servicio degrada de
  forma segura registrando el intento en logs.

## Roadmap MVP

- [x] **Crypto** – precios en vivo desde proveedores externos.
- [x] **Forex** – cotizaciones de pares principales con caché.
- [x] **AI chat básico** – asistente conversacional con contexto de mercado.
- [x] **News** – agregador de noticias financieras y cripto.
- [x] **Alertas** – creación, listado, actualización y envío de alertas personalizadas.
- [ ] **Automatización avanzada** – integración con brokers y ejecución de órdenes.

## Recursos adicionales

- [Documentación FastAPI](https://fastapi.tiangolo.com/)
- [Documentación Next.js](https://nextjs.org/docs)
- [SQLAlchemy 2.x](https://docs.sqlalchemy.org/)

¡Sugerencias y contribuciones son bienvenidas! Abre un issue o PR para seguir
iterando sobre el asistente financiero inteligente de BullBearBroker.

## 🔧 Desarrollo rápido

```bash
python -m pip install -r backend/requirements.txt
python -m pip install -r backend/requirements-dev.txt
pre-commit install
make lint
make test
Generar OpenAPI/Postman:
make openapi      # postman/openapi.json
make postman      # postman/BullBearBroker.postman_collection.json
```

🧪 CI
Este repo incluye GitHub Actions (.github/workflows/ci.yml) con lint (ruff/black/isort) y tests (pytest) en Python 3.12.

✅ Aceptación (debe pasar)
python -m pip install -r backend/requirements.txt
python -m pip install -r backend/requirements-dev.txt
pre-commit run --all-files (o make lint)
pytest backend -q (debe quedar en verde)
make postman crea postman/BullBearBroker.postman_collection.json
