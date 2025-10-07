"""Core configuration helpers for BullBearBroker backend."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any


LOGGER = logging.getLogger(__name__)


class Settings:
    """Centralized access to environment-driven configuration values."""

    def __init__(self) -> None:
        self.APP_ENV: str = os.getenv("APP_ENV", "local")
        self.VAPID_PUBLIC_KEY: str | None = os.getenv("VAPID_PUBLIC_KEY")
        self.VAPID_PRIVATE_KEY: str | None = os.getenv("VAPID_PRIVATE_KEY")

        if not self.VAPID_PUBLIC_KEY or not self.VAPID_PRIVATE_KEY:
            self._load_vapid_keys_from_file()

        if not self.VAPID_PUBLIC_KEY or not self.VAPID_PRIVATE_KEY:
            LOGGER.warning("VAPID keys not found")

    def _load_vapid_keys_from_file(self) -> None:
        """Attempt to populate VAPID keys from a local JSON file."""

        keys_path = os.getenv("VAPID_KEYS_PATH", "vapid_keys.json")
        candidate_paths = self._candidate_paths(keys_path)

        for path in candidate_paths:
            try:
                with path.open("r", encoding="utf-8") as file:
                    payload: dict[str, Any] = json.load(file)
            except FileNotFoundError:
                continue
            except (OSError, json.JSONDecodeError):
                LOGGER.warning("Failed to read VAPID keys from %s", path, exc_info=True)
                continue

            self.VAPID_PUBLIC_KEY = payload.get("publicKey") or payload.get(
                "public_key"
            )
            self.VAPID_PRIVATE_KEY = payload.get("privateKey") or payload.get(
                "private_key"
            )

            if self.VAPID_PUBLIC_KEY and self.VAPID_PRIVATE_KEY:
                return

        # No valid keys found across candidates – keep existing values (likely ``None``).

    def _candidate_paths(self, filename: str) -> list[Path]:
        base_path = Path(filename)
        if base_path.is_absolute():
            return [base_path]

        here = Path(__file__).resolve()
        candidates = [
            Path(filename),
            here.parent / filename,
            here.parents[1] / filename,
            here.parents[2] / filename,
        ]
        # Ensure uniqueness while preserving order
        seen: set[Path] = set()
        ordered_candidates: list[Path] = []
        for candidate in candidates:
            try:
                resolved = candidate.resolve()
            except FileNotFoundError:
                resolved = candidate
            if resolved not in seen:
                seen.add(resolved)
                ordered_candidates.append(candidate)
        return ordered_candidates


settings = Settings()

# Backwards compatibility for modules that import module-level constants.
VAPID_PUBLIC_KEY = settings.VAPID_PUBLIC_KEY or ""
VAPID_PRIVATE_KEY = settings.VAPID_PRIVATE_KEY or ""
