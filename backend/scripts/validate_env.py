#!/usr/bin/env python
# QA: Backend env validator – prints report; exit 1 on critical missing

"""Backend env validator – prints report; exits 1 on critical missing."""

from __future__ import annotations

import json
import os
import sys
from urllib.parse import urlparse

PLACEHOLDER_HOSTS = {"hostname.supabase.co", "hostname.supabase.com"}

ERRORS: list[str] = []
WARNS: list[str] = []


def _has(key: str) -> bool:
    value = os.getenv(key)
    return value not in (None, "")


def _append_error(message: str) -> None:
    if message not in ERRORS:
        ERRORS.append(message)


def _append_warn(message: str) -> None:
    if message not in WARNS and message not in ERRORS:
        WARNS.append(message)


# Required
if not _has("APP_ENV"):
    _append_error("APP_ENV")
if not _has("JWT_SECRET"):
    _append_error("JWT_SECRET")
if not _has("JWT_ALGORITHM"):
    _append_error("JWT_ALGORITHM")

use_pool = os.getenv("DB_USE_POOL", "false").lower() == "true"

if use_pool:
    if not _has("SUPABASE_DB_POOL_URL"):
        _append_error("SUPABASE_DB_POOL_URL")
else:
    direct_url = os.getenv("SUPABASE_DB_URL")
    if not direct_url:
        _append_error("SUPABASE_DB_URL")
    else:
        host = urlparse(direct_url).hostname or ""
        if host.lower() in PLACEHOLDER_HOSTS:
            _append_error(
                "SUPABASE_DB_URL (DB host placeholder; use db.<project_ref>.supabase.co)"
            )

    if _has("SUPABASE_DB_POOL_URL"):
        _append_warn("SUPABASE_DB_POOL_URL (ignored while DB_USE_POOL=false)")
    if _has("DATABASE_URL"):
        _append_warn("DATABASE_URL (ignored while DB_USE_POOL=false)")
    if (
        not os.getenv("SUPABASE_DB_HOSTADDR")
        and direct_url
        and "hostaddr=" not in direct_url
    ):
        _append_warn(
            "SUPABASE_DB_HOSTADDR (define to force IPv4 when automatic resolution fails)"
        )  # QA

# Helpful warnings
for key in [
    "SUPABASE_DB_URL",
    "SUPABASE_DB_POOL_URL",
    "REDIS_URL",
    "VAPID_PUBLIC_KEY",
    "VAPID_PRIVATE_KEY",
    "VAPID_SUBJECT",
]:
    if not _has(key):
        _append_warn(key)

report = {"errors": ERRORS, "warnings": WARNS}
print(json.dumps(report, ensure_ascii=False))
sys.exit(1 if ERRORS else 0)
