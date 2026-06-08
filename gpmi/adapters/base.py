"""Adapter interface.

Every source adapter turns an external feed into ``RawPrice`` objects in the
source's native unit and currency. Normalization to the asset target unit and
USD happens later in the pipeline, so adapters stay thin and testable.

A price adapter implements ``fetch(asset, source)`` and an FX adapter
implements ``fetch_fx(currencies, source)``. Either should return ``[]`` (not
raise) when a feed is unavailable or a key is missing, so one dead source never
takes down a snapshot.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..core.config import AssetConfig, SourceConfig
from ..core.types import RawPrice


class PriceAdapter(ABC):
    name: str = "base"

    @abstractmethod
    def fetch(self, asset: AssetConfig, source: SourceConfig) -> list[RawPrice]:
        ...


class FxAdapter(ABC):
    name: str = "base"

    @abstractmethod
    def fetch_fx(self, currencies: list[str], source: SourceConfig) -> list[RawPrice]:
        ...
