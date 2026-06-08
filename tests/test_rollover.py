from datetime import date

from gpmi.core.contracts import FuturesContract, select_contract


def _c(month, day, volume=1000, oi=1000):
    return FuturesContract(symbol=f"X{month}", expiry=date(2026, month, day),
                           volume=volume, open_interest=oi)


def test_picks_nearest_liquid_contract():
    as_of = date(2026, 1, 1)
    contracts = [_c(2, 15), _c(3, 15), _c(4, 15)]
    chosen = select_contract(contracts, as_of=as_of, min_days_to_expiry=7)
    assert chosen.symbol == "X2"


def test_rolls_past_near_expiry():
    as_of = date(2026, 2, 12)  # Feb contract has < 7 days left
    contracts = [_c(2, 15), _c(3, 15)]
    chosen = select_contract(contracts, as_of=as_of, min_days_to_expiry=7)
    assert chosen.symbol == "X3"


def test_skips_illiquid():
    as_of = date(2026, 1, 1)
    contracts = [_c(2, 15, volume=0), _c(3, 15, volume=5000)]
    chosen = select_contract(contracts, as_of=as_of, min_volume=100)
    assert chosen.symbol == "X3"


def test_none_when_all_ineligible():
    as_of = date(2026, 1, 1)
    contracts = [_c(1, 3)]  # only 2 days to expiry
    assert select_contract(contracts, as_of=as_of, min_days_to_expiry=7) is None
