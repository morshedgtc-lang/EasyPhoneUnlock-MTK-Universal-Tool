import requests
import json
import os
from typing import Dict, Any, Optional
from src.auth.hwid import HWIDGenerator

class LicenseClient:
    """
    Client-side authentication manager for EasyPhoneUnlock Tool.
    Communicates with the central Cloud Admin Panel API.
    """

    def __init__(self, server_url: str = "http://127.0.0.1:8000"):
        self.server_url = server_url.rstrip("/")
        self.token_file = "user_session.json"
        self.token: Optional[str] = None
        self.user_data: Dict[str, Any] = {}
        self.hwid = HWIDGenerator.get_hwid()

    def register(self, username: str, password: str, email: str) -> Dict[str, Any]:
        """Registers a new user account with initial trial credits."""
        url = f"{self.server_url}/api/v1/auth/register"
        payload = {
            "username": username,
            "password": password,
            "email": email,
            "hwid": self.hwid
        }
        try:
            resp = requests.post(url, json=payload, timeout=10)
            return resp.json()
        except Exception as e:
            return {"status": "error", "message": f"Connection error: {str(e)}"}

    def login(self, username: str, password: str) -> Dict[str, Any]:
        """Authenticates user, verifies HWID activation, IP status, and returns session token & credits."""
        url = f"{self.server_url}/api/v1/auth/login"
        payload = {
            "username": username,
            "password": password,
            "hwid": self.hwid
        }
        try:
            resp = requests.post(url, json=payload, timeout=10)
            data = resp.json()
            if data.get("status") == "success":
                self.token = data.get("access_token")
                self.user_data = data.get("user", {})
                self._save_session()
            return data
        except Exception as e:
            return {"status": "error", "message": f"Server unreachable: {str(e)}"}

    def deduct_credits(self, credits_needed: int, operation_name: str) -> Dict[str, Any]:
        """Deducts credits for service actions (e.g. SLA bypass, FRP reset, NVRAM repair)."""
        if not self.token:
            return {"status": "error", "message": "User not authenticated."}

        url = f"{self.server_url}/api/v1/credits/deduct"
        headers = {"Authorization": f"Bearer {self.token}"}
        payload = {
            "hwid": self.hwid,
            "credits": credits_needed,
            "operation": operation_name
        }
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            data = resp.json()
            if data.get("status") == "success":
                self.user_data["credits"] = data.get("remaining_credits", 0)
            return data
        except Exception as e:
            return {"status": "error", "message": f"Credit transaction error: {str(e)}"}

    def check_announcements_and_version(self, current_version: str = "1.0.0") -> Dict[str, Any]:
        """Checks for software updates and system maintenance alerts."""
        url = f"{self.server_url}/api/v1/system/status"
        try:
            resp = requests.get(url, params={"version": current_version}, timeout=5)
            return resp.json()
        except Exception:
            return {"status": "ok", "maintenance": False}

    def _save_session(self):
        try:
            with open(self.token_file, "w") as f:
                json.dump({"token": self.token, "user": self.user_data}, f)
        except Exception:
            pass
