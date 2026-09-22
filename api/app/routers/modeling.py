from __future__ import annotations

import os

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

from credittool_engine.data import load_dataframe
from credittool_engine.modeling import fit_logistic_regression
from credittool_engine.project import StepName, StepStatus

from ..auth import AuthUser, get_current_user
from ..db import get_session
from ..repo import build_woe_frame, get_record_or_404, invalidate_downstream, record_to_project, save_project
from ..schemas import ModelingConfigIn, ModelOut

router = APIRouter(prefix="/api/projects/{project_id}/modeling", tags=["modeling"])


@router.post("", response_model=ModelOut)
def run_modeling(project_id: str, body: ModelingConfigIn, current_user: AuthUser = Depends(get_current_user)) -> ModelOut:
    with get_session() as session:
        record = get_record_or_404(session, project_id)
        project = record_to_project(record)

        binning_artifact = project.artifacts.get(StepName.BINNING.value)
        selection_artifact = project.artifacts.get(StepName.VARIABLE_SELECTION.value)
        if not binning_artifact or not selection_artifact:
            raise HTTPException(status_code=400, detail="Run variable selection before modeling")

        variables = body.variables or selection_artifact["selected"]
        unknown = [v for v in variables if v not in binning_artifact["variables"]]
        if unknown:
            raise HTTPException(status_code=400, detail=f"Unknown binned variable(s): {unknown}")
        if len(variables) == 0:
            raise HTTPException(status_code=400, detail="Select at least one variable to model")

        df = load_dataframe(record.data_path)
        splits = pd.read_parquet(record.splits_path)
        train_idx = splits.index[splits["sample"] == "train"]
        bad_flag = splits.loc[train_idx, "target"]

        woe_frame = build_woe_frame(df, binning_artifact["variables"], train_idx)
        try:
            model = fit_logistic_regression(woe_frame, bad_flag, variables)
        except Exception as exc:  # e.g. perfect separation / non-convergence
            raise HTTPException(status_code=400, detail=f"Model failed to fit: {exc}") from exc

        project.set_artifact(StepName.MODELING, model.to_dict())
        project.mark_step(StepName.MODELING, StepStatus.COMPLETE)
        invalidate_downstream(project, record, StepName.MODELING)
        save_project(session, record, project, current_user, "modeling.run", f"Fit logistic model on {variables}")

    return ModelOut(**model.to_dict())
