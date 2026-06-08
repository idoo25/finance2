"""Futures contract rollover.

Most commodities have no clean hourly spot, so we track the nearest liquid
futures contract. The rule: pick the nearest-expiry contract that still has at
least ``min_days_to_expiry`` days left and clears liquidity floors. As a
contract approaches expiry we roll to the next one. This keeps a stable,
configurable rolling series instead of jumping around illiquid months.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class FuturesContract:
    symbol: str
    expiry: date
    volume: float = 0.0
    open_interest: float = 0.0


def select_contract(
    contracts: list[FuturesContract],
    *,
    as_of: date,
    min_days_to_expiry: int = 7,
    min_volume: float = 0.0,
    min_open_interest: float = 0.0,
) -> FuturesContract | None:
    """Return the nearest liquid contract with enough days to expiry.

    Contracts that expire too soon or fail the liquidity floors are skipped. If
    none qualify, returns ``None`` and the caller should fall back to a
    pre-configured benchmark contract.
    """
    eligible = [
        c
        for c in contracts
        if (c.expiry - as_of).days >= min_days_to_expiry
        and c.volume >= min_volume
        and c.open_interest >= min_open_interest
    ]
    if not eligible:
        return None
    return min(eligible, key=lambda c: c.expiry)
