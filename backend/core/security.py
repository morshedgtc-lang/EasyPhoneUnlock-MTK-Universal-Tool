"""
Password hashing (argon2) and JWT issuing/verification.

This is the single source of truth for all crypto. Never hash or verify a
password, or mint/decode a token, anywhere else.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt
from passlib.context import CryptContext

from backend.core.config import settings

# argon2id — modern, memory-hard. Legacy sha256 hashes (64 hex chars) are
# detected and transparently rehashed on next successful login.
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    # Back-compat: old DBs may hold a bare sha256 hex digest.
    if len(stored_hash) == 64 and all(c in "0123456789abcdef" for c in stored_hash.lower()):
        import hashlib
        return hashlib.sha256(password.encode()).hexdigest() == stored_hash.lower()
    try:
        return pwd_context.verify(password, stored_hash)
    except Exception:
        return False


def needs_rehash(stored_hash: str) -> bool:
    if len(stored_hash) == 64 and all(c in "0123456789abcdef" for c in stored_hash.lower()):
        return True  # legacy sha256
    return pwd_context.needs_update(stored_hash)


# --------------------------------------------------------------------------- #
# JWT
# --------------------------------------------------------------------------- #
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _encode(payload: dict[str, Any]) -> str:
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """Raises jwt.PyJWTError on any problem (expired, bad signature, etc.)."""
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])


def create_access_token(user_id: int, username: str, hwid: str, is_admin: bool) -> str:
    now = _now()
    return _encode({
        "typ": "access",
        "sub": str(user_id),
        "username": username,
        "hwid": hwid,
        "adm": is_admin,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.ACCESS_TOKEN_TTL_MIN)).timestamp()),
    })


def create_refresh_token(user_id: int) -> tuple[str, str, datetime]:
    """Returns (token, jti, expires_at). The jti is stored so it can be revoked."""
    now = _now()
    jti = uuid.uuid4().hex
    expires_at = now + timedelta(days=settings.REFRESH_TOKEN_TTL_DAYS)
    token = _encode({
        "typ": "refresh",
        "sub": str(user_id),
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    })
    return token, jti, expires_at


def create_operation_grant(user_id: int, operation: str, hwid: str, nonce: str) -> str:
    """Short-lived, signed permission to run ONE paid operation and fetch its payload."""
    now = _now()
    return _encode({
        "typ": "grant",
        "sub": str(user_id),
        "op": operation,
        "hwid": hwid,
        "nonce": nonce,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=settings.OPERATION_GRANT_TTL_SEC)).timestamp()),
    })


def new_nonce() -> str:
    return uuid.uuid4().hex
