"""Lookup helpers over config/chip_config.json (hw_code <-> chipset name)."""
import json
from functools import lru_cache
from typing import Optional

from src.core.paths import config_path


@lru_cache
def _load() -> dict:
    with open(config_path("chip_config.json"), "r", encoding="utf-8") as f:
        return json.load(f)


def chip_by_hw_code(hw_code: int) -> Optional[dict]:
    """Return {'name', ...chip fields} for a detected hw_code, or None."""
    for name, data in _load().get("chips", {}).items():
        try:
            if int(str(data.get("hw_code", "0")), 16) == hw_code:
                return {"name": name, **data}
        except ValueError:
            continue
    return None


def name_for_hw_code(hw_code: int) -> str:
    chip = chip_by_hw_code(hw_code)
    return chip["name"] if chip else f"UNKNOWN(0x{hw_code:04X})"


def watchdog_base(hw_code: int, default: int = 0x10007000) -> int:
    chip = chip_by_hw_code(hw_code)
    if chip and "watchdog_base" in chip:
        return int(str(chip["watchdog_base"]), 16)
    return default
