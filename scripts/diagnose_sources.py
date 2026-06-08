"""Source diagnostics.

Runs every configured source (asset + FX) in REAL mode and reports, per source:
  * implemented? (real adapter vs. documented stub)
  * needs an API key, and whether that key is present
  * is the host reachable from here (network-policy / allowlist probe)
  * what a live fetch returned (sample value, empty, or error)

Run:  python scripts/diagnose_sources.py
Honors GPMI_USE_MOCK=0 automatically (forces real adapters regardless of env).
"""
from __future__ import annotations

import os
import socket
import ssl
import sys
from pathlib import Path
from urllib.parse import urlparse

# Force real adapters before importing the registry (USE_MOCK is read at import).
os.environ["GPMI_USE_MOCK"] = "0"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests  # noqa: E402

from gpmi.adapters import realtime  # noqa: E402
from gpmi.adapters.realtime import NullAdapter  # noqa: E402
from gpmi.core.config import SourceConfig, load_config  # noqa: E402

# A representative URL per adapter, used both for the reachability probe and to
# document where the data would come from.
PROBE_URL = {
    "ecb": "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml",
    "frankfurter": "https://api.frankfurter.dev/v1/latest",
    "alpha_vantage": "https://www.alphavantage.co/query",
    "fred": "https://api.stlouisfed.org/fred/series/observations",
    "stooq": "https://stooq.com/q/l/?s=xauusd&f=sd2t2ohlcv&h&e=csv",
    "yahoo": "https://query1.finance.yahoo.com/v8/finance/chart/GC=F",
    "lbma": "https://www.lbma.org.uk/prices-and-data/precious-metal-prices",
    "sge": "https://en.sge.com.cn/data_BenchmarkPrice",
    "euronext": "https://live.euronext.com/",
}

KEY_ENV = {"alpha_vantage": "ALPHA_VANTAGE_API_KEY", "fred": "FRED_API_KEY"}


def probe(adapter_name: str) -> str:
    url = PROBE_URL.get(adapter_name)
    if not url:
        return "no-url"
    host = urlparse(url).hostname
    # 1) DNS
    try:
        socket.gethostbyname(host)
    except Exception as exc:
        return f"DNS FAIL ({exc.__class__.__name__})"
    # 2) HTTP
    try:
        r = requests.get(url, timeout=12)
        body = (r.text or "")[:60].replace("\n", " ")
        if r.status_code == 200:
            return "REACHABLE (200)"
        return f"BLOCKED ({r.status_code}: {body.strip()})"
    except (requests.RequestException, ssl.SSLError) as exc:
        return f"BLOCKED ({exc.__class__.__name__})"


def classify(adapter, adapter_name: str):
    if isinstance(adapter, NullAdapter):
        return "STUB", "not implemented (needs data license / CSV)"
    key_env = KEY_ENV.get(adapter_name)
    if key_env and not os.environ.get(key_env):
        return "REAL", f"needs {key_env} (NOT SET)"
    return "REAL", "keyless" if not key_env else f"{key_env} set"


def try_fetch_price(adapter, asset, source) -> str:
    if not hasattr(adapter, "fetch"):
        return "n/a (fx-only adapter)"
    try:
        rows = adapter.fetch(asset, source)
    except Exception as exc:
        return f"ERROR {exc.__class__.__name__}"
    if rows:
        r = rows[0]
        return f"OK {len(rows)} row(s), e.g. {r.price} {r.currency}/{r.unit}"
    return "empty []"


def try_fetch_fx(adapter, currencies, source) -> str:
    if not hasattr(adapter, "fetch_fx"):
        return "n/a (price-only adapter)"
    try:
        rows = adapter.fetch_fx(currencies, source)
    except Exception as exc:
        return f"ERROR {exc.__class__.__name__}"
    if rows:
        return f"OK {len(rows)} rate(s), e.g. {rows[0].currency}={round(rows[0].price,4)}"
    return "empty []"


def main() -> None:
    cfg = load_config()
    print("MODE: REAL adapters (GPMI_USE_MOCK=0)\n")

    # cache one probe per adapter name
    probes: dict[str, str] = {}

    def net(name: str) -> str:
        if name not in probes:
            probes[name] = probe(name)
        return probes[name]

    print("== PRICE SOURCES ==")
    header = f"{'asset':<12}{'source':<18}{'adapter':<14}{'kind':<6}{'key/impl':<28}{'network':<28}fetch"
    print(header)
    print("-" * len(header))
    for asset_id, asset in cfg.assets.items():
        for src in cfg.sources.get(asset_id, []):
            adapter = realtime.build(src.adapter)
            kind, impl = classify(adapter, src.adapter)
            fetch = try_fetch_price(adapter, asset, src) if kind == "REAL" else "skipped (stub)"
            print(f"{asset_id:<12}{src.id:<18}{src.adapter:<14}{kind:<6}{impl:<28}{net(src.adapter):<28}{fetch}")

    print("\n== FX SOURCES ==")
    for src in cfg.fx_sources:
        adapter = realtime.build(src.adapter)
        kind, impl = classify(adapter, src.adapter)
        fetch = try_fetch_fx(adapter, cfg.currencies, src) if kind == "REAL" else "skipped (stub)"
        print(f"{'fx':<12}{src.id:<18}{src.adapter:<14}{kind:<6}{impl:<28}{net(src.adapter):<28}{fetch}")

    # summary by adapter
    print("\n== SUMMARY (by adapter) ==")
    seen = set()
    for src in [s for lst in cfg.sources.values() for s in lst] + cfg.fx_sources:
        if src.adapter in seen:
            continue
        seen.add(src.adapter)
        adapter = realtime.build(src.adapter)
        kind, impl = classify(adapter, src.adapter)
        print(f"  {src.adapter:<14} {kind:<6} {impl:<28} {net(src.adapter)}")


if __name__ == "__main__":
    main()
