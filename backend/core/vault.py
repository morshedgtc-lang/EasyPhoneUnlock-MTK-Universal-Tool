"""
Encrypted payload vault.

The real DA / exploit binaries never ship inside the client. They live here on
the server, encrypted at rest with a Fernet key, and are only decrypted and
streamed to a client that presents a valid operation grant. A patched client
with no server access therefore has no payload to run.

CLI:
    python -m backend.core.vault keygen                 # print a new key
    python -m backend.core.vault put <name> <file>      # encrypt a file into the vault
    python -m backend.core.vault list                   # list stored payloads
"""
import hashlib
import os
import sys
from pathlib import Path
from typing import List

from cryptography.fernet import Fernet

from backend.core.config import settings

_EXT = ".enc"


def _vault_dir() -> Path:
    d = Path(settings.PAYLOAD_DIR)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _fernet() -> Fernet:
    if not settings.PAYLOAD_ENC_KEY:
        raise RuntimeError("PAYLOAD_ENC_KEY is not set. Generate one: python -m backend.core.vault keygen")
    return Fernet(settings.PAYLOAD_ENC_KEY.encode())


def _safe_name(name: str) -> str:
    # Prevent path traversal; allow only simple payload identifiers.
    if not name or any(c in name for c in ("/", "\\", "..", "\x00")):
        raise ValueError("Invalid payload name.")
    return name


def exists(name: str) -> bool:
    return (_vault_dir() / f"{_safe_name(name)}{_EXT}").is_file()


def list_payloads() -> List[str]:
    return sorted(p.stem for p in _vault_dir().glob(f"*{_EXT}"))


def put(name: str, plaintext: bytes) -> None:
    token = _fernet().encrypt(plaintext)
    (_vault_dir() / f"{_safe_name(name)}{_EXT}").write_bytes(token)


def get(name: str) -> bytes:
    """Return the decrypted payload bytes."""
    path = _vault_dir() / f"{_safe_name(name)}{_EXT}"
    if not path.is_file():
        raise FileNotFoundError(name)
    return _fernet().decrypt(path.read_bytes())


def sha256(name: str) -> str:
    return hashlib.sha256(get(name)).hexdigest()


def _cli() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1
    cmd = args[0]
    if cmd == "keygen":
        print(Fernet.generate_key().decode())
        return 0
    if cmd == "list":
        for n in list_payloads():
            print(n)
        return 0
    if cmd == "put" and len(args) == 3:
        name, src = args[1], args[2]
        put(name, Path(src).read_bytes())
        print(f"[+] Stored '{name}' ({os.path.getsize(src)} bytes, encrypted). sha256={sha256(name)}")
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(_cli())
