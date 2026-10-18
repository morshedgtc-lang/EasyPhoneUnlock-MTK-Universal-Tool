"""
Server-side truth for what each paid operation costs, which encrypted payload(s)
it unlocks, and whether it is "sensitive" (requires technician consent + an IMEI
or serial, and is written to the audit trail for traceability).

The client NEVER decides cost or sensitivity — it can only ask; the server
charges the fixed amount and enforces the rules here.
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
    "NETWORK_UNLOCK": 4,
    "IMEI_REPAIR": 5,
    "BACKUP_FLASH": 1,
    "BACKUP_SECURITY": 2,
}

# which vault payload names a given operation's grant is allowed to fetch
# Loader names per platform: MTK = da1/da2, Qualcomm = loader (Firehose),
# Unisoc = fdl1/fdl2. Every op may fetch its own platform's loaders.
_ALL_LOADERS = ["da1", "da2", "loader", "fdl1", "fdl2"]
OPERATION_PAYLOADS: dict[str, list[str]] = {
    "SLA_BYPASS": _ALL_LOADERS + ["sla_payload"],
    "FLASH_FIRMWARE": _ALL_LOADERS,
    "FRP_RESET": _ALL_LOADERS,
    "FORMAT_PARTITION": _ALL_LOADERS,
    "NVRAM_REPAIR": _ALL_LOADERS,
    "BOOTLOADER_UNLOCK": _ALL_LOADERS + ["sla_payload"],
    "READBACK_DUMP": _ALL_LOADERS,
    "NETWORK_UNLOCK": _ALL_LOADERS,
    "IMEI_REPAIR": _ALL_LOADERS,
    "BACKUP_FLASH": _ALL_LOADERS,
    "BACKUP_SECURITY": _ALL_LOADERS,
}

# Operations that change device identity / remove protections. These REQUIRE
# the technician to confirm a consent prompt and to supply the device IMEI (or
# serial), and every attempt is recorded in the audit trail so the owner can
# trace misuse.
SENSITIVE_OPERATIONS = {
    "FRP_RESET",
    "NETWORK_UNLOCK",
    "IMEI_REPAIR",
    "BOOTLOADER_UNLOCK",
    "BACKUP_SECURITY",
}


def is_known(operation: str) -> bool:
    return operation in OPERATION_COSTS


def cost_of(operation: str) -> int:
    return OPERATION_COSTS[operation]


def payload_allowed(operation: str, payload_name: str) -> bool:
    return payload_name in OPERATION_PAYLOADS.get(operation, [])


def is_sensitive(operation: str) -> bool:
    return operation in SENSITIVE_OPERATIONS
