import asyncio
import websockets
import json

async def test_websocket():
    try:
        print("🔗 Conectando a WebSocket...")
        async with websockets.connect('ws://127.0.0.1:8000/ws/market-data') as ws:
            print("✅ Conectado exitosamente!")
            
            # Enviar mensaje de prueba
            test_message = {"type": "ping"}
            await ws.send(json.dumps(test_message))
            print(f"📤 Enviado: {test_message}")
            
            # Recibir respuesta
            response = await ws.recv()
            print(f"📥 Recibido: {response}")
            
            # Esperar datos de mercado
            print("⏳ Esperando datos de mercado...")
            market_data = await ws.recv()
            print(f"📊 Datos mercado: {market_data}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket())
