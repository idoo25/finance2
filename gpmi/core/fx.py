"""FX rate aggregation.

FX is treated like any other asset: never a single provider. Each currency's
USD rate is the median of several free sources (ECB, Frankfurter, Stooq, ...),
after staleness and outlier filtering.

Convention: a rate is *units of the quote currency per 1 USD*. USD is 1.0 by
definition. FX observations are carried as ``RawPrice`` with ``asset_id`` of the
form ``fx_<CCY>`` and ``unit == "PER_USD"``.
"""
from __future__ import annotations

from datetime import datetime

from .aggregation import median
from .types import AssetStatus, FxRate, RawPrice
from .validation import filter_outliers, reject_invalid_prices
from .types import NormalizedPrice


def fx_asset_id(currency: str) -> str:
    return f"fx_{currency.upper()}"


def compute_fx_rates(
    raws: list[RawPrice],
    currencies: list[str],
    *,
    max_staleness_minutes: float,
    outlier_threshold_pct: float,
    now: datetime | None = None,
) -> dict[str, FxRate]:
    """Return ``{currency: FxRate}`` (units of currency per 1 USD)."""
    rates: dict[str, FxRate] = {}
    rates["USD"] = FxRate(base="USD", quote="USD", rate=1.0, source_count=1)

    by_ccy: dict[str, list[RawPrice]] = {}
    for r in raws:
        by_ccy.setdefault(r.currency.upper(), []).append(r)

    for ccy in currencies:
        if ccy == "USD":
            continue
        observations = by_ccy.get(ccy, [])
        survivors = reject_invalid_prices(
            observations, now=now, max_staleness_minutes=max_staleness_minutes
        )
        # Reuse the outlier filter by wrapping as NormalizedPrice.
        wrapped = [
            NormalizedPrice(r.asset_id, r.source_id, r.region, r.price, "PER_USD", r.timestamp)
            for r in survivors
        ]
        filtered = filter_outliers(wrapped, outlier_threshold_pct)
        if not filtered:
            rates[ccy] = FxRate(base="USD", quote=ccy, rate=float("nan"),
                                source_count=0, status=AssetStatus.FROZEN)
            continue
        rate = median([p.price_usd for p in filtered])
        rates[ccy] = FxRate(base="USD", quote=ccy, rate=rate, source_count=len(filtered))
    return rates
