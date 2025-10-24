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
├── .env.example            # Guía rápida hacia los ejemplos versionados
└── backend/tests/          # Suite de pruebas (autenticación, alertas, servicios...)
```

## Gestión de variables de entorno

El repositorio incluye plantillas sin secretos para cada servicio:

- `./.env.example`: índice rápido que explica dónde viven las variables reales.
- `backend/.env.example`: referencia del backend (copiala a `backend/.env.local`).
- `frontend/.env.example`: referencia del frontend (copiala a `frontend/.env.local`).

Pasos recomendados:

1. Copiá `backend/.env.example` a `backend/.env.local` y completá los valores necesarios solo en tu máquina.
2. Copiá `frontend/.env.example` a `frontend/.env.local`. Next.js solo expone variables que comienzan con `NEXT_PUBLIC_`.
3. No subas archivos `.env*` con secretos: el `.gitignore` ya los protege y los ejemplos son documentación únicamente.

Precedencia en runtime: variables ya presentes en el proceso > `.env.local` > `.env.staging`/`.env.production` > valores por defecto definidos en código. Los archivos `*.example` no se cargan automáticamente.

Scripts útiles:

- `make env-sync`: sincroniza `backend/.env.sample` desde el ejemplo principal.
- `make env-validate-backend`: ejecuta `backend/scripts/validate_env.py` dentro del servicio `api`.
- `make env-validate-frontend`: ejecuta `frontend/scripts/validate-env.mjs`.

Antes de levantar los servicios por primera vez:

```bash
cp backend/.env.example backend/.env.local
cp frontend/.env.example frontend/.env.local
```

Luego rellená los secretos manualmente y corré los validadores (`make env-validate-backend`, `make env-validate-frontend`) para verificar que no falte nada crítico.

## QA (flujo unificado)

1) Validar entornos
   ```bash
   make env-validate-backend
   make env-validate-frontend
   ```

2) QA completo (genera `qa/QA_SUMMARY.md`)
   ```bash
   make qa-full
   ```

Artefactos:
- `qa/backend-coverage.xml` (PyTest)
- `qa/frontend-coverage/` (Jest)
- `frontend/playwright-report/` (Playwright)

## Web Push

- Configurá `NEXT_PUBLIC_VAPID_PUBLIC_KEY` en `frontend/.env.local` y `VAPID_PRIVATE_KEY`,
  `VAPID_PUBLIC_KEY`, `VAPID_SUBJECT` en `backend/.env.local`. Sin claves reales el flujo queda en modo seguro.
- El `NotificationCenter` muestra un panel de depuración (solo en desarrollo) con acciones para pedir
  permisos, suscribirse/desuscribirse y disparar pruebas. Los logs visibles ayudan a diagnosticar navegadores.
- `make push-info` imprime si el backend carga las claves y qué valor tiene el frontend.
- `make push-test` ejecuta `backend/scripts/send_test_push.py` dentro del contenedor y envía una notificación
  básica a todas las suscripciones almacenadas.
- Compatibilidad:
  - **Chrome / Edge**: soporte completo; requiere gesto de usuario para solicitar permisos.
  - **Firefox**: soportado; la UI de permisos puede mostrarse fuera de foco, asegúrate de que la pestaña esté activa.
  - **Safari (macOS/iOS)**: requiere HTTPS o `http://localhost` y un gesto explícito; la notificación puede tardar
    unos segundos en mostrarse.
- Regla general: todas las suscripciones usan `userVisibleOnly: true` y el Service Worker muestra la notificación al
  recibir un `push` antes de resolver la promesa del evento.

### Web Push – Hardening

