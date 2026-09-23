import { useState } from "react";
import { API_BASE, api } from "../api";
import type { ProjectDetail } from "../api";

interface Props {
  project: ProjectDetail;
  onSaved: (project: ProjectDetail) => void;
}

export default function ReportingPanel({ project, onSaved }: Props) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const scalingReady = project.step_status["scaling"] === "complete";
  const base = `${API_BASE}/projects/${project.id}/reporting`;
  const finalModel = project.artifacts.final_model_selection;
  const isMlFinal = finalModel?.source === "ml_benchmark";

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
    <div className="ingestion-panel">
      <p className="muted">Export the finished scorecard build for documentation and deployment.</p>

      {error && <p className="error">{error}</p>}

      <div className="button-row">
        <a className="button-like" href={`${base}/excel`} target="_blank" rel="noreferrer">
          Excel report
        </a>
        <a className="button-like" href={`${base}/pdf`} target="_blank" rel="noreferrer">
          PDF report
        </a>
        <a className="button-like" href={`${base}/scoring-code?lang=python`} target="_blank" rel="noreferrer">
          Python scoring code
        </a>
        {isMlFinal ? (
          <a className="button-like" href={`${base}/model-file`} target="_blank" rel="noreferrer">
            Download model file
          </a>
        ) : (
          <a className="button-like" href={`${base}/scoring-code?lang=sql`} target="_blank" rel="noreferrer">
            SQL scoring code
          </a>
        )}
      </div>

      {isMlFinal && (
        <p className="muted">
          Final model is {finalModel?.algorithm} — there's no SQL export for ML models (tree ensembles don't
          translate to SQL). Use the Python scoring code together with the downloaded model file.
        </p>
      )}

      <div className="button-row">
        <button type="button" onClick={handleComplete} disabled={busy}>
          Mark reporting complete
        </button>
      </div>
    </div>
  );
}
