from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import asyncio
import json
from datetime import datetime
import sys
import os

# Añadir el directorio backend al path para importaciones
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from aiohttp import ClientError

from services.alert_service import alert_service
from services.market_service import market_service
from services.ai_service import ai_service
from services.sentiment_service import sentiment_service

# Importar routers de autenticación
try:
    from routers import auth
except (ImportError, RuntimeError):
    try:
        from backend.routers import auth
    except (ImportError, RuntimeError):
        from fastapi import APIRouter
        auth = APIRouter()
        @auth.get("/test")
        def auth_test():
            return {"message": "Auth module placeholder"}

try:
    from routers.markets import router as markets_router, get_crypto as get_crypto_handler
    from routers.news import router as news_router
    from routers.alerts import router as alerts_router
except (ImportError, RuntimeError):
    from backend.routers.markets import (  # type: ignore
        router as markets_router,
        get_crypto as get_crypto_handler,
    )
    from backend.routers.news import router as news_router  # type: ignore
    from backend.routers.alerts import router as alerts_router  # type: ignore

app = FastAPI(title="BullBearBroker API", version="1.0.0")
crypto_service = market_service.crypto_service
get_crypto = get_crypto_handler

# ✅ CONFIGURACIÓN CORS MEJORADA - ORIGENS COMPLETOS PARA DESARROLLO
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://[::1]:3000",       # ← ¡IPv6 LOCALHOST!
        "http://[::]:3000"        # ← ¡IPv6 TODAS LAS INTERFACES!
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Incluir routers de autenticación
if hasattr(auth, 'router'):
    app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
else:
    @app.post("/api/auth/register")
    async def register(user_data: dict):
        return {"message": "Auth module not fully implemented", "status": "placeholder"}

    @app.post("/api/auth/login")
    async def login(credentials: dict):
        return {"message": "Auth module not fully implemented", "status": "placeholder"}

app.include_router(markets_router)
app.include_router(news_router)
app.include_router(alerts_router)

