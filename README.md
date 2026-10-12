# EasyPhoneUnlock MTK Universal Flash & Service Tool

**EasyPhoneUnlock MTK Universal Tool** is a high-performance flashing, service, unlocking, and partition management tool for MediaTek (MTK) devices across all CPU generations (Legacy MT65xx, Helio Series, Dimensity 5G, and beyond).

---

## 🚀 Key Features

1. **Universal SoC Support:**
   - **Legacy:** MT6572, MT6580, MT6582, MT6592, etc.
   - **Helio Series:** Helio A22/P22/P35 (MT6761/MT6762/MT6765), Helio G25/G35/G80/G85/G88/G90T/G95/G96/G99 (MT6768, MT6785, MT6789, etc.), Helio P60/P70 (MT6771).
   - **Dimensity 5G Series:** Dimensity 6020/6080/700/720/800/810/820/900/920/1080/1200/8000/8100/9000+ (MT6833, MT6853, MT6873, MT6877, MT6893, MT6895, MT6983, MT6985, MT6989).

2. **Security & SLA/DAA Bypass Engine:**
   - Universal BootROM (BROM) handshake & synchronization (`0xA0 0x0A 0x50 0x05`).
   - Hardware register patching (Watchdog timer disable, Crypto engine disable).
   - Exploit payload delivery to bypass OEM SLA (Serial Link Authentication) and DAA (Download Agent Authentication) for Oppo, Realme, Xiaomi, Vivo, Infinix, Tecno, and Samsung MTK.

3. **DA (Download Agent) Multi-Stage Execution:**
   - **DA1 (Loader/EMI Setup):** External RAM / LPDDR4/5 calibration.
   - **DA2 (Storage Driver):** High-speed read/write access to eMMC 5.1 and UFS 2.1/2.2/3.1/4.0 storage.

4. **Flashing & Partition Management:**
   - Scatter format parser (v1.x tab-delimited and v2.x XML/YAML syntax).
   - Sparse unsparse handling (`system.img`, `super.img`, `userdata.img`).
   - Full readback / dump generation (eMMC/UFS raw blocks).
   - RPMB partition backup/write, NVRAM/NVDATA baseband protection.
   - Factory Reset / FRP removal / Bootloader unlock & relock.

---

## 📁 Repository Structure

```
EASY PHONE UNLOCK MTK TOOLS/
├── config/                  # Configuration templates and chip registries
│   ├── chip_config.json     # Chipset hardware codes, register offsets, watchdog addrs
│   └── app_settings.json    # Application UI and log configuration
├── da_database/             # Multi-version Download Agent binaries
├── drivers/                 # USB VCOM and LibUSB driver installers/filters
├── docs/                    # Architectural & Protocol documentation
│   ├── architecture/        # Modular pipeline design
│   ├── protocols/           # BROM, DA1, DA2 packet formats
│   └── api/                 # Developer API reference
├── payloads/                # Exploits & Payload binaries (Kamakiri, Amonet, Watchdog patch)
├── src/
│   ├── cli/                 # Command-line interface entrypoints
│   ├── core/
│   │   ├── crypto/          # SLA challenge responses, hashing, key parsing
│   │   ├── da/              # DA1 / DA2 stage handlers and command execution
│   │   ├── payloads/        # Shellcode delivery & memory write
│   │   ├── protocol/        # Low-level BROM & USB communication
│   │   └── scatter/         # Scatter file parser and partition mapper
│   ├── gui/                 # Modern GUI (PyQt6 / CustomTkinter / Web UI)
│   │   ├── assets/          # Icons, themes, styling
│   │   ├── controllers/     # UI logic controllers
│   │   └── views/           # UI window layouts and widgets
│   └── utils/               # Logging, sparse file handler, device monitor
├── tests/                   # Unit tests and protocol simulators
├── requirements.txt         # Python package dependencies
├── setup.py                 # Setup script
└── run_gui.py               # Main tool launcher
```

---

## 🛠️ Environment Setup & Installation

### 1. Requirements
- **OS:** Windows 10/11 (x64) / Linux (Ubuntu 20.04+)
- **Python:** 3.10+
- **USB Filter:** UsbDk or LibUSB-Win32 (for direct USB endpoint access)

### 2. Virtual Environment Setup
```powershell
# Create virtual environment
python -m venv venv

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### 3. Running the Tool
```powershell
# CLI Mode
python -m src.cli.main --help

# GUI Mode
python run_gui.py
```
