import math

from gpmi.core.config import AssetConfig, Config, Thresholds
from gpmi.core.index import compute_asset_price, compute_index
from gpmi.core.types import AssetStatus, FxRate, IndexStatus, NormalizedPrice, utcnow


def _norm(price, sid):
    return NormalizedPrice("gold", sid, "US", price, "USD_PER_TROY_OUNCE", utcnow())


def _asset(min_sources=2, threshold=1.5):
    return AssetConfig(id="gold", name="Gold", target_unit="USD_PER_TROY_OUNCE",
                       category="precious_metal", min_sources=min_sources,
                       outlier_threshold_pct=threshold)


def test_asset_price_median():
    ap = compute_asset_price(_asset(), [_norm(100, "a"), _norm(102, "b"), _norm(101, "c")])
    assert ap.status == AssetStatus.OK
    assert ap.median_price_usd == 101


def test_asset_freeze_too_few_sources():
    ap = compute_asset_price(_asset(min_sources=3), [_norm(100, "a"), _norm(101, "b")])
    assert ap.status == AssetStatus.FROZEN
    assert ap.rejection_reason == "not_enough_sources"


def test_asset_freeze_after_outlier_filtering():
    # 3 sources, but one is a wild outlier -> drops below min after filtering
    ap = compute_asset_price(
        _asset(min_sources=3, threshold=1.0),
        [_norm(100, "a"), _norm(100.2, "b"), _norm(500, "c")],
    )
    assert ap.status == AssetStatus.FROZEN
    assert ap.rejection_reason == "not_enough_sources_after_filtering"


def _mini_config():
    """Two assets, two currencies, base prices/fx chosen for an easy hand check."""
    assets = {
        "gold": AssetConfig(id="gold", name="Gold", target_unit="USD_PER_TROY_OUNCE",
                            category="precious_metal", min_sources=1),
        "wti": AssetConfig(id="wti", name="WTI", target_unit="USD_PER_BARREL",
                           category="energy", min_sources=1),
    }
    return Config(
        assets=assets,
        currencies=["USD", "EUR"],
        sources={},
        fx_sources=[],
        thresholds=Thresholds(min_valid_pairs_ratio=0.5),
        base_date="2026-01-01",
        base_prices_usd={"gold": 100.0, "wti": 50.0},
        base_fx={"USD": 1.0, "EUR": 2.0},
    )


def test_index_geometric_mean_from_known_sample():
    cfg = _mini_config()
    # gold doubled, wti unchanged (USD). FX unchanged.
    asset_prices = {
        "gold": compute_asset_price(
            AssetConfig(id="gold", name="g", target_unit="USD_PER_TROY_OUNCE",
                        category="precious_metal", min_sources=1),
            [NormalizedPrice("gold", "s", "US", 200.0, "USD_PER_TROY_OUNCE", utcnow())],
        ),
        "wti": compute_asset_price(
            AssetConfig(id="wti", name="w", target_unit="USD_PER_BARREL",
                        category="energy", min_sources=1),
            [NormalizedPrice("wti", "s", "US", 50.0, "USD_PER_BARREL", utcnow())],
        ),
    }
    fx = {
        "USD": FxRate("USD", "USD", 1.0, 1),
        "EUR": FxRate("USD", "EUR", 2.0, 3),
    }
    idx, matrix = compute_index(cfg, asset_prices, fx)
    # ratios: gold/USD=2, gold/EUR=2, wti/USD=1, wti/EUR=1 -> geo mean = sqrt(4*1)...
    # = (2*2*1*1)^(1/4) = 4^(1/4) = sqrt(2)
    assert idx.status == IndexStatus.VALID
    assert idx.valid_pairs == 4
    assert math.isclose(idx.value, math.sqrt(2), rel_tol=1e-9)
    assert len(matrix) == 4


def test_index_freezes_when_too_many_missing():
    cfg = _mini_config()
    asset_prices = {
        "gold": compute_asset_price(
            AssetConfig(id="gold", name="g", target_unit="USD_PER_TROY_OUNCE",
                        category="precious_metal", min_sources=5),
            [NormalizedPrice("gold", "s", "US", 200.0, "USD_PER_TROY_OUNCE", utcnow())],
        ),
        "wti": compute_asset_price(
            AssetConfig(id="wti", name="w", target_unit="USD_PER_BARREL",
                        category="energy", min_sources=5),
            [NormalizedPrice("wti", "s", "US", 50.0, "USD_PER_BARREL", utcnow())],
        ),
    }
    fx = {"USD": FxRate("USD", "USD", 1.0, 1), "EUR": FxRate("USD", "EUR", 2.0, 3)}
    idx, _ = compute_index(cfg, asset_prices, fx)
    assert idx.status == IndexStatus.FROZEN
    assert idx.rejection_reason == "too_many_missing_pairs"
