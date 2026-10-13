"""
Client-side licensing manager.

Talks to the hardened Cloud Admin API. All authorization is server-side: this
client only holds tokens and asks permission. It cannot grant itself credits or
run an operation the server did not authorize, and it downloads the encrypted
DA/exploit payloads only via a server-issued operation grant.
"""
import hashlib
import json
import os
from typing import Any, Dict, Optional

import requests

from src.auth.hwid import HWIDGenerator


class LicenseError(Exception):
    pass


class LicenseClient:
    def __init__(self, server_url: str = "http://127.0.0.1:8000", session_file: str = "user_session.json"):
        self.server_url = server_url.rstrip("/")
        self.session_file = session_file
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.user_data: Dict[str, Any] = {}
        self.hwid = HWIDGenerator.get_hwid()
        self._load_session()

    # ------------------------------------------------------------------ #
    # Session persistence
    # ------------------------------------------------------------------ #
    def _load_session(self) -> None:
        try:
            with open(self.session_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.access_token = data.get("access_token")
            self.refresh_token = data.get("refresh_token")
            self.user_data = data.get("user", {})
        except Exception:
            pass

    def _save_session(self) -> None:
        try:
            with open(self.session_file, "w", encoding="utf-8") as f:
                json.dump({
                    "access_token": self.access_token,
                    "refresh_token": self.refresh_token,
                    "user": self.user_data,
                }, f)
        except Exception:
            pass

    def _auth_headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token}", "X-HWID": self.hwid}

    # ------------------------------------------------------------------ #
    # Auth
    # ------------------------------------------------------------------ #
    def register(self, username: str, password: str, email: str = "") -> Dict[str, Any]:
        try:
            r = requests.post(f"{self.server_url}/api/v1/auth/register",
                              json={"username": username, "password": password,
                                    "email": email, "hwid": self.hwid}, timeout=15)
            return r.json()
        except Exception as e:
            return {"status": "error", "message": f"Connection error: {e}"}

    def login(self, username: str, password: str) -> Dict[str, Any]:
        try:
            r = requests.post(f"{self.server_url}/api/v1/auth/login",
                              json={"username": username, "password": password,
                                    "hwid": self.hwid}, timeout=15)
            data = r.json()
            if r.status_code == 200 and data.get("status") == "success":
                self.access_token = data.get("access_token")
                self.refresh_token = data.get("refresh_token")
                self.user_data = data.get("user", {})
                self._save_session()
            return data
        except Exception as e:
            return {"status": "error", "message": f"Server unreachable: {e}"}

    def _refresh_access(self) -> bool:
        if not self.refresh_token:
            return False
        try:
            r = requests.post(f"{self.server_url}/api/v1/auth/refresh",
                              json={"refresh_token": self.refresh_token}, timeout=15)
            if r.status_code == 200:
                self.access_token = r.json().get("access_token")
                self._save_session()
                return True
        except Exception:
            pass
        return False

    def _authed_request(self, method: str, path: str, **kwargs) -> requests.Response:
        """Issue an authenticated request; transparently refresh once on 401."""
        url = f"{self.server_url}{path}"
        headers = {**kwargs.pop("headers", {}), **self._auth_headers()}
        r = requests.request(method, url, headers=headers, timeout=30, **kwargs)
        if r.status_code == 401 and self._refresh_access():
            headers = {**headers, **self._auth_headers()}
            r = requests.request(method, url, headers=headers, timeout=30, **kwargs)
        return r

    def refresh_profile(self) -> Dict[str, Any]:
        try:
            r = self._authed_request("GET", "/api/v1/auth/me")
            if r.status_code == 200:
                self.user_data = r.json().get("user", {})
                self._save_session()
            return r.json()
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ------------------------------------------------------------------ #
    # Operations
    # ------------------------------------------------------------------ #
    @property
    def credits(self) -> int:
        return int(self.user_data.get("credits", 0))

    def authorize_operation(self, operation: str, device_info: str = "") -> Dict[str, Any]:
        """
        Ask the server to authorize ONE paid operation. On success the server
        has already deducted the credit and returns a short-lived grant + nonce.
        """
        if not self.access_token:
            return {"status": "error", "message": "Not logged in."}
        try:
            r = self._authed_request("POST", "/api/v1/operations/authorize",
                                     json={"operation": operation, "hwid": self.hwid,
                                           "device_info": device_info})
            data = r.json()
            if r.status_code == 200 and "remaining_credits" in data:
                self.user_data["credits"] = data["remaining_credits"]
                self._save_session()
            else:
                data.setdefault("status", "error")
            return data
        except Exception as e:
            return {"status": "error", "message": f"Authorization error: {e}"}

    def report_result(self, nonce: str, success: bool, detail: str = "") -> Dict[str, Any]:
        """Tell the server how the op went. A failure is refunded server-side."""
        try:
            r = self._authed_request("POST", "/api/v1/operations/result",
                                     json={"nonce": nonce, "success": success, "detail": detail})
            data = r.json()
            if "remaining_credits" in data:
                self.user_data["credits"] = data["remaining_credits"]
                self._save_session()
            return data
        except Exception as e:
            return {"status": "error", "message": f"Result report error: {e}"}

    def fetch_payload(self, name: str, grant: str, dest_dir: str) -> str:
        """
        Download an encrypted payload from the vault using an operation grant.
        Verifies the server-provided SHA-256 and writes to dest_dir/name.bin.
        Returns the local path.
        """
        os.makedirs(dest_dir, exist_ok=True)
        r = requests.get(f"{self.server_url}/api/v1/payloads/{name}",
                         headers={"X-Grant": grant, "X-HWID": self.hwid}, timeout=60)
        if r.status_code != 200:
            raise LicenseError(f"Payload '{name}' fetch failed ({r.status_code}): {r.text[:200]}")
        expected = r.headers.get("X-Payload-SHA256")
        if expected and hashlib.sha256(r.content).hexdigest() != expected:
            raise LicenseError(f"Payload '{name}' integrity check failed (SHA-256 mismatch).")
        path = os.path.join(dest_dir, f"{name}.bin")
        with open(path, "wb") as f:
            f.write(r.content)
        return path

    def check_system_status(self, current_version: str = "1.0.0") -> Dict[str, Any]:
        try:
            r = requests.get(f"{self.server_url}/api/v1/system/status",
                             params={"version": current_version}, timeout=10)
            return r.json()
        except Exception:
            return {"status": "ok", "maintenance": False}
