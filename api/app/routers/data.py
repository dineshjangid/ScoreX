from __future__ import annotations

import os
import uuid
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, HTTPException, UploadFile

from credittool_engine.data import SUPPORTED_EXTENSIONS, load_dataframe, profile_dataframe
from credittool_engine.project import StepName, StepStatus

from ..db import UPLOADS_DIR, get_session
from ..repo import get_record_or_404, invalidate_downstream, record_to_project, save_project
from ..schemas import DataPreview, ProjectDetail

router = APIRouter(prefix="/api/projects/{project_id}/data", tags=["data"])


def _project_upload_dir(project_id: str) -> Path:
    path = Path(UPLOADS_DIR) / project_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _clean_records(df: pd.DataFrame) -> list[dict]:
    return df.where(pd.notnull(df), None).to_dict(orient="records")


@router.post("", response_model=ProjectDetail)
async def upload_data(project_id: str, file: UploadFile) -> ProjectDetail:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Supported: {sorted(SUPPORTED_EXTENSIONS)}",
        )

    with get_session() as session:
        record = get_record_or_404(session, project_id)
        project = record_to_project(record)

        dest_dir = _project_upload_dir(project_id)
        dest_path = dest_dir / f"{uuid.uuid4().hex}{suffix}"
        contents = await file.read()
        dest_path.write_bytes(contents)

        try:
            df = load_dataframe(dest_path)
        except Exception as exc:
            os.remove(dest_path)
            raise HTTPException(status_code=400, detail=f"Could not read file: {exc}") from exc

        profile = profile_dataframe(df)
        project.set_artifact(
            StepName.DATA_INGESTION,
            {"original_filename": file.filename, **profile},
        )
        project.mark_step(StepName.DATA_INGESTION, StepStatus.COMPLETE)

        # A new upload invalidates everything computed against the old file.
        invalidate_downstream(project, record, StepName.DATA_INGESTION)

        # Replace any previously uploaded file for this project.
        if record.data_path and record.data_path != str(dest_path) and os.path.exists(record.data_path):
            os.remove(record.data_path)
        record.data_path = str(dest_path)

        save_project(session, record, project)
        return ProjectDetail(**project.to_dict())


@router.get("/preview", response_model=DataPreview)
def preview_data(project_id: str, n: int = 20) -> DataPreview:
    with get_session() as session:
        record = get_record_or_404(session, project_id)
        if not record.data_path or not os.path.exists(record.data_path):
            raise HTTPException(status_code=404, detail="No data uploaded for this project yet")
        df = load_dataframe(record.data_path)
        rows = _clean_records(df.head(n))
        return DataPreview(columns=list(df.columns), rows=rows)
