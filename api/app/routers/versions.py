from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select

from credittool_engine.project import StepName

from ..auth import AuthUser, get_current_user
from ..db import ModelVersionRecord, get_session, now_iso
from ..repo import effective_final_model_artifact, get_record_or_404, log_audit, record_to_project
from ..schemas import VersionCreateIn, VersionDetail, VersionSummary

router = APIRouter(prefix="/api/projects/{project_id}/versions", tags=["versions"])

SNAPSHOT_STEPS = [
    StepName.TARGET_DEFINITION,
    StepName.SAMPLING,
    StepName.BINNING,
    StepName.VARIABLE_SELECTION,
    StepName.MODELING,
    StepName.FINAL_MODEL_SELECTION,
    StepName.SCALING,
    StepName.VALIDATION,
]


def _to_summary(v: ModelVersionRecord) -> VersionSummary:
    snapshot = json.loads(v.snapshot)
    modeling = snapshot.get("modeling") or {}
    scaling = snapshot.get("scaling") or {}
    validation = snapshot.get("validation") or {}
    train = validation.get("train") if validation else None

    return VersionSummary(
        id=v.id,
        version_number=v.version_number,
        label=v.label,
        is_champion=v.is_champion,
        created_at=v.created_at,
        n_variables=len(modeling.get("variables", [])),
        train_auc=train.get("auc") if train else None,
        train_ks=train.get("ks") if train else None,
        train_gini=train.get("gini") if train else None,
        score_range=f"{scaling['min_score']}–{scaling['max_score']}" if scaling and "min_score" in scaling else None,
    )


def _get_version_or_404(session, project_id: str, version_id: str) -> ModelVersionRecord:
    version = session.get(ModelVersionRecord, version_id)
    if version is None or version.project_id != project_id:
        raise HTTPException(status_code=404, detail="Version not found")
    return version


@router.post("", response_model=VersionSummary)
def create_version(project_id: str, body: VersionCreateIn, current_user: AuthUser = Depends(get_current_user)) -> VersionSummary:
    with get_session() as session:
        record = get_record_or_404(session, project_id)
        project = record_to_project(record)

        modeling = project.artifacts.get(StepName.MODELING.value)
        final_model = effective_final_model_artifact(project)
        if not modeling or not final_model:
            raise HTTPException(status_code=400, detail="Fit a model and select a final model before saving a version")
        if final_model["source"] == "logistic" and not project.artifacts.get(StepName.SCALING.value):
            raise HTTPException(status_code=400, detail="Build the scorecard before saving a version")

        snapshot = {step.value: project.artifacts.get(step.value) for step in SNAPSHOT_STEPS}
        snapshot["ml_benchmark"] = project.artifacts.get("ml_benchmark")

        max_version = session.execute(
            select(func.max(ModelVersionRecord.version_number)).where(ModelVersionRecord.project_id == project_id)
        ).scalar()
        next_version = (max_version or 0) + 1

        version = ModelVersionRecord(
            id=str(uuid.uuid4()),
            project_id=project_id,
            version_number=next_version,
            label=body.label,
            is_champion=(max_version is None),  # first version saved becomes champion by default
            created_at=now_iso(),
            snapshot=json.dumps(snapshot),
        )
        session.add(version)
        log_audit(session, current_user, project_id, "version.create", f"Saved v{next_version} ({body.label or 'no label'})")
        session.commit()

        return _to_summary(version)


@router.get("", response_model=list[VersionSummary])
def list_versions(project_id: str) -> list[VersionSummary]:
    with get_session() as session:
        records = (
            session.execute(
                select(ModelVersionRecord)
                .where(ModelVersionRecord.project_id == project_id)
                .order_by(ModelVersionRecord.version_number.desc())
            )
            .scalars()
            .all()
        )
        return [_to_summary(v) for v in records]


@router.get("/{version_id}", response_model=VersionDetail)
def get_version(project_id: str, version_id: str) -> VersionDetail:
    with get_session() as session:
        version = _get_version_or_404(session, project_id, version_id)
        summary = _to_summary(version)
        return VersionDetail(**summary.model_dump(), snapshot=json.loads(version.snapshot))


@router.post("/{version_id}/champion", response_model=VersionSummary)
def set_champion(project_id: str, version_id: str, current_user: AuthUser = Depends(get_current_user)) -> VersionSummary:
    with get_session() as session:
        target = _get_version_or_404(session, project_id, version_id)
        others = (
            session.execute(select(ModelVersionRecord).where(ModelVersionRecord.project_id == project_id))
            .scalars()
            .all()
        )
        for v in others:
            v.is_champion = v.id == version_id
        log_audit(session, current_user, project_id, "version.champion", f"Set v{target.version_number} as champion")
        session.commit()
        return _to_summary(target)


@router.delete("/{version_id}", status_code=204)
def delete_version(project_id: str, version_id: str, current_user: AuthUser = Depends(get_current_user)) -> None:
    with get_session() as session:
        version = _get_version_or_404(session, project_id, version_id)
        log_audit(session, current_user, project_id, "version.delete", f"Deleted v{version.version_number}")
        session.delete(version)
        session.commit()
