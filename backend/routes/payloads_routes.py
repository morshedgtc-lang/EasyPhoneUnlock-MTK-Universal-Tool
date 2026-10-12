"""
Gated payload vault.

The encrypted DA/exploit binaries are streamed to the client ONLY when it
presents a valid operation grant whose operation is allowed to fetch that
payload, the grant's HWID matches the X-HWID header, and the grant's nonce
belongs to an operation still in 'authorized' state. No grant -> no payload.

Admins can upload new binaries (encrypted into the vault) via /payloads/upload.
"""
import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, UploadFile, File, Form
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core import vault
from backend.core.database import get_db
from backend.core.operations import payload_allowed
from backend.core.security import decode_token
from backend.deps import require_admin
from backend.models.models import Operation, User

router = APIRouter(prefix="/api/v1/payloads", tags=["Payload Vault"])


def _validate_grant(grant: str, hwid: str | None, payload_name: str, db: Session) -> Operation:
    try:
        payload = decode_token(grant)
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Operation grant expired. Re-authorize.")
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid operation grant.")

    if payload.get("typ") != "grant":
        raise HTTPException(401, "Not an operation grant.")
    if hwid and payload.get("hwid") != hwid:
        raise HTTPException(403, "Grant/device HWID mismatch.")
    if not payload_allowed(payload.get("op", ""), payload_name):
        raise HTTPException(403, "This operation is not allowed to fetch that payload.")

    op = db.scalar(select(Operation).where(Operation.nonce == payload.get("nonce")))
    if not op or op.status != "authorized":
        raise HTTPException(403, "Grant is not tied to an active operation.")
    return op


@router.get("/{name}")
def fetch_payload(
    name: str,
    x_grant: str | None = Header(default=None),
    x_hwid: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    if not x_grant:
        raise HTTPException(401, "Missing X-Grant header.")
    _validate_grant(x_grant, x_hwid, name, db)
    if not vault.exists(name):
        raise HTTPException(404, "Payload not found in vault.")
    data = vault.get(name)
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"X-Payload-SHA256": vault.sha256(name)},
    )


@router.get("", dependencies=[Depends(require_admin)])
def list_payloads():
    return {"status": "success", "payloads": vault.list_payloads()}


@router.post("/upload", dependencies=[Depends(require_admin)])
async def upload_payload(name: str = Form(...), file: UploadFile = File(...)):
    data = await file.read()
    vault.put(name, data)
    return {"status": "success", "name": name, "bytes": len(data), "sha256": vault.sha256(name)}
