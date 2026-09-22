from __future__ import annotations

import os

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

from credittool_engine.data import load_dataframe
from credittool_engine.project import StepName, StepStatus
from credittool_engine.selection import select_variables

from ..auth import AuthUser, get_current_user
from ..db import get_session
from ..repo import build_woe_frame, get_record_or_404, invalidate_downstream, record_to_project, save_project
from ..schemas import SelectionConfigIn, SelectionResultOut

router = APIRouter(prefix="/api/projects/{project_id}/selection", tags=["selection"])


@router.post("", response_model=SelectionResultOut)
def run_selection(project_id: str, body: SelectionConfigIn, current_user: AuthUser = Depends(get_current_user)) -> SelectionResultOut:
    with get_session() as session:
        record = get_record_or_404(session, project_id)
        project = record_to_project(record)

        binning_artifact = project.artifacts.get(StepName.BINNING.value)
        if not binning_artifact:
            raise HTTPException(status_code=400, detail="Run binning before variable selection")
        if not record.data_path or not os.path.exists(record.data_path):
            raise HTTPException(status_code=400, detail="Upload a dataset first")
        if not record.splits_path or not os.path.exists(record.splits_path):
            raise HTTPException(status_code=400, detail="Run sampling before variable selection")

        df = load_dataframe(record.data_path)
        splits = pd.read_parquet(record.splits_path)
        train_idx = splits.index[splits["sample"] == "train"]

        binning_variables = binning_artifact["variables"]
        woe_frame = build_woe_frame(df, binning_variables, train_idx)
        iv_by_variable = {var: b["iv"] for var, b in binning_variables.items()}

        result = select_variables(
            woe_frame,
            iv_by_variable,
            min_iv=body.min_iv,
            max_corr=body.max_corr,
            max_vif=body.max_vif,
        )

        project.set_artifact(StepName.VARIABLE_SELECTION, {"config": body.model_dump(), **result.to_dict()})
        project.mark_step(StepName.VARIABLE_SELECTION, StepStatus.COMPLETE)
        invalidate_downstream(project, record, StepName.VARIABLE_SELECTION)
        save_project(
            session, record, project, current_user, "selection.run", f"{len(result.selected)} variables selected"
        )

    return SelectionResultOut(**result.to_dict())
