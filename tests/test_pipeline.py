"""End-to-end pipeline + API tests over the mock CSV data."""
import math

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
    assert idx.status == IndexStatus.VALID
    assert idx.valid_pairs == idx.expected_pairs == len(cfg.assets) * len(cfg.currencies)
    assert 0.5 < idx.value < 2.0
    assert 0.0 < idx.quality_score <= 1.0


def test_gold_outlier_filtered_and_cross_currency():
    # gold has 4 sources incl. a +5% outlier and a CNY/gram source; median == base*1.10
    result = run_snapshot(load_config(), persist=False)
    gold = result.asset_prices["gold"]
    assert gold.valid_source_count == 3  # outlier dropped
    assert math.isclose(gold.median_price_usd, 2650 * 1.10, rel_tol=1e-6)


def test_silver_stale_source_rejected():
    result = run_snapshot(load_config(), persist=False)
    silver = result.asset_prices["silver"]
    # one of three silver sources is stale -> degraded with 2 valid
    assert silver.valid_source_count == 2
    assert silver.status == AssetStatus.DEGRADED


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
    assert body["valid_pairs"] == body["expected_pairs"]

    gold = client.get("/api/v1/assets/gold/latest")
    assert gold.status_code == 200
    assert gold.json()["status"] in {"ok", "degraded"}

    assert client.get("/api/v1/assets/unobtainium/latest").status_code == 404

    matrix = client.get("/api/v1/matrix/latest")
    assert matrix.status_code == 200
    assert len(matrix.json()["cells"]) > 0

    health = client.get("/api/v1/health/sources")
    assert health.status_code == 200
    assert health.json()["total"] > 0
