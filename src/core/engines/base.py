"""Common interface every device engine implements."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from src.core.safety import SafetyConfig


@dataclass
class DeviceInfo:
    platform: str                 # mtk | qualcomm | unisoc
    chip: str = "UNKNOWN"
    port: str = ""
    details: Dict[str, str] = field(default_factory=dict)


@dataclass
class StepUpdate:
    partition: str
    action: str                   # READ | WRITE | ERASE
    filename: str = ""
    state: str = "RUNNING"        # RUNNING | DONE | FAIL


class EngineError(Exception):
    pass


class DeviceEngine(ABC):
    """
    Low-level device engine. The orchestrator connects, identifies, then runs
    operations through the engine while the safety layer guards every write.

    `log` and `step` are callbacks the engine uses to stream progress to the UI.
    """
    platform: str = "generic"

    def __init__(self, port: Optional[str] = None,
                 log: Callable[[str, str], None] = lambda level, msg: None,
                 step: Callable[[StepUpdate], None] = lambda u: None):
        self.port = port
        self.log = log
        self.step = step

    @abstractmethod
    def connect(self) -> bool:
        """Open the port / enter download mode. Returns True on success."""

    @abstractmethod
    def identify(self) -> DeviceInfo:
        """Read chip identity. Read-only, safe."""

    @abstractmethod
    def flash(self, steps: List[dict], safety: SafetyConfig) -> None:
        """Write the given partitions. Each step: {partition,file,start,size}."""

    @abstractmethod
    def erase(self, partitions: List[str], safety: SafetyConfig) -> None:
        """Erase/format the given partitions."""

    def close(self) -> None:
        pass
