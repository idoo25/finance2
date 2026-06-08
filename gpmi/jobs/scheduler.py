"""Simple collection scheduler.

The system *collects* on an interval (hourly by default). The official index is
intended to be published daily/weekly, but each snapshot is stored so a
downstream job can pick the official cadence. This is a dependency-free loop;
swap in Celery/APScheduler for production.

Usage:
    python -m gpmi.jobs.scheduler            # hourly
    GPMI_INTERVAL_SECONDS=300 python -m gpmi.jobs.scheduler
"""
from __future__ import annotations

import os
import time

from ..core.config import load_config
from ..pipeline import run_snapshot
from ..storage import init_db


def main() -> None:
    init_db()
    interval = float(os.environ.get("GPMI_INTERVAL_SECONDS", 3600))
    config = load_config()
    while True:
        try:
            result = run_snapshot(config, persist=True)
            idx = result.index
            print(f"[{idx.timestamp.isoformat()}] FreeGPMI={idx.value:.6f} "
                  f"status={idx.status.value} quality={idx.quality_score:.3f}",
                  flush=True)
        except Exception as exc:  # keep the loop alive on transient errors
            print(f"snapshot failed: {exc}", flush=True)
        time.sleep(interval)


if __name__ == "__main__":
    main()
