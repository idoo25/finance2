"""Normalize a raw observation to USD in the asset's target unit.

Two steps: convert the quote currency to USD using the aggregated FX rates,
then convert the native unit to the asset's target unit. Sources quoted in a
currency we cannot price (frozen / missing FX) are rejected rather than guessed.
"""
from __future__ import annotations

from .config import AssetConfig
from .types import AssetStatus, FxRate, NormalizedPrice, RawPrice
from .units import convert


class NormalizationError(ValueError):
    pass


def normalize(raw: RawPrice, asset: AssetConfig, fx_rates: dict[str, FxRate]) -> NormalizedPrice:
    currency = raw.currency.upper()
    if currency == "USD":
        price_usd_native = raw.price
    else:
        fx = fx_rates.get(currency)
        if fx is None or fx.status == AssetStatus.FROZEN or not fx.rate or fx.rate <= 0:
            raise NormalizationError(f"no FX to price {currency} for {raw.source_id}")
        # price is currency-per-unit; rate is currency-per-USD -> USD-per-unit.
        price_usd_native = raw.price / fx.rate

    price_usd = convert(price_usd_native, raw.unit, asset.target_unit, asset.commodity)
    return NormalizedPrice(
        asset_id=asset.id,
        source_id=raw.source_id,
        region=raw.region,
        price_usd=price_usd,
        target_unit=asset.target_unit,
        timestamp=raw.timestamp,
    )
