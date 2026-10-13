"""Glass / clear UI stylesheet and Windows acrylic-blur helper."""

ACCENT = "#7c5cff"
ACCENT2 = "#19d3c5"

QSS = f"""
* {{
    font-family: "Segoe UI", "Inter", sans-serif;
    color: #eef0ff;
    outline: none;
}}

#Root {{
    background: transparent;
}}

/* The translucent glass card that holds everything */
#Glass {{
    background: rgba(22, 24, 40, 0.72);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 18px;
}}

#TitleBar {{ background: transparent; }}
#TitleLabel {{ font-size: 14px; font-weight: 600; letter-spacing: 0.5px; color: #cdd3ff; }}

QLabel#H1 {{ font-size: 22px; font-weight: 700; color: #ffffff; }}
QLabel#Sub {{ color: #9aa0c8; font-size: 12px; }}
QLabel.badge {{ color: {ACCENT2}; font-weight: 600; }}

/* Inputs */
QLineEdit, QComboBox {{
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.14);
    border-radius: 10px;
    padding: 9px 12px;
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QComboBox:focus {{ border: 1px solid {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox QAbstractItemView {{
    background: #1a1c2e; border: 1px solid rgba(255,255,255,0.12);
    selection-background-color: {ACCENT}; border-radius: 8px;
}}

/* Buttons */
QPushButton {{
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(255,255,255,0.14);
    border-radius: 12px;
    padding: 11px 16px;
    font-weight: 600;
}}
QPushButton:hover {{ background: rgba(255,255,255,0.13); border-color: {ACCENT}; }}
QPushButton:pressed {{ background: rgba(124,92,255,0.35); }}
QPushButton:disabled {{ color: #6b7099; background: rgba(255,255,255,0.03); }}

QPushButton#Primary {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {ACCENT}, stop:1 {ACCENT2});
    border: none; color: #0b0d18;
}}
QPushButton#Primary:hover {{ color: #000; }}
QPushButton#Danger {{ border-color: rgba(255,90,110,0.5); }}
QPushButton#Danger:hover {{ background: rgba(255,90,110,0.18); border-color: #ff5a6e; }}
QPushButton#Chip {{ padding: 7px 10px; border-radius: 9px; font-size: 11px; }}

/* Live log + table */
QPlainTextEdit, QTextEdit {{
    background: rgba(8,10,20,0.7);
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 12px;
    font-family: "Cascadia Code", "Consolas", monospace;
    font-size: 12px;
}}
QTableWidget {{
    background: rgba(8,10,20,0.55);
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 12px;
    gridline-color: rgba(255,255,255,0.06);
}}
QHeaderView::section {{
    background: rgba(255,255,255,0.06); color: #aeb4e0; border: none;
    padding: 6px; font-weight: 600;
}}

/* Progress slider */
QProgressBar {{
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 9px; height: 16px; text-align: center; color: #cdd3ff;
}}
QProgressBar::chunk {{
    border-radius: 8px;
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {ACCENT}, stop:1 {ACCENT2});
}}

/* QSlider (used for speed/intensity controls) */
QSlider::groove:horizontal {{ height: 6px; background: rgba(255,255,255,0.1); border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 3px; }}
QSlider::handle:horizontal {{
    background: #fff; width: 16px; height: 16px; margin: -6px 0; border-radius: 8px;
}}
"""


def apply_acrylic(win) -> None:
    """Best-effort Windows 11 acrylic/blur behind the window. No-op elsewhere."""
    try:
        import ctypes
        from ctypes import wintypes

        hwnd = int(win.winId())
        DWMWA_SYSTEMBACKDROP_TYPE = 38  # Win11: 2=Mica, 3=Acrylic, 4=Tabbed
        backdrop = ctypes.c_int(3)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            wintypes.HWND(hwnd), DWMWA_SYSTEMBACKDROP_TYPE,
            ctypes.byref(backdrop), ctypes.sizeof(backdrop))
        # Dark title/frame
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        dark = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            wintypes.HWND(hwnd), DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(dark), ctypes.sizeof(dark))
    except Exception:
        pass
