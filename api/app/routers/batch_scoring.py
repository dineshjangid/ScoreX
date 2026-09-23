from __future__ import annotations

import io
import os
import uuid
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile

from credittool_engine.data import SUPPORTED_EXTENSIONS, load_dataframe
from credittool_engine.modeling import load_model
from credittool_engine.project import StepName
from credittool_engine.reason_codes import (
    compute_reason_codes,
    compute_shap_contributions,
    compute_shap_reason_codes,
    compute_variable_contributions,
)
from credittool_engine.scoring import compute_ml_scores, compute_scores

from ..auth import AuthUser, get_current_user
from ..db import UPLOADS_DIR, get_session
from ..repo import effective_final_model_artifact, final_model_path, get_record_or_404, log_audit, record_to_project, save_project
from ..schemas import BatchScoringOut, ScoreDistribution

router = APIRouter(prefix="/api/projects/{project_id}/batch_scoring", tags=["batch_scoring"])


def _load_scoring_context(project, record):
    binning_artifact = project.artifacts.get(StepName.BINNING.value)
    final_model_artifact = effective_final_model_artifact(project)
    if not binning_artifact or not final_model_artifact:
        raise HTTPException(status_code=400, detail="Select a final model before batch scoring")

    if final_model_artifact["source"] == "logistic":
        model_artifact = project.artifacts.get(StepName.MODELING.value)
        scaling_artifact = project.artifacts.get(StepName.SCALING.value)
        if not model_artifact or not scaling_artifact:
            raise HTTPException(status_code=400, detail="Build the scorecard (through scaling) before batch scoring")
        fitted_params = model_artifact["fitted_params"]
        required_columns = [v for v in fitted_params if v != "const"]

        def score_and_reasons(df: pd.DataFrame, top_n: int) -> tuple[pd.Series, pd.DataFrame]:
            binning_variables = binning_artifact["variables"]
            factor, offset = scaling_artifact["factor"], scaling_artifact["offset"]
            scores = compute_scores(df, binning_variables, fitted_params, factor, offset)
            contributions = compute_variable_contributions(df, binning_variables, fitted_params, factor)
            reasons = compute_reason_codes(contributions, top_n=top_n)
            return scores, reasons

    else:
        algorithm = final_model_artifact["algorithm"]
        variables = final_model_artifact["variables"]
        categories = final_model_artifact["feature_categories"]
        model = load_model(final_model_path(record.id))
        required_columns = variables

        def score_and_reasons(df: pd.DataFrame, top_n: int) -> tuple[pd.Series, pd.DataFrame]:
            scores = compute_ml_scores(df, variables, model, categories, algorithm)
            contributions = compute_shap_contributions(df, variables, model, categories, algorithm)
            reasons = compute_shap_reason_codes(contributions, top_n=top_n)
            return scores, reasons

    return required_columns, score_and_reasons


def _check_required_columns(df: pd.DataFrame, required: list[str]) -> None:
    missing = [v for v in required if v not in df.columns]
    if missing:
        raise HTTPException(status_code=400, detail=f"Uploaded file is missing required column(s): {missing}")


@router.post("", response_model=BatchScoringOut)
async def upload_batch(
    project_id: str, file: UploadFile, top_n: int = 3, current_user: AuthUser = Depends(get_current_user)
) -> BatchScoringOut:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Supported: {sorted(SUPPORTED_EXTENSIONS)}",
        )

    with get_session() as session:
        record = get_record_or_404(session, project_id)
        project = record_to_project(record)
        required_columns, score_and_reasons = _load_scoring_context(project, record)

        dest_dir = Path(UPLOADS_DIR) / project_id / "batch"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / f"{uuid.uuid4().hex}{suffix}"
        dest_path.write_bytes(await file.read())

        try:
            df = load_dataframe(dest_path)
        except Exception as exc:
            os.remove(dest_path)
            raise HTTPException(status_code=400, detail=f"Could not read file: {exc}") from exc

        try:
            _check_required_columns(df, required_columns)
            scores, reasons = score_and_reasons(df, top_n)
        except HTTPException:
            os.remove(dest_path)
            raise

        described = scores.astype(float).describe(percentiles=[0.25, 0.5, 0.75])
        distribution = ScoreDistribution(
            mean=round(float(described["mean"]), 2),
            std=round(float(described["std"]), 2) if not pd.isna(described["std"]) else 0.0,
            min=round(float(described["min"]), 2),
            p25=round(float(described["25%"]), 2),
            median=round(float(described["50%"]), 2),
            p75=round(float(described["75%"]), 2),
            max=round(float(described["max"]), 2),
        )

        preview_n = min(20, len(df))
        preview_rows = []
        for idx in df.index[:preview_n]:
            row = {"row_index": int(idx), "score": int(scores.loc[idx])}
            for i in range(top_n):
                row[f"reason_{i + 1}"] = reasons.loc[idx, f"reason_{i + 1}"]
            preview_rows.append(row)

        result = BatchScoringOut(
            filename=file.filename or dest_path.name,
            n_scored=len(df),
            top_n=top_n,
            score_distribution=distribution,
            preview=preview_rows,
        )

        # Replace any previous batch file for this project.
        if record.batch_path and record.batch_path != str(dest_path) and os.path.exists(record.batch_path):
            os.remove(record.batch_path)
        record.batch_path = str(dest_path)

        project.set_extra("batch_scoring", result.model_dump())
        save_project(
            session, record, project, current_user, "batch_scoring.upload",
            f"Uploaded '{file.filename}' ({len(df)} rows)",
        )

    return result


@router.get("/export")
def export_batch(project_id: str, top_n: int = 3, current_user: AuthUser = Depends(get_current_user)) -> Response:
    with get_session() as session:
        record = get_record_or_404(session, project_id)
        project = record_to_project(record)
        required_columns, score_and_reasons = _load_scoring_context(project, record)

        if not record.batch_path or not os.path.exists(record.batch_path):
            raise HTTPException(status_code=404, detail="No batch file uploaded for this project yet")

        df = load_dataframe(record.batch_path)
        _check_required_columns(df, required_columns)
        scores, reasons = score_and_reasons(df, top_n)

        out = df.copy()
        out["score"] = scores
        out = pd.concat([out, reasons], axis=1)

        log_audit(session, current_user, project_id, "batch_scoring.export", f"Downloaded batch-scored CSV ({len(df)} rows)")
        session.commit()

        buffer = io.StringIO()
        out.to_csv(buffer, index=False)
        return Response(
            content=buffer.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=batch_scored.csv"},
        )
