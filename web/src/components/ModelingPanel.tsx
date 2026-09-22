import { useState } from "react";
import { api } from "../api";
import type { MLBenchmarkResult, ModelArtifact, ProjectDetail } from "../api";

interface Props {
  project: ProjectDetail;
  onSaved: (project: ProjectDetail) => void;
}

export default function ModelingPanel({ project, onSaved }: Props) {
  const selected = project.artifacts.variable_selection?.selected ?? [];
  const [model, setModel] = useState<ModelArtifact | null>(project.artifacts.modeling ?? null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [benchmark, setBenchmark] = useState<MLBenchmarkResult | null>(project.artifacts.ml_benchmark ?? null);
  const [benchmarkError, setBenchmarkError] = useState<string | null>(null);
  const [benchmarkBusy, setBenchmarkBusy] = useState(false);

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

  async function handleRunBenchmark() {
    setBenchmarkBusy(true);
    setBenchmarkError(null);
    try {
      const result = await api.runMlBenchmark(project.id, { variables: null, n_estimators: 100, max_depth: 3 });
      setBenchmark(result);
      onSaved(await api.getProject(project.id));
    } catch (err) {
      setBenchmarkError(String(err));
    } finally {
      setBenchmarkBusy(false);
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

          <hr />
          <p className="muted">
            <strong>ML benchmark</strong> — compare against an XGBoost model on the same (raw, non-WOE) variables,
            with SHAP feature importance. Purely a comparison; it isn't part of the deployed scorecard.
          </p>

          {benchmarkError && <p className="error">{benchmarkError}</p>}

          <div className="button-row">
            <button type="button" onClick={handleRunBenchmark} disabled={benchmarkBusy}>
              Run ML benchmark
            </button>
          </div>

          {benchmark && (
            <>
              <table className="profile-table">
                <thead>
                  <tr>
                    <th>Model</th>
                    <th>Train AUC</th>
                    <th>Test AUC</th>
                    <th>Train Gini</th>
                    <th>Test Gini</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Logistic scorecard</td>
                    <td colSpan={4} className="muted">
                      see Validation step
                    </td>
                  </tr>
                  <tr>
                    <td>XGBoost benchmark</td>
                    <td>{benchmark.train_auc}</td>
                    <td>{benchmark.test_auc}</td>
                    <td>{benchmark.train_gini}</td>
                    <td>{benchmark.test_gini}</td>
                  </tr>
                </tbody>
              </table>

              <table className="profile-table">
                <thead>
                  <tr>
                    <th>Variable</th>
                    <th>Mean |SHAP|</th>
                  </tr>
                </thead>
                <tbody>
                  {benchmark.feature_importance.map((f) => (
                    <tr key={f.variable}>
                      <td>{f.variable}</td>
                      <td>{f.mean_abs_shap}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </>
      )}
    </div>
  );
}
