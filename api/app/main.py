from __future__ import annotations

import os

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import saml_config
from .auth import get_current_user
from .db import init_db
from .routers import (
    audit,
    auth,
    batch_scoring,
    binning,
    data,
    decision_tree,
    final_model,
    ml_benchmark,
    modeling,
    projects,
    reason_codes,
    reporting,
    sampling,
    scaling,
    selection,
    target,
    tuning,
    validation,
    versions,
)

app = FastAPI(title="CSW (Credit Scorecards Workbench) API", version="0.1.0")

# Behind a reverse proxy that serves the frontend and API from the same
# origin (the Docker/on-prem setup — see DEPLOY.md), CORS never applies.
# This only matters for local dev, where the Vite dev server runs on a
# different port than uvicorn.
cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Every route requires a logged-in user except the auth endpoints
# themselves (can't require login to log in) and the health check.
protected = [Depends(get_current_user)]

app.include_router(auth.router)
if saml_config.SAML_ENABLED:
    from .routers import saml_auth

    app.include_router(saml_auth.router)
app.include_router(projects.router, dependencies=protected)
app.include_router(data.router, dependencies=protected)
app.include_router(target.router, dependencies=protected)
app.include_router(sampling.router, dependencies=protected)
app.include_router(binning.router, dependencies=protected)
app.include_router(selection.router, dependencies=protected)
app.include_router(modeling.router, dependencies=protected)
app.include_router(ml_benchmark.router, dependencies=protected)
app.include_router(tuning.router, dependencies=protected)
app.include_router(final_model.router, dependencies=protected)
app.include_router(scaling.router, dependencies=protected)
app.include_router(validation.router, dependencies=protected)
app.include_router(reason_codes.router, dependencies=protected)
app.include_router(reporting.router, dependencies=protected)
app.include_router(batch_scoring.router, dependencies=protected)
app.include_router(versions.router, dependencies=protected)
app.include_router(decision_tree.router, dependencies=protected)
app.include_router(audit.router, dependencies=protected)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
