import hashlib
import platform
import subprocess
import uuid
from typing import List


class HWIDGenerator:
    """
    Generates a stable, tamper-resistant Hardware Identifier bound to CPU ID,
    motherboard serial, system UUID and primary disk serial.

    On Windows this uses PowerShell CIM (Get-CimInstance). The legacy `wmic`
    command has been removed from Windows 11, so it is NOT used here — relying
    on it caused the HWID to silently collapse to a weak MAC-only fallback.
    """

    @staticmethod
    def _run_ps(script: str) -> str:
        try:
            out = subprocess.check_output(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                stderr=subprocess.DEVNULL,
                timeout=15,
            )
            return out.decode("utf-8", errors="ignore").strip()
        except Exception:
            return ""

    @staticmethod
    def _windows_components() -> List[str]:
        # One PowerShell call gathers every serial; blanks/placeholders dropped.
        script = (
            "$u=(Get-CimInstance Win32_ComputerSystemProduct).UUID;"
            "$c=(Get-CimInstance Win32_Processor | Select-Object -First 1).ProcessorId;"
            "$b=(Get-CimInstance Win32_BaseBoard | Select-Object -First 1).SerialNumber;"
            "$d=(Get-CimInstance Win32_DiskDrive | Sort-Object Index | Select-Object -First 1).SerialNumber;"
            "Write-Output \"$u|$c|$b|$d\""
        )
        raw = HWIDGenerator._run_ps(script)
        bad = {"", "none", "to be filled by o.e.m.", "default string",
               "0", "00000000", "ffffffff", "system serial number"}
        components = []
        for part in raw.split("|"):
            part = part.strip()
            if part and part.lower() not in bad:
                components.append(part)
        return components

    @staticmethod
    def get_hwid() -> str:
        raw_components: List[str] = [platform.system(), platform.machine()]

        if platform.system() == "Windows":
            raw_components.extend(HWIDGenerator._windows_components())
        else:
            # Linux: machine-id is a stable per-install identifier.
            for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
                try:
                    with open(path, "r") as f:
                        mid = f.read().strip()
                        if mid:
                            raw_components.append(mid)
                            break
                except Exception:
                    pass

        # Fallback to NIC MAC only if we gathered nothing hardware-specific.
        if len(raw_components) <= 2:
            raw_components.append(str(uuid.getnode()))

        combined = "EPU-MTK-AUTH::" + "::".join(raw_components)
        hashed = hashlib.sha256(combined.encode("utf-8")).hexdigest().upper()
        return f"EPU-{hashed[0:4]}-{hashed[4:8]}-{hashed[8:12]}-{hashed[12:16]}"


if __name__ == "__main__":
    print(f"[+] Your Machine HWID: {HWIDGenerator.get_hwid()}")
