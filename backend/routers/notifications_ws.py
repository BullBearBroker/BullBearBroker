# 🧩 Bloque 9A

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from backend.services.notification_dispatcher import manager

# Intenta importar el decoder de access token del proyecto.
# Si el proyecto usa otro nombre, ajustarlo (sin duplicar lógica).
try:
    from backend.core.security import decode_access  # tipo: (str) -> dict | None
except Exception:
    decode_access = None  # fallback; deberá existir en el proyecto real

router = APIRouter()


async def _resolve_user_id_from_ws(websocket: WebSocket) -> str | None:
    """
    Extrae el token de query (?token=) o header Authorization y retorna user_id (sub).
    Cierra el socket con 1008 si no es válido.
    """
    # Query param ?token=
    token = websocket.query_params.get("token")
    if not token:
        # Header Authorization: Bearer xxx
        auth = websocket.headers.get("authorization") or websocket.headers.get(
            "Authorization"
        )
        if auth and auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1]

    if not token or decode_access is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None

    try:
        payload = decode_access(token)  # debe devolver dict con 'sub' o user_id
        user_id = str(payload.get("sub") or payload.get("user_id"))
        if not user_id:
            raise ValueError("no sub in token")
        return user_id
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None


@router.websocket("/ws/notifications")
async def notifications_ws(websocket: WebSocket):
    # Requiere conectarse con token válido
    user_id = await _resolve_user_id_from_ws(websocket)
    if not user_id:
        return
    await manager.connect(user_id, websocket)
    try:
        # Loop de escucha: recibimos pings del cliente, o eventos controlados.
        while True:
            _ = await websocket.receive_text()
            # Opcional: podríamos soportar comandos del cliente (pong, ack, etc.)
            # Por ahora, sólo ignoramos; el canal es "server -> client".
    except WebSocketDisconnect:
        await manager.disconnect(user_id, websocket)
    except Exception:
        # Cualquier error inesperado: cerrar conexión limpiamente
        await manager.disconnect(user_id, websocket)
        try:
            await websocket.close()
        except Exception:
            pass
