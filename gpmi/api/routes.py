"""FastAPI routes for the FreeGPMI index."""
from __future__ import annotations

import json
import math
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from ..core.config import load_config
from ..core.index import price_in_currency
from ..core.types import AssetStatus, FxRate
from ..pipeline import run_snapshot
from ..storage import get_session, init_db, models

router = APIRouter(prefix="/api/v1")


def _num(x: float | None):
    """JSON-safe float: NaN/inf -> None."""
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return None
    return x


def _iso(ts: datetime | None):
    return ts.isoformat() if ts else None


def _latest_index_row(session):
    return session.execute(
        select(models.IndexValueRow).order_by(models.IndexValueRow.id.desc()).limit(1)
    ).scalar_one_or_none()


@router.post("/compute")
def compute_now():
    """Trigger a fresh snapshot (handy for demos and tests)."""
    init_db()
    result = run_snapshot(load_config(), persist=True)
    return _index_payload(result.index)


def _index_payload(idx) -> dict:
    return {
        "index": "FreeGPMI",
        "value": _num(idx.value),
        "base_date": idx.base_date,
        "status": idx.status.value if hasattr(idx.status, "value") else idx.status,
        "valid_pairs": idx.valid_pairs,
        "expected_pairs": idx.expected_pairs,
        "quality_score": _num(idx.quality_score),
        "degraded_assets": idx.degraded_assets
        if isinstance(idx.degraded_assets, list)
        else json.loads(idx.degraded_assets or "[]"),
        "computed_at": _iso(idx.timestamp),
        "oldest_source_ts": _iso(idx.oldest_source_ts),
        "newest_source_ts": _iso(idx.newest_source_ts),
    }


@router.get("/index/latest")
def index_latest():
    with get_session() as session:
        row = _latest_index_row(session)
        if row is None:
            raise HTTPException(404, "no index computed yet; POST /api/v1/compute")
        return _index_payload(row)


@router.get("/index/history")
def index_history(limit: int = Query(50, ge=1, le=1000)):
    with get_session() as session:
        rows = session.execute(
            select(models.IndexValueRow).order_by(models.IndexValueRow.id.desc()).limit(limit)
        ).scalars().all()
        return [_index_payload(r) for r in rows]


@router.get("/assets/{asset_id}/latest")
def asset_latest(asset_id: str):
    config = load_config()
    if asset_id not in config.assets:
        raise HTTPException(404, f"unknown asset {asset_id}")
    with get_session() as session:
        row = session.execute(
            select(models.AssetPriceRow)
            .where(models.AssetPriceRow.asset_id == asset_id)
            .order_by(models.AssetPriceRow.id.desc())
            .limit(1)
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(404, "no price computed yet; POST /api/v1/compute")
        asset = config.assets[asset_id]
        return {
            "asset_id": asset_id,
            "name": asset.name,
            "target_unit": asset.target_unit,
            "median_price_usd": _num(row.median_price_usd),
            "valid_source_count": row.valid_source_count,
            "source_count": row.source_count,
            "status": row.status,
            "computed_at": _iso(row.timestamp),
        }


@router.get("/matrix/latest")
def matrix_latest():
    """Reconstruct the asset x currency ratio matrix from the latest snapshot."""
    config = load_config()
    base = config.base_matrix()
    with get_session() as session:
        idx_row = _latest_index_row(session)
        if idx_row is None:
            raise HTTPException(404, "no index computed yet; POST /api/v1/compute")
        ts = idx_row.timestamp
        asset_rows = session.execute(
            select(models.AssetPriceRow).where(models.AssetPriceRow.timestamp == ts)
        ).scalars().all()
        fx_rows = session.execute(
            select(models.FxRateRow).where(models.FxRateRow.timestamp == ts)
        ).scalars().all()

    fx = {
        r.quote_currency: FxRate(r.base_currency, r.quote_currency, r.rate,
                                 r.source_count, AssetStatus(r.status))
        for r in fx_rows
    }
    cells = []
    for ar in asset_rows:
        if ar.status == AssetStatus.FROZEN.value:
            continue
        base_row = base.get(ar.asset_id, {})
        for ccy in config.currencies:
            f = fx.get(ccy)
            base_price = base_row.get(ccy)
            if not f or f.status == AssetStatus.FROZEN or not base_price:
                continue
            current = price_in_currency(ar.median_price_usd, f)
            cells.append({
                "asset_id": ar.asset_id,
                "currency": ccy,
                "price": _num(current),
                "base_price": _num(base_price),
                "ratio": _num(current / base_price) if base_price else None,
            })
    return {
        "computed_at": _iso(ts),
        "currencies": config.currencies,
        "cells": cells,
    }


@router.get("/health/sources")
def health_sources(limit: int = Query(200, ge=1, le=2000)):
    with get_session() as session:
        idx_row = _latest_index_row(session)
        if idx_row is None:
            return {"computed_at": None, "sources": []}
        rows = session.execute(
            select(models.SourceHealthRow)
            .where(models.SourceHealthRow.timestamp == idx_row.timestamp)
            .limit(limit)
        ).scalars().all()
        valid = sum(1 for r in rows if r.is_valid)
        return {
            "computed_at": _iso(idx_row.timestamp),
            "total": len(rows),
            "valid": valid,
            "rejected": len(rows) - valid,
            "sources": [
                {
                    "asset_id": r.asset_id,
                    "source_id": r.source_id,
                    "is_valid": r.is_valid,
                    "rejection_reason": r.rejection_reason,
                }
                for r in rows
            ],
        }
