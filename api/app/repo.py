"""Shared helpers for loading/saving Project state against ProjectRecord rows."""
from __future__ import annotations

import json

from fastapi import HTTPException
from sqlalchemy.orm import Session

from credittool_engine.project import Project

from .db import ProjectRecord


def record_to_project(record: ProjectRecord) -> Project:
    return Project.from_dict(json.loads(record.payload))


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
