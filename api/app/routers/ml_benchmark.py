from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

from credittool_engine.data import load_dataframe
from credittool_engine.modeling import ALGORITHM_LABELS, ALL_ALGORITHMS, fit_ml_benchmark
from credittool_engine.project import StepName

from ..auth import AuthUser, get_current_user
from ..db import get_session
from ..repo import get_record_or_404, record_to_project, save_project
from ..schemas import MLBenchmarkAllOut, MLBenchmarkConfigIn, MLBenchmarkOut

router = APIRouter(prefix="/api/projects/{project_id}/ml_benchmark", tags=["ml_benchmark"])


@router.post("", response_model=MLBenchmarkAllOut)
def run_ml_benchmark(
    project_id: str, body: MLBenchmarkConfigIn, current_user: AuthUser = Depends(get_current_user)
) -> MLBenchmarkAllOut:
    algorithms = ALL_ALGORITHMS if body.algorithm == "all" else [body.algorithm]
    for algo in algorithms:
        if algo not in ALL_ALGORITHMS:
            raise HTTPException(status_code=400, detail=f"Unknown algorithm: {algo}")

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

        existing = project.artifacts.get("ml_benchmark") or {}
        stored_results = dict(existing.get("results") or {})

        run_labels = []
        for algo in algorithms:
            result = fit_ml_benchmark(
                df.loc[train_idx],
                splits.loc[train_idx, "target"],
                df.loc[test_idx],
                splits.loc[test_idx, "target"],
                variables,
                algorithm=algo,
                n_estimators=body.n_estimators,
                max_depth=body.max_depth,
            )
            stored_results[algo] = MLBenchmarkOut(**result.to_dict()).model_dump()
            run_labels.append(f"{ALGORITHM_LABELS[algo]} test AUC={result.test_auc}")

        project.set_extra("ml_benchmark", {"config": body.model_dump(), "results": stored_results})
        save_project(
            session,
            record,
            project,
            current_user,
            "ml_benchmark.run",
            f"{'; '.join(run_labels)} on {variables}",
        )

    return MLBenchmarkAllOut(results={k: MLBenchmarkOut(**v) for k, v in stored_results.items()})