# Modelo Pydantic para el request del chat
class ChatRequest(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None

# Configurar servicios
try:
    ai_service.set_market_service(market_service)
except Exception as e:
    print(f"Warning: Could not set market service: {e}")

# ✅ ALMACEN DE CONEXIONES WEB SOCKET MEJORADO
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.connection_data: Dict[WebSocket, Dict] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.connection_data[websocket] = {
            "connected_at": datetime.now(),
            "last_activity": datetime.now(),
            "ip": websocket.client.host if websocket.client else "unknown",
            "origin": websocket.headers.get("origin", "unknown")
        }
        print(f"✅ Nueva conexión WebSocket. Total: {len(self.active_connections)}")
        print(f"   Origen: {self.connection_data[websocket]['origin']}")
        print(f"   IP: {self.connection_data[websocket]['ip']}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            if websocket in self.connection_data:
                del self.connection_data[websocket]
            print(f"❌ Conexión WebSocket cerrada. Total: {len(self.active_connections)}")

    def update_activity(self, websocket: WebSocket):
        if websocket in self.connection_data:
            self.connection_data[websocket]["last_activity"] = datetime.now()

    async def broadcast(self, payload: Dict[str, Any]):
        message = json.dumps(payload)
        stale: List[WebSocket] = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                stale.append(connection)
        for connection in stale:
            self.disconnect(connection)

manager = ConnectionManager()


@app.on_event("startup")
async def startup_services():
    alert_service.register_websocket_manager(manager)
    await alert_service.start()


@app.on_event("shutdown")
async def shutdown_services():
    await alert_service.stop()

@app.get("/")
async def root():
    return {"message": "BullBearBroker API está funcionando!", "version": "1.0.0"}

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "services": {
            "market_service": "active",
            "ai_service": "active",
            "alert_service": "active" if alert_service.is_running else "idle",
            "websocket": "active"
        },
        "websocket_connections": len(manager.active_connections),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/market/chart/{symbol}")
async def get_market_chart(symbol: str, interval: str = "1d", range: str = "1mo"):
    try:
        image_b64 = await market_service.get_chart_image(
            symbol, interval=interval, range_=range
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensivo
        raise HTTPException(status_code=500, detail=f"Error generando gráfico: {exc}") from exc

    return {
        "symbol": symbol.upper(),
        "interval": interval,
        "range": range,
        "image": image_b64,
    }


@app.get("/api/market/sentiment/{symbol}")
async def get_market_sentiment(symbol: str):
    try:
        return await sentiment_service.get_sentiment(symbol)
    except Exception as exc:  # pragma: no cover - defensivo
        raise HTTPException(status_code=500, detail=f"Error obteniendo sentimiento: {exc}") from exc

@app.websocket("/ws/market-data")
async def websocket_market_data(websocket: WebSocket):
    print("🔌 Cliente intentando conectar WebSocket...")
    
    # ✅ VERIFICACIÓN DE ORIGEN MEJORADA (PERMITIR TODO TEMPORALMENTE)
    origin = websocket.headers.get("origin") or websocket.headers.get("Origin") or websocket.headers.get("ORIGIN") or "unknown"
    print(f"   Origen detectado: {origin}")
    
    # ✅ PERMITIR TODOS LOS ORÍGENES TEMPORALMENTE PARA DEBUG
    allow_all_origins = True  # ← CAMBIAR A False EN PRODUCCIÓN
    
    if not allow_all_origins:
        allowed_origins = [
            "http://localhost:3000", "http://127.0.0.1:3000", 
            "http://localhost:5500", "http://127.0.0.1:5500",
            "http://localhost:8000", "http://127.0.0.1:8000",
            "http://localhost:8080", "http://127.0.0.1:8080",
            "http://[::1]:3000", "http://[::]:3000",
            "null", "file://"
        ]
        
        if origin and origin not in allowed_origins and not origin.startswith("file://"):
            print(f"❌ Origen no permitido: {origin}")
            await websocket.close(code=1008, reason="Origin not allowed")
            return
    
    await manager.connect(websocket)
    print(f"✅ Cliente conectado. Total: {len(manager.active_connections)}")
    
    try:
        # ✅ ENVIAR MENSAJE DE BIENVENIDA INMEDIATAMENTE
        await websocket.send_json({
            "type": "connection_established",
            "message": "Conexión WebSocket establecida correctamente",
            "timestamp": datetime.now().isoformat(),
            "connection_id": id(websocket)
        })
        
        # ✅ PRIMER ENVÍO DE DATOS CON MEJOR MANEJO DE ERRORES
        try:
            data = await market_service.get_top_performers()
            await websocket.send_json({
                "type": "market_data",
                "data": data,
                "timestamp": datetime.now().isoformat()
            })
            print("📊 Datos de mercado enviados via WebSocket")
        except Exception as e:
            print(f"⚠️ Error obteniendo datos iniciales: {e}")
            await websocket.send_json({
                "type": "error",
                "message": "Error obteniendo datos de mercado iniciales",
                "timestamp": datetime.now().isoformat()
            })

        # ✅ BUCLE PRINCIPAL MEJORADO CON RECONEXIÓN ROBUSTA
        while True:
            try:
                # Esperar mensaje del cliente (timeout más largo)
                data = await asyncio.wait_for(websocket.receive_text(), timeout=300.0)
                manager.update_activity(websocket)
                
                try:
                    message_data = json.loads(data)
                    
                    if message_data.get("type") == "ping":
                        # Responder a ping inmediatamente
                        await websocket.send_json({
                            "type": "pong",
                            "timestamp": datetime.now().isoformat(),
                            "received_at": message_data.get("timestamp")
                        })
                    elif message_data.get("type") == "get_market_data":
                        # Enviar datos de mercado
                        try:
                            market_data = await market_service.get_top_performers()
                            await websocket.send_json({
                                "type": "market_data",
                                "data": market_data,
                                "timestamp": datetime.now().isoformat()
                            })
                        except Exception as e:
                            print(f"⚠️ Error obteniendo datos de mercado: {e}")
                            await websocket.send_json({
                                "type": "error",
                                "message": "Error obteniendo datos de mercado",
                                "timestamp": datetime.now().isoformat()
                            })
                    else:
                        # Mensaje no reconocido
                        await websocket.send_json({
                            "type": "error",
                            "message": "Tipo de mensaje no reconocido",
                            "timestamp": datetime.now().isoformat()
                        })
                        
                except json.JSONDecodeError:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Mensaje JSON inválido",
                        "timestamp": datetime.now().isoformat()
                    })
                    
            except asyncio.TimeoutError:
                # ✅ ENVIAR HEARTBEAT PERIÓDICO (MANTIENE CONEXIÓN ACTIVA)
                try:
                    # Enviar heartbeat para mantener conexión activa
                    await websocket.send_json({
                        "type": "heartbeat",
                        "message": "Connection alive",
                        "timestamp": datetime.now().isoformat()
                    })
                    print(f"💓 Heartbeat enviado a conexión {id(websocket)}")
                except Exception as e:
                    print(f"⚠️ Error enviando heartbeat: {e}")
                    break  # Salir del bucle si no se puede enviar
                
            except WebSocketDisconnect:
                print("❌ Cliente desconectado normalmente")
                break
                
    except WebSocketDisconnect:
        print("❌ WebSocket desconectado por cliente")
    except Exception as e:
        print(f"❌ Error crítico en WebSocket: {str(e)}")
        # Intentar enviar mensaje de error antes de cerrar
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"Error de conexión: {str(e)}",
                "timestamp": datetime.now().isoformat()
            })
        except:
            pass  # Ignorar si no se puede enviar
    finally:
        manager.disconnect(websocket)
        print(f"🔌 Conexión WebSocket cerrada. Total: {len(manager.active_connections)}")

