# FreeGPMI — Free-source Global Pure Market Index

A **global, market-based, decentralized-by-sources** index that measures how
much physical assets (metals, energy, agriculture) cost against a basket of the
10 most-traded currencies. It is **not** a CPI, not a single government report,
and **never relies on a single data source** — every asset price and FX rate is
the *median* of multiple independent feeds, and the index itself is the
*geometric mean* of all asset-currency ratios.

```
                ⎛  N    M   Price[p,c,t] ⎞ ^ (1 / (N·M))
   FreeGPMI_t = ⎜  ∏    ∏   ───────────  ⎟
                ⎝ p=1  c=1  Price[p,c,0] ⎠
```

This is the **FreeGPMI** variant: it runs on free / publicly-accessible data,
tolerates delayed (daily/weekly) data, and ships with **mock CSV adapters** so
the whole system runs end-to-end offline with no API keys.

## What's in the box

| Concern        | Where |
| -------------- | ----- |
| Index math (median, geometric mean, log-space) | `gpmi/core/aggregation.py`, `gpmi/core/index.py` |
| Validation (stale / non-positive / outlier / freeze) | `gpmi/core/validation.py` |
| Unit conversion (oz, gram, ton, bushel, barrel, MMBtu/MWh) | `gpmi/core/units.py` |
| FX aggregation (median per pair) | `gpmi/core/fx.py` |
| Futures rollover | `gpmi/core/contracts.py` |
| Quality score & freshness | `gpmi/core/quality.py` |
| Source adapters (mock + real free sources) | `gpmi/adapters/` |
| Storage (SQLite dev / Postgres prod) | `gpmi/storage/` |
| Pipeline orchestration | `gpmi/pipeline.py` |
| HTTP API | `gpmi/api/` |
| Config (assets, currencies, sources, thresholds, base) | `gpmi/config/*.yaml` |

## The universe

**14 MVP assets** (each with ≥2 free sources, ideally ≥2 regions): gold, silver,
platinum, palladium, copper, aluminum, WTI, Brent, natural gas, wheat, corn,
cotton, sugar, coffee. Assets without enough independent free feeds (lithium,
uranium, soybeans, rice, nickel, …) are intentionally excluded until they meet
the diversity rule.

**10 currencies** (the denominator): USD, EUR, JPY, GBP, CNY, CHF, AUD, CAD,
HKD, SGD.

## Quick start (offline, no keys)

```bash
pip install -r requirements.txt

# 1. (re)generate the deterministic mock data
python scripts/generate_mock_data.py

# 2. compute one index snapshot (creates ./gpmi.db)
python -m gpmi.jobs.compute_index
#   -> FreeGPMI = 1.044096  status=valid pairs=140/140 quality=0.921

# 3. serve the API
uvicorn gpmi.api.main:app --reload
#   POST http://localhost:8000/api/v1/compute   then browse /docs
```

## API

| Endpoint | Description |
| -------- | ----------- |
| `POST /api/v1/compute` | run a fresh snapshot and persist it |
| `GET  /api/v1/index/latest` | latest published index value + metadata |
| `GET  /api/v1/index/history?limit=N` | recent index values |
| `GET  /api/v1/assets/{asset_id}/latest` | latest median price for an asset |
| `GET  /api/v1/matrix/latest` | the asset × currency ratio matrix |
| `GET  /api/v1/health/sources` | per-source accept/reject status |

Every index payload carries `status`, `valid_pairs`/`expected_pairs`,
`quality_score`, `degraded_assets`, and the oldest/newest contributing source
timestamps — the index never pretends data is fresher than it is.

## How a price is formed

1. Each source is fetched in its **native unit & currency** (adapters stay thin).
2. Stale and non-positive observations are rejected.
3. Survivors are **normalized**: currency → USD (via the median FX rate), then
   native unit → the asset's target unit.
4. Outliers vs. the peer median are dropped (only when ≥3 sources exist).
5. The asset price is the **median** of the survivors. Fewer than `min_sources`
   ⇒ the asset is **frozen**.
6. Each asset×currency ratio vs. the base matrix feeds the **geometric mean**.
   If fewer than 70% of pairs are valid ⇒ the whole index is **frozen**.

## Configuration

Edit the YAML under `gpmi/config/`:
`assets.yaml`, `currencies.yaml`, `sources.yaml`, `thresholds.yaml`, `base.yaml`.

## MVP vs. production

- **MVP** (`GPMI_USE_MOCK=1`, the default): mock CSV adapters, no keys, SQLite.
- **Production** (`GPMI_USE_MOCK=0`): routes to real free adapters. ECB and
  Frankfurter FX work keyless; Alpha Vantage and FRED activate when their env
  keys are set; exchange-licensed sources (LBMA, SGE, Euronext, Stooq) are left
  as documented stubs in `gpmi/adapters/realtime.py` — wire them to your data
  license or downloaded CSVs. Use Postgres via `DATABASE_URL` and add real
  migrations. Do not market delayed/free data as a live commercial index.

## Docker

```bash
docker compose up --build      # api :8000, postgres, redis, hourly scheduler
```

## Tests

```bash
pytest        # 33 tests: units, aggregation, validation, fx, index, rollover, e2e
```
