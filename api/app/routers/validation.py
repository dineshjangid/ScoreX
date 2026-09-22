from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, HTTPException

from credittool_engine.binning import assign_bin_labels
from credittool_engine.data import load_dataframe
from credittool_engine.project import StepName, StepStatus
from credittool_engine.scoring import compute_scores
from credittool_engine.validation import (
    compute_auc_gini,
    compute_ks,
    decile_table,
    population_stability_index,
    roc_curve_points,
    stability_index,
)

from ..db import get_session
from ..repo import get_record_or_404, invalidate_downstream, record_to_project, save_project
from ..schemas import SampleMetrics, StabilityResult, ValidationOut

router = APIRouter(prefix="/api/projects/{project_id}/validation", tags=["validation"])


def _sample_metrics(bad_flag: pd.Series, score: pd.Series) -> SampleMetrics | None:
    if len(bad_flag) == 0:
        return None
    n_total = len(bad_flag)
    n_bad = int((bad_flag == 1).sum())
    ks = compute_ks(bad_flag, score)
    auc, gini = compute_auc_gini(bad_flag, score)
    return SampleMetrics(
        n_total=n_total,
        n_bad=n_bad,
        bad_rate_pct=round(n_bad / n_total * 100, 2),
        ks=ks,
        auc=auc,
        gini=gini,
    )


@router.post("", response_model=ValidationOut)
def run_validation(project_id: str) -> ValidationOut:
    with get_session() as session:
        record = get_record_or_404(session, project_id)
        project = record_to_project(record)

        binning_artifact = project.artifacts.get(StepName.BINNING.value)
        model_artifact = project.artifacts.get(StepName.MODELING.value)
        scaling_artifact = project.artifacts.get(StepName.SCALING.value)
        if not binning_artifact or not model_artifact or not scaling_artifact:
            raise HTTPException(status_code=400, detail="Build the scorecard (through scaling) before validating")

        df = load_dataframe(record.data_path)
        splits = pd.read_parquet(record.splits_path)
        binning_variables = binning_artifact["variables"]
        fitted_params = model_artifact["fitted_params"]
        factor, offset = scaling_artifact["factor"], scaling_artifact["offset"]

        def sample_frame(label: str) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
            idx = splits.index[splits["sample"] == label]
            sub_df = df.loc[idx]
            bad_flag = splits.loc[idx, "target"]
            score = compute_scores(sub_df, binning_variables, fitted_params, factor, offset)
            return sub_df, bad_flag, score

        train_df, train_bad, train_score = sample_frame("train")
        test_df, test_bad, test_score = sample_frame("test")
        oot_df, oot_bad, oot_score = sample_frame("oot")

        train_metrics = _sample_metrics(train_bad, train_score)
        test_metrics = _sample_metrics(test_bad, test_score)
        oot_metrics = _sample_metrics(oot_bad, oot_score)
        if train_metrics is None or test_metrics is None:
            raise HTTPException(status_code=400, detail="Training and test samples must be non-empty")

        psi_test = StabilityResult(**population_stability_index(train_score, test_score))
        psi_oot = StabilityResult(**population_stability_index(train_score, oot_score)) if len(oot_score) > 0 else None

        csi_test: dict[str, StabilityResult] = {}
        csi_oot: dict[str, StabilityResult] | None = {} if len(oot_df) > 0 else None
        model_vars = [v for v in fitted_params if v != "const"]
        for var in model_vars:
            binning = binning_variables[var]
            train_labels = assign_bin_labels(
                train_df[var], binning["kind"], binning.get("cutpoints"), binning.get("categories_map")
            )
            test_labels = assign_bin_labels(
                test_df[var], binning["kind"], binning.get("cutpoints"), binning.get("categories_map")
            )
            csi_test[var] = StabilityResult(**stability_index(train_labels, test_labels))
            if csi_oot is not None:
                oot_labels = assign_bin_labels(
                    oot_df[var], binning["kind"], binning.get("cutpoints"), binning.get("categories_map")
                )
                csi_oot[var] = StabilityResult(**stability_index(train_labels, oot_labels))

        result = ValidationOut(
            train=train_metrics,
            test=test_metrics,
            oot=oot_metrics,
            roc_train=roc_curve_points(train_bad, train_score),
            decile_table_train=decile_table(train_bad, train_score),
            psi_test_vs_train=psi_test,
            psi_oot_vs_train=psi_oot,
            csi_test_vs_train=csi_test,
            csi_oot_vs_train=csi_oot,
        )

        project.set_artifact(StepName.VALIDATION, result.model_dump())
        project.mark_step(StepName.VALIDATION, StepStatus.COMPLETE)
        invalidate_downstream(project, record, StepName.VALIDATION)
        save_project(session, record, project)

    return result
