"""FastAPI application entrypoint.

    uvicorn gpmi.api.main:app --reload
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from ..storage import init_db
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
    return {"index": "FreeGPMI", "docs": "/docs", "api": "/api/v1/index/latest"}


@app.get("/health")
def health():
    return {"status": "ok"}
