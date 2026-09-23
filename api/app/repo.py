"""Shared helpers for loading/saving Project state against ProjectRecord rows."""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import pandas as pd
from fastapi import HTTPException
from sqlalchemy.orm import Session

from credittool_engine.binning import apply_binning
from credittool_engine.project import Project, StepName, StepStatus, steps_for

from .auth import AuthUser
from .db import UPLOADS_DIR, AuditLogRecord, ProjectRecord, now_iso


def record_to_project(record: ProjectRecord) -> Project:
    return Project.from_dict(json.loads(record.payload))


def invalidate_downstream(project: Project, record: ProjectRecord, from_step: StepName) -> None:
    """Reset every step after `from_step` to not_started, drop its
    artifacts, and clear any on-disk side files those steps produced. Call
    this whenever a step is (re)saved, since anything computed against its
    old output is now stale.
    """
    order = steps_for(project.scorecard_type)
    reset_steps = order[order.index(from_step) + 1 :]
    for step in reset_steps:
        project.mark_step(step, StepStatus.NOT_STARTED)
        project.artifacts.pop(step.value, None)
    if StepName.SAMPLING in reset_steps:
        record.splits_path = None
    if StepName.FINAL_MODEL_SELECTION in reset_steps:
        path = final_model_path(record.id)
        if os.path.exists(path):
            os.remove(path)


def final_model_path(project_id: str) -> Path:
    """Where a project's persisted fitted ML final model (if any) lives —
    a fixed, deterministic path, so picking a new algorithm just overwrites
    it and nothing needs to track the path separately in the DB."""
    return Path(UPLOADS_DIR) / project_id / "final_model.joblib"


def effective_final_model_artifact(project: Project) -> dict | None:
    """The project's final-model selection, or — for a project built before
    this step existed — an implicit "logistic" selection synthesized from a
    completed modeling+scaling build, so existing scorecards built under
    the old (logistic-only) flow keep working without redoing everything.
    """
    explicit = project.artifacts.get(StepName.FINAL_MODEL_SELECTION.value)
    if explicit:
        return explicit

    modeling = project.artifacts.get(StepName.MODELING.value)
    scaling = project.artifacts.get(StepName.SCALING.value)
    if modeling and scaling and "config" in scaling:
        return {"source": "logistic", "algorithm": "logistic", "variables": modeling["variables"], "metrics": None}
    return None


def get_record_or_404(session: Session, project_id: str) -> ProjectRecord:
    record = session.get(ProjectRecord, project_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return record


def log_audit(session: Session, actor: AuthUser, project_id: str | None, action: str, detail: str = "") -> None:
    """Record one audit-trail entry. Doesn't commit — callers that aren't
    already inside a save_project() call should commit afterward."""
    session.add(
        AuditLogRecord(
            id=str(uuid.uuid4()),
            user_id=actor.id,
            username=actor.username,
            role=actor.role,
            project_id=project_id,
            action=action,
            detail=detail,
            created_at=now_iso(),
        )
    )


def save_project(
    session: Session,
    record: ProjectRecord,
    project: Project,
    actor: AuthUser | None = None,
    action: str | None = None,
    detail: str = "",
) -> None:
    record.payload = json.dumps(project.to_dict())
    record.updated_at = project.updated_at.isoformat()
    session.add(record)
    if actor and action:
        log_audit(session, actor, record.id, action, detail)
    session.commit()


def build_woe_frame(df: pd.DataFrame, binning_variables: dict, idx: pd.Index) -> pd.DataFrame:
    """WOE-transform every binned variable for the given rows, using the
    binning artifact's stored bins/cutpoints/categories_map (as persisted
    JSON dicts, not the VariableBinning dataclass).
    """
    data = {
        var: apply_binning(
            df.loc[idx, var],
            kind=binning["kind"],
            bins=binning["bins"],
            cutpoints=binning.get("cutpoints"),
            categories_map=binning.get("categories_map"),
        )
        for var, binning in binning_variables.items()
    }
    return pd.DataFrame(data, index=idx)
