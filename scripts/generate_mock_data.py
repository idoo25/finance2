"""Generate deterministic mock CSV data for the MVP pipeline.

Writes ``data/mock/prices.csv`` and ``data/mock/fx.csv``. Values are derived
from the base matrix in ``gpmi/config/base.yaml`` with a per-category drift, so
the resulting index is reproducible and clearly != 1.0. Source ids are read
straight from ``sources.yaml`` (currently Stooq + Yahoo per asset), so this
stays in sync with the keyless config.

The data deliberately includes a stale source on ``coffee`` (one of its two
feeds) to demonstrate the freeze rule: with only the surviving feed left,
coffee drops below ``min_sources`` and is frozen, while the index still
publishes from the remaining assets.

Run:  python scripts/generate_mock_data.py
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gpmi.core.config import load_config  # noqa: E402

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
FX_OFFSETS = [-0.0005, 0.0, 0.0005, 0.0008]


def main() -> None:
    cfg = load_config()
    OUT.mkdir(parents=True, exist_ok=True)

    # ---- prices.csv ----
    price_rows = []
    for asset_id, asset in cfg.assets.items():
        base_usd = cfg.base_prices_usd[asset_id]
        current = base_usd * DRIFT[asset.category]
        srcs = cfg.sources[asset_id]
        offsets = [-0.0008, 0.0008, 0.0003, -0.0003]
        for i, src in enumerate(srcs):
            age = 30
            # coffee: make the 2nd feed stale -> coffee freezes (< min_sources).
            if asset_id == "coffee" and i == 1:
                age = 100000
            price = current * (1 + offsets[i % len(offsets)])
            price_rows.append([asset_id, src.id, src.region, round(price, 6),
                               "USD", asset.target_unit, age])

    with open(OUT / "prices.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["asset_id", "source_id", "region", "price", "currency", "unit", "age_minutes"])
        w.writerows(price_rows)

    # ---- fx.csv ----
    fx_rows = []
    fx_srcs = cfg.fx_sources
    for ccy, rate in CURRENT_FX.items():
        for i, src in enumerate(fx_srcs):
            off = FX_OFFSETS[i % len(FX_OFFSETS)]
            fx_rows.append([src.id, ccy, src.region, round(rate * (1 + off), 6), 60])

    with open(OUT / "fx.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["source_id", "currency", "region", "rate", "age_minutes"])
        w.writerows(fx_rows)

    print(f"wrote {len(price_rows)} price rows and {len(fx_rows)} fx rows to {OUT}")


if __name__ == "__main__":
    main()
