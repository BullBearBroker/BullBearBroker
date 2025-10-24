#!/usr/bin/env python3
"""
Utility to switch backend/.env.local into direct DB mode through the IPv4→IPv6 bridge.
The script is intentionally silent on secrets; it only writes sanitized updates.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


def load_env_lines(env_path: Path) -> List[str]:
    text = env_path.read_text(encoding="utf-8")
    # Preserve trailing newline semantics
    lines = text.splitlines()
    if text.endswith("\n"):
        lines.append("")
    return lines


def extract_existing_url(lines: List[str]) -> str | None:
    for raw in lines:
        if not raw.startswith("SUPABASE_DB_URL="):
            continue
        return raw.split("=", 1)[1]
    return None


def build_direct_url(
    *,
    existing_url: str | None,
    userinfo_env: str | None,
    bridge_host: str,
    bridge_port: str,
    default_db_name: str,
) -> str:
    scheme = "postgresql+psycopg"
    path = f"/{default_db_name}"
    query_pairs: Dict[str, str] = {}
    userinfo: str | None = None

    if existing_url:
        parsed = urlparse(existing_url)
        if parsed.scheme:
            scheme = parsed.scheme
        if parsed.path:
            path = parsed.path
        if parsed.query:
            query_pairs = dict(parse_qsl(parsed.query, keep_blank_values=True))
        netloc = parsed.netloc
        if netloc and "@" in netloc:
            userinfo = netloc.rsplit("@", 1)[0]
    if not userinfo and userinfo_env:
        userinfo = userinfo_env

    if not userinfo:
        raise RuntimeError(
            "No se encontraron credenciales para SUPABASE_DB_URL. "
            "Definí SUPABASE_DIRECT_USER y SUPABASE_DIRECT_PASS_URLENC antes de ejecutar."
        )

    if query_pairs.get("sslmode") not in {"require", "verify-full", "verify-ca"}:
        query_pairs["sslmode"] = "require"

    netloc = f"{userinfo}@{bridge_host}:{bridge_port}"
    new_query = urlencode(query_pairs, doseq=True)
    parsed_result = (scheme, netloc, path, "", new_query, "")
    return urlunparse(parsed_result)


def sanitize_userinfo(user: str | None, password_urlenc: str | None) -> str | None:
    if user and password_urlenc:
        if ":" in user:
            raise RuntimeError("SUPABASE_DIRECT_USER no debe contener ':'")
        return f"{user}:{password_urlenc}"
    return None


def update_env(
    lines: List[str],
    *,
    direct_url: str,
) -> List[str]:
    keys_to_remove = {"SUPABASE_DB_HOSTADDR", "SUPABASE_DB_POOL_URL", "DATABASE_URL"}
    updated: List[str] = []
    seen_keys: Dict[str, bool] = {"DB_USE_POOL": False, "SUPABASE_DB_URL": False}

    for raw in lines:
        stripped = raw.strip()
        if stripped == "":
            updated.append(raw)
            continue
        if stripped.startswith("#") or "=" not in raw:
            updated.append(raw)
            continue

        key, _, value = raw.partition("=")
        if key in keys_to_remove:
            continue
        if key == "DB_USE_POOL":
            updated.append("DB_USE_POOL=false")
            seen_keys["DB_USE_POOL"] = True
            continue
        if key == "SUPABASE_DB_URL":
            # omit; we'll append the fresh one at the end
            seen_keys["SUPABASE_DB_URL"] = True
            continue

        updated.append(raw)

    if not seen_keys["DB_USE_POOL"]:
        if updated and updated[-1] != "":
            updated.append("")
        updated.append("DB_USE_POOL=false")

    if updated and updated[-1] != "":
        updated.append("")
    updated.append(f"SUPABASE_DB_URL={direct_url}")
    return updated


def persist_env(env_path: Path, lines: List[str]) -> None:
    # Ensure single trailing newline
    if lines and lines[-1] == "":
        content = "\n".join(lines[:-1]) + "\n"
    else:
        content = "\n".join(lines) + ("\n" if lines else "")
    env_path.write_text(content, encoding="utf-8")


def main() -> int:
    project_root = Path(os.environ["BBB_PROJECT_ROOT"])
    env_path = project_root / "backend/.env.local"

    bridge_host = os.environ["BBB_BRIDGE_HOST"]
    bridge_port = os.environ["BBB_BRIDGE_PORT"]
    default_db_name = os.environ["BBB_DIRECT_DB_NAME"]
    user = os.environ.get("BBB_DIRECT_USER")
    password_urlenc = os.environ.get("BBB_DIRECT_PASS_URLENC")

    lines = load_env_lines(env_path)
    existing_url = extract_existing_url(lines)
    userinfo_env = sanitize_userinfo(user, password_urlenc)
    direct_url = build_direct_url(
        existing_url=existing_url,
        userinfo_env=userinfo_env,
        bridge_host=bridge_host,
        bridge_port=bridge_port,
        default_db_name=default_db_name,
    )

    new_lines = update_env(lines, direct_url=direct_url)
    persist_env(env_path, new_lines)

    print("env_local_direct_mode_applied")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
