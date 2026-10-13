"""Engine registry: platform routing + USB-signature detection + MTK identify mapping."""
import pytest

from src.core.engines import registry
from src.core.engines.base import DeviceEngine


def test_platform_for_chip():
    assert registry.platform_for_chip("MT6765") == "mtk"
    assert registry.platform_for_chip("MT6991") == "mtk"
    assert registry.platform_for_chip("SM6115") == "qualcomm"
    assert registry.platform_for_chip("SDM845") == "qualcomm"
    assert registry.platform_for_chip("UMS512") == "unisoc"
    assert registry.platform_for_chip("SC9863A") == "unisoc"


def test_platform_for_usb():
    assert registry.platform_for_usb(0x0E8D, 0x0003) == "mtk"
    assert registry.platform_for_usb(0x05C6, 0x9008) == "qualcomm"
    assert registry.platform_for_usb(0x1782, 0x4D00) == "unisoc"
    assert registry.platform_for_usb(0x1234, 0x5678) is None


def test_get_engine_class_returns_engine_subclasses():
    for p in ("mtk", "qualcomm", "unisoc"):
        cls = registry.get_engine_class(p)
        assert issubclass(cls, DeviceEngine)
        assert cls.platform == p


def test_available_platforms_reports_readiness():
    status = registry.available_platforms()
    assert status["mtk"] is True            # identify path is real
    assert status["qualcomm"] is False      # scaffold
    assert status["unisoc"] is False        # scaffold


def test_unknown_platform_raises():
    with pytest.raises(ValueError):
        registry.get_engine_class("potato")


def test_scaffold_engines_fail_cleanly():
    from src.core.engines.base import EngineError
    for p in ("qualcomm", "unisoc"):
        eng = registry.get_engine_class(p)()
        with pytest.raises(EngineError):
            eng.connect()
