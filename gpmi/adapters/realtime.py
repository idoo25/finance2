"""Real free-source adapters (best-effort).

These are used when ``GPMI_USE_MOCK=0``. They favour official / keyless feeds
(ECB, Frankfurter) and degrade gracefully: any network error or missing API key
yields ``[]`` so the snapshot proceeds on whatever sources are available.

The exchange-licensed and scraped sources (LBMA, SGE, Euronext, Stooq) are left
as documented stubs — wire them to your data license / downloaded CSVs. The
mock CSV adapter is the supported offline path for all of them.
"""
from __future__ import annotations

import os
import xml.etree.ElementTree as ET

import requests

from ..core.config import AssetConfig, SourceConfig
from ..core.types import RawPrice, utcnow
from .base import FxAdapter, PriceAdapter

_TIMEOUT = 10


class NullAdapter(PriceAdapter, FxAdapter):
    """Returns nothing. Stand-in for unimplemented / unlicensed sources."""

    def __init__(self, name: str):
        self.name = name

    def fetch(self, asset: AssetConfig, source: SourceConfig) -> list[RawPrice]:
        return []

    def fetch_fx(self, currencies: list[str], source: SourceConfig) -> list[RawPrice]:
        return []


class FrankfurterAdapter(FxAdapter):
    """Free, keyless FX from central-bank reference rates."""

    name = "frankfurter"
    URL = "https://api.frankfurter.dev/v1/latest"

    def fetch_fx(self, currencies: list[str], source: SourceConfig) -> list[RawPrice]:
        symbols = ",".join(c for c in currencies if c != "USD")
        try:
            resp = requests.get(
                self.URL, params={"base": "USD", "symbols": symbols}, timeout=_TIMEOUT
            )
            resp.raise_for_status()
            rates = resp.json().get("rates", {})
        except Exception:
            return []
        now = utcnow()
        return [
            RawPrice(f"fx_{c}", source.id, float(r), c, "PER_USD", now, source.region, source.type)
            for c, r in rates.items()
        ]


class EcbAdapter(FxAdapter):
    """ECB euro reference rates (keyless). Rebased from EUR to USD."""

    name = "ecb"
    URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"

    def fetch_fx(self, currencies: list[str], source: SourceConfig) -> list[RawPrice]:
        try:
            resp = requests.get(self.URL, timeout=_TIMEOUT)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
        except Exception:
            return []
        # eur_rates[ccy] = units of ccy per 1 EUR
        eur_rates = {"EUR": 1.0}
        for cube in root.iter():
            if cube.tag.endswith("Cube") and "currency" in cube.attrib:
                eur_rates[cube.attrib["currency"]] = float(cube.attrib["rate"])
        usd_per_eur = eur_rates.get("USD")
        if not usd_per_eur:
            return []
        now = utcnow()
        out = []
        for c in currencies:
            if c == "USD" or c not in eur_rates:
                continue
            per_usd = eur_rates[c] / usd_per_eur  # (ccy/EUR) / (USD/EUR) = ccy/USD
            out.append(RawPrice(f"fx_{c}", source.id, per_usd, c, "PER_USD", now,
                                source.region, source.type))
        return out


# Alpha Vantage commodity function names by asset id.
_AV_COMMODITY = {
    "wti": ("WTI", "USD_PER_BARREL"),
    "brent": ("BRENT", "USD_PER_BARREL"),
    "natural_gas": ("NATURAL_GAS", "USD_PER_MMBTU"),
    "copper": ("COPPER", "USD_PER_METRIC_TON"),
    "aluminum": ("ALUMINUM", "USD_PER_METRIC_TON"),
    "wheat": ("WHEAT", "USD_PER_METRIC_TON"),
    "corn": ("CORN", "USD_PER_METRIC_TON"),
    "cotton": ("COTTON", "USD_PER_POUND"),
    "sugar": ("SUGAR", "USD_PER_POUND"),
    "coffee": ("COFFEE", "USD_PER_POUND"),
}


class AlphaVantageAdapter(PriceAdapter, FxAdapter):
    name = "alpha_vantage"
    URL = "https://www.alphavantage.co/query"

    def _key(self) -> str | None:
        return os.environ.get("ALPHA_VANTAGE_API_KEY") or None

    def fetch(self, asset: AssetConfig, source: SourceConfig) -> list[RawPrice]:
        key = self._key()
        if not key or asset.id not in _AV_COMMODITY:
            return []
        func, unit = _AV_COMMODITY[asset.id]
        try:
            resp = requests.get(
                self.URL,
                params={"function": func, "interval": "daily", "apikey": key},
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json().get("data", [])
        except Exception:
            return []
        for point in data:
            try:
                price = float(point["value"])
            except (KeyError, ValueError):
                continue
            return [RawPrice(asset.id, source.id, price, "USD", unit, utcnow(),
                             source.region, source.type)]
        return []

    def fetch_fx(self, currencies: list[str], source: SourceConfig) -> list[RawPrice]:
        key = self._key()
        if not key:
            return []
        now = utcnow()
        out = []
        for c in currencies:
            if c == "USD":
                continue
            try:
                resp = requests.get(
                    self.URL,
                    params={
                        "function": "CURRENCY_EXCHANGE_RATE",
                        "from_currency": "USD",
                        "to_currency": c,
                        "apikey": key,
                    },
                    timeout=_TIMEOUT,
                )
                resp.raise_for_status()
                rate = float(
                    resp.json()["Realtime Currency Exchange Rate"]["5. Exchange Rate"]
                )
            except Exception:
                continue
            out.append(RawPrice(f"fx_{c}", source.id, rate, c, "PER_USD", now,
                                source.region, source.type))
        return out


# FRED series ids and their native units.
_FRED_SERIES = {
    "wti": ("DCOILWTICO", "USD_PER_BARREL"),
    "brent": ("DCOILBRENTEU", "USD_PER_BARREL"),
    "natural_gas": ("DHHNGSP", "USD_PER_MMBTU"),
    "copper": ("PCOPPUSDM", "USD_PER_METRIC_TON"),
}


class FredAdapter(PriceAdapter):
    name = "fred"
    URL = "https://api.stlouisfed.org/fred/series/observations"

    def fetch(self, asset: AssetConfig, source: SourceConfig) -> list[RawPrice]:
        key = os.environ.get("FRED_API_KEY")
        if not key or asset.id not in _FRED_SERIES:
            return []
        series, unit = _FRED_SERIES[asset.id]
        try:
            resp = requests.get(
                self.URL,
                params={
                    "series_id": series,
                    "api_key": key,
                    "file_type": "json",
                    "sort_order": "desc",
                    "limit": 5,
                },
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            obs = resp.json().get("observations", [])
        except Exception:
            return []
        for o in obs:
            if o.get("value") in (None, "", "."):
                continue
            return [RawPrice(asset.id, source.id, float(o["value"]), "USD", unit,
                             utcnow(), source.region, source.type)]
        return []


_BUILDERS = {
    "frankfurter": FrankfurterAdapter,
    "ecb": EcbAdapter,
    "alpha_vantage": AlphaVantageAdapter,
    "fred": FredAdapter,
}


def build(name: str):
    builder = _BUILDERS.get(name)
    if builder:
        return builder()
    # stooq, lbma, sge, euronext: wire to your data license / CSVs.
    return NullAdapter(name)
