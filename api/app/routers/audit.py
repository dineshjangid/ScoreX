from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from ..db import AuditLogRecord, get_session
from ..repo import get_record_or_404
from ..schemas import AuditLogOut

router = APIRouter(prefix="/api/projects/{project_id}/audit", tags=["audit"])


@router.get("", response_model=list[AuditLogOut])
def list_audit_log(project_id: str) -> list[AuditLogOut]:
    with get_session() as session:
        get_record_or_404(session, project_id)  # 404 if the project doesn't exist
        records = (
            session.execute(
                select(AuditLogRecord)
                .where(AuditLogRecord.project_id == project_id)
                .order_by(AuditLogRecord.created_at.desc())
            )
            .scalars()
            .all()
        )
        return [
            AuditLogOut(
                id=r.id, username=r.username, role=r.role, action=r.action, detail=r.detail, created_at=r.created_at
            )
            for r in records
        ]
