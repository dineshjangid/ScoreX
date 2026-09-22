import { useState } from "react";
import { api } from "../api";
import type { ModelArtifact, ProjectDetail } from "../api";

interface Props {
  project: ProjectDetail;
  onSaved: (project: ProjectDetail) => void;
}

export default function ModelingPanel({ project, onSaved }: Props) {
  const selected = project.artifacts.variable_selection?.selected ?? [];
  const [model, setModel] = useState<ModelArtifact | null>(project.artifacts.modeling ?? null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const selectionReady = project.step_status["variable_selection"] === "complete";

  async function handleRun() {
    setBusy(true);
    setError(null);
    try {
      const m = await api.runModeling(project.id, { variables: null });
      setModel(m);
      onSaved(await api.getProject(project.id));
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  if (!selectionReady) {
    return <p className="muted">Run variable selection first.</p>;
  }

  return (
    <div className="ingestion-panel">
      <p className="muted">Variables: {selected.join(", ") || "none selected"}</p>

      {error && <p className="error">{error}</p>}

      <div className="button-row">
        <button type="button" onClick={handleRun} disabled={busy || selected.length === 0}>
          Fit logistic regression
        </button>
      </div>

      {model && (
        <>
          <table className="profile-table">
            <tbody>
              <tr>
                <td>N observations</td>
                <td>{model.n_obs}</td>
              </tr>
              <tr>
                <td>Log-likelihood</td>
                <td>{model.log_likelihood}</td>
              </tr>
              <tr>
                <td>Pseudo R²</td>
                <td>{model.pseudo_r2}</td>
              </tr>
              <tr>
                <td>AIC</td>
                <td>{model.aic}</td>
              </tr>
            </tbody>
          </table>

          <table className="profile-table">
            <thead>
              <tr>
                <th>Variable</th>
                <th>Coefficient</th>
                <th>Std error</th>
                <th>z</th>
                <th>p-value</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>(intercept)</td>
                <td>{model.intercept}</td>
                <td colSpan={3}></td>
              </tr>
              {model.coefficients.map((c) => (
                <tr key={c.variable}>
                  <td>{c.variable}</td>
                  <td>{c.coefficient}</td>
                  <td>{c.std_error}</td>
                  <td>{c.z_value}</td>
                  <td className={c.p_value < 0.05 ? "" : "muted"}>{c.p_value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}
