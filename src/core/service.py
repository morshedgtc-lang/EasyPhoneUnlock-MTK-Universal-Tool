"""
Operation orchestrator — the single entry point the GUI/CLI call for any paid
action. It enforces the full safe + authorized lifecycle:

    1. Ask the server to authorize the operation (credits deducted there).
    2. Download the required encrypted payloads via the grant.
    3. Run the operation through the device layer WITH the safety guards.
    4. Report success/failure to the server (a failure is auto-refunded).

If any step raises, the operation is reported as failed and credits come back,
so an aborted/blocked-by-safety action never costs the technician a credit.
"""
from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from src.auth.license_client import LicenseClient
from src.core.safety import SafetyConfig, SafetyError

logger = logging.getLogger("Service")


@dataclass
class OperationResult:
    ok: bool
    operation: str
    message: str
    remaining_credits: Optional[int] = None
    detail: str = ""


class OperationRunner:
    def __init__(self, license_client: LicenseClient, safety: SafetyConfig):
        self.lic = license_client
        self.safety = safety

    def run(
        self,
        operation: str,
        payload_names: List[str],
        executor: Callable[[Dict[str, str]], None],
        device_info: str = "",
    ) -> OperationResult:
        """
        operation    - server operation key (e.g. "SLA_BYPASS")
        payload_names- vault payloads this op needs (e.g. ["da1", "da2"])
        executor     - callable given {name: local_path} of fetched payloads;
                       does the real device work and raises on any failure.
        """
        # 1. Authorize (server deducts credit, returns grant)
        auth = self.lic.authorize_operation(operation, device_info)
        if auth.get("status") != "success":
            return OperationResult(False, operation,
                                   auth.get("detail") or auth.get("message", "Authorization failed."))
        grant = auth["grant"]
        nonce = auth["nonce"]

        # 2 + 3. Fetch payloads and execute, all guarded. Any problem -> refund.
        with tempfile.TemporaryDirectory(prefix="epu_payload_") as tmp:
            try:
                fetched: Dict[str, str] = {}
                for name in payload_names:
                    fetched[name] = self.lic.fetch_payload(name, grant, tmp)
                    logger.info("Fetched payload '%s'.", name)

                executor(fetched)  # real device work happens here

            except SafetyError as e:
                logger.error("Blocked by safety guard: %s", e)
                res = self.lic.report_result(nonce, False, f"safety: {e}")
                return OperationResult(False, operation, f"Blocked for device safety: {e}",
                                       res.get("remaining_credits"), str(e))
            except Exception as e:
                logger.exception("Operation failed.")
                res = self.lic.report_result(nonce, False, str(e)[:300])
                return OperationResult(False, operation, f"Operation failed: {e}",
                                       res.get("remaining_credits"), str(e))

        # 4. Success
        res = self.lic.report_result(nonce, True, "ok")
        return OperationResult(True, operation, "Operation completed successfully.",
                               res.get("remaining_credits"))
