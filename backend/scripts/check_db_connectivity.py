#!/usr/bin/env python
"""QA 2.1: Supabase connectivity smoke test."""

import json
import os
import sys

from sqlalchemy import text

from backend.database import engine


def main() -> None:
    mode = (
        "pgbouncer" if os.getenv("DB_USE_POOL", "false").lower() == "true" else "direct"
    )
    timeout = os.getenv("DB_CONNECT_TIMEOUT", "10")

    try:
        with engine.connect() as conn:
            version = conn.execute(text("SELECT version();")).scalar_one()
            pong = conn.execute(text("SELECT 1;"))
            select_one = pong.scalar_one()
            info = {
                "version": version,
                "select1": select_one,
                "mode": mode,
                "timeout": timeout,
            }
            print(json.dumps({"status": "ok", "info": info}, ensure_ascii=False))
            sys.exit(0)
    except Exception as exc:  # pragma: no cover - logging intent only
        print(json.dumps({"status": "error", "error": str(exc)[:400]}))
        sys.exit(1)


if __name__ == "__main__":
    main()
