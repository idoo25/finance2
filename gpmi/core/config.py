"""Configuration loader.

Reads the YAML files under ``gpmi/config`` into typed dataclasses: the asset
universe, the currency basket, per-asset source lists, global thresholds, and
the base-date matrix used to form ratios.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

CONFIG_DIR = Path(os.environ.get("GPMI_CONFIG_DIR", Path(__file__).resolve().parent.parent / "config"))


@dataclass
class AssetConfig:
    id: str
    name: str
    target_unit: str
    category: str
    symbol: str | None = None
    commodity: str | None = None  # used for bushel conversions
    min_sources: int = 2
    max_staleness_minutes: float = 60.0
    outlier_threshold_pct: float = 3.0


@dataclass
class SourceConfig:
    id: str
    adapter: str
    region: str = "unknown"
    type: str = "unknown"
    params: dict = field(default_factory=dict)


@dataclass
class Thresholds:
    min_valid_pairs_ratio: float = 0.70
    fx_outlier_threshold_pct: float = 0.5
    fx_max_staleness_minutes: float = 1440.0
    index_jump_confirm_pct: float = 0.05
    # freshness buckets, in days
    fresh_days: float = 1.0
    valid_daily_days: float = 3.0
    valid_weekly_days: float = 7.0
    reject_days: float = 14.0


@dataclass
class Config:
    assets: dict[str, AssetConfig]
    currencies: list[str]
    sources: dict[str, list[SourceConfig]]
    fx_sources: list[SourceConfig]
    thresholds: Thresholds
    base_date: str
    base_prices_usd: dict[str, float]
    base_fx: dict[str, float]  # currency -> units of currency per 1 USD

    def base_matrix(self) -> dict[str, dict[str, float]]:
        """base price of each asset in each currency at the base date."""
        matrix: dict[str, dict[str, float]] = {}
        for asset_id, usd in self.base_prices_usd.items():
            matrix[asset_id] = {c: usd * self.base_fx[c] for c in self.currencies}
        return matrix


def _read(name: str) -> dict:
    path = CONFIG_DIR / name
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


@lru_cache(maxsize=1)
def load_config() -> Config:
    assets_raw = _read("assets.yaml").get("physical_assets", [])
    assets = {a["id"]: AssetConfig(**a) for a in assets_raw}

    currencies = _read("currencies.yaml").get("currencies", [])

    sources_doc = _read("sources.yaml")
    sources_raw = sources_doc.get("sources", {})
    sources = {
        asset_id: [SourceConfig(**s) for s in src_list]
        for asset_id, src_list in sources_raw.items()
    }
    fx_sources = [SourceConfig(**s) for s in sources_doc.get("fx_sources", [])]

    thresholds = Thresholds(**_read("thresholds.yaml").get("thresholds", {}))

    base_raw = _read("base.yaml")
    base = Config(
        assets=assets,
        currencies=currencies,
        sources=sources,
        fx_sources=fx_sources,
        thresholds=thresholds,
        base_date=base_raw.get("base_date", "2026-01-01"),
        base_prices_usd=base_raw.get("base_prices_usd", {}),
        base_fx=base_raw.get("base_fx", {}),
    )
    return base


def reset_config_cache() -> None:
    load_config.cache_clear()
