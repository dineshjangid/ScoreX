from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

from credittool_engine.data import load_dataframe
from credittool_engine.modeling import fit_logistic_regression, predict_probability
from credittool_engine.project import Project, StepName, StepStatus
from credittool_engine.validation import discrimination_metrics

from ..auth import AuthUser, get_current_user
from ..candidates import add_candidate
from ..db import ProjectRecord, get_session
from ..repo import build_woe_frame, get_record_or_404, invalidate_downstream, record_to_project, save_project
from ..schemas import ModelingConfigIn, ModelOut

router = APIRouter(prefix="/api/projects/{project_id}/modeling", tags=["modeling"])


def activate_logistic(project: Project, record: ProjectRecord, model_artifact: dict) -> None:
    """Make `model_artifact` (a logistic model dict carrying its
    candidate_id) the project's model. Everything downstream was built
    from the previous model, so it's reset."""
    project.set_artifact(StepName.MODELING, model_artifact)
    project.mark_step(StepName.MODELING, StepStatus.COMPLETE)
    invalidate_downstream(project, record, StepName.MODELING)


@router.post("", response_model=ModelOut)
def run_modeling(project_id: str, body: ModelingConfigIn, current_user: AuthUser = Depends(get_current_user)) -> ModelOut:
    """Fit a logistic model and save it as a candidate. It becomes the
    project's active model only if there isn't one yet — otherwise it's
    activated explicitly from the candidates list, so trying settings
    doesn't reset Final Model Selection, Scaling and Validation."""
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
        binning_variables = binning_artifact["variables"]

        def woe_and_target(sample: str) -> tuple[pd.DataFrame, pd.Series]:
            idx = splits.index[splits["sample"] == sample]
            return build_woe_frame(df, binning_variables, idx), splits.loc[idx, "target"]

        train_woe, train_bad = woe_and_target("train")
        try:
            model = fit_logistic_regression(train_woe, train_bad, variables, penalty=body.penalty, alpha=body.alpha)
        except Exception as exc:  # e.g. perfect separation / non-convergence
            raise HTTPException(status_code=400, detail=f"Model failed to fit: {exc}") from exc
        if not model.variables:
            raise HTTPException(
                status_code=400, detail="The L1 penalty dropped every variable — lower the penalty strength"
            )

        sample_metrics = {"train": discrimination_metrics(train_bad, predict_probability(train_woe, model.fitted_params))}
        for sample in ("test", "oot"):
            woe, bad = woe_and_target(sample)
            sample_metrics[sample] = discrimination_metrics(bad, predict_probability(woe, model.fitted_params)) if len(bad) else None

        model_dict = model.to_dict()
        candidate_id = add_candidate(
            project,
            current_user,
            kind="logistic",
            variables=model.variables,
            settings={"penalty": model.penalty, "alpha": model.alpha, "dropped_variables": model.dropped_variables},
            sample_metrics=sample_metrics,
            payload=model_dict,
        )
        artifact = {**model_dict, "candidate_id": candidate_id, "sample_metrics": sample_metrics}

        activated = not project.artifacts.get(StepName.MODELING.value)
        if activated:
            activate_logistic(project, record, artifact)

        penalty_note = "" if model.penalty == "none" else f", {model.penalty.upper()} alpha={model.alpha}"
        test_gini = (sample_metrics.get("test") or {}).get("gini")
        save_project(
            session, record, project, current_user, "modeling.run",
            f"Fit logistic candidate {candidate_id} on {model.variables}{penalty_note} "
            f"(test Gini={test_gini}){' — now the active model' if activated else ''}",
        )

    return ModelOut(**artifact)
