import asyncio
import json

import websockets


async def test_websocket():
    try:
        async with websockets.connect("ws://127.0.0.1:8000/ws/market-data") as ws:
            print("✅ Conectado exitosamente al WebSocket!")

            # Enviar mensaje de prueba
            test_message = {"type": "test", "message": "Hola WebSocket!"}
            await ws.send(json.dumps(test_message))
            print(f"📤 Enviado: {test_message}")

            # Recibir respuesta
            response = await ws.recv()
            print(f"📥 Recibido: {response}")

    except Exception as e:
        print(f"❌ Error: {e}")


# Ejecutar la prueba
asyncio.run(test_websocket())
