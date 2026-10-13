"""
Serves the device/chip catalog so clients can update it without a new EXE.

The catalog JSON lives in <repo>/config and is the single source of truth,
stored locally, in git, and served here from the server. Admins can replace the
served copy at runtime via /catalog/upload.
"""
import hashlib
import json
import os

from fastapi import APIRouter, Depends, HTTPException

from backend.deps import require_admin
from backend.models.models import User

router = APIRouter(prefix="/api/v1/catalog", tags=["Catalog"])

# <repo>/config  (backend/routes/ -> backend/ -> repo root)
_CONFIG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "config",
)
_FILES = {"chips": "chip_config.json", "devices": "device_models.json"}


def _read(name: str) -> dict:
    path = os.path.join(_CONFIG_DIR, _FILES[name])
    if not os.path.isfile(path):
        raise HTTPException(404, f"Catalog '{name}' not found on server.")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _sha(obj: dict) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()[:16]


@router.get("/chips")
def chips():
    return _read("chips")


@router.get("/devices")
def devices():
    return _read("devices")


@router.get("/version")
def version():
    """Lets the client tell whether its cached catalog is stale."""
    c, d = _read("chips"), _read("devices")
    return {
        "status": "success",
        "chips_version": _sha(c),
        "devices_version": _sha(d),
        "chip_count": len(c.get("chips", {})),
        "brand_count": len(d.get("brands", {})),
        "model_count": sum(len(b.get("models", {})) for b in d.get("brands", {}).values()),
    }


@router.post("/upload", dependencies=[Depends(require_admin)])
def upload(name: str, payload: dict):
    """Admin: replace the served chips/devices catalog at runtime."""
    if name not in _FILES:
        raise HTTPException(400, "name must be 'chips' or 'devices'.")
    os.makedirs(_CONFIG_DIR, exist_ok=True)
    with open(os.path.join(_CONFIG_DIR, _FILES[name]), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return {"status": "success", "updated": _FILES[name]}
