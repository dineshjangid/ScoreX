from __future__ import annotations

import os

import pandas as pd
from fastapi import APIRouter, HTTPException

from credittool_engine.binning import apply_manual_categorical_bins, apply_manual_numeric_bins, bin_variable
from credittool_engine.data import load_dataframe
from credittool_engine.project import StepName, StepStatus

from ..db import get_session
from ..repo import get_record_or_404, invalidate_downstream, record_to_project, save_project
from ..schemas import BinningConfigIn, BinningSummaryItem, ManualBinningIn

router = APIRouter(prefix="/api/projects/{project_id}/binning", tags=["binning"])


@router.post("", response_model=list[BinningSummaryItem])
def run_binning(project_id: str, body: BinningConfigIn) -> list[BinningSummaryItem]:
    with get_session() as session:
        record = get_record_or_404(session, project_id)
        project = record_to_project(record)

        if not record.data_path or not os.path.exists(record.data_path):
            raise HTTPException(status_code=400, detail="Upload a dataset before binning")
        if not record.splits_path or not os.path.exists(record.splits_path):
            raise HTTPException(status_code=400, detail="Run sampling before binning")

        target_artifact = project.artifacts.get(StepName.TARGET_DEFINITION.value)
        if not target_artifact:
            raise HTTPException(status_code=400, detail="Define the target before binning")

        df = load_dataframe(record.data_path)
        splits = pd.read_parquet(record.splits_path)
        train_idx = splits.index[splits["sample"] == "train"]
        if len(train_idx) == 0:
            raise HTTPException(status_code=400, detail="Training sample is empty; adjust sampling first")
        bad_flag = splits.loc[train_idx, "target"]

        definition = target_artifact["definition"]
        skip_columns = {definition["target_column"]}
        if definition.get("exclude_column"):
            skip_columns.add(definition["exclude_column"])

        candidate_vars = body.variables or [c for c in df.columns if c not in skip_columns]
        missing = [v for v in candidate_vars if v not in df.columns]
        if missing:
            raise HTTPException(status_code=400, detail=f"Unknown column(s): {missing}")

        results: list[BinningSummaryItem] = []
        detail: dict[str, dict] = {}
        for var in candidate_vars:
            binning = bin_variable(
                df.loc[train_idx, var],
                bad_flag,
                max_bins=body.max_bins,
                min_bin_size=body.min_bin_size,
            )
            detail[var] = binning.to_dict()
            results.append(
                BinningSummaryItem(variable=var, kind=binning.kind, iv=binning.iv, n_bins=len(binning.bins))
            )
        results.sort(key=lambda r: r.iv, reverse=True)

        project.set_artifact(
            StepName.BINNING,
            {"config": body.model_dump(), "variables": detail},
        )
        project.mark_step(StepName.BINNING, StepStatus.COMPLETE)
        invalidate_downstream(project, record, StepName.BINNING)
        save_project(session, record, project)

    return results


@router.put("/{variable}", response_model=BinningSummaryItem)
def edit_variable_binning(project_id: str, variable: str, body: ManualBinningIn) -> BinningSummaryItem:
    with get_session() as session:
        record = get_record_or_404(session, project_id)
        project = record_to_project(record)

        binning_artifact = project.artifacts.get(StepName.BINNING.value)
        if not binning_artifact or variable not in binning_artifact["variables"]:
            raise HTTPException(status_code=400, detail=f"Variable '{variable}' has not been binned yet")

        kind = binning_artifact["variables"][variable]["kind"]

        df = load_dataframe(record.data_path)
        splits = pd.read_parquet(record.splits_path)
        train_idx = splits.index[splits["sample"] == "train"]
        bad_flag = splits.loc[train_idx, "target"]

        if kind == "numeric":
            if body.cutpoints is None:
                raise HTTPException(status_code=400, detail="cutpoints is required for a numeric variable")
            binning = apply_manual_numeric_bins(df.loc[train_idx, variable], bad_flag, body.cutpoints)
        else:
            if body.categories_map is None:
                raise HTTPException(status_code=400, detail="categories_map is required for a categorical variable")
            try:
                binning = apply_manual_categorical_bins(df.loc[train_idx, variable], bad_flag, body.categories_map)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        binning_artifact["variables"][variable] = binning.to_dict()
        project.set_artifact(StepName.BINNING, binning_artifact)
        # The edited variable's WOE/IV changed, so anything built from it
        # (selection onward) is stale.
        invalidate_downstream(project, record, StepName.BINNING)
        save_project(session, record, project)

    return BinningSummaryItem(variable=variable, kind=binning.kind, iv=binning.iv, n_bins=len(binning.bins))
