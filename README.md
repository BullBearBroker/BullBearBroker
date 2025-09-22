## BullBearBroker

### Requisitos previos

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/) (Docker Desktop ya lo incluye)
- Opcional: `make` si prefieres ejecutar comandos abreviados

### Variables de entorno

Crea un archivo `.env` en la raíz del proyecto con las variables necesarias para la API. Puedes usar el siguiente ejemplo como punto de partida:

```env
# Seguridad JWT
BULLBEARBROKER_SECRET_KEY="coloca_aquí_una_clave_aleatoria_segura"
# BULLBEARBROKER_JWT_ALGORITHM="HS256"  # opcional

# Credenciales para la base de datos (opcional si usas docker-compose por defecto)
# POSTGRES_USER=bullbear
# POSTGRES_PASSWORD=bullbear
# POSTGRES_DB=bullbear

# Claves para servicios externos (todas opcionales)
# ALPHA_VANTAGE_API_KEY=
# TWELVEDATA_API_KEY=
# COINGECKO_API_KEY=
# COINMARKETCAP_API_KEY=
# NEWSAPI_API_KEY=
# CRYPTOPANIC_API_KEY=
```

> 💡 Genera una clave segura ejecutando `python -c "import secrets; print(secrets.token_urlsafe(64))"`.

Si la variable `BULLBEARBROKER_SECRET_KEY` no está definida, el backend creará una clave aleatoria en cada arranque, lo que invalida cualquier token emitido previamente.

### Ejecución con Docker Compose

1. Construye e inicia los servicios (backend, PostgreSQL y Redis):

   ```bash
   docker compose up --build
   ```

   El backend quedará disponible en [http://localhost:8000](http://localhost:8000).

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

Actualmente, los modelos de SQLAlchemy se sincronizan automáticamente al iniciar el backend (`Base.metadata.create_all`). No existe todavía un flujo formal de migraciones, por lo que no es necesario ejecutar un comando adicional.

Si en el futuro se añade Alembic (u otra herramienta), podrás ejecutar las migraciones sobre los contenedores con un comando similar a:

```bash
docker compose run --rm backend alembic upgrade head
```

### Desarrollo sin Docker

Los scripts de `npm` siguen disponibles para desarrollo local sin contenedores:

1. Instala las dependencias del frontend con `npm install`.
2. Levanta el frontend estático con `npm run start` y accede a [http://localhost:8080](http://localhost:8080).
3. Inicia el backend con `npm run backend` (lanza Uvicorn en [http://localhost:8000](http://localhost:8000)).

Detén cada proceso con `Ctrl+C` cuando termines.
