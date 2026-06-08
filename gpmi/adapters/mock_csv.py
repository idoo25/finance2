"""Mock CSV adapter — the MVP data path.

Reads ``prices.csv`` and ``fx.csv`` from ``GPMI_MOCK_DATA_DIR`` so the whole
pipeline runs with no network or API keys. Timestamps are derived from an
``age_minutes`` column relative to *now*, so sample data never goes stale and
the demo is reproducible.

prices.csv columns: asset_id,source_id,region,price,currency,unit,age_minutes
fx.csv     columns: source_id,currency,region,rate,age_minutes
"""
from __future__ import annotations

import csv
import os
from datetime import timedelta
from pathlib import Path

from ..core.config import AssetConfig, SourceConfig
from ..core.types import RawPrice, utcnow
from .base import FxAdapter, PriceAdapter


def _data_dir() -> Path:
    return Path(os.environ.get("GPMI_MOCK_DATA_DIR", "./data/mock"))


class MockCsvAdapter(PriceAdapter, FxAdapter):
    name = "mock_csv"

    def __init__(self, data_dir: Path | None = None):
        self.data_dir = Path(data_dir) if data_dir else _data_dir()

    def _rows(self, filename: str) -> list[dict]:
        path = self.data_dir / filename
        if not path.exists():
            return []
        with open(path, newline="", encoding="utf-8") as fh:
            return list(csv.DictReader(fh))

    def fetch(self, asset: AssetConfig, source: SourceConfig) -> list[RawPrice]:
        now = utcnow()
        out: list[RawPrice] = []
        for row in self._rows("prices.csv"):
            if row["asset_id"] != asset.id or row["source_id"] != source.id:
                continue
            age = float(row.get("age_minutes", 0) or 0)
            out.append(
                RawPrice(
                    asset_id=asset.id,
                    source_id=source.id,
                    price=float(row["price"]),
                    currency=row["currency"].upper(),
                    unit=row["unit"].upper(),
                    timestamp=now - timedelta(minutes=age),
                    region=row.get("region", source.region),
                    source_type=source.type,
                )
            )
        return out

    def fetch_fx(self, currencies: list[str], source: SourceConfig) -> list[RawPrice]:
        now = utcnow()
        wanted = {c.upper() for c in currencies}
        out: list[RawPrice] = []
        for row in self._rows("fx.csv"):
            if row["source_id"] != source.id:
                continue
            ccy = row["currency"].upper()
            if ccy not in wanted:
                continue
            age = float(row.get("age_minutes", 0) or 0)
            out.append(
                RawPrice(
                    asset_id=f"fx_{ccy}",
                    source_id=source.id,
                    price=float(row["rate"]),
                    currency=ccy,
                    unit="PER_USD",
                    timestamp=now - timedelta(minutes=age),
                    region=row.get("region", source.region),
                    source_type=source.type,
                )
            )
        return out
