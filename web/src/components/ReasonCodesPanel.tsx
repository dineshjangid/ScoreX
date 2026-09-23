import { useState } from "react";
import { API_BASE, api } from "../api";
import type { ProjectDetail, ReasonCodesArtifact } from "../api";

interface Props {
  project: ProjectDetail;
  onSaved: (project: ProjectDetail) => void;
}

export default function ReasonCodesPanel({ project, onSaved }: Props) {
  const existing = project.artifacts.reason_codes;
  const [topN, setTopN] = useState(existing?.top_n ?? 3);
  const [result, setResult] = useState<ReasonCodesArtifact | null>(existing ?? null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const scalingReady = project.step_status["scaling"] === "complete";
  const isMlFinal = project.artifacts.final_model_selection?.source === "ml_benchmark";

  async function handleRun() {
    setBusy(true);
    setError(null);
    try {
      const r = await api.runReasonCodes(project.id, { top_n: topN, preview_rows: 20 });
      setResult(r);
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

  const reasonColumns = result ? Array.from({ length: result.top_n }, (_, i) => i + 1) : [];

  return (
    <div className="ingestion-panel">
      {isMlFinal && (
        <p className="muted">
          Final model is an ML model — reason values are SHAP contributions to the predicted risk (higher = pushes
          the score down more), not points.
        </p>
      )}
      <label>
        Number of reasons per record
        <input type="number" min="1" max="10" value={topN} onChange={(e) => setTopN(parseInt(e.target.value, 10))} />
      </label>

      {error && <p className="error">{error}</p>}

      <div className="button-row">
        <button type="button" onClick={handleRun} disabled={busy}>
          Generate reason codes
        </button>
        {result && (
          <a
            className="button-like"
            href={`${API_BASE}/projects/${project.id}/reason_codes/export?top_n=${result.top_n}`}
            target="_blank"
            rel="noreferrer"
          >
            Download full CSV export
          </a>
        )}
      </div>

      {result && (
        <>
          <p className="muted">Scored {result.n_scored} rows. Preview:</p>
          <table className="profile-table">
            <thead>
              <tr>
                <th>Row</th>
                <th>Score</th>
                {reasonColumns.map((i) => (
                  <th key={i}>Reason {i}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {result.preview.map((row) => (
                <tr key={row.row_index as number}>
                  <td>{row.row_index as number}</td>
                  <td>{row.score as number}</td>
                  {reasonColumns.map((i) => (
                    <td key={i}>
                      {(row[`reason_${i}`] as string) ?? "—"} ({row[`reason_${i}_points`] as number})
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}
