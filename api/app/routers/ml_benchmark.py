from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

from credittool_engine.data import load_dataframe
from credittool_engine.modeling import ALGORITHM_LABELS, ALL_ALGORITHMS, Hyperparams, fit_ml_benchmark
from credittool_engine.project import Project, StepName

from ..auth import AuthUser, get_current_user
from ..candidates import add_candidate
from ..db import ProjectRecord, get_session
from ..repo import get_record_or_404, invalidate_downstream, record_to_project, save_project
from ..schemas import MLBenchmarkAllOut, MLBenchmarkConfigIn, MLBenchmarkOut, MLHyperparamsIn

router = APIRouter(prefix="/api/projects/{project_id}/ml_benchmark", tags=["ml_benchmark"])


def activate_ml_result(project: Project, record: ProjectRecord, algorithm: str, result: dict) -> None:
    """Make `result` (a benchmark result dict carrying its candidate_id)
    the one Final Model Selection offers for `algorithm`. If that algorithm
    is the current final model, the final model and everything after it
    were built from the previous result, so they're reset."""
    existing = project.artifacts.get("ml_benchmark") or {}
    results = dict(existing.get("results") or {})
    results[algorithm] = result
    project.set_extra("ml_benchmark", {**existing, "results": results})

    final_model = project.artifacts.get(StepName.FINAL_MODEL_SELECTION.value) or {}
    if final_model.get("algorithm") == algorithm:
        invalidate_downstream(project, record, StepName.MODELING)


@router.post("", response_model=MLBenchmarkAllOut)
def run_ml_benchmark(
    project_id: str, body: MLBenchmarkConfigIn, current_user: AuthUser = Depends(get_current_user)
) -> MLBenchmarkAllOut:
    """Fit the chosen algorithm(s) and save each fit as a candidate. A fit
    becomes its algorithm's active result only if that algorithm has none
    yet; otherwise it's activated explicitly from the candidates list."""
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
        idx = {s: splits.index[splits["sample"] == s] for s in ("train", "test", "oot")}
        if len(idx["train"]) == 0 or len(idx["test"]) == 0:
            raise HTTPException(status_code=400, detail="Training and test samples must be non-empty")

        hyperparams = Hyperparams.from_dict(MLHyperparamsIn(**body.model_dump()).model_dump())
        active_results = (project.artifacts.get("ml_benchmark") or {}).get("results") or {}

        new_ids = []
        run_labels = []
        for algo in algorithms:
            result = fit_ml_benchmark(
                df.loc[idx["train"]],
                splits.loc[idx["train"], "target"],
                df.loc[idx["test"]],
                splits.loc[idx["test"], "target"],
                variables,
                algorithm=algo,
                hyperparams=hyperparams,
                oot_df=df.loc[idx["oot"]],
                oot_bad=splits.loc[idx["oot"], "target"],
            )
            result_dict = MLBenchmarkOut(**result.to_dict()).model_dump()
            candidate_id = add_candidate(
                project,
                current_user,
                kind=algo,
                variables=variables,
                settings=result_dict["hyperparams"],
                sample_metrics=result_dict["sample_metrics"],
                payload=result_dict,
            )
            new_ids.append(candidate_id)
            if algo not in active_results:
                activate_ml_result(project, record, algo, {**result_dict, "candidate_id": candidate_id})
            run_labels.append(f"{ALGORITHM_LABELS[algo]} test AUC={result.test_auc}")

        save_project(
            session,
            record,
            project,
            current_user,
            "ml_benchmark.run",
            f"{'; '.join(run_labels)} on {', '.join(variables)} "
            f"({', '.join(f'{k}={v}' for k, v in hyperparams.to_dict().items() if v is not None)})",
        )
        results = (project.artifacts.get("ml_benchmark") or {}).get("results") or {}

    return MLBenchmarkAllOut(results={k: MLBenchmarkOut(**v) for k, v in results.items()}, new_candidate_ids=new_ids)
