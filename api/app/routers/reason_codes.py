from __future__ import annotations

import io

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Response

from credittool_engine.data import load_dataframe
from credittool_engine.project import StepName, StepStatus
from credittool_engine.reason_codes import compute_reason_codes, compute_variable_contributions
from credittool_engine.scoring import compute_scores

from ..auth import AuthUser, get_current_user
from ..db import get_session
from ..repo import get_record_or_404, invalidate_downstream, log_audit, record_to_project, save_project
from ..schemas import ReasonCodesConfigIn, ReasonCodesOut

router = APIRouter(prefix="/api/projects/{project_id}/reason_codes", tags=["reason_codes"])


def _load_scorecard_pieces(project):
    binning_artifact = project.artifacts.get(StepName.BINNING.value)
    model_artifact = project.artifacts.get(StepName.MODELING.value)
    scaling_artifact = project.artifacts.get(StepName.SCALING.value)
    if not binning_artifact or not model_artifact or not scaling_artifact:
        raise HTTPException(status_code=400, detail="Build the scorecard before generating reason codes")
    return binning_artifact["variables"], model_artifact["fitted_params"], scaling_artifact["factor"], scaling_artifact["offset"]


@router.post("", response_model=ReasonCodesOut)
def run_reason_codes(
    project_id: str, body: ReasonCodesConfigIn, current_user: AuthUser = Depends(get_current_user)
) -> ReasonCodesOut:
    with get_session() as session:
        record = get_record_or_404(session, project_id)
        project = record_to_project(record)

        binning_variables, fitted_params, factor, offset = _load_scorecard_pieces(project)

        df = load_dataframe(record.data_path)
        contributions = compute_variable_contributions(df, binning_variables, fitted_params, factor)
        reasons = compute_reason_codes(contributions, top_n=body.top_n)
        scores = compute_scores(df, binning_variables, fitted_params, factor, offset)

        preview_n = min(body.preview_rows, len(df))
        preview_rows = []
        for idx in df.index[:preview_n]:
            row = {"row_index": int(idx), "score": int(scores.loc[idx])}
            for i in range(body.top_n):
                row[f"reason_{i + 1}"] = reasons.loc[idx, f"reason_{i + 1}"]
                row[f"reason_{i + 1}_points"] = reasons.loc[idx, f"reason_{i + 1}_points"]
            preview_rows.append(row)

        result = ReasonCodesOut(top_n=body.top_n, n_scored=len(df), preview=preview_rows)

        project.set_artifact(StepName.REASON_CODES, {"config": body.model_dump(), **result.model_dump()})
        project.mark_step(StepName.REASON_CODES, StepStatus.COMPLETE)
        invalidate_downstream(project, record, StepName.REASON_CODES)
        save_project(session, record, project, current_user, "reason_codes.run", f"top_n={body.top_n}, n_scored={len(df)}")

    return result


@router.get("/export")
def export_reason_codes(project_id: str, top_n: int = 3, current_user: AuthUser = Depends(get_current_user)) -> Response:
    with get_session() as session:
        record = get_record_or_404(session, project_id)
        project = record_to_project(record)
        binning_variables, fitted_params, factor, offset = _load_scorecard_pieces(project)

        df = load_dataframe(record.data_path)
        contributions = compute_variable_contributions(df, binning_variables, fitted_params, factor)
        reasons = compute_reason_codes(contributions, top_n=top_n)
        scores = compute_scores(df, binning_variables, fitted_params, factor, offset)

        out = df.copy()
        out["score"] = scores
        out = pd.concat([out, reasons], axis=1)

        log_audit(session, current_user, project_id, "reason_codes.export", f"Downloaded scored CSV ({len(df)} rows)")
        session.commit()

        buffer = io.StringIO()
        out.to_csv(buffer, index=False)
        return Response(
            content=buffer.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=scored_data_with_reason_codes.csv"},
        )
