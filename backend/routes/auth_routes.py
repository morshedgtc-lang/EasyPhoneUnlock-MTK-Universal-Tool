"""User authentication: register, login (JWT), refresh, logout."""
import jwt
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.core.database import get_db
from backend.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    needs_rehash,
    verify_password,
)
from backend.deps import client_ip, get_current_user, limiter
from backend.models.models import (
    CreditLog,
    LoginAttempt,
    RefreshToken,
    SystemConfig,
    User,
    as_utc,
    utcnow,
)
from backend.schemas import LoginRequest, RefreshRequest, RegisterRequest

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


def _maintenance_on(db: Session) -> bool:
    row = db.get(SystemConfig, "maintenance_mode")
    return bool(row and row.value == "1")


def _check_lockout(db: Session, username: str, ip: str) -> None:
    key = f"{username}|{ip}"
    att = db.scalar(select(LoginAttempt).where(LoginAttempt.key == key))
    if att and att.locked_until and as_utc(att.locked_until) > utcnow():
        raise HTTPException(429, "Too many failed attempts. Try again later.")


def _record_failure(db: Session, username: str, ip: str) -> None:
    key = f"{username}|{ip}"
    att = db.scalar(select(LoginAttempt).where(LoginAttempt.key == key))
    if not att:
        att = LoginAttempt(key=key, failures=0)
        db.add(att)
    att.failures += 1
    att.updated_at = utcnow()
    if att.failures >= settings.LOGIN_MAX_ATTEMPTS:
        att.locked_until = utcnow() + timedelta(minutes=settings.LOGIN_LOCKOUT_MIN)
        att.failures = 0
    db.commit()


def _clear_failures(db: Session, username: str, ip: str) -> None:
    key = f"{username}|{ip}"
    att = db.scalar(select(LoginAttempt).where(LoginAttempt.key == key))
    if att:
        db.delete(att)
        db.commit()


@router.post("/register")
@limiter.limit("5/minute")
def register(req: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    ip = client_ip(request)
    if db.scalar(select(User).where(User.username == req.username)):
        raise HTTPException(400, "Username already exists.")

    user = User(
        username=req.username,
        password_hash=hash_password(req.password),
        email=req.email,
        credits=settings.REGISTER_BONUS_CREDITS,
        hwid=None,
        is_active=True,
        is_admin=False,
    )
    db.add(user)
    db.flush()
    db.add(CreditLog(
        user_id=user.id, amount=settings.REGISTER_BONUS_CREDITS,
        operation="REGISTER_BONUS", hwid=req.hwid or None, ip=ip,
    ))
    db.commit()
    return {
        "status": "success",
        "message": f"Account created. {settings.REGISTER_BONUS_CREDITS} trial credits granted.",
        "user_id": user.id,
    }


@router.post("/login")
@limiter.limit("10/minute")
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    ip = client_ip(request)
    if _maintenance_on(db):
        raise HTTPException(503, "Server is under maintenance. Please try again later.")

    _check_lockout(db, req.username, ip)

    user = db.scalar(select(User).where(User.username == req.username))
    if not user or not verify_password(req.password, user.password_hash):
        _record_failure(db, req.username, ip)
        raise HTTPException(401, "Invalid username or password.")
    if not user.is_active:
        raise HTTPException(403, "Account disabled by administrator.")

    # Upgrade legacy / weak hashes transparently on successful login.
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(req.password)

    # HWID: bind on first login, enforce thereafter.
    if not user.hwid:
        if not req.hwid:
            raise HTTPException(400, "Missing device identifier (HWID).")
        user.hwid = req.hwid
    elif user.hwid != req.hwid:
        raise HTTPException(403, "HWID mismatch. This license is bound to another PC. Contact admin.")

    user.last_ip = ip
    user.last_login = utcnow()

    access = create_access_token(user.id, user.username, user.hwid, user.is_admin)
    refresh, jti, exp = create_refresh_token(user.id)
    db.add(RefreshToken(jti=jti, user_id=user.id, expires_at=exp))
    db.commit()
    _clear_failures(db, req.username, ip)

    return {
        "status": "success",
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "user": {
            "id": user.id, "username": user.username, "email": user.email,
            "credits": user.credits, "is_admin": user.is_admin, "hwid": user.hwid, "ip": ip,
        },
    }


@router.post("/refresh")
def refresh(req: RefreshRequest, db: Session = Depends(get_db)):
    try:
        payload = decode_token(req.refresh_token)
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid refresh token.")
    if payload.get("typ") != "refresh":
        raise HTTPException(401, "Wrong token type.")

    stored = db.scalar(select(RefreshToken).where(RefreshToken.jti == payload.get("jti")))
    if not stored or stored.revoked or as_utc(stored.expires_at) <= utcnow():
        raise HTTPException(401, "Refresh token revoked or expired.")

    user = db.get(User, int(payload.get("sub", 0)))
    if not user or not user.is_active:
        raise HTTPException(403, "Account unavailable.")

    access = create_access_token(user.id, user.username, user.hwid or "", user.is_admin)
    return {"status": "success", "access_token": access, "token_type": "bearer"}


@router.post("/logout")
def logout(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Revoke all of this user's refresh tokens."""
    for tok in db.scalars(select(RefreshToken).where(RefreshToken.user_id == user.id)):
        tok.revoked = True
    db.commit()
    return {"status": "success", "message": "Logged out everywhere."}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {
        "status": "success",
        "user": {
            "id": user.id, "username": user.username, "email": user.email,
            "credits": user.credits, "is_admin": user.is_admin, "hwid": user.hwid,
        },
    }
