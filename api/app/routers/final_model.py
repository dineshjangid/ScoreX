from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sklearn.metrics import roc_auc_score

from credittool_engine.data import load_dataframe
from credittool_engine.modeling import (
    ALGORITHM_LABELS,
    ALL_ALGORITHMS,
    fit_model,
    predict_probability,
    save_model,
)
from credittool_engine.project import StepName, StepStatus

from ..auth import AuthUser, get_current_user
from ..db import get_session
from ..repo import build_woe_frame, final_model_path, get_record_or_404, invalidate_downstream, record_to_project, save_project
from ..schemas import FinalModelCandidateOut, FinalModelOut, FinalModelSetIn, FinalModelStatusOut

router = APIRouter(prefix="/api/projects/{project_id}/final_model", tags=["final_model"])


def _logistic_candidate(df, splits, binning_variables, fitted_params) -> FinalModelCandidateOut:
    def auc_gini(idx: pd.Index) -> tuple[float, float]:
        bad = splits.loc[idx, "target"]
        if bad.nunique() < 2:
            return 0.5, 0.0
        woe_frame = build_woe_frame(df, binning_variables, idx)
        p_bad = predict_probability(woe_frame, fitted_params)
        auc = roc_auc_score(bad, p_bad)
        return round(float(auc), 4), round(float(2 * auc - 1), 4)

    train_idx = splits.index[splits["sample"] == "train"]
    test_idx = splits.index[splits["sample"] == "test"]
    train_auc, train_gini = auc_gini(train_idx)
    test_auc, test_gini = auc_gini(test_idx)
    return FinalModelCandidateOut(algorithm="logistic", train_auc=train_auc, test_auc=test_auc, train_gini=train_gini, test_gini=test_gini)


@router.get("", response_model=FinalModelStatusOut)
def get_final_model_status(project_id: str) -> FinalModelStatusOut:
    with get_session() as session:
        record = get_record_or_404(session, project_id)
        project = record_to_project(record)

        binning_artifact = project.artifacts.get(StepName.BINNING.value)
        model_artifact = project.artifacts.get(StepName.MODELING.value)
        if not binning_artifact or not model_artifact:
            raise HTTPException(status_code=400, detail="Fit a model before selecting a final model")

        df = load_dataframe(record.data_path)
        splits = pd.read_parquet(record.splits_path)

        candidates: dict[str, FinalModelCandidateOut] = {
            "logistic": _logistic_candidate(df, splits, binning_artifact["variables"], model_artifact["fitted_params"])
        }
        ml_benchmark_artifact = project.artifacts.get("ml_benchmark") or {}
        for algo, result in (ml_benchmark_artifact.get("results") or {}).items():
            candidates[algo] = FinalModelCandidateOut(
                algorithm=algo,
                train_auc=result["train_auc"],
                test_auc=result["test_auc"],
                train_gini=result["train_gini"],
                test_gini=result["test_gini"],
            )

        current_artifact = project.artifacts.get(StepName.FINAL_MODEL_SELECTION.value)
        current = FinalModelOut(**current_artifact) if current_artifact else None

    return FinalModelStatusOut(current=current, candidates=candidates)


@router.post("", response_model=FinalModelOut)
def set_final_model(project_id: str, body: FinalModelSetIn, current_user: AuthUser = Depends(get_current_user)) -> FinalModelOut:
    if body.algorithm != "logistic" and body.algorithm not in ALL_ALGORITHMS:
        raise HTTPException(status_code=400, detail=f"Unknown algorithm: {body.algorithm}")

    with get_session() as session:
        record = get_record_or_404(session, project_id)
        project = record_to_project(record)

        model_artifact = project.artifacts.get(StepName.MODELING.value)
        if not model_artifact:
            raise HTTPException(status_code=400, detail="Fit a model before selecting a final model")

        if body.algorithm == "logistic":
            artifact = {
                "source": "logistic",
                "algorithm": "logistic",
                "variables": model_artifact["variables"],
                "metrics": None,
            }
            project.set_artifact(StepName.FINAL_MODEL_SELECTION, artifact)
            project.mark_step(StepName.FINAL_MODEL_SELECTION, StepStatus.COMPLETE)
            invalidate_downstream(project, record, StepName.FINAL_MODEL_SELECTION)
            save_project(
                session, record, project, current_user, "final_model.set", "Final model: logistic regression scorecard"
            )
            return FinalModelOut(**artifact)

        ml_benchmark_artifact = project.artifacts.get("ml_benchmark") or {}
        results = ml_benchmark_artifact.get("results") or {}
        if body.algorithm not in results:
            raise HTTPException(
                status_code=400, detail=f"Run the ML benchmark for {ALGORITHM_LABELS[body.algorithm]} first"
            )

        config = ml_benchmark_artifact["config"]
        variables = config.get("variables") or results[body.algorithm]["variables"]

        df = load_dataframe(record.data_path)
        splits = pd.read_parquet(record.splits_path)
        train_idx = splits.index[splits["sample"] == "train"]
        train_df = df.loc[train_idx]
        train_bad = splits.loc[train_idx, "target"]

        model, categories = fit_model(
            train_df, train_bad, variables, body.algorithm, config["n_estimators"], config["max_depth"]
        )
        save_model(model, final_model_path(project_id))

        metrics = results[body.algorithm]
        artifact = {
            "source": "ml_benchmark",
            "algorithm": body.algorithm,
            "variables": variables,
            "feature_categories": categories,
            "metrics": {
                "algorithm": body.algorithm,
                "train_auc": metrics["train_auc"],
                "test_auc": metrics["test_auc"],
                "train_gini": metrics["train_gini"],
                "test_gini": metrics["test_gini"],
            },
        }
        project.set_artifact(StepName.FINAL_MODEL_SELECTION, artifact)
        project.mark_step(StepName.FINAL_MODEL_SELECTION, StepStatus.COMPLETE)
        invalidate_downstream(project, record, StepName.FINAL_MODEL_SELECTION)
        # Scaling to points isn't meaningful for an ML final model — mark it
        # complete with a sentinel so downstream steps (which all gate on
        # "scaling complete") unlock without a dead-end manual "skip" step.
        project.set_artifact(
            StepName.SCALING,
            {
                "not_applicable": True,
                "reason": f"Final model is {ALGORITHM_LABELS[body.algorithm]}; points-based scaling isn't used for ML models.",
            },
        )
        project.mark_step(StepName.SCALING, StepStatus.COMPLETE)
        save_project(
            session, record, project, current_user, "final_model.set",
            f"Final model: {ALGORITHM_LABELS[body.algorithm]} (test AUC={metrics['test_auc']})",
        )
        return FinalModelOut(**artifact)
