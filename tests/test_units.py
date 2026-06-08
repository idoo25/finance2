import math

import pytest

from gpmi.core.units import (
    GRAMS_PER_TROY_OUNCE,
    UnitConversionError,
    convert,
)


def test_troy_ounce_to_gram_roundtrip():
    # $3110.35/oz -> ~$100/gram
    per_gram = convert(GRAMS_PER_TROY_OUNCE * 100, "USD_PER_TROY_OUNCE", "USD_PER_GRAM")
    assert math.isclose(per_gram, 100.0, rel_tol=1e-9)
    back = convert(per_gram, "USD_PER_GRAM", "USD_PER_TROY_OUNCE")
    assert math.isclose(back, GRAMS_PER_TROY_OUNCE * 100, rel_tol=1e-9)


def test_pound_to_metric_ton():
    # $1/lb -> $2204.62/metric ton
    per_ton = convert(1.0, "USD_PER_POUND", "USD_PER_METRIC_TON")
    assert math.isclose(per_ton, 2204.6226, rel_tol=1e-4)


def test_bushel_requires_commodity():
    with pytest.raises(UnitConversionError):
        convert(6.0, "USD_PER_BUSHEL", "USD_PER_METRIC_TON")


def test_wheat_bushel_to_ton():
    # 1 wheat bushel = 27.2155 kg -> 36.744 bushels per ton
    per_ton = convert(1.0, "USD_PER_BUSHEL", "USD_PER_METRIC_TON", commodity="wheat")
    assert math.isclose(per_ton, 1000.0 / 27.2155, rel_tol=1e-6)


def test_mwh_to_mmbtu():
    # 1 MWh = 3.412 MMBtu, so $1/MWh is a lower price per (smaller) MMBtu unit.
    per_mmbtu = convert(1.0, "USD_PER_MWH", "USD_PER_MMBTU")
    assert math.isclose(per_mmbtu, 1.0 / 3.412141633, rel_tol=1e-9)


def test_cross_dimension_rejected():
    with pytest.raises(UnitConversionError):
        convert(1.0, "USD_PER_BARREL", "USD_PER_GRAM")
