from datetime import timedelta

from gpmi.core.types import NormalizedPrice, RawPrice, utcnow
from gpmi.core.validation import (
    filter_outliers,
    is_stale,
    reject_invalid_prices,
)


def _raw(price, age_min=0, currency="USD"):
    return RawPrice(
        asset_id="gold", source_id="s", price=price, currency=currency,
        unit="USD_PER_TROY_OUNCE", timestamp=utcnow() - timedelta(minutes=age_min),
    )


def test_is_stale():
    ts = utcnow() - timedelta(minutes=90)
    assert is_stale(ts, max_staleness_minutes=60)
    assert not is_stale(ts, max_staleness_minutes=120)


def test_reject_nonpositive_and_stale():
    raws = [_raw(100), _raw(-5), _raw(0), _raw(100, age_min=120)]
    survivors = reject_invalid_prices(raws, max_staleness_minutes=60)
    assert len(survivors) == 1
    assert survivors[0].price == 100
    reasons = {r.rejection_reason for r in raws if not r.is_valid}
    assert reasons == {"non_positive", "stale"}


def _norm(price, sid="s"):
    return NormalizedPrice("gold", sid, "US", price, "USD_PER_TROY_OUNCE", utcnow())


def test_outlier_filtered_with_enough_sources():
    prices = [_norm(100), _norm(101), _norm(99), _norm(150)]
    kept = filter_outliers(prices, threshold_pct=5.0)
    assert len(kept) == 3
    assert all(p.price_usd < 110 for p in kept)


def test_outlier_kept_when_fewer_than_three():
    prices = [_norm(100), _norm(150)]
    kept = filter_outliers(prices, threshold_pct=5.0)
    assert len(kept) == 2
