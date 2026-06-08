"""Parser + symbol/unit tests for the keyless Stooq and Yahoo adapters.

These verify the pure parsing and scale/inversion logic with representative
payloads, so unit correctness is covered even though live network fetch can't
be exercised in every environment.
"""
import math

from gpmi.adapters.keyless import (
    STOOQ_ASSETS,
    STOOQ_FX,
    YAHOO_ASSETS,
    YAHOO_FX,
    parse_stooq_csv,
    parse_yahoo_chart,
)
from gpmi.core.units import convert


def test_parse_stooq_csv_basic():
    csv = (
        "Symbol,Date,Time,Open,High,Low,Close,Volume\n"
        "XAUUSD,2026-06-08,21:00:00,2900,2920,2890,2915.5,0\n"
        "CL.F,2026-06-08,21:00:00,68,69,67,68.4,12345\n"
    )
    out = parse_stooq_csv(csv)
    assert math.isclose(out["xauusd"][0], 2915.5)
    assert out["xauusd"][1].year == 2026
    assert math.isclose(out["cl.f"][0], 68.4)


def test_parse_stooq_skips_no_data():
    csv = (
        "Symbol,Date,Time,Open,High,Low,Close,Volume\n"
        "BAD,N/D,N/D,N/D,N/D,N/D,N/D,N/D\n"
    )
    assert parse_stooq_csv(csv) == {}


def test_parse_yahoo_chart():
    payload = {
        "chart": {
            "result": [
                {"meta": {"regularMarketPrice": 4.25, "regularMarketTime": 1780000000,
                          "currency": "USD"}}
            ]
        }
    }
    price, ts = parse_yahoo_chart(payload)
    assert price == 4.25
    assert ts is not None


def test_parse_yahoo_chart_missing():
    assert parse_yahoo_chart({"chart": {"result": []}}) is None
    assert parse_yahoo_chart({"chart": {"error": "x"}}) is None


def test_stooq_cents_scale_produces_sane_dollars():
    # wheat ~600 cents/bushel -> $6/bushel -> ~$220/ton (matches base config)
    _, unit, scale = STOOQ_ASSETS["wheat"]
    usd_per_bushel = 600 * scale
    assert math.isclose(usd_per_bushel, 6.0)
    per_ton = convert(usd_per_bushel, unit, "USD_PER_METRIC_TON", commodity="wheat")
    assert 200 < per_ton < 240


def test_yahoo_copper_dollars_per_pound_to_ton():
    _, unit, scale = YAHOO_ASSETS["copper"]
    # Yahoo HG=F quotes ~$4.1/lb already in dollars (scale 1)
    per_ton = convert(4.1 * scale, unit, "USD_PER_METRIC_TON")
    assert 8000 < per_ton < 9500


def test_fx_inversion_convention():
    # EUR is quoted EURUSD (USD per EUR) -> must invert to get EUR-per-USD.
    assert STOOQ_FX["EUR"][1] is True
    assert YAHOO_FX["EUR"][1] is True
    # JPY is quoted USDJPY (JPY per USD) -> used directly.
    assert STOOQ_FX["JPY"][1] is False
    assert YAHOO_FX["JPY"][1] is False
