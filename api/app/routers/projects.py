from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy import select

from credittool_engine.project import Project

from ..auth import AuthUser, get_current_user
from ..db import ProjectRecord, get_session
from ..repo import get_record_or_404, log_audit, record_to_project
from ..schemas import ProjectCreate, ProjectDetail, ProjectSummary

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=ProjectDetail)
def create_project(body: ProjectCreate, current_user: AuthUser = Depends(get_current_user)) -> ProjectDetail:
    project = Project(name=body.name, scorecard_type=body.scorecard_type)
    record = ProjectRecord(
        id=project.id,
        name=project.name,
        scorecard_type=project.scorecard_type.value,
        created_at=project.created_at.isoformat(),
        updated_at=project.updated_at.isoformat(),
        payload=json.dumps(project.to_dict()),
    )
    with get_session() as session:
        session.add(record)
        log_audit(session, current_user, project.id, "project.create", f"Created project '{project.name}'")
        session.commit()
    return ProjectDetail(**project.to_dict())


@router.get("", response_model=list[ProjectSummary])
def list_projects() -> list[ProjectSummary]:
    with get_session() as session:
        records = session.execute(select(ProjectRecord).order_by(ProjectRecord.updated_at.desc())).scalars().all()
        return [
            ProjectSummary(
                id=r.id,
                name=r.name,
                scorecard_type=r.scorecard_type,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in records
        ]


@router.get("/{project_id}", response_model=ProjectDetail)
def get_project(project_id: str) -> ProjectDetail:
    with get_session() as session:
        record = get_record_or_404(session, project_id)
        project = record_to_project(record)
        return ProjectDetail(**project.to_dict())


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, current_user: AuthUser = Depends(get_current_user)) -> None:
    with get_session() as session:
        record = get_record_or_404(session, project_id)
        log_audit(session, current_user, project_id, "project.delete", f"Deleted project '{record.name}'")
        session.delete(record)
        session.commit()
