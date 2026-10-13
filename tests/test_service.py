"""OperationRunner tests with a fake license client (no network, no hardware)."""
from src.core.safety import SafetyConfig, SafetyError
from src.core.service import OperationRunner


class FakeLicense:
    """Mimics LicenseClient's server-side contract and tracks refunds."""
    def __init__(self, credits=10):
        self._credits = credits
        self.reported = []
        self.payloads_fetched = []

    def authorize_operation(self, operation, device_info=""):
        if self._credits < 1:
            return {"status": "error", "message": "Insufficient credits."}
        self._credits -= 1
        return {"status": "success", "grant": "GRANT", "nonce": "N1",
                "remaining_credits": self._credits, "charged": 1}

    def fetch_payload(self, name, grant, dest_dir):
        self.payloads_fetched.append(name)
        import os
        p = os.path.join(dest_dir, f"{name}.bin")
        with open(p, "wb") as f:
            f.write(b"PAYLOAD")
        return p

    def report_result(self, nonce, success, detail=""):
        if not success:
            self._credits += 1  # refund, as the server does
        self.reported.append((nonce, success, detail))
        return {"status": "success", "remaining_credits": self._credits}


def _runner(lic, confirm=False):
    return OperationRunner(lic, SafetyConfig(confirm_cb=lambda m: confirm))


def test_success_path_charges_and_fetches():
    lic = FakeLicense(credits=5)
    runner = _runner(lic)
    executed = {}
    def executor(payloads):
        executed["paths"] = payloads
    res = runner.run("SLA_BYPASS", ["da1", "da2"], executor)
    assert res.ok
    assert res.remaining_credits == 4           # charged 1, not refunded
    assert lic.payloads_fetched == ["da1", "da2"]
    assert set(executed["paths"].keys()) == {"da1", "da2"}
    assert lic.reported == [("N1", True, "ok")]


def test_executor_failure_triggers_refund():
    lic = FakeLicense(credits=5)
    runner = _runner(lic)
    def executor(payloads):
        raise RuntimeError("device disconnected")
    res = runner.run("FLASH_FIRMWARE", ["da1"], executor)
    assert not res.ok
    assert res.remaining_credits == 5           # refunded back
    assert lic.reported[-1][1] is False


def test_safety_block_triggers_refund():
    lic = FakeLicense(credits=5)
    runner = _runner(lic)
    def executor(payloads):
        raise SafetyError("preloader write declined")
    res = runner.run("FLASH_FIRMWARE", ["da1"], executor)
    assert not res.ok
    assert "device safety" in res.message.lower()
    assert res.remaining_credits == 5           # refunded, safety never costs a credit


def test_no_credits_blocks_before_execution():
    lic = FakeLicense(credits=0)
    runner = _runner(lic)
    ran = {"x": False}
    def executor(payloads):
        ran["x"] = True
    res = runner.run("SLA_BYPASS", ["da1"], executor)
    assert not res.ok
    assert ran["x"] is False
    assert lic.payloads_fetched == []
