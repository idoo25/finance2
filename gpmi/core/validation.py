"""Per-source validation rules.

The pipeline rejects a source if it is non-positive, stale, or an outlier
relative to the median of its peers. An asset is frozen if too few sources
survive. None of these rules trusts a single feed.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from .aggregation import median
from .types import NormalizedPrice, RawPrice, utcnow


def is_positive(price: float) -> bool:
    return price is not None and price > 0


def staleness_seconds(timestamp: datetime, now: datetime | None = None) -> float:
    now = now or utcnow()
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return (now - timestamp).total_seconds()


def is_stale(timestamp: datetime, max_staleness_minutes: float, now: datetime | None = None) -> bool:
    return staleness_seconds(timestamp, now) > max_staleness_minutes * 60.0


def reject_invalid_prices(raws: Sequence[RawPrice], now: datetime | None = None,
                          max_staleness_minutes: float = 60.0) -> list[RawPrice]:
    """Mark non-positive and stale raws; return the survivors (also marked)."""
    survivors: list[RawPrice] = []
    for r in raws:
        if not is_positive(r.price):
            r.is_valid = False
            r.rejection_reason = "non_positive"
            continue
        if is_stale(r.timestamp, max_staleness_minutes, now):
            r.is_valid = False
            r.rejection_reason = "stale"
            continue
        r.is_valid = True
        r.rejection_reason = None
        survivors.append(r)
    return survivors


def filter_outliers(prices: Sequence[NormalizedPrice], threshold_pct: float) -> list[NormalizedPrice]:
    """Drop sources whose USD price deviates from the peer median by more than
    ``threshold_pct`` percent. With fewer than 3 sources we cannot reliably tell
    an outlier from a legitimate spread, so we keep them all.
    """
    if len(prices) < 3:
        return list(prices)
    med = median([p.price_usd for p in prices])
    if med <= 0:
        return list(prices)
    limit = threshold_pct / 100.0
    return [p for p in prices if abs(p.price_usd - med) / med <= limit]
