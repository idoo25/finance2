"""Run one full snapshot (fetch + normalize + aggregate + index) and persist it.

Usage:
    python -m gpmi.jobs.compute_index
"""
from __future__ import annotations

from ..core.config import load_config
from ..pipeline import run_snapshot
from ..storage import init_db


def main() -> None:
    init_db()
    config = load_config()
    result = run_snapshot(config, persist=True)
    idx = result.index
    print(f"FreeGPMI = {idx.value:.6f}  status={idx.status.value} "
          f"pairs={idx.valid_pairs}/{idx.expected_pairs} "
          f"quality={idx.quality_score:.3f}")
    if idx.degraded_assets:
        print(f"  degraded/frozen assets: {', '.join(idx.degraded_assets)}")


if __name__ == "__main__":
    main()
