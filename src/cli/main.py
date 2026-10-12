import argparse
import sys
import os
import logging
from src.core.protocol.transport import USBTransport
from src.core.protocol.brom_protocol import BROMProtocol
from src.core.crypto.sla_bypass import SLABypassEngine
from src.core.scatter.scatter_parser import ScatterParser
from src.core.da.da_handler import DAHandler

def setup_logger():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

def main():
    setup_logger()
    parser = argparse.ArgumentParser(description="EasyPhoneUnlock MTK Universal CLI Tool")
    parser.add_argument("--port", type=str, help="Specific COM port (e.g. COM3 or /dev/ttyUSB0)")
    parser.add_argument("--scatter", type=str, help="Path to scatter file")
    parser.add_argument("--action", choices=["identify", "bypass", "flash", "format-frp", "unlock-bootloader"], default="identify")
    parser.add_argument("--partition", type=str, help="Partition name for single partition flash/format")
    parser.add_argument("--file", type=str, help="Image file path to flash")
    
    args = parser.parse_args()

    transport = USBTransport(port_name=args.port)
    if not transport.connect():
        sys.exit(1)

    brom = BROMProtocol(transport)
    sla_engine = SLABypassEngine(brom)

    try:
        if not brom.handshake():
            print("[!] Handshake failed.")
            sys.exit(1)

        hw_code, hw_ver, sw_ver = brom.get_hardware_info()
        print(f"[+] Device Identified: HW Code 0x{hw_code:04X} | HW Ver 0x{hw_ver:04X} | SW Ver 0x{sw_ver:04X}")

        if args.action in ["bypass", "flash", "format-frp", "unlock-bootloader"]:
            sla_engine.patch_security_registers(hw_code)

        if args.action == "flash" and args.scatter:
            partitions = ScatterParser.parse_file(args.scatter)
            print(f"[+] Loaded scatter file with {len(partitions)} partitions.")
            da_handler = DAHandler(transport)
            # Proceed with flashing sequence
            
    finally:
        transport.close()

if __name__ == "__main__":
    main()
