# scripts/check_backend.py
import sys

import requests

BASE_URL = "http://127.0.0.1:8000"


def check_health():
    try:
        resp = requests.get(f"{BASE_URL}/api/health/", timeout=5)
        if resp.status_code == 200 and resp.json().get("status") == "ok":
            print("✅ Backend responde correctamente")
            return True
        else:
            print(f"⚠️ Respuesta inesperada: {resp.status_code} -> {resp.text}")
            return False
    except Exception as e:
        print(f"❌ No se pudo conectar al backend: {e}")
        return False


def check_docs():
    try:
        resp = requests.get(f"{BASE_URL}/docs", timeout=5)
        if resp.status_code == 200:
            print("✅ Documentación Swagger accesible")
            return True
        else:
            print(f"⚠️ Problema accediendo a /docs: {resp.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error al conectar con /docs: {e}")
        return False


if __name__ == "__main__":
    ok_health = check_health()
    ok_docs = check_docs()
    if not (ok_health and ok_docs):
        sys.exit(1)
