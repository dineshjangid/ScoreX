from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, HTTPException

from credittool_engine.data import load_dataframe
from credittool_engine.modeling import fit_ml_benchmark
from credittool_engine.project import StepName

from ..db import get_session
from ..repo import get_record_or_404, record_to_project, save_project
from ..schemas import MLBenchmarkConfigIn, MLBenchmarkOut

router = APIRouter(prefix="/api/projects/{project_id}/ml_benchmark", tags=["ml_benchmark"])


@router.post("", response_model=MLBenchmarkOut)
def run_ml_benchmark(project_id: str, body: MLBenchmarkConfigIn) -> MLBenchmarkOut:
    with get_session() as session:
        record = get_record_or_404(session, project_id)
        project = record_to_project(record)

        selection_artifact = project.artifacts.get(StepName.VARIABLE_SELECTION.value)
        if not selection_artifact:
            raise HTTPException(status_code=400, detail="Run variable selection before the ML benchmark")

        variables = body.variables or selection_artifact["selected"]
        if not variables:
            raise HTTPException(status_code=400, detail="No variables to benchmark")

        df = load_dataframe(record.data_path)
        splits = pd.read_parquet(record.splits_path)
        train_idx = splits.index[splits["sample"] == "train"]
        test_idx = splits.index[splits["sample"] == "test"]
        if len(train_idx) == 0 or len(test_idx) == 0:
            raise HTTPException(status_code=400, detail="Training and test samples must be non-empty")

        result = fit_ml_benchmark(
            df.loc[train_idx],
            splits.loc[train_idx, "target"],
            df.loc[test_idx],
            splits.loc[test_idx, "target"],
            variables,
            n_estimators=body.n_estimators,
            max_depth=body.max_depth,
        )

        response = MLBenchmarkOut(**result.to_dict())
        project.set_extra("ml_benchmark", {"config": body.model_dump(), **response.model_dump()})
        save_project(session, record, project)

    return response
