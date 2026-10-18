# Reference Tool Analysis — Findings & Decision

Date: 2026-10-18. Static analysis only (no execution, no unpacking of proprietary
payloads, no license/DRM bypass, no proprietary code/branding reused).

## Reference A — github.com/morluto/rea
- **What it is:** `rea-agents` v6.7.0, **MIT license**. An AI *reverse-engineering
  assistant* (MCP server + CLI, TypeScript/Node) that drives Ghidra/Hopper etc.
- **Relevance:** a tool you *run* to analyze binaries; not a library to embed and
  not a flash/unlock tool. Not integrated into our project.

## Reference B — local installers (`refarence tools exe file/`)
Evidence from PE metadata + streaming byte-marker scan:

| Tool | Vendor | Ver | Size | Arch | Signed | Installer | App framework |
|---|---|---|---|---|---|---|---|
| Pandora Tool Ultra | Pandora | 10.3.2 | 174 MB | x86 | No | **Inno Setup** | **Delphi / Embarcadero (VCL)** |
| Z3X SamsTool | z3x-team | — | 232 MB | x86 | No | **Inno Setup** | **Delphi / Embarcadero (VCL)** |

Evidence: both contain `Inno Setup` + `Embarcadero` markers at the installer head.
Large size = bundled USB drivers + loader/firmware-helper payloads (not inspected
further — that would cross into extracting proprietary content).

Confidence: **high** for installer tech and Delphi/VCL app framework. Not inspected:
their proprietary engines, loaders, keys, licensing (out of bounds by design).

## Framework decision — KEEP our stack
- Our project: **Python 3 + FastAPI (server) + PyQt6 (desktop)**, server-side
  licensing/credits/audit, universal engine architecture (MTK ready; QC/Unisoc
  scaffolded), OFP firmware decrypt, 31 tests, deployed on Railway.
- The reference tools are **Delphi/VCL** — a heavier, legacy RAD stack. There is
  **no benefit** to migrating; PyQt6 is modern, cross-platform, maintainable, and
  already working. **Decision: no framework change.**

## What we legitimately adopt (patterns, not code)
1. **Professional installer** — both use Inno Setup. We now ship an Inno Setup
   installer (`installer/EasyPhoneUnlock.iss`) that packages the EXE, creates
   shortcuts, and runs an optional USB-driver step. Turns our bare EXE into an
   official, brandable product install.
2. **Driver bundling** — reference tools install MTK VCOM/preloader drivers. Our
   installer has a driver step (operator supplies the driver package).
3. UX patterns already present in our app (brand/model select, live per-partition
   log, Read Info, progress, confirmations) match the category norms.

## What we do NOT do
Decompile/extract their engines, loaders, keys; reproduce their code or branding;
replicate their licensing. Our engines use our own code + open-source (MIT) ports.
