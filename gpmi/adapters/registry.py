"""Adapter registry and mock routing.

In MVP mode (``GPMI_USE_MOCK`` truthy, the default) every adapter lookup returns
the single mock CSV adapter, so the pipeline runs offline with no keys. Set
``GPMI_USE_MOCK=0`` to route to the real free-source adapters; any adapter that
needs a missing key returns ``[]`` and is simply skipped.
"""
from __future__ import annotations

import os

from .base import FxAdapter, PriceAdapter
from .mock_csv import MockCsvAdapter


def _truthy(val: str | None) -> bool:
    return (val or "").strip().lower() in {"1", "true", "yes", "on"}


USE_MOCK = _truthy(os.environ.get("GPMI_USE_MOCK", "1"))

_mock = MockCsvAdapter()
_real_cache: dict[str, object] = {}


def _build_real(name: str):
    if name in _real_cache:
        return _real_cache[name]
    # Imported lazily so missing optional deps never break MVP mode.
    from . import realtime

    adapter = realtime.build(name)
    _real_cache[name] = adapter
    return adapter


def get_adapter(name: str) -> PriceAdapter | None:
    if USE_MOCK:
        return _mock
    adapter = _build_real(name)
    return adapter if isinstance(adapter, PriceAdapter) else None


def get_fx_adapter(name: str) -> FxAdapter | None:
    if USE_MOCK:
        return _mock
    adapter = _build_real(name)
    return adapter if isinstance(adapter, FxAdapter) else None
