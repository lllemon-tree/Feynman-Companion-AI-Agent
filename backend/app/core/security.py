from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

from backend.app.core.config import Settings, get_settings


ALGORITHM = "HS256"
password_hash = PasswordHash.recommended()
DUMMY_PASSWORD_HASH = password_hash.hash("dummy-password-for-timing-protection")


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        return password_hash.verify(password, encoded_hash)
    except UnknownHashError:
        return False


def create_access_token(
    user_id: str,
    username: str,
    *,
    settings: Settings | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    active_settings = settings or get_settings()
    expires_at = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=active_settings.auth_token_expire_minutes)
    )
    payload = {
        "sub": user_id,
        "username": username,
        "exp": expires_at,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, active_settings.auth_secret_key, algorithm=ALGORITHM)


def decode_access_token(
    token: str,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    active_settings = settings or get_settings()
    try:
        payload = jwt.decode(
            token,
            active_settings.auth_secret_key,
            algorithms=[ALGORITHM],
        )
    except InvalidTokenError as exc:
        raise ValueError("invalid or expired token") from exc

    if not payload.get("sub") or not payload.get("username"):
        raise ValueError("invalid token payload")
    return payload
