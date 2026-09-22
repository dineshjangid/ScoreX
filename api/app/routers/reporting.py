from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response

from credittool_engine.project import Project, StepName, StepStatus
from credittool_engine.reporting import build_excel_report, build_pdf_report, generate_scoring_python, generate_scoring_sql

from ..db import get_session
from ..repo import get_record_or_404, record_to_project, save_project

router = APIRouter(prefix="/api/projects/{project_id}/reporting", tags=["reporting"])


def _build_report_data(project: Project) -> dict:
    scaling_artifact = project.artifacts.get(StepName.SCALING.value)
    if not scaling_artifact:
        raise HTTPException(status_code=400, detail="Build the scorecard (through scaling) before exporting a report")
    return {
        "project_name": project.name,
        "scorecard_type": project.scorecard_type.value,
        "target_definition": project.artifacts.get(StepName.TARGET_DEFINITION.value),
        "sampling": project.artifacts.get(StepName.SAMPLING.value),
        "binning": project.artifacts.get(StepName.BINNING.value),
        "variable_selection": project.artifacts.get(StepName.VARIABLE_SELECTION.value),
        "modeling": project.artifacts.get(StepName.MODELING.value),
        "scaling": scaling_artifact,
        "validation": project.artifacts.get(StepName.VALIDATION.value),
    }


@router.post("")
def complete_reporting(project_id: str) -> dict:
    with get_session() as session:
        record = get_record_or_404(session, project_id)
        project = record_to_project(record)
        _build_report_data(project)  # raises 400 if not ready
        project.mark_step(StepName.REPORTING, StepStatus.COMPLETE)
        save_project(session, record, project)
    return {"status": "ok"}


@router.get("/excel")
def export_excel(project_id: str) -> Response:
    with get_session() as session:
        record = get_record_or_404(session, project_id)
        project = record_to_project(record)
        data = _build_report_data(project)
    content = build_excel_report(data)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=scorecard_report.xlsx"},
    )


@router.get("/pdf")
def export_pdf(project_id: str) -> Response:
    with get_session() as session:
        record = get_record_or_404(session, project_id)
        project = record_to_project(record)
        data = _build_report_data(project)
    content = build_pdf_report(data)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=scorecard_report.pdf"},
    )


@router.get("/scoring-code")
def export_scoring_code(project_id: str, lang: str = "python") -> Response:
    with get_session() as session:
        record = get_record_or_404(session, project_id)
        project = record_to_project(record)
        data = _build_report_data(project)

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

    return Response(content=code, media_type=media_type, headers={"Content-Disposition": f"attachment; filename={filename}"})
