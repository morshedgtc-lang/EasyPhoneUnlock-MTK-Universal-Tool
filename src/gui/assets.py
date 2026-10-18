"""Original brand assets (logo/icon) as inline SVG + helpers to render them.

Embedded as strings so they work inside the single-file EXE with no external
files. Original artwork (a flash bolt on a rounded gradient tile) — not derived
from any third-party brand.
"""
from PyQt6.QtCore import QByteArray, Qt
from PyQt6.QtGui import QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

# App/tile icon — gradient rounded square with a lightning bolt (flash) and a
# small open-padlock notch (unlock). All original shapes.
ICON_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#7c5cff"/>
      <stop offset="1" stop-color="#19d3c5"/>
    </linearGradient>
  </defs>
  <rect x="8" y="8" width="240" height="240" rx="58" fill="url(#g)"/>
  <rect x="8" y="8" width="240" height="240" rx="58" fill="none"
        stroke="rgba(255,255,255,0.20)" stroke-width="2"/>
  <!-- open padlock ring (unlock) -->
  <path d="M150 86 v-14 a26 26 0 0 1 52 0 v10"
        fill="none" stroke="rgba(255,255,255,0.55)" stroke-width="12" stroke-linecap="round"/>
  <!-- lightning bolt (flash) -->
  <path d="M138 36 L70 150 H112 L104 226 L190 104 H142 Z"
        fill="#ffffff" stroke="rgba(0,0,0,0.08)" stroke-width="1"/>
</svg>
"""

# Compact square mark for the title bar / login (just the tile).
MARK_SVG = ICON_SVG


def svg_pixmap(svg: str, width: int, height: int | None = None) -> QPixmap:
    height = height or width
    renderer = QSvgRenderer(QByteArray(svg.strip().encode("utf-8")))
    pm = QPixmap(width, height)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    renderer.render(painter)
    painter.end()
    return pm


def app_icon() -> QIcon:
    icon = QIcon()
    for s in (32, 64, 128, 256):
        icon.addPixmap(svg_pixmap(ICON_SVG, s))
    return icon
