"""Test configuration.

Forces MVP mock mode and an isolated temp SQLite DB before any gpmi module
(whose engine is created at import time) is imported.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

os.environ.setdefault("GPMI_USE_MOCK", "1")
os.environ.setdefault("GPMI_MOCK_DATA_DIR", str(ROOT / "data" / "mock"))
os.environ["DATABASE_URL"] = f"sqlite:///{ROOT / 'test_gpmi.db'}"
