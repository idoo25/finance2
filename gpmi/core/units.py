"""Unit conversion.

Every source quotes a commodity in its own unit. Before we can compare or take
a median, all sources for one asset must be expressed in that asset's
``target_unit``. We never mix bushels, pounds, troy ounces, barrels and metric
tons without an explicit conversion.

A price is expressed as ``currency per unit``. To convert a price from one unit
to another we use the size of each unit in a shared canonical base for its
dimension::

    price_target = price_source * (base_per_target_unit / base_per_source_unit)

Mass-based bushels are commodity specific (a bushel of wheat and a bushel of
corn weigh different amounts), so conversions touching ``bushel`` require the
asset's commodity key.
"""
from __future__ import annotations

# Canonical bases per dimension:
#   mass   -> grams
#   energy -> MMBtu
#   volume -> barrel  (oil)
# A unit maps to (dimension, base_units_per_one_unit).
_MASS = "mass"
_ENERGY = "energy"
_VOLUME = "volume"

GRAMS_PER_TROY_OUNCE = 31.1034768
GRAMS_PER_POUND = 453.59237
GRAMS_PER_METRIC_TON = 1_000_000.0
MMBTU_PER_MWH = 3.412141633

# Bushel weight is commodity dependent (US standard bushel weights, kg).
_BUSHEL_KG = {
    "wheat": 27.2155,
    "soybeans": 27.2155,
    "corn": 25.401172,
    "rice": 20.411657,
}

_UNITS = {
    "USD_PER_GRAM": (_MASS, 1.0),
    "USD_PER_TROY_OUNCE": (_MASS, GRAMS_PER_TROY_OUNCE),
    "USD_PER_POUND": (_MASS, GRAMS_PER_POUND),
    "USD_PER_METRIC_TON": (_MASS, GRAMS_PER_METRIC_TON),
    "USD_PER_BARREL": (_VOLUME, 1.0),
    "USD_PER_MMBTU": (_ENERGY, 1.0),
    "USD_PER_MWH": (_ENERGY, MMBTU_PER_MWH),
}


class UnitConversionError(ValueError):
    """Raised when two units cannot be converted into one another."""


def _base_per_unit(unit: str, commodity: str | None) -> tuple[str, float]:
    unit = unit.upper()
    if unit.startswith("USD_PER_BUSHEL"):
        if not commodity or commodity not in _BUSHEL_KG:
            raise UnitConversionError(
                f"bushel conversion needs a known commodity, got {commodity!r}"
            )
        return _MASS, _BUSHEL_KG[commodity] * 1000.0  # kg -> grams
    if unit not in _UNITS:
        raise UnitConversionError(f"unknown unit {unit!r}")
    return _UNITS[unit]


def convert(price: float, from_unit: str, to_unit: str, commodity: str | None = None) -> float:
    """Convert a ``currency per unit`` price between units of the same dimension."""
    from_dim, from_size = _base_per_unit(from_unit, commodity)
    to_dim, to_size = _base_per_unit(to_unit, commodity)
    if from_dim != to_dim:
        raise UnitConversionError(
            f"cannot convert {from_unit} ({from_dim}) to {to_unit} ({to_dim})"
        )
    return price * (to_size / from_size)
