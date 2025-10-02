#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.main import app  # si no existe aquí, ajusta a la ruta real sin romper el proyecto

import argparse
import json

from fastapi.openapi.utils import get_openapi

def export_openapi(dest: Path) -> dict:
    schema = get_openapi(
        title=app.title or "BullBearBroker API",
        version=getattr(app, "version", "0.0.0"),
        routes=app.routes,
    )
    dest.write_text(json.dumps(schema, indent=2), encoding="utf-8")
    return schema


def to_postman(schema: dict) -> dict:
    """
    Conversor mínimo OpenAPI -> Postman v2 (solo requests básicas).
    Suficiente para tener un collection utilizable sin dependencias extra.
    """
    info = schema.get("info", {})
    servers = schema.get("servers", [{"url": "http://localhost:8000"}])
    base_url = servers[0]["url"]

    items = []
    paths = schema.get("paths", {})
    for path, methods in paths.items():
        for method, spec in methods.items():
            name = spec.get("summary") or f"{method.upper()} {path}"
            items.append({
                "name": name,
                "request": {
                    "method": method.upper(),
                    "header": [{"key": "Content-Type", "value": "application/json"}],
                    "url": {
                        "raw": f"{base_url}{path}",
                        "protocol": base_url.split("://")[0],
                        "host": [base_url.split("://")[1]],
                        "path": [p for p in path.strip("/").split("/") if p],
                    },
                },
            })

    return {
        "info": {
            "name": info.get("title", "BullBearBroker API"),
            "_postman_id": "auto-generated",
            "description": info.get("description", ""),
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "item": items,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--export-openapi", action="store_true")
    parser.add_argument("--out", default="postman/BullBearBroker.postman_collection.json")
    parser.add_argument("--openapi-out", default="postman/openapi.json")
    args = parser.parse_args()

    out_path = Path(args.out)
    openapi_path = Path(args.openapi_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    schema = export_openapi(openapi_path)

    if not args.export_openapi:
        collection = to_postman(schema)
        out_path.write_text(json.dumps(collection, indent=2), encoding="utf-8")
        print(f"Wrote Postman collection to: {out_path}")
    else:
        print(f"Wrote OpenAPI to: {openapi_path}")


if __name__ == "__main__":
    main()
