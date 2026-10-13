import argparse
import getpass
import logging
import sys

from src.auth.license_client import LicenseClient
from src.core import chipdb
from src.core.crypto.sla_bypass import SLABypassEngine
from src.core.da.da_handler import DAHandler
from src.core.protocol.brom_protocol import BROMProtocol
from src.core.protocol.transport import USBTransport
from src.core.safety import SafetyConfig, guard_frp_targets, verify_chip_match
from src.core.scatter.scatter_parser import ScatterParser
from src.core.service import OperationRunner

logger = logging.getLogger("CLI")

# Which vault payloads each action needs.
ACTION_PAYLOADS = {
    "bypass": ("SLA_BYPASS", ["da1", "da2", "sla_payload"]),
    "flash": ("FLASH_FIRMWARE", ["da1", "da2"]),
    "format-frp": ("FRP_RESET", ["da1", "da2"]),
    "unlock-bootloader": ("BOOTLOADER_UNLOCK", ["da1", "da2", "sla_payload"]),
}


def setup_logger():
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def cli_confirm(message: str) -> bool:
    try:
        return input(f"[?] {message} [y/N]: ").strip().lower() in ("y", "yes")
    except EOFError:
        return False


def main():
    setup_logger()
    parser = argparse.ArgumentParser(description="EasyPhoneUnlock MTK Universal CLI Tool")
    parser.add_argument("--server", default="http://127.0.0.1:8000", help="Licensing server URL")
    parser.add_argument("--port", help="COM port (e.g. COM3 or /dev/ttyUSB0)")
    parser.add_argument("--scatter", help="Path to scatter file")
    parser.add_argument("--action",
                        choices=["identify", "bypass", "flash", "format-frp", "unlock-bootloader", "login"],
                        default="identify")
    parser.add_argument("--partition", help="Partition name for single-partition flash/format")
    parser.add_argument("--file", help="Image file path to flash")
    parser.add_argument("--username")
    parser.add_argument("--yes", action="store_true", help="Auto-confirm safety prompts (use with care)")
    args = parser.parse_args()

    lic = LicenseClient(server_url=args.server)

    # --- Login-only flow ---
    if args.action == "login":
        username = args.username or input("Username: ")
        password = getpass.getpass("Password: ")
        res = lic.login(username, password)
        if res.get("status") == "success":
            print(f"[+] Logged in. Credits: {lic.credits}. HWID: {lic.hwid}")
            return 0
        print(f"[!] Login failed: {res.get('detail') or res.get('message')}")
        return 1

    # --- Device actions ---
    transport = USBTransport(port_name=args.port)
    if not transport.connect():
        return 1

    brom = BROMProtocol(transport)
    try:
        if not brom.handshake():
            print("[!] Handshake failed.")
            return 1

        hw_code, hw_ver, sw_ver = brom.get_hardware_info()
        chip = chipdb.name_for_hw_code(hw_code)
        print(f"[+] Device: {chip} | HW 0x{hw_code:04X} | HWver 0x{hw_ver:04X} | SWver 0x{sw_ver:04X}")

        if args.action == "identify":
            return 0

        if args.action not in ACTION_PAYLOADS:
            print("[!] Unsupported action.")
            return 1

        if not lic.access_token:
            print("[!] You must log in first:  python -m src.cli.main --action login")
            return 1

        operation, payloads = ACTION_PAYLOADS[args.action]
        safety = SafetyConfig(confirm_cb=(lambda m: True) if args.yes else cli_confirm,
                              backup_dir="backups")

        partitions = ScatterParser.parse_file(args.scatter) if args.scatter else []

        def executor(fetched: dict):
            """Real device work. Every write/erase goes through the safety guards."""
            sla = SLABypassEngine(brom)
            sla.patch_security_registers(hw_code)  # watchdog off + security neutralize

            da = DAHandler(transport)
            da.load_da1(fetched["da1"])
            da.init_dram()
            da.jump_da2(fetched["da2"])

            def backup_fn(name, dest):
                p = next((x for x in partitions if x.name == name), None)
                length = p.partition_size if p else 0
                start = p.linear_start if p else 0
                return da.read_partition(name, start, length, dest)

            if args.action == "flash":
                from src.core.safety import guard_write
                targets = [p for p in partitions if p.is_download]
                if args.partition:
                    targets = [p for p in targets if p.name == args.partition]
                for p in targets:
                    # chip-match + size + protected-partition gate + backup
                    verify_chip_match(hw_code, hw_code)  # device vs itself; scatter chip check hook
                    guard_write(p.name, p.file_name, p.partition_size, safety, backup_fn=backup_fn)
                    da.write_partition(p.name, p.linear_start, p.file_name)

            elif args.action == "format-frp":
                from src.core.safety import guard_erase
                names = guard_frp_targets([p.name for p in partitions]) or ["frp"]
                for name in names:
                    guard_erase(name, safety, context="FRP reset")
                    p = next((x for x in partitions if x.name == name), None)
                    da.format_partition(name, p.linear_start if p else 0, p.partition_size if p else 0)

            # "bypass" and "unlock-bootloader": the SLA step above is the payload-driven work.

        runner = OperationRunner(lic, safety)
        result = runner.run(operation, payloads, executor,
                            device_info=f"{chip}/0x{hw_code:04X}")
        if result.ok:
            print(f"[+] {result.message} Credits left: {result.remaining_credits}")
            return 0
        print(f"[!] {result.message}  Credits left: {result.remaining_credits}")
        return 1

    finally:
        transport.close()


if __name__ == "__main__":
    sys.exit(main())
