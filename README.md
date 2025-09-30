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
- **BULLBEAR_DEFAULT_USER / PASSWORD**: credenciales sembradas automáticamente para pruebas.
- **NEXT_PUBLIC_API_BASE_URL**: URL base que consume el frontend (en Docker se
  resuelve a `http://backend:8000`).

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
   pip install -r backend/requirements.txt
   export $(grep -v '^#' .env | xargs)  # o configura variables manualmente
   uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
   ```

2. **Frontend**
   ```bash
   cd frontend
   npm install
   npm run dev -- --hostname 0.0.0.0 --port 3000
   ```

Asegúrate de tener PostgreSQL y Redis ejecutándose en tu entorno local y que las
variables de entorno apunten a esas instancias.

## Pruebas automatizadas

Ejecuta toda la suite (backend + frontend) con un solo comando:

```bash
make test
```

- Backend: `python -m pytest backend/tests`
- Frontend: `npm --prefix frontend test -- --watch=false`

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
