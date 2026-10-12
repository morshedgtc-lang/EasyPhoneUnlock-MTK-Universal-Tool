import subprocess
import hashlib
import platform
import os
import uuid

class HWIDGenerator:
    """
    Generates a unique, tamper-resistant Hardware Identifier (HWID)
    bound to CPU ID, Motherboard Serial, BIOS UUID, and primary Disk UUID.
    """

    @staticmethod
    def get_hwid() -> str:
        raw_components = []

        # 1. OS details
        raw_components.append(platform.system())
        raw_components.append(platform.machine())

        # 2. Windows specific hardware serial queries via WMIC / PowerShell
        if platform.system() == "Windows":
            # Motherboard UUID
            try:
                out = subprocess.check_output("wmic csproduct get uuid", shell=True).decode().split()
                if len(out) >= 2:
                    raw_components.append(out[1].strip())
            except Exception:
                pass

            # CPU Processor ID
            try:
                out = subprocess.check_output("wmic cpu get processorid", shell=True).decode().split()
                if len(out) >= 2:
                    raw_components.append(out[1].strip())
            except Exception:
                pass

            # BaseBoard Serial
            try:
                out = subprocess.check_output("wmic baseboard get serialnumber", shell=True).decode().split()
                if len(out) >= 2:
                    raw_components.append(out[1].strip())
            except Exception:
                pass

            # Primary Disk Drive Serial
            try:
                out = subprocess.check_output("wmic diskdrive get serialnumber", shell=True).decode().split()
                if len(out) >= 2:
                    raw_components.append(out[1].strip())
            except Exception:
                pass

        # Fallback to system node/MAC if WMIC fails
        if len(raw_components) <= 2:
            raw_components.append(str(uuid.getnode()))

        # Combine, salt, and create cryptographic SHA-256 fingerprint
        combined = "EPU-MTK-AUTH::" + "::".join(raw_components)
        hashed = hashlib.sha256(combined.encode("utf-8")).hexdigest().upper()

        # Format into clean readable product-key format: EPU-XXXX-XXXX-XXXX-XXXX
        formatted_hwid = f"EPU-{hashed[0:4]}-{hashed[4:8]}-{hashed[8:12]}-{hashed[12:16]}"
        return formatted_hwid

if __name__ == "__main__":
    print(f"[+] Your Machine HWID: {HWIDGenerator.get_hwid()}")
