"""FastAPI application entrypoint.

    uvicorn gpmi.api.main:app --reload
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from ..core.config import load_config
from ..pipeline import run_snapshot
from ..storage import init_db
from .dashboard import render_dashboard
from .routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="FreeGPMI",
    version="0.1.0",
    description="Free-source, decentralized global market index "
                "(physical assets vs. a basket of major currencies).",
    lifespan=lifespan,
)
app.include_router(router)


@app.get("/")
def root():
    return {"index": "FreeGPMI", "dashboard": "/dashboard", "docs": "/docs",
            "api": "/api/v1/index/latest"}


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    """Live HTML view of every source, the medians, FX and the index."""
    result = run_snapshot(load_config(), persist=True)
    return render_dashboard(result)


@app.get("/health")
def health():
    return {"status": "ok"}
