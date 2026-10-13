"""
Pluggable device engines for the universal flash tool.

One shared shell (UI, licensing, audit, catalog, firmware, safety) drives three
interchangeable low-level engines, selected by chip platform or USB signature:

    mtk       - MediaTek  : BROM -> Download Agent
    qualcomm  - Qualcomm  : EDL (Sahara + Firehose)
    unisoc    - Unisoc    : BootROM -> FDL1/FDL2

Each engine implements the DeviceEngine interface in base.py.
"""
