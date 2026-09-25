import { useState } from "react";
import { api } from "../../api";
import type { ModelArtifact, Penalty, ProjectDetail } from "../../api";
import HelpIcon from "../HelpIcon";
import SampleMetricsTable from "./SampleMetricsTable";

interface Props {
  project: ProjectDetail;
  onFitted: (model: ModelArtifact) => void;
}

const PENALTIES: { value: Penalty; label: string }[] = [
  { value: "none", label: "None" },
  { value: "l1", label: "L1 (lasso)" },
  { value: "l2", label: "L2 (ridge)" },
];

const ALPHA_PRESETS = [0.001, 0.005, 0.01, 0.02, 0.05];

export default function LogisticTuningCard({ project, onFitted }: Props) {
  const binning = project.artifacts.binning?.variables ?? {};
  const selection = project.artifacts.variable_selection;
  const active = project.artifacts.modeling ?? null;

  const [checked, setChecked] = useState<Set<string>>(new Set(active?.variables ?? selection?.selected ?? []));
  const [penalty, setPenalty] = useState<Penalty>(active?.penalty ?? "none");
  const [alpha, setAlpha] = useState<number>(active?.alpha || 0.01);
  const [lastFit, setLastFit] = useState<ModelArtifact | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // The fit whose coefficients are shown: the one just run, else the active model.
  const shown = lastFit ?? active;
  const coefficients = new Map(shown?.coefficients.map((c) => [c.variable, c]) ?? []);
  const droppedBySelection = new Map(selection?.dropped.map((d) => [d.variable, d.reason]) ?? []);
  const variables = Object.values(binning).sort((a, b) => b.iv - a.iv);

  function toggle(variable: string) {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(variable)) next.delete(variable);
      else next.add(variable);
      return next;
    });
  }

  async function handleFit() {
    setBusy(true);
    setError(null);
    try {
      // Keep the IV ordering shown in the table.
      const chosen = variables.map((v) => v.variable).filter((v) => checked.has(v));
      const model = await api.runModeling(project.id, { variables: chosen, penalty, alpha: penalty === "none" ? 0 : alpha });
      setLastFit(model);
      onFitted(model);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  const wrongSign = shown?.coefficients.filter((c) => c.coefficient > 0) ?? [];

  return (
    <section className="card tuning-card">
      <div className="tuning-card-header">
        <h2>Logistic scorecard</h2>
        <span className="muted">{checked.size} of {variables.length} variables</span>
      </div>

      <div className="table-scroll">
        <table className="profile-table compact-table">
          <thead>
            <tr>
              <th className="col-check">
                <span className="visually-hidden">Include</span>
              </th>
              <th>Variable</th>
              <th className="num">IV</th>
              <th className="num">Coefficient</th>
              <th className="num">p-value</th>
              <th>
                Check{" "}
                <HelpIcon text="WOE here is ln(%good/%bad), so a variable should get a negative coefficient when predicting P(bad). A positive one usually means collinearity or overfitting — consider dropping it." />
              </th>
            </tr>
          </thead>
          <tbody>
            {variables.map((v) => {
              const c = coefficients.get(v.variable);
              const inShown = shown?.variables.includes(v.variable);
              const droppedByPenalty = shown?.dropped_variables?.includes(v.variable);
              return (
                <tr key={v.variable} className={checked.has(v.variable) ? "" : "unchecked-row"}>
                  <td className="col-check">
                    <input
                      type="checkbox"
                      checked={checked.has(v.variable)}
                      onChange={() => toggle(v.variable)}
                      aria-label={`Include ${v.variable}`}
                    />
                  </td>
                  <td>
                    {v.variable}
                    {droppedBySelection.has(v.variable) && (
                      <span className="muted small-note" title={droppedBySelection.get(v.variable)}>
                        {" "}
                        · dropped in selection
                      </span>
                    )}
                  </td>
                  <td className="num">{v.iv.toFixed(3)}</td>
                  <td className="num">{c ? c.coefficient.toFixed(4) : <span className="muted">—</span>}</td>
                  <td className="num">
                    {c?.p_value != null ? (
                      <span className={c.p_value < 0.05 ? "" : "muted"}>{c.p_value.toFixed(4)}</span>
                    ) : (
                      <span className="muted">{c ? "n/a" : "—"}</span>
                    )}
                  </td>
                  <td>
                    {droppedByPenalty ? (
                      <span className="status-flag muted">Zeroed by L1</span>
                    ) : !inShown || !c ? null : c.coefficient > 0 ? (
                      <span className="status-flag warning">⚠ Wrong sign</span>
                    ) : c.p_value != null && c.p_value >= 0.05 ? (
                      <span className="status-flag warning">⚠ Not significant</span>
                    ) : (
                      <span className="status-flag ok">✓</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="tuning-controls">
        <div className="field">
          <span className="field-label">
            Penalty{" "}
            <HelpIcon text="Shrinks coefficients to reduce overfitting. L1 can drop weak variables entirely; L2 shrinks all of them. Penalised fits have no p-values." />
          </span>
          <div className="view-toggle" role="group" aria-label="Penalty">
            {PENALTIES.map((p) => (
              <button
                key={p.value}
                type="button"
                className={penalty === p.value ? "selected" : ""}
                aria-pressed={penalty === p.value}
                onClick={() => setPenalty(p.value)}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>
        {penalty !== "none" && (
          <label className="field">
            <span className="field-label">Strength (α)</span>
            <input
              type="number"
              min={0}
              step={0.001}
              value={alpha}
              list="alpha-presets"
              onChange={(e) => setAlpha(Number(e.target.value))}
              className="narrow-input"
            />
            <datalist id="alpha-presets">
              {ALPHA_PRESETS.map((a) => (
                <option key={a} value={a} />
              ))}
            </datalist>
          </label>
        )}
        <button type="button" className="primary" onClick={handleFit} disabled={busy || checked.size === 0 || (penalty !== "none" && !(alpha > 0))}>
          {busy ? "Fitting…" : "Fit candidate"}
        </button>
      </div>

      {error && <p className="error">{error}</p>}

      {shown && (
        <div className="fit-result">
          <p className="fit-result-title">
            {lastFit
              ? lastFit.candidate_id === active?.candidate_id
                ? "New fit — now the active logistic model"
                : "New fit — saved as a candidate (not active)"
              : "Active logistic model"}
            <span className="muted">
              {" "}
              · Pseudo R² {shown.pseudo_r2} · AIC {shown.aic}
              {shown.penalty && shown.penalty !== "none" ? ` · ${shown.penalty.toUpperCase()} α=${shown.alpha}` : ""}
            </span>
          </p>
          {shown.sample_metrics ? (
            <SampleMetricsTable metrics={shown.sample_metrics} />
          ) : (
            <p className="muted">Fitted before per-sample metrics were tracked — refit to see Train/Test/OOT here.</p>
          )}
          {wrongSign.length > 0 && (
            <p className="notice">
              ⚠ {wrongSign.map((c) => c.variable).join(", ")} {wrongSign.length === 1 ? "has" : "have"} a positive coefficient — the
              opposite of what its WOE implies.
            </p>
          )}
          {shown.dropped_variables && shown.dropped_variables.length > 0 && (
            <p className="muted">L1 dropped: {shown.dropped_variables.join(", ")}</p>
          )}
        </div>
      )}
    </section>
  );
}
