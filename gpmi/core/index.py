"""Index computation: asset price aggregation and the GPMI geometric mean.

Pipeline per snapshot:
  1. normalized USD prices  -> median asset price (per asset), with freeze rules
  2. asset price + FX        -> price of each asset in each currency
  3. ratio vs base matrix    -> geometric mean over all valid pairs = GPMI
"""
from __future__ import annotations

from datetime import datetime

from .aggregation import geometric_mean, median
from .config import AssetConfig, Config
from .types import (
    AssetPrice,
    AssetStatus,
    FxRate,
    IndexStatus,
    IndexValue,
    NormalizedPrice,
    utcnow,
)
from .validation import filter_outliers


def compute_asset_price(
    asset: AssetConfig,
    normalized: list[NormalizedPrice],
) -> AssetPrice:
    """Median USD price for one asset, applying min-source and outlier rules.

    ``normalized`` should already have stale / non-positive sources removed.
    """
    source_count = len(normalized)
    if source_count < asset.min_sources:
        return AssetPrice(
            asset_id=asset.id,
            median_price_usd=float("nan"),
            valid_source_count=source_count,
            source_count=source_count,
            status=AssetStatus.FROZEN,
            rejection_reason="not_enough_sources",
        )

    filtered = filter_outliers(normalized, asset.outlier_threshold_pct)
    if len(filtered) < asset.min_sources:
        return AssetPrice(
            asset_id=asset.id,
            median_price_usd=float("nan"),
            valid_source_count=len(filtered),
            source_count=source_count,
            status=AssetStatus.FROZEN,
            rejection_reason="not_enough_sources_after_filtering",
        )

    price = median([p.price_usd for p in filtered])
    regions = [p.region for p in filtered]
    timestamps = [p.timestamp for p in filtered]
    healthy = asset.healthy_sources or asset.min_sources
    status = AssetStatus.OK if len(filtered) >= healthy else AssetStatus.DEGRADED
    return AssetPrice(
        asset_id=asset.id,
        median_price_usd=price,
        valid_source_count=len(filtered),
        source_count=source_count,
        status=status,
        regions=regions,
        oldest_timestamp=min(timestamps),
        newest_timestamp=max(timestamps),
    )


def price_in_currency(asset_usd: float, fx: FxRate) -> float:
    """asset price in a currency = USD price * (currency units per USD)."""
    return asset_usd * fx.rate


def compute_index(
    config: Config,
    asset_prices: dict[str, AssetPrice],
    fx_rates: dict[str, FxRate],
    *,
    timestamp: datetime | None = None,
) -> tuple[IndexValue, list[tuple[str, str, float]]]:
    """Compute GPMI and return ``(IndexValue, [(asset, currency, ratio), ...])``.

    The ratio list is the asset-currency matrix, handy for the /matrix endpoint.
    """
    timestamp = timestamp or utcnow()
    base = config.base_matrix()
    currencies = config.currencies
    expected_pairs = len(config.assets) * len(currencies)

    ratios: list[float] = []
    matrix: list[tuple[str, str, float]] = []
    degraded: list[str] = []

    for asset_id, asset in config.assets.items():
        ap = asset_prices.get(asset_id)
        if ap is None or ap.status == AssetStatus.FROZEN:
            degraded.append(asset_id)
            continue
        if ap.status == AssetStatus.DEGRADED:
            degraded.append(asset_id)
        base_row = base.get(asset_id, {})
        for ccy in currencies:
            fx = fx_rates.get(ccy)
            if fx is None or fx.status == AssetStatus.FROZEN:
                continue
            base_price = base_row.get(ccy)
            if not base_price or base_price <= 0:
                continue
            current = price_in_currency(ap.median_price_usd, fx)
            if current <= 0:
                continue
            ratio = current / base_price
            ratios.append(ratio)
            matrix.append((asset_id, ccy, ratio))

    valid_pairs = len(ratios)
    min_pairs = int(expected_pairs * config.thresholds.min_valid_pairs_ratio)

    if valid_pairs == 0 or valid_pairs < min_pairs:
        return (
            IndexValue(
                value=float("nan"),
                base_date=config.base_date,
                status=IndexStatus.FROZEN,
                valid_pairs=valid_pairs,
                expected_pairs=expected_pairs,
                quality_score=0.0,
                degraded_assets=degraded,
                timestamp=timestamp,
                rejection_reason="too_many_missing_pairs",
            ),
            matrix,
        )

    value = geometric_mean(ratios)
    return (
        IndexValue(
            value=value,
            base_date=config.base_date,
            status=IndexStatus.VALID,
            valid_pairs=valid_pairs,
            expected_pairs=expected_pairs,
            quality_score=0.0,  # filled in by the pipeline with freshness context
            degraded_assets=degraded,
            timestamp=timestamp,
        ),
        matrix,
    )
