"""SQLAlchemy persistence models.

Mirrors the index pipeline stages: raw observations, normalized USD prices,
aggregated asset prices, FX rates, published index values, and a source-health
log of why feeds were rejected.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class RawPriceRow(Base):
    __tablename__ = "raw_prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_id: Mapped[str] = mapped_column(String(64), index=True)
    source_id: Mapped[str] = mapped_column(String(64), index=True)
    source_region: Mapped[str | None] = mapped_column(String(32), nullable=True)
    price: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8))
    unit: Mapped[str] = mapped_column(String(32))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)


class NormalizedPriceRow(Base):
    __tablename__ = "normalized_prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_id: Mapped[str] = mapped_column(String(64), index=True)
    source_id: Mapped[str] = mapped_column(String(64))
    price_usd: Mapped[float] = mapped_column(Float)
    target_unit: Mapped[str] = mapped_column(String(32))
    region: Mapped[str | None] = mapped_column(String(32), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class AssetPriceRow(Base):
    __tablename__ = "asset_prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_id: Mapped[str] = mapped_column(String(64), index=True)
    median_price_usd: Mapped[float] = mapped_column(Float)
    valid_source_count: Mapped[int] = mapped_column(Integer)
    source_count: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class FxRateRow(Base):
    __tablename__ = "fx_rates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    base_currency: Mapped[str] = mapped_column(String(8))
    quote_currency: Mapped[str] = mapped_column(String(8), index=True)
    rate: Mapped[float] = mapped_column(Float)
    source_count: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class IndexValueRow(Base):
    __tablename__ = "index_values"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    index_name: Mapped[str] = mapped_column(String(32), index=True, default="FreeGPMI")
    value: Mapped[float] = mapped_column(Float)
    base_date: Mapped[str] = mapped_column(String(16))
    valid_pairs: Mapped[int] = mapped_column(Integer)
    expected_pairs: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16))
    quality_score: Mapped[float] = mapped_column(Float)
    degraded_assets: Mapped[str | None] = mapped_column(Text, nullable=True)
    oldest_source_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    newest_source_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class SourceHealthRow(Base):
    __tablename__ = "source_health"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_id: Mapped[str] = mapped_column(String(64), index=True)
    source_id: Mapped[str] = mapped_column(String(64), index=True)
    is_valid: Mapped[bool] = mapped_column(Boolean)
    rejection_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
