"""Core configuration helpers for BullBearBroker backend."""

# 🧩 Bloque 8A
# Asegurar que la clave pública VAPID esté accesible desde las variables de entorno
import os

VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "")

# Añadir validación mínima
if not VAPID_PUBLIC_KEY:
    print("⚠️ Warning: VAPID_PUBLIC_KEY not set in environment.")
