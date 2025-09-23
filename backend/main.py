from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Routers de la app
from backend.routers import alerts, markets, news, auth, ai
from backend.routers import health  # nuevo router de salud

app = FastAPI(
    title="BullBearBroker API",
    version="0.1.0",
    description="🚀 API conversacional para análisis financiero en tiempo real",
)

# Configuración de CORS (para el frontend en localhost:3000)
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Endpoint raíz
@app.get("/")
def read_root():
    return {"message": "🚀 BullBearBroker API corriendo correctamente!"}

# Routers registrados
app.include_router(health.router)
app.include_router(alerts.router)
app.include_router(markets.router)
app.include_router(news.router)
app.include_router(auth.router)
app.include_router(ai.router)