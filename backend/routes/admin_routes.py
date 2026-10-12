from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from backend.models.db import DatabaseManager

router = APIRouter(prefix="/api/v1/admin", tags=["Admin Panel"])

def require_admin(request: Request):
    """Simple admin guard via header X-Admin-Token (set at admin login)."""
    token = request.headers.get("X-Admin-Token", "")
    conn = DatabaseManager.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM system_config WHERE key = 'admin_session_token'")
    row = cursor.fetchone()
    conn.close()
    if not row or row["value"] != token:
        raise HTTPException(403, "Admin access denied.")
    return True

class CreditRequest(BaseModel):
    user_id: int
    credits: int

class UserActionRequest(BaseModel):
    user_id: int
    action: str  # activate / disable / reset_hwid / delete

class ConfigRequest(BaseModel):
    key: str
    value: str

@router.post("/login")
def admin_login(username: str, password: str):
    import hashlib
    conn = DatabaseManager.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ? AND is_admin = 1", (username,))
    user = cursor.fetchone()
    conn.close()
    if not user or user["password_hash"] != hashlib.sha256(password.encode()).hexdigest():
        raise HTTPException(401, "Invalid admin credentials.")
    import uuid
    token = uuid.uuid4().hex
    conn = DatabaseManager.get_connection()
    conn.execute("INSERT OR REPLACE INTO system_config (key, value) VALUES ('admin_session_token', ?)", (token,))
    conn.commit()
    conn.close()
    return {"status": "success", "admin_token": token}

@router.get("/users")
def list_users(request: Request):
    require_admin(request)
    conn = DatabaseManager.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, email, credits, hwid, is_active, is_admin, last_ip, last_login, created_at FROM users")
    users = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {"status": "success", "users": users}

@router.post("/credits/add")
def add_credits(req: CreditRequest, request: Request):
    require_admin(request)
    conn = DatabaseManager.get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET credits = credits + ? WHERE id = ?", (req.credits, req.user_id))
    cursor.execute('''
        INSERT INTO credit_logs (user_id, amount, operation, hwid, ip, timestamp)
        VALUES (?, ?, 'ADMIN_ADD', NULL, ?, ?)
    ''', (req.user_id, req.credits, request.client.host, datetime.utcnow().isoformat()))
    conn.commit()
    cursor.execute("SELECT credits FROM users WHERE id = ?", (req.user_id,))
    credits = cursor.fetchone()["credits"]
    conn.close()
    return {"status": "success", "user_id": req.user_id, "new_balance": credits}

@router.post("/users/action")
def user_action(req: UserActionRequest, request: Request):
    require_admin(request)
    conn = DatabaseManager.get_connection()
    cursor = conn.cursor()
    if req.action == "activate":
        cursor.execute("UPDATE users SET is_active = 1 WHERE id = ?", (req.user_id,))
    elif req.action == "disable":
        cursor.execute("UPDATE users SET is_active = 0 WHERE id = ?", (req.user_id,))
    elif req.action == "reset_hwid":
        cursor.execute("UPDATE users SET hwid = NULL WHERE id = ?", (req.user_id,))
    elif req.action == "delete":
        cursor.execute("DELETE FROM users WHERE id = ? AND is_admin = 0", (req.user_id,))
    else:
        conn.close()
        raise HTTPException(400, "Unknown action.")
    conn.commit()
    conn.close()
    return {"status": "success", "action": req.action, "user_id": req.user_id}

@router.post("/config")
def set_config(req: ConfigRequest, request: Request):
    """Admin controls: maintenance_mode (0/1), latest_version, announcement."""
    require_admin(request)
    conn = DatabaseManager.get_connection()
    conn.execute("INSERT OR REPLACE INTO system_config (key, value) VALUES (?, ?)", (req.key, req.value))
    conn.commit()
    conn.close()
    return {"status": "success", "key": req.key, "value": req.value}

@router.get("/logs")
def credit_logs(request: Request, limit: int = 50):
    require_admin(request)
    conn = DatabaseManager.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM credit_logs ORDER BY id DESC LIMIT ?", (limit,))
    logs = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {"status": "success", "logs": logs}
