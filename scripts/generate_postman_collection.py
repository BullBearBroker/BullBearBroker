"""Generate a Postman collection from the FastAPI OpenAPI schema."""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

os.environ.setdefault("ENV", "testing")
os.environ.setdefault("TESTING", "True")
os.environ.setdefault("BULLBEAR_SKIP_AUTOCREATE", "1")

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    # Ensure the backend package can be imported when invoking the script directly.
    sys.path.insert(0, str(ROOT_DIR))

from backend.main import app

def _build_url(path: str) -> Dict[str, Any]:
    parts = [segment for segment in path.strip("/").split("/") if segment]
    return {
        "raw": f"{{{{baseUrl}}}}{path}",
        "host": ["{{baseUrl}}"],
        "path": parts,
    }


def _build_body(operation: Dict[str, Any]) -> Dict[str, Any] | None:
    request_body = operation.get("requestBody")
    if not request_body:
        return None

    content = request_body.get("content", {})
    json_payload = content.get("application/json")
    if not json_payload:
        return None

    example = json_payload.get("example")
    if not example:
        examples = json_payload.get("examples") or {}
        if examples:
            example = next(iter(examples.values())).get("value")
    if not example:
        schema = json_payload.get("schema", {})
        example = schema.get("example")
    if example is None:
        return None

    return {
        "mode": "raw",
        "raw": json.dumps(example, indent=2, ensure_ascii=False),
        "options": {"raw": {"language": "json"}},
    }


def _build_query(operation: Dict[str, Any]) -> List[Dict[str, str]]:
    params = []
    for parameter in operation.get("parameters", []):
        if parameter.get("in") != "query":
            continue
        params.append(
            {
                "key": parameter.get("name", ""),
                "value": parameter.get("example", ""),
                "description": parameter.get("description", ""),
            }
        )
    return params


def _build_request(method: str, path: str, operation: Dict[str, Any]) -> Dict[str, Any]:
    body = _build_body(operation)
    request: Dict[str, Any] = {
        "method": method.upper(),
        "header": [],
        "url": _build_url(path),
        "description": operation.get("summary") or operation.get("description", ""),
    }
    query = _build_query(operation)
    if query:
        request["url"]["query"] = query
    if body:
        request["body"] = body
    return request


def build_collection() -> Dict[str, Any]:
    schema = app.openapi()
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for path, methods in schema.get("paths", {}).items():
        for method, operation in methods.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete", "options"}:
                continue
            tags = operation.get("tags") or ["general"]
            tag = tags[0]
            name = operation.get("summary") or f"{method.upper()} {path}"
            item = {
                "name": name,
                "request": _build_request(method, path, operation),
                "response": [],
            }
            grouped[tag].append(item)

    items = [
        {"name": tag, "item": sorted(entries, key=lambda entry: entry["name"])}
        for tag, entries in sorted(grouped.items())
    ]

    return {
        "info": {
            "name": "BullBearBroker API",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "item": items,
        "variable": [
            {"key": "baseUrl", "value": "http://localhost:8000"},
        ],
    }


if __name__ == "__main__":
    destination = Path("docs/postman_collection.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    collection = build_collection()
    destination.write_text(json.dumps(collection, indent=2, ensure_ascii=False))
    print(f"Postman collection generated at {destination}")
