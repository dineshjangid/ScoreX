from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException

from credittool_engine.data import load_dataframe
from credittool_engine.project import StepName, StepStatus
from credittool_engine.target import TargetDefinition, apply_target_definition, target_summary, vintage_analysis

from ..auth import AuthUser, get_current_user
from ..db import get_session
from ..repo import get_record_or_404, invalidate_downstream, record_to_project, save_project
from ..schemas import TargetDefinitionIn, TargetSummary, VintageRow

router = APIRouter(prefix="/api/projects/{project_id}/target", tags=["target"])


def _load_raw_df(record):
    if not record.data_path or not os.path.exists(record.data_path):
        raise HTTPException(status_code=400, detail="Upload a dataset before defining the target")
    return load_dataframe(record.data_path)


def _compute_summary(project_id: str, body: TargetDefinitionIn) -> TargetSummary:
    with get_session() as session:
        record = get_record_or_404(session, project_id)
        df = _load_raw_df(record)
        target_def = TargetDefinition(
            target_column=body.target_column,
            mode=body.mode,
            bad_values=body.bad_values,
            threshold=body.threshold,
            exclude_values=body.exclude_values,
            exclude_column=body.exclude_column,
            observation_date_column=body.observation_date_column,
            performance_window_months=body.performance_window_months,
        )
        try:
            bad_flag = apply_target_definition(df, target_def)
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return TargetSummary(**target_summary(bad_flag))


@router.post("/preview", response_model=TargetSummary)
def preview_target(project_id: str, body: TargetDefinitionIn) -> TargetSummary:
    return _compute_summary(project_id, body)


@router.post("", response_model=TargetSummary)
def save_target(project_id: str, body: TargetDefinitionIn, current_user: AuthUser = Depends(get_current_user)) -> TargetSummary:
    summary = _compute_summary(project_id, body)

    with get_session() as session:
        record = get_record_or_404(session, project_id)
        project = record_to_project(record)
        project.set_artifact(
            StepName.TARGET_DEFINITION,
            {"definition": body.model_dump(), "summary": summary.model_dump()},
        )
        project.mark_step(StepName.TARGET_DEFINITION, StepStatus.COMPLETE)
        # Changing the target definition invalidates everything downstream.
        invalidate_downstream(project, record, StepName.TARGET_DEFINITION)
        save_project(
            session, record, project, current_user, "target.save",
            f"Target: {body.target_column} ({body.mode}), bad rate {summary.bad_rate_pct}%",
        )

    return summary


@router.get("/vintage", response_model=list[VintageRow])
def get_vintage_analysis(project_id: str, date_column: str | None = None) -> list[VintageRow]:
    with get_session() as session:
        record = get_record_or_404(session, project_id)
        project = record_to_project(record)
        df = _load_raw_df(record)

        target_artifact = project.artifacts.get(StepName.TARGET_DEFINITION.value)
        if not target_artifact:
            raise HTTPException(status_code=400, detail="Define the target before running vintage analysis")

        target_def = TargetDefinition.from_dict(target_artifact["definition"])
        date_col = date_column or target_def.observation_date_column
        if not date_col:
            raise HTTPException(
                status_code=400,
                detail="Provide a date_column, or set an observation date column on the target definition",
            )
        if date_col not in df.columns:
            raise HTTPException(status_code=400, detail=f"Unknown column '{date_col}'")

        bad_flag = apply_target_definition(df, target_def)
        rows = vintage_analysis(df, date_col, bad_flag)
        return [VintageRow(**r) for r in rows]
