import { useCallback, useEffect, useState } from "react";
import { API_BASE, api } from "../api";
import type { NarrativeField, ProjectDetail } from "../api";

interface Props {
  project: ProjectDetail;
  onSaved: (project: ProjectDetail) => void;
}

export default function ReportingPanel({ project, onSaved }: Props) {
  const [fields, setFields] = useState<NarrativeField[]>([]);
  const [values, setValues] = useState<Record<string, string>>({});
  const [savedValues, setSavedValues] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<Date | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const scalingReady = project.step_status["scaling"] === "complete";
  const base = `${API_BASE}/projects/${project.id}/reporting`;
  const finalModel = project.artifacts.final_model_selection;
  const isMlFinal = finalModel?.source === "ml_benchmark";

  const applyNarrative = useCallback((next: NarrativeField[]) => {
    const text = Object.fromEntries(next.map((f) => [f.key, f.saved ?? f.draft]));
    setFields(next);
    setValues(text);
    setSavedValues(text);
  }, []);

  useEffect(() => {
    if (!scalingReady) return;
    api
      .getNarrative(project.id)
      .then((n) => applyNarrative(n.fields))
      .catch((e) => setError(String(e)));
  }, [project.id, scalingReady, applyNarrative]);

  const dirty = fields.some((f) => values[f.key] !== savedValues[f.key]);

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      // Text left identical to the draft is sent blank, so the field keeps
      // following the draft as the project's numbers change.
      const payload = Object.fromEntries(fields.map((f) => [f.key, values[f.key].trim() === f.draft.trim() ? "" : values[f.key]]));
      const result = await api.saveNarrative(project.id, payload);
      applyNarrative(result.fields);
      setSavedAt(new Date());
    } catch (err) {
      setError(String(err));
    } finally {
      setSaving(false);
    }
  }

  async function handleComplete() {
    setBusy(true);
    setError(null);
    try {
      await api.completeReporting(project.id);
      onSaved(await api.getProject(project.id));
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  if (!scalingReady) {
    return <p className="muted">Build the scorecard first.</p>;
  }

  return (
    <div className="tuning-panel">
      <section className="doc-intro">
        <div>
          <h2>Model development document</h2>
          <p className="muted">
            Generated from every step of this project: data, target, sampling, characteristic analysis, selection, model estimates
            and alternatives considered, scorecard, train/test/OOT validation with charts, reason codes, versions, the audit trail
            and a sign-off block. Add the commentary below, then download.
          </p>
        </div>
        <div className="doc-downloads">
          <a
            className={`button-like primary-link ${dirty ? "disabled-link" : ""}`}
            href={`${base}/docx`}
            aria-disabled={dirty}
            onClick={(e) => dirty && e.preventDefault()}
            title={dirty ? "Save your text first" : "Editable Word document"}
          >
            Word document (.docx)
          </a>
          <a
            className={`button-like ${dirty ? "disabled-link" : ""}`}
            href={`${base}/pdf`}
            aria-disabled={dirty}
            onClick={(e) => dirty && e.preventDefault()}
            title={dirty ? "Save your text first" : "Fixed copy for archiving"}
          >
            PDF
          </a>
        </div>
      </section>

      {error && <p className="error">{error}</p>}

      <section className="card tuning-card">
        <div className="tuning-card-header">
          <h2>Commentary</h2>
          <span className="muted">
            Each section starts as a draft written from the project's numbers. Replace the [bracketed] prompts with your own
            judgement.
          </span>
        </div>
        <div className="narrative-list">
          {fields.map((f) => {
            const edited = values[f.key].trim() !== f.draft.trim();
            return (
              <div key={f.key} className="narrative-field">
                <div className="narrative-field-header">
                  <label htmlFor={`narrative-${f.key}`} className="field-label">
                    {f.title}
                  </label>
                  <span className={`badge ${edited ? "active-badge" : "draft-badge"}`}>{edited ? "Edited" : "Draft"}</span>
                  {edited && (
                    <button type="button" className="link-button" onClick={() => setValues((v) => ({ ...v, [f.key]: f.draft }))}>
                      Reset to draft
                    </button>
                  )}
                </div>
                <p className="muted small-note">{f.guidance}</p>
                <textarea
                  id={`narrative-${f.key}`}
                  value={values[f.key]}
                  rows={Math.min(8, Math.max(3, Math.ceil(values[f.key].length / 95)))}
                  onChange={(e) => setValues((v) => ({ ...v, [f.key]: e.target.value }))}
                />
              </div>
            );
          })}
        </div>
        <div className="tuning-controls">
          <button type="button" className="primary" onClick={handleSave} disabled={saving || !dirty}>
            {saving ? "Saving…" : "Save commentary"}
          </button>
          <span className="muted small-note">
            {dirty ? "Unsaved changes — downloads use the last saved text." : savedAt ? `Saved ${savedAt.toLocaleTimeString()}` : ""}
          </span>
        </div>
      </section>

      <section className="card tuning-card">
        <div className="tuning-card-header">
          <h2>Deployment files</h2>
        </div>
        <div className="button-row">
          <a className="button-like" href={`${base}/excel`}>
            Excel data workbook
          </a>
          <a className="button-like" href={`${base}/scoring-code?lang=python`}>
            Python scoring code
          </a>
          {isMlFinal ? (
            <a className="button-like" href={`${base}/model-file`}>
              Model file
            </a>
          ) : (
            <a className="button-like" href={`${base}/scoring-code?lang=sql`}>
              SQL scoring code
            </a>
          )}
        </div>
        {isMlFinal && (
          <p className="muted small-note">
            Final model is {finalModel?.algorithm} — there's no SQL export for tree ensembles. Use the Python scoring code with the
            model file.
          </p>
        )}
      </section>

      <div className="button-row">
        <button type="button" onClick={handleComplete} disabled={busy}>
          Mark documentation complete
        </button>
      </div>
    </div>
  );
}
