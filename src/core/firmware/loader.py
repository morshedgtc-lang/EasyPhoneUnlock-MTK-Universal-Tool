"""
Firmware loader: detect a flash-file format and produce a scatter + partitions.

Supported inputs:
  - scatter (*scatter*.txt / .xml / .yaml)  -> parsed directly
  - .ofp (MediaTek)                         -> decrypted/unpacked, then scatter
  - .ozip (ColorOS)                         -> not yet (needs per-device key)

Everything downstream (chip-match, protected-partition safety, live flash)
consumes the returned scatter partitions unchanged.
"""
from __future__ import annotations

import glob
import os
from dataclasses import dataclass, field
from typing import List

from src.core.firmware import ofp_mtk
from src.core.scatter.scatter_parser import ScatterParser, ScatterPartition


class FirmwareError(Exception):
    pass


@dataclass
class LoadedFirmware:
    format: str
    scatter_path: str | None
    partitions: List[ScatterPartition] = field(default_factory=list)
    extract_dir: str | None = None
    notes: List[str] = field(default_factory=list)


def detect(path: str) -> str:
    """Identify the firmware format from extension + magic bytes."""
    low = path.lower()
    if low.endswith(".ofp"):
        return "ofp"
    if low.endswith(".ozip"):
        return "ozip"
    if low.endswith((".xml", ".yaml", ".yml")) or "scatter" in os.path.basename(low):
        return "scatter"
    if low.endswith(".txt"):
        return "scatter"
    # Magic sniff for OZIP ("OPPOENCRYPT!") if extension is ambiguous.
    try:
        with open(path, "rb") as f:
            head = f.read(16)
        if head.startswith(b"OPPOENCRYPT!"):
            return "ozip"
    except Exception:
        pass
    return "unknown"


def _find_scatter(directory: str) -> str | None:
    for pat in ("*scatter*.txt", "*.xml", "*.yaml", "*.yml"):
        hits = glob.glob(os.path.join(directory, "**", pat), recursive=True)
        if hits:
            # Prefer a file that actually looks like a scatter.
            for h in hits:
                if "scatter" in os.path.basename(h).lower():
                    return h
            return hits[0]
    return None


def load(path: str, extract_root: str, log=lambda m: None) -> LoadedFirmware:
    fmt = detect(path)
    if fmt == "scatter":
        parts = ScatterParser.parse_file(path)
        return LoadedFirmware("scatter", path, parts)

    if fmt == "ofp":
        outdir = os.path.join(extract_root, os.path.splitext(os.path.basename(path))[0])
        log(f"Decrypting OFP: {os.path.basename(path)}")
        ofp_mtk.decrypt_ofp(path, outdir, log=log)
        scatter = _find_scatter(outdir)
        notes = []
        if os.path.isfile(os.path.join(outdir, "super_map.csv")):
            notes.append("super_map.csv present — multiple carrier super images; verify before flashing.")
        if not scatter:
            raise FirmwareError("OFP decrypted but no scatter file was found inside.")
        parts = ScatterParser.parse_file(scatter)
        return LoadedFirmware("ofp", scatter, parts, extract_dir=outdir, notes=notes)

    if fmt == "ozip":
        raise FirmwareError(
            "OZIP needs a device-specific decryption key. Supply the ColorOS key "
            "for this model, or provide a scatter/OFP instead.")

    raise FirmwareError(f"Unrecognized firmware format: {os.path.basename(path)}")
