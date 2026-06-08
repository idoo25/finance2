"""Keyless free-data adapters: Stooq and Yahoo Finance.

Both are free and require **no API key**, and together they cover all 14 MVP
assets plus FX, giving every asset >= 2 independent providers. Network fetch is
kept separate from parsing so the parsers can be unit-tested with captured
payloads even where outbound network is restricted.

Units: commodity futures quote in native exchange units. Each symbol carries a
``scale`` (e.g. US cents -> dollars = 0.01) and the resulting ``unit``; the
pipeline's unit converter then takes it to the asset target unit. FX symbols
carry an ``invert`` flag because providers quote some pairs as USD-per-CCY.
"""
from __future__ import annotations

from datetime import datetime, timezone

import requests

from ..core.config import AssetConfig, SourceConfig
from ..core.types import RawPrice, utcnow
from .base import FxAdapter, PriceAdapter

_TIMEOUT = 15
_HEADERS = {"User-Agent": "Mozilla/5.0 (FreeGPMI data collector)"}


# --------------------------------------------------------------------------
# Stooq  (https://stooq.com/q/l/?s=SYMBOL&f=sd2t2ohlcv&h&e=csv)
# --------------------------------------------------------------------------
# asset_id -> (stooq symbol, target unit of the quote, price scale)
STOOQ_ASSETS: dict[str, tuple[str, str, float]] = {
    "gold": ("xauusd", "USD_PER_TROY_OUNCE", 1.0),
    "silver": ("xagusd", "USD_PER_TROY_OUNCE", 1.0),
    "platinum": ("xptusd", "USD_PER_TROY_OUNCE", 1.0),
    "palladium": ("xpdusd", "USD_PER_TROY_OUNCE", 1.0),
    "wti": ("cl.f", "USD_PER_BARREL", 1.0),
    "brent": ("cb.f", "USD_PER_BARREL", 1.0),
    "natural_gas": ("ng.f", "USD_PER_MMBTU", 1.0),
    "copper": ("hg.f", "USD_PER_POUND", 0.01),   # cents/lb -> $/lb
    "aluminum": ("ali.f", "USD_PER_METRIC_TON", 1.0),  # best-effort; may be absent
    "wheat": ("zw.f", "USD_PER_BUSHEL", 0.01),   # cents/bushel -> $/bushel
    "corn": ("zc.f", "USD_PER_BUSHEL", 0.01),
    "cotton": ("ct.f", "USD_PER_POUND", 0.01),
    "sugar": ("sb.f", "USD_PER_POUND", 0.01),
    "coffee": ("kc.f", "USD_PER_POUND", 0.01),
}

# currency -> (stooq fx symbol, invert?)  rate wanted = units of CCY per 1 USD
STOOQ_FX: dict[str, tuple[str, bool]] = {
    "EUR": ("eurusd", True),   # eurusd = USD per EUR -> invert
    "GBP": ("gbpusd", True),
    "AUD": ("audusd", True),
    "JPY": ("usdjpy", False),  # usdjpy = JPY per USD -> direct
    "CNY": ("usdcny", False),
    "CHF": ("usdchf", False),
    "CAD": ("usdcad", False),
    "HKD": ("usdhkd", False),
    "SGD": ("usdsgd", False),
}


def parse_stooq_csv(text: str) -> dict[str, tuple[float, datetime | None]]:
    """Parse a Stooq quote CSV into ``{symbol_lower: (close, timestamp)}``.

    Header: Symbol,Date,Time,Open,High,Low,Close,Volume. Rows whose Close is
    missing / ``N/D`` are skipped.
    """
    out: dict[str, tuple[float, datetime | None]] = {}
    lines = [ln for ln in text.strip().splitlines() if ln.strip()]
    if not lines:
        return out
    header = [h.strip().lower() for h in lines[0].split(",")]
    idx = {name: i for i, name in enumerate(header)}
    for line in lines[1:]:
        parts = line.split(",")
        if len(parts) < len(header):
            continue
        try:
            close = parts[idx["close"]].strip()
            if close in ("", "N/D", "n/d"):
                continue
            price = float(close)
        except (KeyError, ValueError):
            continue
        ts = None
        try:
            date = parts[idx["date"]].strip()
            time = parts[idx.get("time", -1)].strip() if "time" in idx else "00:00:00"
            if date and date not in ("N/D",):
                ts = datetime.fromisoformat(f"{date} {time}").replace(tzinfo=timezone.utc)
        except (KeyError, ValueError, IndexError):
            ts = None
        out[parts[idx["symbol"]].strip().lower()] = (price, ts)
    return out


