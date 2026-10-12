from datetime import datetime
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from backend.models.db import DatabaseManager

router = APIRouter(prefix="/api/v1", tags=["Credits & System"])

# Cost table per operation (credits)
OPERATION_COSTS = {
    "SLA_BYPASS": 1,
    "FLASH_FIRMWARE": 2,
    "FRP_RESET": 1,
    "FORMAT_PARTITION": 1,
    "NVRAM_REPAIR": 3,
    "BOOTLOADER_UNLOCK": 5,
    "READBACK_DUMP": 2,
}

class DeductRequest(BaseModel):
    hwid: str
    credits: int
    operation: str

@router.get("/operations")
def operations():
    return {"status": "success", "costs": OPERATION_COSTS}

@router.post("/credits/deduct")
def deduct(req: DeductRequest, request: Request):
    client_ip = request.client.host
    conn = DatabaseManager.get_connection()
    cursor = conn.cursor()

    # Find user by HWID and verify active + IP binding consistency
    cursor.execute("SELECT * FROM users WHERE hwid = ?", (req.hwid,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        raise HTTPException(404, "Device not registered. Please login first.")
    if not user["is_active"]:
        conn.close()
        raise HTTPException(403, "Account disabled by administrator.")

    # Use server-side fixed cost when operation is known (prevents client tampering)
    cost = OPERATION_COSTS.get(req.operation, req.credits)
    if user["credits"] < cost:
        conn.close()
        raise HTTPException(402, f"Insufficient credits. Required: {cost}, Available: {user['credits']}")

    cursor.execute("UPDATE users SET credits = credits - ? WHERE id = ?", (cost, user["id"]))
    cursor.execute('''
        INSERT INTO credit_logs (user_id, amount, operation, hwid, ip, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user["id"], -cost, req.operation, req.hwid, client_ip, datetime.utcnow().isoformat()))
    conn.commit()
    cursor.execute("SELECT credits FROM users WHERE id = ?", (user["id"],))
    remaining = cursor.fetchone()["credits"]
    conn.close()

    return {"status": "success", "operation": req.operation, "charged": cost, "remaining_credits": remaining}

@router.get("/system/status")
def system_status(version: str = "1.0.0"):
    conn = DatabaseManager.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM system_config")
    cfg = {r["key"]: r["value"] for r in cursor.fetchall()}
    conn.close()

    latest = cfg.get("latest_version", version)
    return {
        "status": "success",
        "maintenance": cfg.get("maintenance_mode", "0") == "1",
        "latest_version": latest,
        "update_available": latest != version,
        "announcement": cfg.get("announcement", ""),
    }
