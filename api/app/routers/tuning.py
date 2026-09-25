"""Model tuning: compare saved candidates, switch the active one, and
rebuild Final Model Selection → Scaling → Validation in one call."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from credittool_engine.modeling import ALGORITHM_LABELS
from credittool_engine.project import StepName

from ..auth import AuthUser, get_current_user
from ..candidates import active_candidate_ids, downstream_settings, get_candidate, list_candidates, remove_candidate
from ..db import get_session
from ..repo import get_record_or_404, record_to_project, save_project
from ..schemas import (
    DownstreamSettingsOut,
    FinalModelSetIn,
    ModelCandidateOut,
    ModelCandidatesOut,
    ScalingConfigIn,
    ValidationOut,
)
from .final_model import set_final_model
from .ml_benchmark import activate_ml_result
from .modeling import activate_logistic
from .scaling import run_scaling
from .validation import run_validation

router = APIRouter(prefix="/api/projects/{project_id}", tags=["tuning"])


def _candidates_out(project) -> ModelCandidatesOut:
    active = active_candidate_ids(project)
    return ModelCandidatesOut(
        candidates=[
            ModelCandidateOut(
                id=c["id"],
                kind=c["kind"],
                created_at=c["created_at"],
                created_by=c["created_by"],
                is_active=c["id"] in active,
                variables=c["variables"],
                settings=c["settings"],
                sample_metrics=c["sample_metrics"],
            )
            for c in list_candidates(project)
        ],
        downstream_settings=DownstreamSettingsOut(**downstream_settings(project)),
    )


def _label(kind: str) -> str:
    return "Logistic" if kind == "logistic" else ALGORITHM_LABELS.get(kind, kind)


@router.get("/model_candidates", response_model=ModelCandidatesOut)
def get_model_candidates(project_id: str) -> ModelCandidatesOut:
    with get_session() as session:
        project = record_to_project(get_record_or_404(session, project_id))
        return _candidates_out(project)


@router.post("/model_candidates/{candidate_id}/activate", response_model=ModelCandidatesOut)
def activate_candidate(
    project_id: str, candidate_id: str, current_user: AuthUser = Depends(get_current_user)
) -> ModelCandidatesOut:
    with get_session() as session:
        record = get_record_or_404(session, project_id)
        project = record_to_project(record)
        candidate = get_candidate(project, candidate_id)
        if candidate is None:
            raise HTTPException(status_code=404, detail="Candidate not found")
        if candidate_id in active_candidate_ids(project):
            return _candidates_out(project)

        restored = {**candidate["payload"], "candidate_id": candidate_id, "sample_metrics": candidate["sample_metrics"]}
        if candidate["kind"] == "logistic":
            activate_logistic(project, record, restored)
        else:
            activate_ml_result(project, record, candidate["kind"], restored)

        save_project(
            session, record, project, current_user, "modeling.activate",
            f"Active {_label(candidate['kind'])} model is now candidate {candidate_id}",
        )
        return _candidates_out(project)


@router.delete("/model_candidates/{candidate_id}", response_model=ModelCandidatesOut)
def delete_candidate(
    project_id: str, candidate_id: str, current_user: AuthUser = Depends(get_current_user)
) -> ModelCandidatesOut:
    with get_session() as session:
        record = get_record_or_404(session, project_id)
        project = record_to_project(record)
        candidate = get_candidate(project, candidate_id)
        if candidate is None:
            raise HTTPException(status_code=404, detail="Candidate not found")
        if candidate_id in active_candidate_ids(project):
            raise HTTPException(status_code=400, detail="Can't delete the active model — activate another candidate first")
        remove_candidate(project, candidate_id)
        save_project(
            session, record, project, current_user, "modeling.delete_candidate",
            f"Deleted {_label(candidate['kind'])} candidate {candidate_id}",
        )
        return _candidates_out(project)


@router.post("/rebuild", response_model=ValidationOut)
def rebuild_downstream(project_id: str, current_user: AuthUser = Depends(get_current_user)) -> ValidationOut:
    """Re-run Final Model Selection, Scaling (logistic only) and Validation
    with the settings last used for each, after the model has changed."""
    with get_session() as session:
        project = record_to_project(get_record_or_404(session, project_id))
        settings = downstream_settings(project)
        algorithm = settings.get("final_model_algorithm")

        # Check everything up front so a rebuild never stops half-way.
        if not project.artifacts.get(StepName.MODELING.value):
            raise HTTPException(status_code=400, detail="Fit a model before rebuilding")
        if algorithm is None:
            raise HTTPException(
                status_code=400,
                detail="Choose a final model once in Final Model Selection — Rebuild then reuses that choice",
            )
        if algorithm == "logistic" and not settings.get("scaling"):
            raise HTTPException(
                status_code=400, detail="Run Scaling to Points once — Rebuild then reuses its PDO/base score settings"
            )
        if algorithm != "logistic":
            results = (project.artifacts.get("ml_benchmark") or {}).get("results") or {}
            if algorithm not in results:
                raise HTTPException(
                    status_code=400,
                    detail=f"The last final model was {_label(algorithm)}, which has no active candidate — activate one or choose another final model",
                )

    set_final_model(project_id, FinalModelSetIn(algorithm=algorithm), current_user)
    if algorithm == "logistic":
        run_scaling(project_id, ScalingConfigIn(**settings["scaling"]), current_user)
    return run_validation(project_id, current_user)
