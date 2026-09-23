import { useState } from "react";
import { api, ML_ALGORITHM_LABELS } from "../api";
import type { MLAlgorithm, MLBenchmarkResult, ModelArtifact, ProjectDetail } from "../api";

interface Props {
  project: ProjectDetail;
  onSaved: (project: ProjectDetail) => void;
}

const ALGORITHM_OPTIONS: { value: MLAlgorithm | "all"; label: string }[] = [
  { value: "xgboost", label: "XGBoost" },
  { value: "random_forest", label: "Random Forest" },
  { value: "lightgbm", label: "LightGBM" },
  { value: "catboost", label: "CatBoost" },
  { value: "all", label: "Compare all four" },
];

export default function ModelingPanel({ project, onSaved }: Props) {
  const selected = project.artifacts.variable_selection?.selected ?? [];
  const [model, setModel] = useState<ModelArtifact | null>(project.artifacts.modeling ?? null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [results, setResults] = useState<Record<string, MLBenchmarkResult>>(project.artifacts.ml_benchmark?.results ?? {});
  const [algorithm, setAlgorithm] = useState<MLAlgorithm | "all">("xgboost");
  const [viewAlgorithm, setViewAlgorithm] = useState<string | null>(Object.keys(results)[0] ?? null);
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
      const result = await api.runMlBenchmark(project.id, { variables: null, n_estimators: 100, max_depth: 3, algorithm });
      setResults(result.results);
      setViewAlgorithm(algorithm === "all" ? Object.keys(result.results)[0] ?? null : algorithm);
      onSaved(await api.getProject(project.id));
    } catch (err) {
      setBenchmarkError(String(err));
    } finally {
      setBenchmarkBusy(false);
    }
  }

  const resultRows = Object.values(results);
  const viewedResult = viewAlgorithm ? results[viewAlgorithm] : undefined;

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
            <strong>ML benchmark</strong> — compare against tree-ensemble challenger models (XGBoost, Random Forest,
            LightGBM, CatBoost) on the same (raw, non-WOE) variables, with SHAP feature importance. Purely a
            comparison; it isn't part of the deployed scorecard.
          </p>

          {benchmarkError && <p className="error">{benchmarkError}</p>}

          <div className="button-row">
            <label>
              Algorithm
              <select value={algorithm} onChange={(e) => setAlgorithm(e.target.value as MLAlgorithm | "all")}>
                {ALGORITHM_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </label>
            <button type="button" onClick={handleRunBenchmark} disabled={benchmarkBusy}>
              Run ML benchmark
            </button>
          </div>

          {resultRows.length > 0 && (
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
                  {resultRows.map((r) => (
                    <tr key={r.algorithm}>
                      <td>{ML_ALGORITHM_LABELS[r.algorithm as MLAlgorithm] ?? r.algorithm}</td>
                      <td>{r.train_auc}</td>
                      <td>{r.test_auc}</td>
                      <td>{r.train_gini}</td>
                      <td>{r.test_gini}</td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <label>
                Feature importance for
                <select value={viewAlgorithm ?? ""} onChange={(e) => setViewAlgorithm(e.target.value)}>
                  {resultRows.map((r) => (
                    <option key={r.algorithm} value={r.algorithm}>
                      {ML_ALGORITHM_LABELS[r.algorithm as MLAlgorithm] ?? r.algorithm}
                    </option>
                  ))}
                </select>
              </label>

              {viewedResult && (
                <table className="profile-table">
                  <thead>
                    <tr>
                      <th>Variable</th>
                      <th>Mean |SHAP|</th>
                    </tr>
                  </thead>
                  <tbody>
                    {viewedResult.feature_importance.map((f) => (
                      <tr key={f.variable}>
                        <td>{f.variable}</td>
                        <td>{f.mean_abs_shap}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