@app.get("/api/market/top-performers")
async def get_top_performers():
    try:
        data = await market_service.get_top_performers()
        return {"success": True, "data": data}
    except Exception as e:
        print(f"Error en top-performers: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/market/price/{symbol}")
async def get_price(symbol: str):
    try:
        asset_type = await market_service.detect_asset_type(symbol)
        price = await market_service.get_price(symbol.upper(), asset_type)
        
        if price:
            return {
                "success": True, 
                "symbol": symbol.upper(),
                "asset_type": asset_type,
                "data": price
            }
        else:
            raise HTTPException(status_code=404, detail=f"Precio no encontrado para {symbol}")
    except Exception as e:
        print(f"Error en price endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/market/orderbook/{symbol}")
async def get_orderbook(symbol: str, limit: int = 10):
    try:
        orderbook = await market_service.get_binance_orderbook(symbol.upper(), limit)
        if orderbook:
            return {
                "success": True, 
                "symbol": symbol.upper(),
                "data": orderbook
            }
        else:
            raise HTTPException(status_code=404, detail=f"Orderbook no encontrado para {symbol}")
    except Exception as e:
        print(f"Error en orderbook endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/market/klines/{symbol}")
async def get_klines(symbol: str, interval: str = "1h", limit: int = 24):
    try:
        klines = await market_service.get_binance_klines(symbol.upper(), interval, limit)
        if klines:
            return {
                "success": True, 
                "symbol": symbol.upper(),
                "interval": interval,
                "data": klines
            }
        else:
            raise HTTPException(status_code=404, detail=f"Klines no encontrados para {symbol}")
    except Exception as e:
        print(f"Error en klines endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat/message")
async def chat_message(request: ChatRequest):
    """
    Endpoint para enviar mensajes al asistente de IA
    """
    try:
        print(f"Received message: {request.message}")
        
        # Procesar el mensaje con el servicio de IA
        response = await ai_service.process_message(request.message, request.context)
        
        return {
            "success": True, 
            "response": response,
            "metadata": {
                "message_length": len(request.message),
                "response_length": len(response)
            }
        }
    except Exception as e:
        print(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/chat/message")
async def chat_message_get(message: str):
    """
    Versión GET del endpoint de chat para testing fácil
    """
    try:
        response = await ai_service.process_message(message)
        return {
            "success": True, 
            "response": response,
            "metadata": {
                "message_length": len(message),
                "response_length": len(response)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/market/symbols")
async def get_available_symbols():
    """
    Obtener lista de símbolos disponibles
    """
    try:
        symbols = {
            "stocks": ["AAPL", "TSLA", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "NFLX"],
            "crypto": ["BTC", "ETH", "BNB", "XRP", "ADA", "SOL", "DOT", 'DOGE', "AVAX", "MATIC", "LTC", "LINK"]
        }
        return {"success": True, "data": symbols}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@app.get("/api/debug/websockets")
async def debug_websockets():
    """Endpoint de debug para ver conexiones activas"""
    connections_info = []
    for ws, data in manager.connection_data.items():
        connections_info.append({
            "connection_id": id(ws),
            "connected_at": data["connected_at"].isoformat(),
            "last_activity": data["last_activity"].isoformat(),
            "ip": data["ip"],
            "origin": data["origin"]
        })
    
    return {
        "active_connections": len(manager.active_connections),
        "connections": connections_info,
        "status": "running"
    }

@app.get("/api/auth/test")
async def auth_test():
    """Endpoint de prueba para auth"""
    return {"message": "Auth endpoint is working!"}

@app.get("/api/debug/cors")
async def debug_cors():
    """Endpoint para debug de CORS"""
    return {
        "cors_enabled": True,
        "allowed_origins": [
            "http://localhost:3000", "http://127.0.0.1:3000", 
            "http://localhost:5500", "http://127.0.0.1:5500",
            "http://localhost:8000", "http://127.0.0.1:8000",
            "http://localhost:8080", "http://127.0.0.1:8080",
            "http://[::1]:3000", "http://[::]:3000",
            "null", "file://",
            "*"
        ],
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    print("🚀 Iniciando BullBearBroker API con soporte WebSocket y Auth...")
    print("📊 WebSocket disponible en: ws://localhost:8000/ws/market-data")  # ← CORREGIDO
    print("🔐 Endpoints Auth disponibles en: /api/auth/")
    print("🌐 CORS configurado para desarrollo (todos los orígenes permitidos)")
    print("🔧 Debug CORS disponible en: /api/debug/cors")
    print("💓 Heartbeat activado cada 30 segundos")
    print("⚠️  MODO DESARROLLO: CORS permitiendo todos los orígenes")
    uvicorn.run(app, host="0.0.0.0", port=8000, ws_ping_interval=10, ws_ping_timeout=10)
