from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse

from credittool_engine.modeling import FEATURE_MODE
from credittool_engine.project import Project, StepName, StepStatus
from credittool_engine.reporting import (
    build_excel_report,
    build_pdf_report,
    generate_ml_scoring_python,
    generate_scoring_python,
    generate_scoring_sql,
)

from ..auth import AuthUser, get_current_user
from ..db import get_session
from ..repo import effective_final_model_artifact, final_model_path, get_record_or_404, log_audit, record_to_project, save_project

router = APIRouter(prefix="/api/projects/{project_id}/reporting", tags=["reporting"])


def _build_report_data(project: Project) -> dict:
    final_model_artifact = effective_final_model_artifact(project)
    if not final_model_artifact:
        raise HTTPException(status_code=400, detail="Select a final model before exporting a report")

    data = {
        "project_name": project.name,
        "scorecard_type": project.scorecard_type.value,
        "target_definition": project.artifacts.get(StepName.TARGET_DEFINITION.value),
        "sampling": project.artifacts.get(StepName.SAMPLING.value),
        "binning": project.artifacts.get(StepName.BINNING.value),
        "variable_selection": project.artifacts.get(StepName.VARIABLE_SELECTION.value),
        "modeling": project.artifacts.get(StepName.MODELING.value),
        "final_model": final_model_artifact,
        "validation": project.artifacts.get(StepName.VALIDATION.value),
    }

    if final_model_artifact["source"] == "logistic":
        scaling_artifact = project.artifacts.get(StepName.SCALING.value)
        if not scaling_artifact:
            raise HTTPException(status_code=400, detail="Build the scorecard (through scaling) before exporting a report")
        data["scaling"] = scaling_artifact
    else:
        ml_benchmark_artifact = project.artifacts.get("ml_benchmark") or {}
        data["ml_benchmark_result"] = (ml_benchmark_artifact.get("results") or {}).get(final_model_artifact["algorithm"])

    return data


@router.post("")
def complete_reporting(project_id: str, current_user: AuthUser = Depends(get_current_user)) -> dict:
    with get_session() as session:
        record = get_record_or_404(session, project_id)
        project = record_to_project(record)
        _build_report_data(project)  # raises 400 if not ready
        project.mark_step(StepName.REPORTING, StepStatus.COMPLETE)
        save_project(session, record, project, current_user, "reporting.complete")
    return {"status": "ok"}


@router.get("/excel")
def export_excel(project_id: str, current_user: AuthUser = Depends(get_current_user)) -> Response:
    with get_session() as session:
        record = get_record_or_404(session, project_id)
        project = record_to_project(record)
        data = _build_report_data(project)
        log_audit(session, current_user, project_id, "reporting.export_excel", "Downloaded Excel report")
        session.commit()
    content = build_excel_report(data)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=scorecard_report.xlsx"},
    )


@router.get("/pdf")
def export_pdf(project_id: str, current_user: AuthUser = Depends(get_current_user)) -> Response:
    with get_session() as session:
        record = get_record_or_404(session, project_id)
        project = record_to_project(record)
        data = _build_report_data(project)
        log_audit(session, current_user, project_id, "reporting.export_pdf", "Downloaded PDF report")
        session.commit()
    content = build_pdf_report(data)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=scorecard_report.pdf"},
    )


@router.get("/scoring-code")
def export_scoring_code(project_id: str, lang: str = "python", current_user: AuthUser = Depends(get_current_user)) -> Response:
    with get_session() as session:
        record = get_record_or_404(session, project_id)
        project = record_to_project(record)
        data = _build_report_data(project)
        final_model_artifact = data["final_model"]

        if final_model_artifact["source"] != "logistic":
            if lang == "sql":
                raise HTTPException(
                    status_code=400,
                    detail="SQL export isn't available for ML final models — tree ensembles don't translate to SQL. "
                    "Use the Python export or download the model file instead.",
                )
            if lang != "python":
                raise HTTPException(status_code=400, detail="lang must be 'python' or 'sql'")
            code = generate_ml_scoring_python(
                final_model_artifact["algorithm"],
                final_model_artifact["variables"],
                final_model_artifact["feature_categories"],
                FEATURE_MODE[final_model_artifact["algorithm"]],
            )
            filename, media_type = "score_application.py", "text/x-python"
        else:
            binning_variables = data["binning"]["variables"]
            scorecard = data["scaling"]

            if lang == "sql":
                code = generate_scoring_sql(scorecard, binning_variables)
                filename, media_type = "score_application.sql", "text/plain"
            elif lang == "python":
                code = generate_scoring_python(scorecard, binning_variables)
                filename, media_type = "score_application.py", "text/x-python"
            else:
                raise HTTPException(status_code=400, detail="lang must be 'python' or 'sql'")

        log_audit(session, current_user, project_id, "reporting.export_code", f"Downloaded {lang} scoring code")
        session.commit()

    return Response(content=code, media_type=media_type, headers={"Content-Disposition": f"attachment; filename={filename}"})


@router.get("/model-file")
def export_model_file(project_id: str, current_user: AuthUser = Depends(get_current_user)) -> FileResponse:
    with get_session() as session:
        record = get_record_or_404(session, project_id)
        project = record_to_project(record)
        final_model_artifact = project.artifacts.get(StepName.FINAL_MODEL_SELECTION.value)
        if not final_model_artifact or final_model_artifact["source"] != "ml_benchmark":
            raise HTTPException(status_code=400, detail="No ML final model to download for this project")

        path = final_model_path(project_id)
        if not path.exists():
            raise HTTPException(status_code=404, detail="Model file not found — re-select the final model")

        log_audit(session, current_user, project_id, "reporting.export_model_file", "Downloaded fitted model file")
        session.commit()

    return FileResponse(path, media_type="application/octet-stream", filename="final_model.joblib")
