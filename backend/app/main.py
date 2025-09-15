from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
from services.market_service import market_service
from services.ai_service import ai_service

app = FastAPI(title="BullBearBroker API", version="1.0.0")

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5500", "file://"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modelo Pydantic para el request del chat
class ChatRequest(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None

# Configurar servicios
ai_service.set_market_service(market_service)

@app.get("/")
async def root():
    return {"message": "BullBearBroker API Running", "status": "active"}

@app.get("/api/health")
async def health_check():
    """Endpoint para verificar que la API está funcionando"""
    return {
        "status": "healthy",
        "services": {
            "market_service": "active",
            "ai_service": "active"
        }
    }

@app.get("/api/market/top-performers")
async def get_top_performers():
    try:
        data = await market_service.get_top_performers()
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/market/price/{symbol}")
async def get_price(symbol: str):
    try:
        # Detectar automáticamente el tipo de activo
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
            "crypto": ["BTC", "ETH", "BNB", "XRP", "ADA", "SOL", "DOT", "DOGE"]
        }
        return {"success": True, "data": symbols}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)