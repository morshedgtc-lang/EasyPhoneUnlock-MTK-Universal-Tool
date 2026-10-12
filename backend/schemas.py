"""Pydantic request/response models."""
from pydantic import BaseModel, Field


# --- Auth ---
class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    email: str = ""
    hwid: str = ""


class LoginRequest(BaseModel):
    username: str
    password: str
    hwid: str = ""


class RefreshRequest(BaseModel):
    refresh_token: str


class AdminLoginRequest(BaseModel):
    username: str
    password: str


# --- Operations ---
class AuthorizeRequest(BaseModel):
    operation: str
    hwid: str
    device_info: str = ""


class ResultRequest(BaseModel):
    nonce: str
    success: bool
    detail: str = ""


# --- Admin ---
class CreditRequest(BaseModel):
    user_id: int
    credits: int


class UserActionRequest(BaseModel):
    user_id: int
    action: str  # activate | disable | reset_hwid | delete


class ConfigRequest(BaseModel):
    key: str
    value: str
