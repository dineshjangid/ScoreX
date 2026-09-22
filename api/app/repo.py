"""Shared helpers for loading/saving Project state against ProjectRecord rows."""
from __future__ import annotations

import json

from fastapi import HTTPException
from sqlalchemy.orm import Session

from credittool_engine.project import STEP_ORDER, Project, StepName, StepStatus

from .db import ProjectRecord


def record_to_project(record: ProjectRecord) -> Project:
    return Project.from_dict(json.loads(record.payload))


def invalidate_downstream(project: Project, record: ProjectRecord, from_step: StepName) -> None:
    """Reset every step after `from_step` to not_started, drop its
    artifacts, and clear any on-disk side files those steps produced. Call
    this whenever a step is (re)saved, since anything computed against its
    old output is now stale.
    """
    reset_steps = STEP_ORDER[STEP_ORDER.index(from_step) + 1 :]
    for step in reset_steps:
        project.mark_step(step, StepStatus.NOT_STARTED)
        project.artifacts.pop(step.value, None)
    if StepName.SAMPLING in reset_steps:
        record.splits_path = None


def get_record_or_404(session: Session, project_id: str) -> ProjectRecord:
    record = session.get(ProjectRecord, project_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return record


def save_project(session: Session, record: ProjectRecord, project: Project) -> None:
    record.payload = json.dumps(project.to_dict())
    record.updated_at = project.updated_at.isoformat()
    session.add(record)
    session.commit()
