import { useEffect, useState } from "react";
import { ML_ALGORITHM_LABELS, api } from "../api";
import type { FinalModelStatus, MLAlgorithm, ProjectDetail } from "../api";

interface Props {
  project: ProjectDetail;
  onSaved: (project: ProjectDetail) => void;
}

function algorithmLabel(algorithm: string): string {
  if (algorithm === "logistic") return "Logistic regression scorecard";
  return ML_ALGORITHM_LABELS[algorithm as MLAlgorithm] ?? algorithm;
}

export default function FinalModelPanel({ project, onSaved }: Props) {
  const [status, setStatus] = useState<FinalModelStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  const modelingReady = project.step_status["modeling"] === "complete";

  useEffect(() => {
    if (!modelingReady) return;
    setLoading(true);
    api
      .getFinalModelStatus(project.id)
      .then(setStatus)
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false));
  }, [project.id, modelingReady]);

  async function handleSelect(algorithm: string) {
    setBusy(true);
    setError(null);
    try {
      await api.setFinalModel(project.id, algorithm);
      const [refreshedProject, refreshedStatus] = await Promise.all([
        api.getProject(project.id),
        api.getFinalModelStatus(project.id),
      ]);
      onSaved(refreshedProject);
      setStatus(refreshedStatus);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  if (!modelingReady) {
    return <p className="muted">Fit a model first.</p>;
  }

  if (loading) {
    return <p className="muted">Loading model comparison…</p>;
  }

  const current = status?.current ?? null;
  const rows = Object.values(status?.candidates ?? {});
  // Show logistic first, then ML algorithms in a stable order.
  rows.sort((a, b) => (a.algorithm === "logistic" ? -1 : b.algorithm === "logistic" ? 1 : 0));

  return (
    <div className="ingestion-panel">
      <p className="muted">
        Compare the logistic regression scorecard against any ML benchmark models you've run, then pick one as the
        project's final model. Picking an ML model skips points-based scaling — validation, reason codes, and
        exports switch to that model's own predicted probability and SHAP contributions.
      </p>

      {error && <p className="error">{error}</p>}

      {current && (
        <p>
          Current final model: <strong>{algorithmLabel(current.algorithm)}</strong>
        </p>
      )}

      <table className="profile-table">
        <thead>
          <tr>
            <th>Model</th>
            <th>Train AUC</th>
            <th>Test AUC</th>
            <th>Train Gini</th>
            <th>Test Gini</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.algorithm}>
              <td>{algorithmLabel(r.algorithm)}</td>
              <td>{r.train_auc}</td>
              <td>{r.test_auc}</td>
              <td>{r.train_gini}</td>
              <td>{r.test_gini}</td>
              <td>
                {current?.algorithm === r.algorithm ? (
                  <span className="status-pill status-complete">final model</span>
                ) : (
                  <button type="button" onClick={() => handleSelect(r.algorithm)} disabled={busy}>
                    Set as final model
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {rows.length === 1 && (
        <p className="muted">
          Only the logistic scorecard is available so far. Run the ML benchmark in Model Building to compare more
          algorithms here.
        </p>
      )}
    </div>
  );
}
