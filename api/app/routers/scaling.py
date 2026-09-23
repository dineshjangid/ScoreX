from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

from credittool_engine.data import load_dataframe
from credittool_engine.project import StepName, StepStatus
from credittool_engine.scaling import ScalingConfig, build_scorecard
from credittool_engine.scoring import compute_scores

from ..auth import AuthUser, get_current_user
from ..db import get_session
from ..repo import get_record_or_404, invalidate_downstream, record_to_project, save_project
from ..schemas import ScalingConfigIn, ScorecardOut, ScoreDistribution

router = APIRouter(prefix="/api/projects/{project_id}/scaling", tags=["scaling"])


@router.post("", response_model=ScorecardOut)
def run_scaling(project_id: str, body: ScalingConfigIn, current_user: AuthUser = Depends(get_current_user)) -> ScorecardOut:
    with get_session() as session:
        record = get_record_or_404(session, project_id)
        project = record_to_project(record)

        binning_artifact = project.artifacts.get(StepName.BINNING.value)
        model_artifact = project.artifacts.get(StepName.MODELING.value)
        final_model_artifact = project.artifacts.get(StepName.FINAL_MODEL_SELECTION.value)
        if not binning_artifact or not model_artifact:
            raise HTTPException(status_code=400, detail="Fit a model before scaling")
        if not final_model_artifact:
            raise HTTPException(status_code=400, detail="Select a final model before scaling")
        if final_model_artifact["source"] != "logistic":
            raise HTTPException(
                status_code=400,
                detail=f"Scaling to points isn't applicable — the final model is {final_model_artifact['algorithm']}",
            )

        config = ScalingConfig(pdo=body.pdo, base_score=body.base_score, base_odds=body.base_odds)
        scorecard = build_scorecard(model_artifact["fitted_params"], binning_artifact["variables"], config)

        df = load_dataframe(record.data_path)
        splits = pd.read_parquet(record.splits_path)
        train_idx = splits.index[splits["sample"] == "train"]
        train_scores = compute_scores(
            df.loc[train_idx],
            binning_artifact["variables"],
            model_artifact["fitted_params"],
            scorecard.factor,
            scorecard.offset,
        )
        described = train_scores.astype(float).describe(percentiles=[0.25, 0.5, 0.75])
        distribution = ScoreDistribution(
            mean=round(float(described["mean"]), 2),
            std=round(float(described["std"]), 2),
            min=round(float(described["min"]), 2),
            p25=round(float(described["25%"]), 2),
            median=round(float(described["50%"]), 2),
            p75=round(float(described["75%"]), 2),
            max=round(float(described["max"]), 2),
        )

        result = ScorecardOut(**scorecard.to_dict(), train_score_distribution=distribution)

        project.set_artifact(StepName.SCALING, {"config": body.model_dump(), **result.model_dump()})
        project.mark_step(StepName.SCALING, StepStatus.COMPLETE)
        invalidate_downstream(project, record, StepName.SCALING)
        save_project(
            session, record, project, current_user, "scaling.run",
            f"PDO={body.pdo}, base_score={body.base_score}, score range {result.min_score}-{result.max_score}",
        )

    return result
