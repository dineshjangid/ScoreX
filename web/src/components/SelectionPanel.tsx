import { useState } from "react";
import { api } from "../api";
import type { ProjectDetail, SelectionResult } from "../api";

interface Props {
  project: ProjectDetail;
  onSaved: (project: ProjectDetail) => void;
}

export default function SelectionPanel({ project, onSaved }: Props) {
  const existing = project.artifacts.variable_selection;
  const [minIv, setMinIv] = useState(existing?.config.min_iv ?? 0.02);
  const [maxCorr, setMaxCorr] = useState(existing?.config.max_corr ?? 0.7);
  const [maxVif, setMaxVif] = useState(existing?.config.max_vif ?? 5.0);
  const [result, setResult] = useState<SelectionResult | null>(existing ?? null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const binningReady = project.step_status["binning"] === "complete";

  async function handleRun() {
    setBusy(true);
    setError(null);
    try {
      const r = await api.runSelection(project.id, { min_iv: minIv, max_corr: maxCorr, max_vif: maxVif });
      setResult(r);
      onSaved(await api.getProject(project.id));
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  if (!binningReady) {
    return <p className="muted">Run binning first.</p>;
  }

  return (
    <div className="ingestion-panel">
      <label>
        Minimum IV
        <input type="number" step="0.01" min="0" value={minIv} onChange={(e) => setMinIv(parseFloat(e.target.value))} />
      </label>
      <label>
        Max pairwise correlation
        <input type="number" step="0.05" min="0" max="1" value={maxCorr} onChange={(e) => setMaxCorr(parseFloat(e.target.value))} />
      </label>
      <label>
        Max VIF
        <input type="number" step="0.5" min="1" value={maxVif} onChange={(e) => setMaxVif(parseFloat(e.target.value))} />
      </label>

      {error && <p className="error">{error}</p>}

      <div className="button-row">
        <button type="button" onClick={handleRun} disabled={busy}>
          Run selection
        </button>
      </div>

      {result && (
        <>
          <p className="muted">Selected: {result.selected.join(", ") || "none"}</p>

          {result.dropped.length > 0 && (
            <table className="profile-table">
              <thead>
                <tr>
                  <th>Dropped variable</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>
                {result.dropped.map((d) => (
                  <tr key={d.variable}>
                    <td>{d.variable}</td>
                    <td className="muted">{d.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {result.selected.length > 0 && (
            <table className="profile-table">
              <thead>
                <tr>
                  <th>Variable</th>
                  <th>VIF</th>
                </tr>
              </thead>
              <tbody>
                {result.selected.map((v) => (
                  <tr key={v}>
                    <td>{v}</td>
                    <td>{result.vif[v]?.toFixed(3) ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </div>
  );
}
