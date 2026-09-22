from __future__ import annotations

import io
import os
import uuid
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, HTTPException, Response, UploadFile

from credittool_engine.data import SUPPORTED_EXTENSIONS, load_dataframe
from credittool_engine.project import StepName
from credittool_engine.reason_codes import compute_reason_codes, compute_variable_contributions
from credittool_engine.scoring import compute_scores

from ..db import UPLOADS_DIR, get_session
from ..repo import get_record_or_404, record_to_project, save_project
from ..schemas import BatchScoringOut, ScoreDistribution

router = APIRouter(prefix="/api/projects/{project_id}/batch_scoring", tags=["batch_scoring"])


def _load_scorecard_pieces(project):
    binning_artifact = project.artifacts.get(StepName.BINNING.value)
    model_artifact = project.artifacts.get(StepName.MODELING.value)
    scaling_artifact = project.artifacts.get(StepName.SCALING.value)
    if not binning_artifact or not model_artifact or not scaling_artifact:
        raise HTTPException(status_code=400, detail="Build the scorecard (through scaling) before batch scoring")
    return binning_artifact["variables"], model_artifact["fitted_params"], scaling_artifact["factor"], scaling_artifact["offset"]


def _check_required_columns(df: pd.DataFrame, fitted_params: dict) -> None:
    required = [v for v in fitted_params if v != "const"]
    missing = [v for v in required if v not in df.columns]
    if missing:
        raise HTTPException(status_code=400, detail=f"Uploaded file is missing required column(s): {missing}")


@router.post("", response_model=BatchScoringOut)
async def upload_batch(project_id: str, file: UploadFile, top_n: int = 3) -> BatchScoringOut:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Supported: {sorted(SUPPORTED_EXTENSIONS)}",
        )

    with get_session() as session:
        record = get_record_or_404(session, project_id)
        project = record_to_project(record)
        binning_variables, fitted_params, factor, offset = _load_scorecard_pieces(project)

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
            _check_required_columns(df, fitted_params)

            scores = compute_scores(df, binning_variables, fitted_params, factor, offset)
            contributions = compute_variable_contributions(df, binning_variables, fitted_params, factor)
            reasons = compute_reason_codes(contributions, top_n=top_n)
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
        save_project(session, record, project)

    return result


@router.get("/export")
def export_batch(project_id: str, top_n: int = 3) -> Response:
    with get_session() as session:
        record = get_record_or_404(session, project_id)
        project = record_to_project(record)
        binning_variables, fitted_params, factor, offset = _load_scorecard_pieces(project)

        if not record.batch_path or not os.path.exists(record.batch_path):
            raise HTTPException(status_code=404, detail="No batch file uploaded for this project yet")

        df = load_dataframe(record.batch_path)
        _check_required_columns(df, fitted_params)

        scores = compute_scores(df, binning_variables, fitted_params, factor, offset)
        contributions = compute_variable_contributions(df, binning_variables, fitted_params, factor)
        reasons = compute_reason_codes(contributions, top_n=top_n)

        out = df.copy()
        out["score"] = scores
        out = pd.concat([out, reasons], axis=1)

        buffer = io.StringIO()
        out.to_csv(buffer, index=False)
        return Response(
            content=buffer.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=batch_scored.csv"},
        )
