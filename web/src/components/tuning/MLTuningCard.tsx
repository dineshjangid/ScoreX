import { useState } from "react";
import { HYPERPARAM_SUPPORT, ML_ALGORITHM_LABELS, api } from "../../api";
import type { MLAlgorithm, MLBenchmarkAllResult, MLHyperparams, OptionalHyperparam, ProjectDetail } from "../../api";
import HelpIcon from "../HelpIcon";
import SampleMetricsTable from "./SampleMetricsTable";

interface Props {
  project: ProjectDetail;
  onFitted: (result: MLBenchmarkAllResult) => void;
}

const ALGORITHMS: MLAlgorithm[] = ["xgboost", "random_forest", "lightgbm", "catboost"];

const DEFAULTS: MLHyperparams = {
  n_estimators: 100,
  max_depth: 3,
  learning_rate: null,
  subsample: null,
  min_samples_leaf: null,
  l2_reg: null,
};

const OPTIONAL: { key: OptionalHyperparam; label: string; help: string; step: number; min: number; max?: number }[] = [
  { key: "learning_rate", label: "Learning rate", help: "Lower values learn more slowly and usually generalise better; pair with more trees.", step: 0.01, min: 0.001, max: 1 },
  { key: "subsample", label: "Subsample", help: "Share of rows each tree sees (0–1). Below 1 adds randomness that reduces overfitting.", step: 0.05, min: 0.1, max: 1 },
  { key: "min_samples_leaf", label: "Min samples per leaf", help: "Leaves must hold at least this many rows — larger values stop trees memorising small groups.", step: 5, min: 1 },
  { key: "l2_reg", label: "L2 regularisation", help: "Penalty on leaf weights; higher values shrink predictions and reduce overfitting.", step: 0.5, min: 0 },
];

export default function MLTuningCard({ project, onFitted }: Props) {
  const results = project.artifacts.ml_benchmark?.results ?? {};
  const [algorithm, setAlgorithm] = useState<MLAlgorithm | "all">("xgboost");
  const [params, setParams] = useState<MLHyperparams>(DEFAULTS);
  const [viewAlgorithm, setViewAlgorithm] = useState<string | null>(Object.keys(results)[0] ?? null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const supported = new Set<OptionalHyperparam>(
    algorithm === "all" ? OPTIONAL.map((o) => o.key) : HYPERPARAM_SUPPORT[algorithm]
  );

  function setParam<K extends keyof MLHyperparams>(key: K, raw: string) {
    // Blank means "default": the fixed default for trees/depth, the library's own for the rest.
    setParams((p) => ({ ...p, [key]: raw === "" ? DEFAULTS[key] : Number(raw) }));
  }

  async function handleFit() {
    setBusy(true);
    setError(null);
    try {
      const result = await api.runMlBenchmark(project.id, { variables: null, algorithm, ...params });
      setViewAlgorithm(algorithm === "all" ? "xgboost" : algorithm);
      onFitted(result);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  const viewed = viewAlgorithm ? results[viewAlgorithm] : undefined;
  const resultKeys = Object.keys(results);

  return (
    <section className="card tuning-card">
      <div className="tuning-card-header">
        <h2>ML models</h2>
        <span className="muted">Tree ensembles on the raw (non-WOE) selected variables</span>
      </div>

      <div className="tuning-controls">
        <label className="field">
          <span className="field-label">Algorithm</span>
          <select value={algorithm} onChange={(e) => setAlgorithm(e.target.value as MLAlgorithm | "all")}>
            {ALGORITHMS.map((a) => (
              <option key={a} value={a}>
                {ML_ALGORITHM_LABELS[a]}
              </option>
            ))}
            <option value="all">All four</option>
          </select>
        </label>
        <label className="field">
          <span className="field-label">Trees</span>
          <input
            type="number"
            min={1}
            max={5000}
            step={50}
            value={params.n_estimators}
            onChange={(e) => setParam("n_estimators", e.target.value)}
            className="narrow-input"
          />
        </label>
        <label className="field">
          <span className="field-label">
            Max depth <HelpIcon text="Deeper trees capture more interactions but overfit faster. 2–4 is typical for credit data." />
          </span>
          <input
            type="number"
            min={1}
            max={16}
            value={params.max_depth}
            onChange={(e) => setParam("max_depth", e.target.value)}
            className="narrow-input"
          />
        </label>
        {OPTIONAL.map((o) => {
          const enabled = supported.has(o.key);
          return (
            <label key={o.key} className={`field ${enabled ? "" : "field-disabled"}`}>
              <span className="field-label">
                {o.label} <HelpIcon text={enabled ? o.help : `${o.help} Not used by ${ML_ALGORITHM_LABELS[algorithm as MLAlgorithm]}.`} />
              </span>
              <input
                type="number"
                min={o.min}
                max={o.max}
                step={o.step}
                value={params[o.key] ?? ""}
                placeholder={enabled ? "default" : "n/a"}
                disabled={!enabled}
                onChange={(e) => setParam(o.key, e.target.value)}
                className="narrow-input"
              />
            </label>
          );
        })}
        <button type="button" className="primary" onClick={handleFit} disabled={busy}>
          {busy ? "Fitting…" : algorithm === "all" ? "Fit 4 candidates" : "Fit candidate"}
        </button>
      </div>
      {algorithm === "all" && <p className="muted small-note">Settings an algorithm doesn't have are ignored for it.</p>}
      {error && <p className="error">{error}</p>}

      {resultKeys.length > 0 && (
        <div className="fit-result">
          <div className="section-header">
            <p className="fit-result-title">Active result per algorithm</p>
            <div className="view-toggle" role="group" aria-label="Algorithm">
              {resultKeys.map((k) => (
                <button
                  key={k}
                  type="button"
                  className={viewAlgorithm === k ? "selected" : ""}
                  aria-pressed={viewAlgorithm === k}
                  onClick={() => setViewAlgorithm(k)}
                >
                  {ML_ALGORITHM_LABELS[k as MLAlgorithm] ?? k}
                </button>
              ))}
            </div>
          </div>
          {viewed && (
            <>
              {viewed.sample_metrics ? (
                <SampleMetricsTable metrics={viewed.sample_metrics} />
              ) : (
                <p className="muted">
                  Train Gini {viewed.train_gini} · Test Gini {viewed.test_gini} — fitted before OOT metrics were tracked.
                </p>
              )}
              <p className="muted">Feature importance (mean |SHAP|)</p>
              <table className="profile-table compact-table">
                <tbody>
                  {viewed.feature_importance.map((f) => (
                    <tr key={f.variable}>
                      <td>{f.variable}</td>
                      <td className="num">{f.mean_abs_shap}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </div>
      )}
    </section>
  );
}
