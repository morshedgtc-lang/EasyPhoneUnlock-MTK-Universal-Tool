# EasyPhoneUnlock — MTK Universal Flash & Service Tool

A Windows desktop service tool for MediaTek (MTK) devices with a **glass UI**,
**brand/model-driven operations**, a **live operation display**, and a hardened
**server-side licensing + audit** backend. Built for repair technicians:
hassle-free, and designed to be safe — every write/erase passes through
guards intended to prevent bricking a device.

---

## What it does

**Client (technician's PC — single EXE):**
- Clean, translucent "glass" UI (frameless, Windows acrylic blur).
- Pick **Brand → Model**; the tool shows only the operations that model supports.
- Operations: **Flash Firmware, FRP Erase, Network Unlock, IMEI Repair,
  Backup Flash File, Backup Security File, Bootloader Unlock, SLA/DAA Bypass.**
- **Live display**: a table + console showing each partition action as it runs
  (e.g. `boot — WRITE — boot.img — RUNNING/DONE`) with a progress bar.
- **Consent popup** before any sensitive operation (FRP, network unlock, IMEI,
  bootloader, security backup): the technician must confirm authorization and
  enter the device **IMEI/serial**.

**Server (owner's VPS):**
- Central licensing: accounts, credits, **HWID (PC ID) + IP** bound on login.
- **All authorization is server-side** — a cracked client can't self-grant.
- **Audit trail**: every sensitive operation is recorded with username, PC ID,
  IP, IMEI/serial, brand/model and timestamp, so misuse can be traced by the
  admin panel.
- Encrypted **payload vault**: the real DA/exploit binaries live on the server,
  encrypted, and are released only against a short-lived operation grant.

---

## Safety model (no-brick design)

Every device-modifying step is routed through `src/core/safety.py`:
1. **Chip match** — refuses to flash an image built for a different SoC.
2. **Image sanity** — blocks empty images or any image larger than its partition.
3. **Protected partitions** (preloader, GPT, PMT, nvram, tee, …) — modifying them
   requires explicit confirmation **and a read-back backup is taken first**.
4. **FRP reset** only touches FRP-safe partitions; never silently wipes user data.
A blocked or failed operation is **auto-refunded** — safety never costs a credit.

---

## Architecture

```
backend/                 FastAPI licensing + audit server
  core/                  config, security (JWT/argon2), db, vault, operations, bootstrap
  models/                SQLAlchemy models (users, credits, operations, audit, ...)
  routes/                auth, admin, operations, payloads
  admin_web/             admin control panel (static)
src/
  auth/                  hwid (PowerShell CIM), license_client (JWT + grants)
  core/                  safety, service (orchestrator), chipdb, devices, protocol/, da/, scatter/
  gui/                   PyQt6 glass UI (theme, worker, main_window, app)
  cli/                   command-line entrypoint
config/                  chip_config.json, device_models.json
tests/                   unit + backend tests
Dockerfile, docker-compose.yml, Caddyfile   deployment (API + Postgres + TLS)
EasyPhoneUnlock.spec, build_windows.ps1      single-EXE packaging
```

---

## Run the server (dev)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
copy .env.example .env      # set JWT_SECRET, ADMIN_BOOTSTRAP_PASSWORD, PAYLOAD_ENC_KEY
python -m uvicorn backend.main:app --reload
# Admin panel: http://127.0.0.1:8000/admin
```

Generate secrets:
```powershell
python -c "import secrets;print(secrets.token_urlsafe(48))"   # JWT_SECRET
python -m backend.core.vault keygen                            # PAYLOAD_ENC_KEY
```

Load your real DA/exploit binaries into the encrypted vault:
```powershell
python -m backend.core.vault put da1 path\to\DA1.bin
python -m backend.core.vault put da2 path\to\DA2.bin
```

## Deploy the server (VPS, HTTPS)

Edit `Caddyfile` (your domain) and `.env` (prod secrets + Postgres), then:
```bash
docker compose up -d --build
```
Caddy fetches a Let's Encrypt certificate automatically. `ENV=prod` refuses to
start with weak/empty secrets.

## Run / build the client

```powershell
pip install -r requirements.txt
python run_gui.py                      # dev run
powershell -ExecutionPolicy Bypass -File build_windows.ps1   # -> dist\EasyPhoneUnlock.exe
```
Point the client at the server with `EPU_SERVER`:
```powershell
$env:EPU_SERVER="https://panel.example.com"; python run_gui.py
```

## Tests

```powershell
pip install pytest httpx
$env:PYTHONPATH=(Get-Location).Path
python -m pytest tests/ -q
```

---

## Status

- Server (licensing, credits, operation grants, payload vault, audit): **done, tested.**
- Client (JWT sessions, authorized operations, safety guards, glass GUI): **done, tested.**
- Single-EXE packaging: **done.**
- Low-level BROM/DA device I/O: **framework in place**; the real read/write
  protocol is marked `--- real ... goes here ---` and is finished with your DA
  binaries against a test device.
