from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from sqlalchemy import select

from credittool_engine.modeling import FEATURE_MODE
from credittool_engine.project import Project, StepName, StepStatus
from credittool_engine.reporting import (
    FIELD_KEYS,
    NARRATIVE_FIELDS,
    build_docx_report,
    build_excel_report,
    build_pdf_report,
    draft_narrative,
    generate_ml_scoring_python,
    generate_scoring_python,
    generate_scoring_sql,
)

from ..auth import AuthUser, get_current_user
from ..candidates import active_candidate_ids, list_candidates
from ..db import AuditLogRecord, ModelVersionRecord, get_session, now_iso
from ..repo import effective_final_model_artifact, final_model_path, get_record_or_404, log_audit, record_to_project, save_project
from ..schemas import NarrativeFieldOut, NarrativeIn, NarrativeOut
from .versions import _to_summary as version_summary

router = APIRouter(prefix="/api/projects/{project_id}/reporting", tags=["reporting"])


def _filename(project_name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9]+", "_", project_name).strip("_") or "model"
    return f"{safe}_model_development_document"


NARRATIVE_KEY = "documentation_narrative"


def _collect_report_data(project: Project, session, current_user: AuthUser) -> dict:
    """Everything the model development document draws on. Works on a
    partly built project too (sections without data are left out), which
    is what narrative drafting needs; exports use _build_report_data."""
    final_model_artifact = effective_final_model_artifact(project)
    data = {
        "project_name": project.name,
        "scorecard_type": project.scorecard_type.value,
        "project_created_at": project.created_at.isoformat(),
        "generated_at": now_iso(),
        "generated_by": current_user.username,
        "data_profile": project.artifacts.get(StepName.DATA_INGESTION.value),
        "target_definition": project.artifacts.get(StepName.TARGET_DEFINITION.value),
        "sampling": project.artifacts.get(StepName.SAMPLING.value),
        "binning": project.artifacts.get(StepName.BINNING.value),
        "variable_selection": project.artifacts.get(StepName.VARIABLE_SELECTION.value),
        "modeling": project.artifacts.get(StepName.MODELING.value),
        "final_model": final_model_artifact,
        "validation": project.artifacts.get(StepName.VALIDATION.value),
        "reason_codes": project.artifacts.get(StepName.REASON_CODES.value),
        "narrative": project.artifacts.get(NARRATIVE_KEY) or {},
    }

    active = active_candidate_ids(project)
    data["candidates"] = [
        {k: c[k] for k in ("id", "kind", "created_at", "created_by", "variables", "settings", "sample_metrics")} | {"is_active": c["id"] in active}
        for c in list_candidates(project)
    ]

    versions = session.execute(
        select(ModelVersionRecord)
        .where(ModelVersionRecord.project_id == project.id)
        .order_by(ModelVersionRecord.version_number.desc())
    ).scalars()
    data["versions"] = [version_summary(v).model_dump() for v in versions]

    audit = session.execute(
        select(AuditLogRecord).where(AuditLogRecord.project_id == project.id).order_by(AuditLogRecord.created_at.asc())
    ).scalars()
    data["audit"] = [
        {"created_at": e.created_at, "username": e.username, "role": e.role, "action": e.action, "detail": e.detail}
        for e in audit
    ]

    if final_model_artifact and final_model_artifact["source"] == "logistic":
        data["scaling"] = project.artifacts.get(StepName.SCALING.value)
    elif final_model_artifact:
        ml_benchmark_artifact = project.artifacts.get("ml_benchmark") or {}
        data["ml_benchmark_result"] = (ml_benchmark_artifact.get("results") or {}).get(final_model_artifact["algorithm"])
    return data


def _build_report_data(project: Project, session, current_user: AuthUser) -> dict:
    final_model_artifact = effective_final_model_artifact(project)
    if not final_model_artifact:
        raise HTTPException(status_code=400, detail="Select a final model before exporting a report")
    if final_model_artifact["source"] == "logistic" and not project.artifacts.get(StepName.SCALING.value):
        raise HTTPException(status_code=400, detail="Build the scorecard (through scaling) before exporting a report")
    return _collect_report_data(project, session, current_user)


@router.get("/narrative", response_model=NarrativeOut)
def get_narrative(project_id: str, current_user: AuthUser = Depends(get_current_user)) -> NarrativeOut:
    with get_session() as session:
        project = record_to_project(get_record_or_404(session, project_id))
        data = _collect_report_data(project, session, current_user)
    drafts = draft_narrative(data)
    saved = data["narrative"]
    return NarrativeOut(
        fields=[
            NarrativeFieldOut(key=f.key, title=f.title, guidance=f.guidance, draft=drafts[f.key], saved=saved.get(f.key) or None)
            for f in NARRATIVE_FIELDS
        ]
    )


@router.put("/narrative", response_model=NarrativeOut)
def save_narrative(project_id: str, body: NarrativeIn, current_user: AuthUser = Depends(get_current_user)) -> NarrativeOut:
    unknown = set(body.values) - set(FIELD_KEYS)
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown narrative field(s): {sorted(unknown)}")
    with get_session() as session:
        record = get_record_or_404(session, project_id)
        project = record_to_project(record)
        saved = dict(project.artifacts.get(NARRATIVE_KEY) or {})
        for key, text in body.values.items():
            # Blank text means "use the draft", so it isn't stored.
            if text and text.strip():
                saved[key] = text.strip()
            else:
                saved.pop(key, None)
        project.set_extra(NARRATIVE_KEY, saved)
        save_project(
            session, record, project, current_user, "reporting.narrative",
            f"Updated documentation text: {', '.join(sorted(body.values))}",
        )
    return get_narrative(project_id, current_user)


@router.post("")
def complete_reporting(project_id: str, current_user: AuthUser = Depends(get_current_user)) -> dict:
    with get_session() as session:
        record = get_record_or_404(session, project_id)
        project = record_to_project(record)
        _build_report_data(project, session, current_user)  # raises 400 if not ready
        project.mark_step(StepName.REPORTING, StepStatus.COMPLETE)
        save_project(session, record, project, current_user, "reporting.complete")
    return {"status": "ok"}


@router.get("/excel")
def export_excel(project_id: str, current_user: AuthUser = Depends(get_current_user)) -> Response:
    with get_session() as session:
        record = get_record_or_404(session, project_id)
        project = record_to_project(record)
        data = _build_report_data(project, session, current_user)
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
        data = _build_report_data(project, session, current_user)
        log_audit(session, current_user, project_id, "reporting.export_pdf", "Downloaded PDF report")
        session.commit()
    content = build_pdf_report(data)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={_filename(project.name)}.pdf"},
    )


@router.get("/docx")
def export_docx(project_id: str, current_user: AuthUser = Depends(get_current_user)) -> Response:
    with get_session() as session:
        record = get_record_or_404(session, project_id)
        project = record_to_project(record)
        data = _build_report_data(project, session, current_user)
        log_audit(session, current_user, project_id, "reporting.export_docx", "Downloaded Word model development document")
        session.commit()
    content = build_docx_report(data)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename={_filename(project.name)}.docx"},
    )


@router.get("/scoring-code")
def export_scoring_code(project_id: str, lang: str = "python", current_user: AuthUser = Depends(get_current_user)) -> Response:
    with get_session() as session:
        record = get_record_or_404(session, project_id)
        project = record_to_project(record)
        data = _build_report_data(project, session, current_user)
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
