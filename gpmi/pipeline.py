"""End-to-end snapshot pipeline.

Orchestrates one index computation:

    FX sources  -> validate -> median FX rates
    asset sources -> validate (stale/positive) -> normalize to USD/target unit
                  -> outlier filter + median -> asset price (with freeze rules)
    asset prices + FX + base matrix -> GPMI geometric mean
    + freshness/quality scoring, then persist every stage.

Runs entirely on the mock CSV adapter in MVP mode, so it works offline.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone

from .adapters import get_adapter, get_fx_adapter
from .core.config import Config, load_config
from .core.fx import compute_fx_rates
from .core.index import compute_asset_price, compute_index
from .core.normalize import NormalizationError, normalize
from .core.quality import classify_freshness, quality_score
from .core.types import (
    AssetPrice,
    AssetStatus,
    Freshness,
    FxRate,
    IndexValue,
    NormalizedPrice,
    RawPrice,
    utcnow,
)
from .core.validation import reject_invalid_prices
from .storage import get_session, models


@dataclass
class SnapshotResult:
    index: IndexValue
    asset_prices: dict[str, AssetPrice]
    fx_rates: dict[str, FxRate]
    matrix: list[tuple[str, str, float]]
    raws: list[RawPrice]
    normalized: list[NormalizedPrice]


def _age_days(ts: datetime, now: datetime) -> float:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return (now - ts).total_seconds() / 86400.0


def run_snapshot(config: Config | None = None, *, persist: bool = True,
                 now: datetime | None = None) -> SnapshotResult:
    config = config or load_config()
    now = now or utcnow()
    t = config.thresholds

    # 1. FX --------------------------------------------------------------
    fx_raws: list[RawPrice] = []
    for src in config.fx_sources:
        adapter = get_fx_adapter(src.adapter)
        if adapter is None:
            continue
        fx_raws.extend(adapter.fetch_fx(config.currencies, src))
    fx_rates = compute_fx_rates(
        fx_raws,
        config.currencies,
        max_staleness_minutes=t.fx_max_staleness_minutes,
        outlier_threshold_pct=t.fx_outlier_threshold_pct,
        now=now,
    )

    # 2. Asset prices ----------------------------------------------------
    all_raws: list[RawPrice] = list(fx_raws)
    all_normalized: list[NormalizedPrice] = []
    asset_prices: dict[str, AssetPrice] = {}

    for asset_id, asset in config.assets.items():
        raws: list[RawPrice] = []
        for src in config.sources.get(asset_id, []):
            adapter = get_adapter(src.adapter)
            if adapter is None:
                continue
            raws.extend(adapter.fetch(asset, src))
        all_raws.extend(raws)

        survivors = reject_invalid_prices(
            raws, now=now, max_staleness_minutes=asset.max_staleness_minutes
        )
        normalized: list[NormalizedPrice] = []
        for r in survivors:
            try:
                normalized.append(normalize(r, asset, fx_rates))
            except NormalizationError:
                r.is_valid = False
                r.rejection_reason = "no_fx"
        all_normalized.extend(normalized)
        asset_prices[asset_id] = compute_asset_price(asset, normalized)

    # 3. Index -----------------------------------------------------------
    index, matrix = compute_index(config, asset_prices, fx_rates, timestamp=now)

    # 4. Freshness + quality --------------------------------------------
    contributing_ts = [
        ap.oldest_timestamp
        for ap in asset_prices.values()
        if ap.status != AssetStatus.FROZEN and ap.oldest_timestamp
    ]
    newest_ts = [
        ap.newest_timestamp
        for ap in asset_prices.values()
        if ap.status != AssetStatus.FROZEN and ap.newest_timestamp
    ]
    if contributing_ts:
        oldest = min(contributing_ts)
        newest = max(newest_ts)
        freshness = classify_freshness(_age_days(oldest, now), t)
    else:
        oldest = newest = None
        freshness = Freshness.REJECT

    expected_sources = 3
    contributing_assets = [
        ap for ap in asset_prices.values() if ap.status != AssetStatus.FROZEN
    ]
    outlier_consistency = (
        sum(ap.valid_source_count / max(1, ap.source_count) for ap in contributing_assets)
        / len(contributing_assets)
        if contributing_assets
        else 0.0
    )
    index.quality_score = quality_score(
        list(asset_prices.values()),
        expected_sources_per_asset=expected_sources,
        freshness=freshness,
        outlier_consistency=outlier_consistency,
    )
    index.oldest_source_ts = oldest
    index.newest_source_ts = newest

    result = SnapshotResult(
        index=index,
        asset_prices=asset_prices,
        fx_rates=fx_rates,
        matrix=matrix,
        raws=all_raws,
        normalized=all_normalized,
    )
    if persist:
        _persist(result, now)
    return result


def _persist(result: SnapshotResult, now: datetime) -> None:
    with get_session() as session:
        for r in result.raws:
            session.add(models.RawPriceRow(
                asset_id=r.asset_id, source_id=r.source_id, source_region=r.region,
                price=r.price, currency=r.currency, unit=r.unit, timestamp=r.timestamp,
                received_at=r.received_at, is_valid=r.is_valid,
                rejection_reason=r.rejection_reason,
            ))
            session.add(models.SourceHealthRow(
                asset_id=r.asset_id, source_id=r.source_id, is_valid=r.is_valid,
                rejection_reason=r.rejection_reason, timestamp=now,
            ))
        for n in result.normalized:
            session.add(models.NormalizedPriceRow(
                asset_id=n.asset_id, source_id=n.source_id, price_usd=n.price_usd,
                target_unit=n.target_unit, region=n.region, timestamp=n.timestamp,
            ))
        for ap in result.asset_prices.values():
            session.add(models.AssetPriceRow(
                asset_id=ap.asset_id, median_price_usd=ap.median_price_usd,
                valid_source_count=ap.valid_source_count, source_count=ap.source_count,
                status=ap.status.value, timestamp=now,
            ))
        for fx in result.fx_rates.values():
            session.add(models.FxRateRow(
                base_currency=fx.base, quote_currency=fx.quote, rate=fx.rate,
                source_count=fx.source_count, status=fx.status.value, timestamp=now,
            ))
        idx = result.index
        session.add(models.IndexValueRow(
            index_name="FreeGPMI", value=idx.value, base_date=idx.base_date,
            valid_pairs=idx.valid_pairs, expected_pairs=idx.expected_pairs,
            status=idx.status.value, quality_score=idx.quality_score,
            degraded_assets=json.dumps(idx.degraded_assets),
            oldest_source_ts=idx.oldest_source_ts, newest_source_ts=idx.newest_source_ts,
            timestamp=now,
        ))
