"""
Qualcomm engine (EDL: Sahara loader transfer + Firehose storage ops).

Flow: device in EDL (05c6:9008) -> Sahara uploads a SIGNED Firehose programmer
(provided by the operator from the server vault) -> device runs Firehose -> we
configure storage and run program/erase through the shared safety guards.

The protocol here is real (see qc/sahara.py, qc/firehose.py). It is marked
READY=False until verified on hardware with a real signed loader, because secure
devices reject unsigned/incorrect loaders by Qualcomm's design and we cannot and
do not forge one.
"""
from __future__ import annotations

from typing import List, Optional

from src.core.engines.base import DeviceEngine, DeviceInfo, EngineError, StepUpdate
from src.core.engines.qc.firehose import FirehoseClient
from src.core.engines.qc.sahara import SaharaClient
from src.core.safety import SafetyConfig, guard_erase, guard_write

QC_VID = 0x05C6
QC_PID_EDL = 0x9008


class QualcommEngine(DeviceEngine):
    platform = "qualcomm"
    READY = False  # real protocol; needs hardware + signed loader to verify

    def __init__(self, port=None, log=None, step=None, transport=None, loader: Optional[bytes] = None,
                 mem="UFS"):
        super().__init__(port, log or (lambda l, m: None), step or (lambda u: None))
        self.transport = transport      # EDL endpoint (serial/bulk) exposing read/write
        self.loader = loader            # signed Firehose programmer bytes (from vault)
        self.mem = mem
        self.fh: Optional[FirehoseClient] = None

    def set_loader(self, loader: bytes) -> None:
        self.loader = loader

    def connect(self) -> bool:
        if self.transport is None:
            raise EngineError("No EDL transport. Put the device in EDL (9008) mode and attach it.")
        if not self.loader:
            raise EngineError("No signed Firehose loader supplied. Load it into the vault for this chip.")
        self.log("info", "Qualcomm: Sahara loader transfer...")
        SaharaClient(self.transport).transfer(self.loader)
        self.fh = FirehoseClient(self.transport)
        self.log("info", "Qualcomm: configuring Firehose storage...")
        self.fh.configure(self.mem)
        return True

    def identify(self) -> DeviceInfo:
        if self.fh is None:
            raise EngineError("Not connected (run connect() first).")
        # Storage identity comes from the Firehose <configure> ACK / storage info.
        return DeviceInfo(platform="qualcomm", chip="Qualcomm (EDL)",
                          port=getattr(self.transport, "port_name", ""),
                          details={"mem": self.mem})

    def flash(self, steps: List[dict], safety: SafetyConfig) -> None:
        if self.fh is None:
            raise EngineError("Not connected.")
        for s in steps:
            name, fpath = s["partition"], s.get("file", "")
            guard_write(name, fpath, s.get("size", 0), safety)
            if "lun" not in s or "start_sector" not in s:
                raise EngineError(f"Partition '{name}' needs lun/start_sector from the rawprogram map.")
            self.step(StepUpdate(name, "WRITE", fpath, "RUNNING"))
            with open(fpath, "rb") as f:
                data = f.read()
            self.fh.program(s["lun"], s["start_sector"], data)
            self.step(StepUpdate(name, "WRITE", fpath, "DONE"))

    def erase(self, partitions: List[dict], safety: SafetyConfig) -> None:
        if self.fh is None:
            raise EngineError("Not connected.")
        for p in partitions:
            name = p["partition"] if isinstance(p, dict) else p
            guard_erase(name, safety, context="erase")
            if not isinstance(p, dict) or "lun" not in p:
                raise EngineError(f"Erase of '{name}' needs lun/start_sector/num_sectors.")
            self.step(StepUpdate(name, "ERASE", "-", "RUNNING"))
            self.fh.erase(p["lun"], p["start_sector"], p["num_sectors"])
            self.step(StepUpdate(name, "ERASE", "-", "DONE"))

    def close(self) -> None:
        if self.fh is not None:
            try:
                self.fh.reset()
            except Exception:
                pass
