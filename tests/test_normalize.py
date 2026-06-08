"""Normalization: currency -> USD then unit -> target unit."""
import math

import pytest

from gpmi.core.config import AssetConfig
from gpmi.core.normalize import NormalizationError, normalize
from gpmi.core.types import AssetStatus, FxRate, RawPrice, utcnow


def _gold():
    return AssetConfig(id="gold", name="Gold", target_unit="USD_PER_TROY_OUNCE",
                       category="precious_metal")


def test_usd_same_unit_is_identity():
    raw = RawPrice("gold", "s", 2915.0, "USD", "USD_PER_TROY_OUNCE", utcnow())
    n = normalize(raw, _gold(), {})
    assert math.isclose(n.price_usd, 2915.0)


def test_cross_currency_and_unit():
    # SGE-style: CNY per gram, FX 7.15 CNY/USD -> back to USD/oz
    raw = RawPrice("gold", "sge", 639.6, "CNY", "USD_PER_GRAM", utcnow())
    fx = {"CNY": FxRate("USD", "CNY", 7.15, 3)}
    n = normalize(raw, _gold(), fx)
    # 639.6 / 7.15 = 89.45 USD/gram; * 31.1035 ≈ 2782 USD/oz
    assert 2700 < n.price_usd < 2850


def test_missing_fx_rejects():
    raw = RawPrice("gold", "sge", 639.6, "CNY", "USD_PER_GRAM", utcnow())
    with pytest.raises(NormalizationError):
        normalize(raw, _gold(), {})


def test_frozen_fx_rejects():
    raw = RawPrice("gold", "sge", 639.6, "CNY", "USD_PER_GRAM", utcnow())
    fx = {"CNY": FxRate("USD", "CNY", float("nan"), 0, AssetStatus.FROZEN)}
    with pytest.raises(NormalizationError):
        normalize(raw, _gold(), fx)
