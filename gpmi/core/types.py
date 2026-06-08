"""Runtime dataclasses passed between adapters, validation and aggregation.

These are plain in-memory value objects, distinct from the SQLAlchemy
persistence models in ``gpmi.storage``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AssetStatus(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"
    FROZEN = "frozen"


class IndexStatus(str, Enum):
    VALID = "valid"
    FROZEN = "frozen"


class Freshness(str, Enum):
    FRESH = "fresh"
    VALID_DAILY = "valid_daily"
    VALID_WEEKLY = "valid_weekly"
    STALE = "stale"
    REJECT = "reject"


@dataclass
class RawPrice:
    """One observation from one source, in that source's native unit/currency."""

    asset_id: str
    source_id: str
    price: float
    currency: str
    unit: str
    timestamp: datetime
    region: str = "unknown"
    source_type: str = "unknown"
    received_at: datetime = field(default_factory=utcnow)
    is_valid: bool = True
    rejection_reason: str | None = None


@dataclass
class NormalizedPrice:
    """A raw price converted to the asset's target unit and to USD."""

    asset_id: str
    source_id: str
    region: str
    price_usd: float
    target_unit: str
    timestamp: datetime


@dataclass
class AssetPrice:
    """The aggregated, median USD price for one asset at one point in time."""

    asset_id: str
    median_price_usd: float
    valid_source_count: int
    source_count: int
    status: AssetStatus
    regions: list[str] = field(default_factory=list)
    oldest_timestamp: datetime | None = None
    newest_timestamp: datetime | None = None
    rejection_reason: str | None = None


@dataclass
class FxRate:
    """Median FX rate. ``rate`` is units of ``quote`` per 1 unit of ``base``."""

    base: str
    quote: str
    rate: float
    source_count: int
    status: AssetStatus = AssetStatus.OK


@dataclass
class IndexValue:
    value: float
    base_date: str
    status: IndexStatus
    valid_pairs: int
    expected_pairs: int
    quality_score: float
    degraded_assets: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=utcnow)
    oldest_source_ts: datetime | None = None
    newest_source_ts: datetime | None = None
    rejection_reason: str | None = None
