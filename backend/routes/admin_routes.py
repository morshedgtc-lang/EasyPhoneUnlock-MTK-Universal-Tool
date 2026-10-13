"""Admin panel API. Admin auth uses the same JWT as users (with an admin claim)."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.security import (
    create_access_token,
    create_refresh_token,
    verify_password,
)
from backend.deps import client_ip, limiter, require_admin
from backend.models.models import AuditLog, CreditLog, RefreshToken, SystemConfig, User, utcnow
from backend.schemas import AdminLoginRequest, ConfigRequest, CreditRequest, UserActionRequest

router = APIRouter(prefix="/api/v1/admin", tags=["Admin Panel"])


@router.post("/login")
@limiter.limit("10/minute")
def admin_login(req: AdminLoginRequest, request: Request, db: Session = Depends(get_db)):
    # Credentials come in the BODY, never the query string.
    user = db.scalar(select(User).where(User.username == req.username, User.is_admin == True))  # noqa: E712
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(401, "Invalid admin credentials.")

    user.last_ip = client_ip(request)
    user.last_login = utcnow()
    access = create_access_token(user.id, user.username, user.hwid or "", True)
    refresh, jti, exp = create_refresh_token(user.id)
    db.add(RefreshToken(jti=jti, user_id=user.id, expires_at=exp))
    db.commit()
    return {"status": "success", "admin_token": access, "refresh_token": refresh}


@router.get("/users")
def list_users(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    users = db.scalars(select(User)).all()
    return {"status": "success", "users": [{
        "id": u.id, "username": u.username, "email": u.email, "credits": u.credits,
        "hwid": u.hwid, "is_active": u.is_active, "is_admin": u.is_admin,
        "last_ip": u.last_ip,
        "last_login": u.last_login.isoformat() if u.last_login else None,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    } for u in users]}


@router.post("/credits/add")
def add_credits(req: CreditRequest, request: Request,
                admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.get(User, req.user_id)
    if not user:
        raise HTTPException(404, "User not found.")
    user.credits += req.credits
    db.add(CreditLog(user_id=user.id, amount=req.credits, operation="ADMIN_ADD",
                     hwid=None, ip=client_ip(request)))
    db.commit()
    return {"status": "success", "user_id": user.id, "new_balance": user.credits}


@router.post("/users/action")
def user_action(req: UserActionRequest, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.get(User, req.user_id)
    if not user:
        raise HTTPException(404, "User not found.")
    if req.action == "activate":
        user.is_active = True
    elif req.action == "disable":
        user.is_active = False
    elif req.action == "reset_hwid":
        user.hwid = None
    elif req.action == "delete":
        if user.is_admin:
            raise HTTPException(400, "Cannot delete an admin account.")
        db.delete(user)
    else:
        raise HTTPException(400, "Unknown action.")
    db.commit()
    return {"status": "success", "action": req.action, "user_id": req.user_id}


@router.post("/config")
def set_config(req: ConfigRequest, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    row = db.get(SystemConfig, req.key)
    if row:
        row.value = req.value
    else:
        db.add(SystemConfig(key=req.key, value=req.value))
    db.commit()
    return {"status": "success", "key": req.key, "value": req.value}


@router.get("/audit")
def audit_trail(limit: int = 100, imei: str = "", serial: str = "", username: str = "",
                operation: str = "", admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Trace sensitive operations. Filter by imei / serial / username / operation."""
    limit = max(1, min(limit, 1000))
    q = select(AuditLog).order_by(AuditLog.id.desc())
    if imei:
        q = q.where(AuditLog.imei == imei)
    if serial:
        q = q.where(AuditLog.serial == serial)
    if username:
        q = q.where(AuditLog.username == username)
    if operation:
        q = q.where(AuditLog.operation == operation)
    rows = db.scalars(q.limit(limit)).all()
    return {"status": "success", "entries": [{
        "id": r.id, "user_id": r.user_id, "username": r.username, "operation": r.operation,
        "brand": r.brand, "model": r.model, "imei": r.imei, "serial": r.serial,
        "ip": r.ip, "hwid": r.hwid, "consent": r.consent,
        "timestamp": r.timestamp.isoformat() if r.timestamp else None,
    } for r in rows]}


@router.get("/logs")
def credit_logs(limit: int = 50, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    limit = max(1, min(limit, 500))
    rows = db.scalars(select(CreditLog).order_by(CreditLog.id.desc()).limit(limit)).all()
    return {"status": "success", "logs": [{
        "id": r.id, "user_id": r.user_id, "amount": r.amount, "operation": r.operation,
        "hwid": r.hwid, "ip": r.ip,
        "timestamp": r.timestamp.isoformat() if r.timestamp else None,
    } for r in rows]}
