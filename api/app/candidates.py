"""Saved model fits ("candidates") and the downstream settings Rebuild reuses.

Every logistic fit and every ML benchmark run is kept as a candidate in the
project's "model_candidates" side artifact, so fits can be compared and an
earlier one brought back. At most one candidate per kind is *active*: the
active logistic candidate is the project's modeling artifact, and the active
candidate for each ML algorithm is that algorithm's ml_benchmark result —
exactly what Final Model Selection offers.
"""
from __future__ import annotations

import uuid
from typing import Any

from credittool_engine.project import Project, StepName

from .auth import AuthUser
from .db import now_iso

CANDIDATES_KEY = "model_candidates"
DOWNSTREAM_KEY = "downstream_settings"

# Oldest inactive candidates beyond this are discarded.
MAX_CANDIDATES = 50


def list_candidates(project: Project) -> list[dict[str, Any]]:
    return list(project.artifacts.get(CANDIDATES_KEY) or [])


def add_candidate(
    project: Project,
    actor: AuthUser,
    kind: str,
    variables: list[str],
    settings: dict[str, Any],
    sample_metrics: dict[str, Any],
    payload: dict[str, Any],
) -> str:
    """Store a new candidate (newest first) and return its id. `payload` is
    what activating it restores: the logistic model dict, or the ML
    benchmark result dict."""
    candidate_id = uuid.uuid4().hex[:12]
    candidates = [
        {
            "id": candidate_id,
            "kind": kind,
            "created_at": now_iso(),
            "created_by": actor.username,
            "variables": variables,
            "settings": settings,
            "sample_metrics": sample_metrics,
            "payload": payload,
        },
        *list_candidates(project),
    ]
    active = active_candidate_ids(project)
    while len(candidates) > MAX_CANDIDATES:
        oldest_inactive = next((c for c in reversed(candidates) if c["id"] not in active), None)
        if oldest_inactive is None:
            break
        candidates.remove(oldest_inactive)
    project.set_extra(CANDIDATES_KEY, candidates)
    return candidate_id


def get_candidate(project: Project, candidate_id: str) -> dict[str, Any] | None:
    return next((c for c in list_candidates(project) if c["id"] == candidate_id), None)


def remove_candidate(project: Project, candidate_id: str) -> None:
    project.set_extra(CANDIDATES_KEY, [c for c in list_candidates(project) if c["id"] != candidate_id])


def active_candidate_ids(project: Project) -> set[str]:
    ids = set()
    modeling = project.artifacts.get(StepName.MODELING.value) or {}
    if modeling.get("candidate_id"):
        ids.add(modeling["candidate_id"])
    for result in ((project.artifacts.get("ml_benchmark") or {}).get("results") or {}).values():
        if result.get("candidate_id"):
            ids.add(result["candidate_id"])
    return ids


def remember_downstream_settings(project: Project) -> None:
    """Record the current Final Model Selection choice and Scaling config
    (whichever exist) so Rebuild can re-run them after a model change
    has reset those steps. Leaves previously remembered values in place
    for anything not currently set."""
    settings = dict(project.artifacts.get(DOWNSTREAM_KEY) or {})
    final_model = project.artifacts.get(StepName.FINAL_MODEL_SELECTION.value)
    if final_model and final_model.get("algorithm"):
        settings["final_model_algorithm"] = final_model["algorithm"]
    scaling = project.artifacts.get(StepName.SCALING.value)
    # An ML final model stores a not-applicable sentinel, not a config.
    if scaling and "config" in scaling:
        settings["scaling"] = scaling["config"]
    if settings:
        project.set_extra(DOWNSTREAM_KEY, settings)


def downstream_settings(project: Project) -> dict[str, Any]:
    return dict(project.artifacts.get(DOWNSTREAM_KEY) or {})
