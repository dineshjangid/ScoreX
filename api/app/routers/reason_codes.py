from __future__ import annotations

import io

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Response

from credittool_engine.data import load_dataframe
from credittool_engine.modeling import load_model
from credittool_engine.project import StepName, StepStatus
from credittool_engine.reason_codes import (
    compute_reason_codes,
    compute_shap_contributions,
    compute_shap_reason_codes,
    compute_variable_contributions,
)
from credittool_engine.scoring import compute_ml_scores, compute_scores

from ..auth import AuthUser, get_current_user
from ..db import get_session
from ..repo import effective_final_model_artifact, final_model_path, get_record_or_404, invalidate_downstream, log_audit, record_to_project, save_project
from ..schemas import ReasonCodesConfigIn, ReasonCodesOut

router = APIRouter(prefix="/api/projects/{project_id}/reason_codes", tags=["reason_codes"])


def _score_and_reasons(project, record, df: pd.DataFrame, top_n: int) -> tuple[pd.Series, pd.DataFrame]:
    """Returns (scores, reasons) for `df`, using whichever final model the
    project has selected — the logistic scorecard's WOE/points contributions,
    or an ML model's per-row SHAP contributions."""
    binning_artifact = project.artifacts.get(StepName.BINNING.value)
    final_model_artifact = effective_final_model_artifact(project)
    if not binning_artifact or not final_model_artifact:
        raise HTTPException(status_code=400, detail="Select a final model before generating reason codes")

    if final_model_artifact["source"] == "logistic":
        model_artifact = project.artifacts.get(StepName.MODELING.value)
        scaling_artifact = project.artifacts.get(StepName.SCALING.value)
        if not model_artifact or not scaling_artifact:
            raise HTTPException(status_code=400, detail="Build the scorecard before generating reason codes")
        binning_variables = binning_artifact["variables"]
        fitted_params = model_artifact["fitted_params"]
        factor, offset = scaling_artifact["factor"], scaling_artifact["offset"]

        scores = compute_scores(df, binning_variables, fitted_params, factor, offset)
        contributions = compute_variable_contributions(df, binning_variables, fitted_params, factor)
        reasons = compute_reason_codes(contributions, top_n=top_n)
    else:
        algorithm = final_model_artifact["algorithm"]
        variables = final_model_artifact["variables"]
        categories = final_model_artifact["feature_categories"]
        model = load_model(final_model_path(record.id))

        scores = compute_ml_scores(df, variables, model, categories, algorithm)
        contributions = compute_shap_contributions(df, variables, model, categories, algorithm)
        reasons = compute_shap_reason_codes(contributions, top_n=top_n)

    return scores, reasons


@router.post("", response_model=ReasonCodesOut)
def run_reason_codes(
    project_id: str, body: ReasonCodesConfigIn, current_user: AuthUser = Depends(get_current_user)
) -> ReasonCodesOut:
    with get_session() as session:
        record = get_record_or_404(session, project_id)
        project = record_to_project(record)

        df = load_dataframe(record.data_path)
        scores, reasons = _score_and_reasons(project, record, df, body.top_n)

        preview_n = min(body.preview_rows, len(df))
        preview_rows = []
        for idx in df.index[:preview_n]:
            row = {"row_index": int(idx), "score": int(scores.loc[idx])}
            for i in range(body.top_n):
                row[f"reason_{i + 1}"] = reasons.loc[idx, f"reason_{i + 1}"]
                row[f"reason_{i + 1}_points"] = reasons.loc[idx, f"reason_{i + 1}_points"]
            preview_rows.append(row)

        primary = reasons["reason_1"].dropna()
        frequency = [
            {"variable": str(var), "count": int(count), "pct": round(count / len(primary) * 100, 2)}
            for var, count in primary.value_counts().items()
        ] if len(primary) else []

        result = ReasonCodesOut(top_n=body.top_n, n_scored=len(df), preview=preview_rows, reason_1_frequency=frequency)

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

        df = load_dataframe(record.data_path)
        scores, reasons = _score_and_reasons(project, record, df, top_n)

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
