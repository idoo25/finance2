"""Generate deterministic mock CSV data for the MVP pipeline.

Writes ``data/mock/prices.csv`` and ``data/mock/fx.csv``. Values are derived
from the base matrix in ``gpmi/config/base.yaml`` with a per-category drift, so
the resulting index is reproducible and clearly != 1.0. The data deliberately
includes:
  * a cross-currency, per-gram gold source (SGE in CNY) to exercise FX + unit
    conversion end to end,
  * an outlier gold source that the validator should filter out,
  * a stale silver source that should be rejected on age.

Run:  python scripts/generate_mock_data.py
"""
from __future__ import annotations

import csv
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gpmi.core.config import load_config  # noqa: E402
from gpmi.core.units import GRAMS_PER_TROY_OUNCE  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "data" / "mock"

# per-category drift applied to base USD prices to get "current" prices
DRIFT = {
    "precious_metal": 1.10,
    "industrial_metal": 1.05,
    "energy": 0.95,
    "agriculture": 1.08,
}

# current FX (units of currency per USD), drifted slightly from base_fx
CURRENT_FX = {
    "EUR": 0.93, "JPY": 155.0, "GBP": 0.79, "CNY": 7.15, "CHF": 0.88,
    "AUD": 1.52, "CAD": 1.38, "HKD": 7.79, "SGD": 1.34,
}
FX_SOURCES = ["ecb", "frankfurter", "stooq_fx"]
FX_OFFSETS = [-0.0005, 0.0, 0.0005]


def main() -> None:
    cfg = load_config()
    OUT.mkdir(parents=True, exist_ok=True)

    # ---- prices.csv ----
    price_rows = []
    for asset_id, asset in cfg.assets.items():
        base_usd = cfg.base_prices_usd[asset_id]
        current = base_usd * DRIFT[asset.category]
        sources = [s.id for s in cfg.sources[asset_id]]
        offsets = [-0.0008, 0.0, 0.0008, 0.0015]

        for i, sid in enumerate(sources):
            # gold: route SGE through CNY per-gram to exercise conversion.
            if asset_id == "gold" and sid == "sge_gold":
                usd_per_gram = current / GRAMS_PER_TROY_OUNCE
                cny_per_gram = usd_per_gram * CURRENT_FX["CNY"]
                price_rows.append([asset_id, sid, "CN", round(cny_per_gram, 4),
                                   "CNY", "USD_PER_GRAM", 30])
                continue
            # gold: av_gold is a deliberate outlier (filtered by validator).
            if asset_id == "gold" and sid == "av_gold":
                price_rows.append([asset_id, sid, "US",
                                   round(current * 1.05, 4), "USD",
                                   asset.target_unit, 20])
                continue
            # silver: stooq source is deliberately stale (rejected on age).
            age = 30
            if asset_id == "silver" and sid == "stooq_silver":
                age = 100000  # ~69 days -> stale
            offset = offsets[i % len(offsets)]
            price = current * (1 + offset)
            region = {0: "UK", 1: "CN", 2: "PL", 3: "US"}.get(i, "US")
            price_rows.append([asset_id, sid, region, round(price, 6),
                               "USD", asset.target_unit, age])

    with open(OUT / "prices.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["asset_id", "source_id", "region", "price", "currency", "unit", "age_minutes"])
        w.writerows(price_rows)

    # ---- fx.csv ----
    fx_rows = []
    for ccy, rate in CURRENT_FX.items():
        for sid, off in zip(FX_SOURCES, FX_OFFSETS):
            region = {"ecb": "EU", "frankfurter": "EU", "stooq_fx": "PL"}[sid]
            fx_rows.append([sid, ccy, region, round(rate * (1 + off), 6), 60])

    with open(OUT / "fx.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["source_id", "currency", "region", "rate", "age_minutes"])
        w.writerows(fx_rows)

    print(f"wrote {len(price_rows)} price rows and {len(fx_rows)} fx rows to {OUT}")


if __name__ == "__main__":
    main()
