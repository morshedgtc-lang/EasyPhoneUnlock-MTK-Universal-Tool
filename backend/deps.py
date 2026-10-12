"""Shared FastAPI dependencies: auth guards and the rate limiter."""
import jwt
from fastapi import Depends, Header, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.security import decode_token
from backend.models.models import User

limiter = Limiter(key_func=get_remote_address)


def client_ip(request: Request) -> str:
    # Honour a single proxy hop (Caddy/nginx sets X-Forwarded-For).
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Missing or malformed Authorization header.")
    return authorization.split(" ", 1)[1].strip()


def get_current_user(
    request: Request,
    authorization: str | None = Header(default=None),
    x_hwid: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """
    Validates the access token on EVERY protected request and re-checks that
    the token's HWID still matches the device making the call, and that the
    account is still active. This is what makes the security server-side: the
    client cannot fake any of it.
    """
    token = _bearer(authorization)
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Session expired. Please log in again.")
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid session token.")

    if payload.get("typ") != "access":
        raise HTTPException(401, "Wrong token type.")

    user = db.get(User, int(payload.get("sub", 0)))
    if not user:
        raise HTTPException(401, "Account not found.")
    if not user.is_active:
        raise HTTPException(403, "Account disabled by administrator.")

    # HWID must match the one baked into the token AND the current binding.
    token_hwid = payload.get("hwid")
    if user.hwid and token_hwid != user.hwid:
        raise HTTPException(403, "HWID mismatch for this session.")
    # If the caller sends X-HWID, it must agree with the token too.
    if x_hwid and token_hwid and x_hwid != token_hwid:
        raise HTTPException(403, "Device identity mismatch.")

    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(403, "Admin access required.")
    return user
