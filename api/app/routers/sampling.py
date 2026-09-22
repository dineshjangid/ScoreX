from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException

from credittool_engine.data import load_dataframe
from credittool_engine.project import StepName, StepStatus
from credittool_engine.sampling import SamplingConfig, assign_samples, sampling_summary
from credittool_engine.target import TargetDefinition, apply_target_definition

from ..db import UPLOADS_DIR, get_session
from ..repo import get_record_or_404, record_to_project, save_project
from ..schemas import SamplingConfigIn, SamplingSummary

router = APIRouter(prefix="/api/projects/{project_id}/sampling", tags=["sampling"])


@router.post("", response_model=SamplingSummary)
def save_sampling(project_id: str, body: SamplingConfigIn) -> SamplingSummary:
    with get_session() as session:
        record = get_record_or_404(session, project_id)
        project = record_to_project(record)

        target_artifact = project.artifacts.get(StepName.TARGET_DEFINITION.value)
        if not target_artifact:
            raise HTTPException(status_code=400, detail="Define the target before sampling")
        if not record.data_path or not os.path.exists(record.data_path):
            raise HTTPException(status_code=400, detail="Upload a dataset before sampling")

        df = load_dataframe(record.data_path)
        target_def = TargetDefinition.from_dict(target_artifact["definition"])
        bad_flag = apply_target_definition(df, target_def)

        config = SamplingConfig(
            test_size=body.test_size,
            oot_size=body.oot_size,
            date_column=body.date_column,
            random_state=body.random_state,
        )
        try:
            assignment = assign_samples(df, bad_flag, config)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        summary_dict = sampling_summary(assignment)

        dest_dir = Path(UPLOADS_DIR) / project_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        splits_path = dest_dir / "splits.parquet"
        assignment.to_parquet(splits_path)

        project.set_artifact(
            StepName.SAMPLING,
            {"config": body.model_dump(), "summary": summary_dict},
        )
        project.mark_step(StepName.SAMPLING, StepStatus.COMPLETE)
        record.splits_path = str(splits_path)
        save_project(session, record, project)

        return SamplingSummary(**summary_dict)
