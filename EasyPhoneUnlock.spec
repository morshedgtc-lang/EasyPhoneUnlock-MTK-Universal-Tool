# PyInstaller spec — builds a single Windows EXE of the GUI tool.
#   pip install pyinstaller
#   pyinstaller EasyPhoneUnlock.spec
# Output: dist/EasyPhoneUnlock.exe
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['run_gui.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config/chip_config.json', 'config'),
        ('config/device_models.json', 'config'),
        ('src/gui/assets/icon.svg', 'src/gui/assets'),
        ('src/gui/assets/icon.ico', 'src/gui/assets'),
        ('src/gui/assets/logo.svg', 'src/gui/assets'),
    ],
    hiddenimports=[
        'serial', 'serial.tools.list_ports',
        'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets',
        'PyQt6.QtSvg',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'pytest', 'uvicorn', 'fastapi', 'sqlalchemy'],
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='EasyPhoneUnlock',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    runtime_tmpdir=None,
    console=False,          # windowed GUI (no console)
    disable_windowed_traceback=False,
    icon='src/gui/assets/icon.ico',
)
