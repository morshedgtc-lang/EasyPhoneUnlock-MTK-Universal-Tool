import hashlib
import uuid
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from backend.models.db import DatabaseManager

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

class RegisterRequest(BaseModel):
    username: str
    password: str
    email: str = ""
    hwid: str = ""

class LoginRequest(BaseModel):
    username: str
    password: str
    hwid: str = ""

@router.post("/register")
def register(req: RegisterRequest, request: Request):
    client_ip = request.client.host
    conn = DatabaseManager.get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM users WHERE username = ?", (req.username,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(400, "Username already exists.")

    now = datetime.utcnow().isoformat()
    # New users register themselves; HWID is auto-bound on first login.
    # Default trial credits: 10
    cursor.execute('''
        INSERT INTO users (username, password_hash, email, credits, hwid, is_active, is_admin, last_ip, created_at)
        VALUES (?, ?, ?, 10, NULL, 1, 0, NULL, ?)
    ''', (req.username, hash_password(req.password), req.email, now))
    conn.commit()
    user_id = cursor.lastrowid

    cursor.execute('''
        INSERT INTO credit_logs (user_id, amount, operation, hwid, ip, timestamp)
        VALUES (?, 10, 'REGISTER_BONUS', ?, ?, ?)
    ''', (user_id, req.hwid, client_ip, now))
    conn.commit()
    conn.close()

    return {"status": "success", "message": "Account created. 10 trial credits granted.", "user_id": user_id}

@router.post("/login")
def login(req: LoginRequest, request: Request):
    client_ip = request.client.host
    conn = DatabaseManager.get_connection()
    cursor = conn.cursor()

    # 1. Check maintenance mode
    cursor.execute("SELECT value FROM system_config WHERE key = 'maintenance_mode'")
    row = cursor.fetchone()
    if row and row["value"] == "1":
        conn.close()
        raise HTTPException(503, "Server is under maintenance. Please try again later.")

    # 2. Validate credentials
    cursor.execute("SELECT * FROM users WHERE username = ?", (req.username,))
    user = cursor.fetchone()
    if not user or user["password_hash"] != hash_password(req.password):
        conn.close()
        raise HTTPException(401, "Invalid username or password.")

    # 3. Check account active status
    if not user["is_active"]:
        conn.close()
        raise HTTPException(403, "Account disabled by administrator.")

    # 4. HWID binding - activate on first login, verify after
    if user["hwid"] is None or user["hwid"] == "":
        cursor.execute("UPDATE users SET hwid = ? WHERE id = ?", (req.hwid, user["id"]))
        conn.commit()
    elif user["hwid"] != req.hwid:
        conn.close()
        raise HTTPException(403, f"HWID mismatch. This license is bound to another PC. Contact admin. Your HWID: {req.hwid}")

    # 5. Update last IP / login time
    now = datetime.utcnow().isoformat()
    token = uuid.uuid4().hex
    cursor.execute("UPDATE users SET last_ip = ?, last_login = ? WHERE id = ?", (client_ip, now, user["id"]))
    conn.commit()

    # Refresh user after updates
    cursor.execute("SELECT * FROM users WHERE id = ?", (user["id"],))
    user = cursor.fetchone()
    conn.close()

    return {
        "status": "success",
        "access_token": token,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "credits": user["credits"],
            "is_admin": bool(user["is_admin"]),
            "hwid": user["hwid"],
            "ip": client_ip
        }
    }
