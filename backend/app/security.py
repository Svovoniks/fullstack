from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta, timezone

PASSWORD_ITERATIONS = 100_000
ACCESS_TOKEN_LIFETIME = timedelta(minutes=15)
REFRESH_TOKEN_LIFETIME = timedelta(days=7)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return f"{PASSWORD_ITERATIONS}${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(derived_key).decode()}"


def verify_password(password: str, stored_hash: str) -> bool:
    iterations_raw, salt_raw, digest_raw = stored_hash.split("$", maxsplit=2)
    salt = base64.urlsafe_b64decode(salt_raw.encode())
    expected_digest = base64.urlsafe_b64decode(digest_raw.encode())
    derived_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations_raw))
    return hmac.compare_digest(derived_key, expected_digest)


def create_access_token(user_id: str, username: str) -> tuple[str, datetime]:
    expires_at = _utc_now() + ACCESS_TOKEN_LIFETIME
    payload = {
        "sub": user_id,
        "username": username,
        "exp": int(expires_at.timestamp()),
        "type": "access",
    }
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    secret = os.getenv("APP_SECRET_KEY", "development-secret-key").encode("utf-8")
    signature = hmac.new(secret, payload_bytes, hashlib.sha256).digest()
    token = ".".join(
        [
            base64.urlsafe_b64encode(payload_bytes).decode().rstrip("="),
            base64.urlsafe_b64encode(signature).decode().rstrip("="),
        ]
    )
    return token, expires_at


def decode_access_token(token: str) -> dict[str, str | int]:
    payload_part, signature_part = token.split(".", maxsplit=1)
    payload_bytes = base64.urlsafe_b64decode(f"{payload_part}==")
    signature = base64.urlsafe_b64decode(f"{signature_part}==")
    secret = os.getenv("APP_SECRET_KEY", "development-secret-key").encode("utf-8")
    expected_signature = hmac.new(secret, payload_bytes, hashlib.sha256).digest()

    if not hmac.compare_digest(signature, expected_signature):
        raise ValueError("Invalid token signature")

    payload = json.loads(payload_bytes.decode("utf-8"))
    if payload.get("type") != "access":
        raise ValueError("Invalid token type")

    if int(payload["exp"]) <= int(_utc_now().timestamp()):
        raise ValueError("Token expired")

    return payload


def create_refresh_token() -> tuple[str, datetime]:
    expires_at = _utc_now() + REFRESH_TOKEN_LIFETIME
    return secrets.token_urlsafe(48), expires_at
