"""
Qualcomm engine (EDL: Sahara + Firehose).

Scaffold for Snapdragon Oppo/Realme/OnePlus and other QC devices. The device is
put in EDL mode (USB 05c6:9008); the host completes the Sahara handshake, uploads
a signed Firehose programmer, then issues Firehose XML commands to read/write
partitions.

NOTE: the Firehose programmer (prog_firehose_*.elf/.mbn) is per-chip and must be
SIGNED by the vendor for secure-boot devices. The tool loads the correct signed
loader from the server vault; it never ships one bundled. The real Sahara/Firehose
I/O is implemented where marked and verified against a device.
"""
from __future__ import annotations

from typing import List

from src.core.engines.base import DeviceEngine, DeviceInfo, EngineError, StepUpdate
from src.core.safety import SafetyConfig, guard_erase, guard_write

# Qualcomm EDL USB identifiers.
QC_VID = 0x05C6
QC_PID_EDL = 0x9008


class QualcommEngine(DeviceEngine):
    platform = "qualcomm"
    READY = False  # scaffold: protocol framed, device I/O to be implemented

    def __init__(self, port=None, log=None, step=None):
        super().__init__(port, log or (lambda l, m: None), step or (lambda u: None))

    def connect(self) -> bool:
        self.log("info", "Qualcomm: looking for EDL (QDLoader 9008)...")
        # --- real Sahara handshake over the EDL endpoint goes here ---
        raise EngineError(
            "Qualcomm EDL engine is not enabled yet. Put the device in EDL (9008) "
            "mode; this engine will handshake Sahara and upload a signed Firehose "
            "loader from the vault once enabled.")

    def identify(self) -> DeviceInfo:
        # --- Sahara read of HWID/serial, then Firehose <configure> goes here ---
        raise EngineError("Qualcomm identify not implemented yet.")

    def flash(self, steps: List[dict], safety: SafetyConfig) -> None:
        for s in steps:  # safety guards apply identically across engines
            guard_write(s["partition"], s.get("file", ""), s.get("size", 0), safety)
        raise EngineError("Qualcomm Firehose write not implemented yet.")

    def erase(self, partitions: List[str], safety: SafetyConfig) -> None:
        for name in partitions:
            guard_erase(name, safety, context="erase")
        raise EngineError("Qualcomm Firehose erase not implemented yet.")
