"""
Server-authorized operations — the core of the anti-crack design.

A paid operation (SLA bypass, flash, FRP reset, ...) can only run if the server
says so. The client calls /authorize; the server validates the session + HWID,
deducts credits atomically, logs it, and returns a short-lived signed GRANT.
The client later reports success/failure at /result, and a failed op is
refunded exactly once. A patched client cannot forge the grant (it's signed
with the server's secret) and cannot fetch the payload without one.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.operations import OPERATION_COSTS, cost_of, is_known
from backend.core.security import create_operation_grant, new_nonce
from backend.deps import client_ip, get_current_user
from backend.models.models import CreditLog, Operation, SystemConfig, User, utcnow
from backend.schemas import AuthorizeRequest, ResultRequest

router = APIRouter(prefix="/api/v1", tags=["Operations"])


@router.get("/operations")
def operations():
    return {"status": "success", "costs": OPERATION_COSTS}


@router.post("/operations/authorize")
def authorize(req: AuthorizeRequest, request: Request,
              user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ip = client_ip(request)

    if not is_known(req.operation):
        raise HTTPException(400, "Unknown operation.")
    if user.hwid and req.hwid != user.hwid:
        raise HTTPException(403, "HWID mismatch for this operation.")

    cost = cost_of(req.operation)

    # Atomic deduction. On Postgres we lock the row so concurrent authorizes
    # can't both read the old balance and overspend.
    is_pg = db.bind.dialect.name == "postgresql"
    stmt = select(User).where(User.id == user.id)
    if is_pg:
        stmt = stmt.with_for_update()
    locked = db.scalar(stmt)

    if locked.credits < cost:
        raise HTTPException(402, f"Insufficient credits. Required: {cost}, Available: {locked.credits}")

    locked.credits -= cost
    nonce = new_nonce()
    db.add(Operation(
        nonce=nonce, user_id=locked.id, operation=req.operation, cost=cost,
        hwid=req.hwid, device_info=req.device_info[:2000], status="authorized",
    ))
    db.add(CreditLog(
        user_id=locked.id, amount=-cost, operation=req.operation, hwid=req.hwid, ip=ip,
    ))
    db.commit()

    grant = create_operation_grant(locked.id, req.operation, req.hwid, nonce)
    return {
        "status": "success",
        "operation": req.operation,
        "charged": cost,
        "remaining_credits": locked.credits,
        "grant": grant,
        "nonce": nonce,
    }


@router.post("/operations/result")
def result(req: ResultRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    op = db.scalar(select(Operation).where(Operation.nonce == req.nonce, Operation.user_id == user.id))
    if not op:
        raise HTTPException(404, "Operation not found.")
    if op.status != "authorized":
        # Idempotent: already closed/refunded — report current state, no double action.
        return {"status": "success", "operation_status": op.status, "note": "Already finalized."}

    if req.success:
        op.status = "success"
    else:
        # Refund exactly once.
        op.status = "refunded"
        refunded = db.get(User, user.id)
        refunded.credits += op.cost
        db.add(CreditLog(
            user_id=user.id, amount=op.cost, operation=f"REFUND_{op.operation}", hwid=op.hwid, ip=None,
        ))
    op.closed_at = utcnow()
    db.commit()

    fresh = db.get(User, user.id)
    return {"status": "success", "operation_status": op.status, "remaining_credits": fresh.credits}


@router.get("/system/status")
def system_status(version: str = "1.0.0", db: Session = Depends(get_db)):
    cfg = {c.key: c.value for c in db.scalars(select(SystemConfig))}
    latest = cfg.get("latest_version", version)
    return {
        "status": "success",
        "maintenance": cfg.get("maintenance_mode", "0") == "1",
        "latest_version": latest,
        "update_available": latest != version,
        "announcement": cfg.get("announcement", ""),
    }
