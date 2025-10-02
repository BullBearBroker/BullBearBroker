from __future__ import annotations

import hashlib
import string
from pathlib import Path
from threading import RLock

from backend.utils.config import Config


class PasswordBreachDetector:
    """Offline detector that checks passwords against a local dataset."""

    def __init__(self, dataset_path: str | None = None) -> None:
        self._dataset_path = dataset_path
        self._plain_passwords: set[str] | None = None
        self._sha1_passwords: set[str] | None = None
        self._lock = RLock()

    def configure(self, dataset_path: str | None) -> None:
        with self._lock:
            self._dataset_path = dataset_path
            self._plain_passwords = None
            self._sha1_passwords = None

    def _load_dataset(self) -> tuple[set[str], set[str]]:
        plain: set[str] = set()
        hashed: set[str] = set()
        if not self._dataset_path:
            return plain, hashed

        path = Path(self._dataset_path)
        if not path.exists() or not path.is_file():
            return plain, hashed

        try:
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    token = line.strip()
                    if not token:
                        continue
                    token = token.split(":", 1)[0]
                    if len(token) == 40 and all(c in string.hexdigits for c in token):
                        hashed.add(token.lower())
                    else:
                        plain.add(token)
        except OSError:
            return set(), set()

        return plain, hashed

    def _ensure_loaded(self) -> None:
        if self._plain_passwords is not None and self._sha1_passwords is not None:
            return
        with self._lock:
            if self._plain_passwords is not None and self._sha1_passwords is not None:
                return
            plain, hashed = self._load_dataset()
            self._plain_passwords = plain
            self._sha1_passwords = hashed

    def is_compromised(self, password: str) -> bool:
        if not password:
            return False
        self._ensure_loaded()
        if self._plain_passwords is None or self._sha1_passwords is None:
            return False

        candidate = password.strip()
        if not candidate:
            return False

        if candidate in self._plain_passwords or candidate.lower() in self._plain_passwords:
            return True

        sha1_hash = hashlib.sha1(candidate.encode("utf-8")).hexdigest()
        return bool(
            sha1_hash in self._sha1_passwords
            or sha1_hash.upper() in self._sha1_passwords
        )


_default_dataset = Config.PASSWORD_BREACH_DATASET_PATH
if not _default_dataset:
    candidate = Path(__file__).resolve().parent.parent / "data" / "compromised_passwords.txt"
    if candidate.exists():
        _default_dataset = str(candidate)

password_breach_detector = PasswordBreachDetector(_default_dataset)


def configure_password_detector(dataset_path: str | None) -> None:
    password_breach_detector.configure(dataset_path)


def is_password_compromised(password: str) -> bool:
    if not Config.ENABLE_PASSWORD_BREACH_CHECK:
        return False
    return password_breach_detector.is_compromised(password)


__all__ = [
    "configure_password_detector",
    "is_password_compromised",
    "password_breach_detector",
    "PasswordBreachDetector",
]
