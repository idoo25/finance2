from datetime import timedelta

from gpmi.core.fx import compute_fx_rates, fx_asset_id
from gpmi.core.types import AssetStatus, RawPrice, utcnow


def _fx(currency, rate, sid, age_min=0):
    return RawPrice(
        asset_id=fx_asset_id(currency), source_id=sid, price=rate, currency=currency,
        unit="PER_USD", timestamp=utcnow() - timedelta(minutes=age_min),
    )


def test_usd_is_one():
    rates = compute_fx_rates([], ["USD"], max_staleness_minutes=60, outlier_threshold_pct=0.5)
    assert rates["USD"].rate == 1.0


def test_median_of_sources():
    raws = [_fx("EUR", 0.90, "a"), _fx("EUR", 0.92, "b"), _fx("EUR", 0.91, "c")]
    rates = compute_fx_rates(raws, ["USD", "EUR"], max_staleness_minutes=120,
                             outlier_threshold_pct=5.0)
    assert rates["EUR"].rate == 0.91
    assert rates["EUR"].source_count == 3


def test_outlier_dropped():
    raws = [_fx("EUR", 0.90, "a"), _fx("EUR", 0.901, "b"), _fx("EUR", 1.50, "c")]
    rates = compute_fx_rates(raws, ["USD", "EUR"], max_staleness_minutes=120,
                             outlier_threshold_pct=0.5)
    assert rates["EUR"].source_count == 2
    assert rates["EUR"].rate < 1.0


def test_frozen_when_no_sources():
    rates = compute_fx_rates([], ["USD", "JPY"], max_staleness_minutes=60,
                             outlier_threshold_pct=0.5)
    assert rates["JPY"].status == AssetStatus.FROZEN
