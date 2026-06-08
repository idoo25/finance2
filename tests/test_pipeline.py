"""End-to-end pipeline + API tests over the mock CSV data (keyless config)."""
from fastapi.testclient import TestClient

from gpmi.api.main import app
from gpmi.core.config import load_config
from gpmi.core.types import AssetStatus, IndexStatus
from gpmi.pipeline import run_snapshot
from gpmi.storage import init_db


def test_snapshot_runs_and_is_valid():
    cfg = load_config()
    result = run_snapshot(cfg, persist=False)
    idx = result.index
    expected = len(cfg.assets) * len(cfg.currencies)
    assert idx.status == IndexStatus.VALID
    assert idx.expected_pairs == expected
    # coffee is frozen by a stale source -> its 10 pairs drop out
    assert idx.valid_pairs == expected - len(cfg.currencies)
    assert 0.5 < idx.value < 2.0
    assert 0.0 < idx.quality_score <= 1.0


def test_two_keyless_sources_per_asset_is_ok():
    result = run_snapshot(load_config(), persist=False)
    gold = result.asset_prices["gold"]
    assert gold.valid_source_count == 2
    assert gold.status == AssetStatus.OK
    # 2 regions (Stooq PL + Yahoo US) -> good geographic diversity
    assert len(set(gold.regions)) == 2


def test_coffee_frozen_by_stale_source():
    result = run_snapshot(load_config(), persist=False)
    coffee = result.asset_prices["coffee"]
    assert coffee.status == AssetStatus.FROZEN
    assert coffee.valid_source_count < 2
    assert "coffee" in result.index.degraded_assets


def test_api_endpoints():
    init_db()
    client = TestClient(app)

    posted = client.post("/api/v1/compute")
    assert posted.status_code == 200
    assert posted.json()["status"] == "valid"

    latest = client.get("/api/v1/index/latest")
    assert latest.status_code == 200
    body = latest.json()
    assert body["index"] == "FreeGPMI"
    assert "coffee" in body["degraded_assets"]

    gold = client.get("/api/v1/assets/gold/latest")
    assert gold.status_code == 200
    assert gold.json()["status"] == "ok"

    assert client.get("/api/v1/assets/unobtainium/latest").status_code == 404

    matrix = client.get("/api/v1/matrix/latest")
    assert matrix.status_code == 200
    cfg = load_config()
    assert len(matrix.json()["cells"]) == (len(cfg.assets) - 1) * len(cfg.currencies)

    health = client.get("/api/v1/health/sources")
    assert health.status_code == 200
    hb = health.json()
    assert hb["total"] > 0
    assert hb["rejected"] == 1  # the stale coffee feed
