import os
import pytest

from src.core import safety
from src.core.safety import SafetyConfig, SafetyError


def test_chip_match_blocks_mismatch():
    with pytest.raises(SafetyError):
        safety.verify_chip_match(0x0766, 0x0816)  # MT6765 image on MT6833


def test_chip_match_allows_equal():
    safety.verify_chip_match(0x0766, 0x0766)  # no raise


def test_validate_image_missing(tmp_path):
    with pytest.raises(SafetyError):
        safety.validate_image("boot", str(tmp_path / "nope.img"), 1024)


def test_validate_image_too_big(tmp_path):
    f = tmp_path / "boot.img"
    f.write_bytes(b"x" * 2048)
    with pytest.raises(SafetyError):
        safety.validate_image("boot", str(f), 1024)  # overflow


def test_validate_image_ok(tmp_path):
    f = tmp_path / "boot.img"
    f.write_bytes(b"x" * 512)
    assert safety.validate_image("boot", str(f), 1024) == 512


def test_protected_partition_requires_confirmation(tmp_path):
    f = tmp_path / "preloader.img"
    f.write_bytes(b"x" * 100)
    cfg = SafetyConfig(confirm_cb=lambda m: False, backup_dir=str(tmp_path / "bk"))
    with pytest.raises(SafetyError):
        safety.guard_write("preloader", str(f), 4096, cfg)


def test_protected_partition_backs_up_when_confirmed(tmp_path):
    f = tmp_path / "preloader.img"
    f.write_bytes(b"x" * 100)
    calls = {}

    def backup_fn(name, dest):
        calls["name"] = name
        with open(dest, "wb") as fh:
            fh.write(b"orig")
        return dest

    cfg = SafetyConfig(confirm_cb=lambda m: True, backup_dir=str(tmp_path / "bk"))
    safety.guard_write("preloader", str(f), 4096, cfg, backup_fn=backup_fn)
    assert calls["name"] == "preloader"
    assert os.path.isfile(str(tmp_path / "bk" / "preloader.backup.bin"))


def test_non_protected_partition_no_confirm_needed(tmp_path):
    f = tmp_path / "system.img"
    f.write_bytes(b"x" * 100)
    cfg = SafetyConfig(confirm_cb=lambda m: False)  # would deny, but not needed
    safety.guard_write("system", str(f), 4096, cfg)  # no raise


def test_frp_targets_filtered():
    out = safety.guard_frp_targets(["frp", "preloader", "userdata", "boot"])
    assert "frp" in out and "userdata" in out
    assert "preloader" not in out and "boot" not in out


def test_guard_erase_protected_denied():
    cfg = SafetyConfig(confirm_cb=lambda m: False)
    with pytest.raises(SafetyError):
        safety.guard_erase("nvram", cfg)
