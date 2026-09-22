from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db
from .routers import (
    binning,
    data,
    modeling,
    projects,
    reason_codes,
    reporting,
    sampling,
    scaling,
    selection,
    target,
    validation,
)

app = FastAPI(title="Credit Risk Scorecard Tool API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router)
app.include_router(data.router)
app.include_router(target.router)
app.include_router(sampling.router)
app.include_router(binning.router)
app.include_router(selection.router)
app.include_router(modeling.router)
app.include_router(scaling.router)
app.include_router(validation.router)
app.include_router(reason_codes.router)
app.include_router(reporting.router)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
