from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from services.market_service import market_service
from services.ai_service import ai_service

app = FastAPI(title="BullBearBroker API", version="1.0.0")

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5500"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configurar servicios
ai_service.set_market_service(market_service)

@app.get("/")
async def root():
    return {"message": "BullBearBroker API Running", "status": "active"}

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
        price = await market_service.get_price(symbol.upper())
        if price:
            return {"success": True, "symbol": symbol.upper(), "data": price}
        else:
            raise HTTPException(status_code=404, detail=f"Precio no encontrado para {symbol}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat/message")
async def chat_message(message: str):
    try:
        response = await ai_service.process_message(message)
        return {"success": True, "response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)