class StooqAdapter(PriceAdapter, FxAdapter):
    name = "stooq"
    URL = "https://stooq.com/q/l/"

    def _fetch_csv(self, symbols: list[str]) -> dict[str, tuple[float, datetime | None]]:
        try:
            resp = requests.get(
                self.URL,
                params={"s": ",".join(symbols), "f": "sd2t2ohlcv", "h": "", "e": "csv"},
                headers=_HEADERS,
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
        except requests.RequestException:
            return {}
        return parse_stooq_csv(resp.text)

    def fetch(self, asset: AssetConfig, source: SourceConfig) -> list[RawPrice]:
        meta = STOOQ_ASSETS.get(asset.id)
        if not meta:
            return []
        symbol, unit, scale = meta
        quotes = self._fetch_csv([symbol])
        if symbol not in quotes:
            return []
        price, ts = quotes[symbol]
        return [RawPrice(asset.id, source.id, price * scale, "USD", unit,
                         ts or utcnow(), source.region, source.type)]

    def fetch_fx(self, currencies: list[str], source: SourceConfig) -> list[RawPrice]:
        wanted = {c.upper(): STOOQ_FX[c.upper()] for c in currencies if c.upper() in STOOQ_FX}
        if not wanted:
            return []
        quotes = self._fetch_csv([sym for sym, _ in wanted.values()])
        out: list[RawPrice] = []
        for ccy, (symbol, invert) in wanted.items():
            if symbol not in quotes:
                continue
            price, ts = quotes[symbol]
            if price <= 0:
                continue
            rate = 1.0 / price if invert else price
            out.append(RawPrice(f"fx_{ccy}", source.id, rate, ccy, "PER_USD",
                                ts or utcnow(), source.region, source.type))
        return out


# --------------------------------------------------------------------------
# Yahoo Finance  (https://query1.finance.yahoo.com/v8/finance/chart/SYMBOL)
# --------------------------------------------------------------------------
YAHOO_ASSETS: dict[str, tuple[str, str, float]] = {
    "gold": ("GC=F", "USD_PER_TROY_OUNCE", 1.0),
    "silver": ("SI=F", "USD_PER_TROY_OUNCE", 1.0),
    "platinum": ("PL=F", "USD_PER_TROY_OUNCE", 1.0),
    "palladium": ("PA=F", "USD_PER_TROY_OUNCE", 1.0),
    "copper": ("HG=F", "USD_PER_POUND", 1.0),       # $/lb
    "aluminum": ("ALI=F", "USD_PER_METRIC_TON", 1.0),  # COMEX aluminium, $/tonne
    "wti": ("CL=F", "USD_PER_BARREL", 1.0),
    "brent": ("BZ=F", "USD_PER_BARREL", 1.0),
    "natural_gas": ("NG=F", "USD_PER_MMBTU", 1.0),
    "wheat": ("ZW=F", "USD_PER_BUSHEL", 0.01),      # cents/bushel
    "corn": ("ZC=F", "USD_PER_BUSHEL", 0.01),
    "cotton": ("CT=F", "USD_PER_POUND", 0.01),
    "sugar": ("SB=F", "USD_PER_POUND", 0.01),
    "coffee": ("KC=F", "USD_PER_POUND", 0.01),
}

YAHOO_FX: dict[str, tuple[str, bool]] = {
    "EUR": ("EURUSD=X", True),
    "GBP": ("GBPUSD=X", True),
    "AUD": ("AUDUSD=X", True),
    "JPY": ("USDJPY=X", False),
    "CNY": ("USDCNY=X", False),
    "CHF": ("USDCHF=X", False),
    "CAD": ("USDCAD=X", False),
    "HKD": ("USDHKD=X", False),
    "SGD": ("USDSGD=X", False),
}


def parse_yahoo_chart(payload: dict) -> tuple[float, datetime | None] | None:
    """Pull (price, timestamp) from a Yahoo v8 chart response."""
    try:
        meta = payload["chart"]["result"][0]["meta"]
    except (KeyError, IndexError, TypeError):
        return None
    price = meta.get("regularMarketPrice")
    if price is None:
        return None
    ts = None
    epoch = meta.get("regularMarketTime")
    if epoch:
        ts = datetime.fromtimestamp(int(epoch), tz=timezone.utc)
    return float(price), ts


class YahooAdapter(PriceAdapter, FxAdapter):
    name = "yahoo"
    URL = "https://query1.finance.yahoo.com/v8/finance/chart/"

    def _fetch_one(self, symbol: str) -> tuple[float, datetime | None] | None:
        try:
            resp = requests.get(
                self.URL + symbol,
                params={"interval": "1d", "range": "5d"},
                headers=_HEADERS,
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
        except requests.RequestException:
            return None
        return parse_yahoo_chart(resp.json())

    def fetch(self, asset: AssetConfig, source: SourceConfig) -> list[RawPrice]:
        meta = YAHOO_ASSETS.get(asset.id)
        if not meta:
            return []
        symbol, unit, scale = meta
        result = self._fetch_one(symbol)
        if not result:
            return []
        price, ts = result
        return [RawPrice(asset.id, source.id, price * scale, "USD", unit,
                         ts or utcnow(), source.region, source.type)]

    def fetch_fx(self, currencies: list[str], source: SourceConfig) -> list[RawPrice]:
        out: list[RawPrice] = []
        for c in currencies:
            ccy = c.upper()
            meta = YAHOO_FX.get(ccy)
            if not meta:
                continue
            symbol, invert = meta
            result = self._fetch_one(symbol)
            if not result:
                continue
            price, ts = result
            if price <= 0:
                continue
            rate = 1.0 / price if invert else price
            out.append(RawPrice(f"fx_{ccy}", source.id, rate, ccy, "PER_USD",
                                ts or utcnow(), source.region, source.type))
        return out
