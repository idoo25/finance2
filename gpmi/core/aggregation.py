"""Aggregation primitives.

Asset prices and FX rates use the *median* of valid sources so a single broken
or outlier feed cannot drag the result. The final index uses the *geometric
mean* of all asset-currency ratios so one asset that jumps 5x cannot dominate
the whole index, and so the index is symmetric to inversion.
"""
from __future__ import annotations

import math
from typing import Iterable


def median(values: Iterable[float]) -> float:
    data = sorted(values)
    if not data:
        raise ValueError("median of empty sequence")
    n = len(data)
    mid = n // 2
    if n % 2 == 1:
        return data[mid]
    return (data[mid - 1] + data[mid]) / 2.0


def geometric_mean(values: Iterable[float]) -> float:
    """Geometric mean computed in log space for numerical stability.

    ``exp(mean(log(x)))`` avoids the overflow/underflow of multiplying many
    factors together. All values must be strictly positive.
    """
    logs = []
    for v in values:
        if v <= 0:
            raise ValueError(f"geometric mean requires positive values, got {v}")
        logs.append(math.log(v))
    if not logs:
        raise ValueError("geometric mean of empty sequence")
    return math.exp(sum(logs) / len(logs))
