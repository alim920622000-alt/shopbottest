from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any

from fastapi import HTTPException, status


JWT_ALG = "HS256"
JWT_EXPIRE_SECONDS = int(os.getenv("API_JWT_EXPIRE_SECONDS", "86400"))


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("utf-8")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("utf-8"))


def _get_secret() -> str:
    secret = os.getenv("API_JWT_SECRET", "")
    if not secret:
        raise RuntimeError("API_JWT_SECRET is empty. Set it in environment or .env")
    return secret


def create_access_token(payload: dict[str, Any]) -> str:
    now = int(time.time())
    body = {
        **payload,
        "iat": now,
        "exp": now + JWT_EXPIRE_SECONDS,
    }
    header_json = json.dumps({"alg": JWT_ALG, "typ": "JWT"}, separators=(",", ":")).encode("utf-8")
    body_json = json.dumps(body, separators=(",", ":")).encode("utf-8")
    header = _b64url_encode(header_json)
    body_part = _b64url_encode(body_json)
    signing_input = f"{header}.{body_part}".encode("utf-8")
    signature = hmac.new(_get_secret().encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{header}.{body_part}.{_b64url_encode(signature)}"


def decode_access_token(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Некорректный токен")

    header_b64, payload_b64, signature_b64 = parts
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    expected = hmac.new(_get_secret().encode("utf-8"), signing_input, hashlib.sha256).digest()

    actual = _b64url_decode(signature_b64)
    if not hmac.compare_digest(expected, actual):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Некорректная подпись токена")

    payload_raw = _b64url_decode(payload_b64)
    payload: dict[str, Any] = json.loads(payload_raw.decode("utf-8"))

    if int(payload.get("exp", 0)) < int(time.time()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Срок действия токена истек")
    return payload
