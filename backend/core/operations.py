"""
Server-side truth for what each paid operation costs and which encrypted
payload(s) it unlocks. The client NEVER decides cost — it can only ask, and the
server charges the fixed amount here.
"""

# credits charged per operation
OPERATION_COSTS: dict[str, int] = {
    "SLA_BYPASS": 1,
    "FLASH_FIRMWARE": 2,
    "FRP_RESET": 1,
    "FORMAT_PARTITION": 1,
    "NVRAM_REPAIR": 3,
    "BOOTLOADER_UNLOCK": 5,
    "READBACK_DUMP": 2,
}

# which vault payload names a given operation's grant is allowed to fetch
OPERATION_PAYLOADS: dict[str, list[str]] = {
    "SLA_BYPASS": ["da1", "da2", "sla_payload"],
    "FLASH_FIRMWARE": ["da1", "da2"],
    "FRP_RESET": ["da1", "da2"],
    "FORMAT_PARTITION": ["da1", "da2"],
    "NVRAM_REPAIR": ["da1", "da2"],
    "BOOTLOADER_UNLOCK": ["da1", "da2", "sla_payload"],
    "READBACK_DUMP": ["da1", "da2"],
}


def is_known(operation: str) -> bool:
    return operation in OPERATION_COSTS


def cost_of(operation: str) -> int:
    return OPERATION_COSTS[operation]


def payload_allowed(operation: str, payload_name: str) -> bool:
    return payload_name in OPERATION_PAYLOADS.get(operation, [])
