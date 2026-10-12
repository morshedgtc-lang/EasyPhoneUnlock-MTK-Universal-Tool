import re
import os
from typing import List, Dict, Optional

class ScatterPartition:
    def __init__(self, name: str, file_name: str, linear_start: int, physical_start: int, partition_size: int, region: str = "EMMC_USER"):
        self.name = name
        self.file_name = file_name
        self.linear_start = linear_start
        self.physical_start = physical_start
        self.partition_size = partition_size
        self.region = region
        self.is_download = True if file_name and file_name != "NONE" else False

    def __repr__(self):
        return f"<Partition {self.name} [Start: 0x{self.linear_start:012X}, Size: 0x{self.partition_size:012X}, File: {self.file_name}]>"

class ScatterParser:
    """
    Universal Parser for MediaTek Scatter files.
    Supports:
    - Legacy v1.x (Tab/Key-value syntax)
    - Modern v2.x (XML / YAML formatted scatter files)
    """

    @staticmethod
    def parse_file(scatter_path: str) -> List[ScatterPartition]:
        if not os.path.exists(scatter_path):
            raise FileNotFoundError(f"Scatter file not found: {scatter_path}")

        with open(scatter_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        if "general:" in content or "partition_index:" in content:
            return ScatterParser._parse_v2(content)
        else:
            return ScatterParser._parse_v1(content)

    @staticmethod
    def _parse_v1(content: str) -> List[ScatterPartition]:
        partitions = []
        blocks = content.split("__NODL_")
        # Legacy format regex matching
        pattern = re.compile(
            r"partition_name:\s*(\w+)\s*"
            r"file_name:\s*([^\r\n]+)\s*"
            r"is_download:\s*(\w+)\s*"
            r"linear_start_addr:\s*(0x[0-9a-fA-F]+)\s*"
            r"physical_start_addr:\s*(0x[0-9a-fA-F]+)\s*"
            r"partition_size:\s*(0x[0-9a-fA-F]+)",
            re.IGNORECASE
        )
        for match in pattern.finditer(content):
            p_name, f_name, is_dl, lin_addr, phys_addr, size = match.groups()
            partitions.append(
                ScatterPartition(
                    name=p_name.strip(),
                    file_name=f_name.strip(),
                    linear_start=int(lin_addr, 16),
                    physical_start=int(phys_addr, 16),
                    partition_size=int(size, 16)
                )
            )
        return partitions

    @staticmethod
    def _parse_v2(content: str) -> List[ScatterPartition]:
        partitions = []
        # Modern v2 scatter chunk matching
        part_pattern = re.compile(
            r"- partition_index:\s*SYS\d+\s*"
            r"  partition_name:\s*([^\r\n]+)\s*"
            r"  file_name:\s*([^\r\n]+)\s*"
            r"  is_download:\s*([^\r\n]+)\s*"
            r"  type:\s*([^\r\n]+)\s*"
            r"  linear_start_addr:\s*(0x[0-9a-fA-F]+)\s*"
            r"  physical_start_addr:\s*(0x[0-9a-fA-F]+)\s*"
            r"  partition_size:\s*(0x[0-9a-fA-F]+)\s*"
            r"  region:\s*([^\r\n]+)",
            re.IGNORECASE
        )
        for match in part_pattern.finditer(content):
            p_name, f_name, is_dl, p_type, lin_addr, phys_addr, size, region = match.groups()
            partitions.append(
                ScatterPartition(
                    name=p_name.strip(),
                    file_name=f_name.strip(),
                    linear_start=int(lin_addr, 16),
                    physical_start=int(phys_addr, 16),
                    partition_size=int(size, 16),
                    region=region.strip()
                )
            )
        return partitions
