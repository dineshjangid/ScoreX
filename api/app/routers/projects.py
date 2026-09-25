from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from credittool_engine.project import Project, lifecycle_progress

from ..auth import AuthUser, get_current_user
from ..db import AuditLogRecord, ModelVersionRecord, ProjectRecord, get_session
from ..repo import get_record_or_404, log_audit, record_to_project
from ..schemas import ChampionSummary, ProjectCreate, ProjectDetail, ProjectListItem
from .versions import _to_summary as version_summary

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


@router.get("", response_model=list[ProjectListItem])
def list_projects() -> list[ProjectListItem]:
    with get_session() as session:
        records = session.execute(select(ProjectRecord).order_by(ProjectRecord.updated_at.desc())).scalars().all()

        latest = (
            select(AuditLogRecord.project_id, func.max(AuditLogRecord.created_at).label("at"))
            .where(AuditLogRecord.project_id.is_not(None))
            .group_by(AuditLogRecord.project_id)
            .subquery()
        )
        last_editors = dict(
            session.execute(
                select(AuditLogRecord.project_id, AuditLogRecord.username).join(
                    latest,
                    (AuditLogRecord.project_id == latest.c.project_id) & (AuditLogRecord.created_at == latest.c.at),
                )
            ).all()
        )

        champions = {}
        for v in session.execute(select(ModelVersionRecord).where(ModelVersionRecord.is_champion)).scalars():
            summary = version_summary(v)
            champions[v.project_id] = ChampionSummary(
                version_number=summary.version_number,
                label=summary.label,
                train_ks=summary.train_ks,
                train_gini=summary.train_gini,
            )

        items = []
        for r in records:
            completed, total, current = lifecycle_progress(record_to_project(r))
            items.append(
                ProjectListItem(
                    id=r.id,
                    name=r.name,
                    scorecard_type=r.scorecard_type,
                    created_at=r.created_at,
                    updated_at=r.updated_at,
                    steps_completed=completed,
                    steps_total=total,
                    current_step=current.value if current else None,
                    last_edited_by=last_editors.get(r.id),
                    champion=champions.get(r.id),
                )
            )
        return items


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
