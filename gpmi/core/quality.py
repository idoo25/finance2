"""Index quality score.

Each published index value carries a 0..1 quality score blending source
coverage, geographic diversity, data freshness and outlier consistency. Low
scores signal a thin or stale snapshot even when the index still computes.
"""
from __future__ import annotations

from .types import AssetPrice, Freshness

# weights from the spec
W_COVERAGE = 0.40
W_DIVERSITY = 0.25
W_FRESHNESS = 0.20
W_OUTLIER = 0.15

_FRESHNESS_SCORE = {
    Freshness.FRESH: 1.0,
    Freshness.VALID_DAILY: 0.85,
    Freshness.VALID_WEEKLY: 0.6,
    Freshness.STALE: 0.3,
    Freshness.REJECT: 0.0,
}


def classify_freshness(age_days: float, t) -> Freshness:
    if age_days <= t.fresh_days:
        return Freshness.FRESH
    if age_days <= t.valid_daily_days:
        return Freshness.VALID_DAILY
    if age_days <= t.valid_weekly_days:
        return Freshness.VALID_WEEKLY
    if age_days <= t.reject_days:
        return Freshness.STALE
    return Freshness.REJECT


def quality_score(
    asset_prices: list[AssetPrice],
    *,
    expected_sources_per_asset: int,
    freshness: Freshness,
    outlier_consistency: float,
) -> float:
    if not asset_prices:
        return 0.0
    ok = [a for a in asset_prices if a.valid_source_count > 0]
    if not ok:
        return 0.0

    coverage = sum(
        min(1.0, a.valid_source_count / max(1, expected_sources_per_asset)) for a in ok
    ) / len(ok)

    diversity = sum(min(1.0, len(set(a.regions)) / 2.0) for a in ok) / len(ok)

    freshness_score = _FRESHNESS_SCORE.get(freshness, 0.0)

    score = (
        W_COVERAGE * coverage
        + W_DIVERSITY * diversity
        + W_FRESHNESS * freshness_score
        + W_OUTLIER * max(0.0, min(1.0, outlier_consistency))
    )
    return round(score, 4)
