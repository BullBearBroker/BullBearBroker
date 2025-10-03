"""Ligera implementación compatible con las partes usadas de PyOTP."""

from __future__ import annotations

import base64
import hmac
import secrets
import struct
import time
from hashlib import sha1
from urllib.parse import quote

__all__ = ["TOTP", "random_base32"]


def random_base32(length: int = 32) -> str:
    """Genera un secreto base32 utilizando caracteres válidos."""

    if length <= 0:
        raise ValueError("length must be positive")
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _normalize_secret(secret: str) -> bytes:
    if not secret:
        raise ValueError("secret must not be empty")
    normalized = secret.strip().replace(" ", "").upper()
    padding = (8 - len(normalized) % 8) % 8
    normalized += "=" * padding
    return base64.b32decode(normalized, casefold=True)


class TOTP:
    def __init__(
        self,
        secret: str,
        interval: int = 30,
        digits: int = 6,
    ) -> None:
        self._secret = secret
        self.interval = interval
        self.digits = digits

    def _generate_otp(self, counter: int) -> str:
        key = _normalize_secret(self._secret)
        msg = struct.pack("!Q", counter)
        digest = hmac.new(key, msg, sha1).digest()
        offset = digest[-1] & 0x0F
        code = (
            ((digest[offset] & 0x7F) << 24)
            | ((digest[offset + 1] & 0xFF) << 16)
            | ((digest[offset + 2] & 0xFF) << 8)
            | (digest[offset + 3] & 0xFF)
        )
        otp = code % (10**self.digits)
        return f"{otp:0{self.digits}d}"

    def at(self, for_time: float | int) -> str:
        counter = int(for_time // self.interval)
        return self._generate_otp(counter)

    def now(self) -> str:
        return self.at(time.time())

    def verify(
        self,
        code: str,
        valid_window: int = 0,
        for_time: float | None = None,
    ) -> bool:
        if not code:
            return False
        if for_time is None:
            for_time = time.time()
        try:
            int(code)
        except ValueError:
            return False
        target = str(code).zfill(self.digits)
        for offset in range(-valid_window, valid_window + 1):
            comparison_time = for_time + offset * self.interval
            if self.at(comparison_time) == target:
                return True
        return False

    def provisioning_uri(self, name: str, issuer_name: str | None = None) -> str:
        label = name
        if issuer_name:
            label = f"{issuer_name}:{name}"
        label = quote(label)
        issuer_param = f"&issuer={quote(issuer_name)}" if issuer_name else ""
        return f"otpauth://totp/{label}?secret={self._secret}{issuer_param}"