- Retries con backoff exponencial (410/404 → marcadas para pruning, 429 → reintentos con backoff progresivo, 5xx → reintentos cortos) y logging con `endpoint_fingerprint` para preservar privacidad.
- El servicio incrementa `fail_count`/`last_fail_at` y marca `pruning_marked` ante fallos críticos; ejecutá `make push-prune` (usa `backend/scripts/prune_stale_push_subs.py`) para limpiar suscripciones caducas.
- Los healthchecks incluyen el subcomponente `push` (`/api/health` → `services.push`) para verificar la presencia de claves VAPID sin exponerlas.
- Audit trail ligero via `AuditService`: altas/bajas y envíos de prueba quedan registrados en los logs de backend.
- La UI respeta la flag `NEXT_PUBLIC_FEATURE_NOTIFICATIONS_DEBUG` (solo activa en desarrollo) y deshabilita la suscripción cuando detecta claves placeholder.

## Secretos y .env

- `backend/.env` es la fuente de verdad local para credenciales y URIs sensibles (no se versiona). Copiá solo lo necesario a `backend/.env.local` y `frontend/.env.local` para ejecutar la app.
- `docker-compose.yml` utiliza `backend/.env.local` mediante `env_file`; nunca montes `.env.example` en contenedores.
- Los archivos `.env.example`/`.env.sample` incluyen únicamente placeholders (# QA) y se sincronizan con `tools/sync_env_examples.py`.
- Comandos útiles:
  - `make env-validate-backend`
  - `make env-validate-frontend`
  - `make secrets-scan`
- Regla estricta: ningún secreto real en código, docs ni archivos de ejemplo. Usa la checklist `qa/SECRETS_CHECKLIST.md` y el barrido `make secrets-scan` antes de publicar.
- # QA: En redes sin IPv6, define `SUPABASE_DB_HOSTADDR` en `backend/.env.local` para forzar IPv4 (el valor se inserta como `hostaddr=<ip>` en `SUPABASE_DB_URL`).
- # QA: Para forzar conexión directa sin PgBouncer usando un puente IPv4→IPv6, ejecutá `qa/direct_db_bridge.sh` (requiere `SUPABASE_DIRECT_USER` y `SUPABASE_DIRECT_PASS_URLENC` exportados si `backend/.env.local` no contiene las credenciales). El script levanta el puente con `socat`, reinicia el stack Docker y corre `make db-smoke`/`make db-migrate-direct`.
- Secuencia recomendada para verificar la conexión directa (IPv4):
  ```bash
  docker compose down
  docker compose up -d --build
  make db-force-ipv4
  make db-smoke
  make db-migrate-direct
  curl -s http://127.0.0.1:8000/api/health | jq .
  ```
- Si `make db-force-ipv4` devuelve `no_ipv4`, define manualmente `SUPABASE_DB_HOSTADDR=<IPv4>` en `backend/.env.local` y vuelve a ejecutar el comando.
- Evitar pegar comentarios (`# …`) en el shell: zsh los interpreta como comandos si se parte la línea.

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

## Running backend tests isolated on Supabase Session Pooler

Some CI/dev envs are IPv4-only. Use Supabase Session Pooler (IPv4) and isolate the test run in a dedicated schema to avoid residual data and PgBouncer prepared-statement issues.

### One-time
```bash
chmod +x qa/test_isolated.sh
```

```bash
# Replace with your Session Pooler DSN from Supabase (user/pass redacted here):
export SUPABASE_POOLER_URL='postgresql+psycopg://postgres.<project>:<password>@aws-1-us-east-2.pooler.supabase.com:5432/postgres'

# Run isolated suite (creates a test_YYYYmmdd_HHMMSS schema, migrates it to head and runs tests)
qa/test_isolated.sh

# Optional: custom schema name, extra pytest opts, and cleanup at the end:
qa/test_isolated.sh --schema my_ephemeral_schema --pytest-opts "-k rate_limits -q" --drop-after
```

The runner:
- forces TLS (`sslmode=require`) and disables prepared statements for PgBouncer via SQLAlchemy connect args;
- sets the `search_path` to the ephemeral schema;
- runs Alembic migrations on that schema;
- executes the suite without polluting other schemas.

Notes
- Keep secrets out of commits and terminals; the script masks user/password in its preview logs.
- If your Pooler hostname differs (e.g. `aws-0-…`), just set `SUPABASE_POOLER_URL` accordingly.
