import { Fragment, useState } from "react";
import { api } from "../api";
import type { BinningSummaryItem, ProjectDetail } from "../api";
import BarChart from "./BarChart";
import BinEditor from "./BinEditor";

interface Props {
  project: ProjectDetail;
  onSaved: (project: ProjectDetail) => void;
}

function ivStrength(iv: number): string {
  if (iv < 0.02) return "unpredictive";
  if (iv < 0.1) return "weak";
  if (iv < 0.3) return "medium";
  if (iv < 0.5) return "strong";
  return "suspicious";
}

export default function BinningPanel({ project, onSaved }: Props) {
  const existing = project.artifacts.binning;
  const [maxBins, setMaxBins] = useState(existing?.config.max_bins ?? 10);
  const [minBinSize, setMinBinSize] = useState(existing?.config.min_bin_size ?? 0.05);
  const [results, setResults] = useState<BinningSummaryItem[] | null>(
    existing ? Object.values(existing.variables).map((v) => ({ variable: v.variable, kind: v.kind, iv: v.iv, n_bins: v.bins.length })).sort((a, b) => b.iv - a.iv) : null
  );
  const [expanded, setExpanded] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const samplingReady = project.step_status["sampling"] === "complete";

  async function handleRun() {
    setBusy(true);
    setError(null);
    try {
      const result = await api.runBinning(project.id, { max_bins: maxBins, min_bin_size: minBinSize, variables: null });
      setResults(result);
      onSaved(await api.getProject(project.id));
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleEditSaved(result: BinningSummaryItem) {
    setResults((prev) => (prev ? prev.map((r) => (r.variable === result.variable ? result : r)).sort((a, b) => b.iv - a.iv) : prev));
    setEditing(null);
    setExpanded(result.variable);
    onSaved(await api.getProject(project.id));
  }

  if (!samplingReady) {
    return <p className="muted">Run sampling first.</p>;
  }

  return (
    <div className="ingestion-panel">
      <label>
        Max bins per variable
        <input type="number" min="2" max="20" value={maxBins} onChange={(e) => setMaxBins(parseInt(e.target.value, 10))} />
      </label>
      <label>
        Min bin size (fraction of training sample)
        <input
          type="number"
          step="0.01"
          min="0.01"
          max="0.3"
          value={minBinSize}
          onChange={(e) => setMinBinSize(parseFloat(e.target.value))}
        />
      </label>

      {error && <p className="error">{error}</p>}

      <div className="button-row">
        <button type="button" onClick={handleRun} disabled={busy}>
          Run binning
        </button>
      </div>

      {results && results.length > 0 && (
        <>
          <p className="muted">IV ranking</p>
          <BarChart
            data={results.map((r) => ({ label: r.variable, value: r.iv }))}
            positiveColor="var(--accent)"
            negativeColor="var(--accent)"
            formatValue={(v) => v.toFixed(4)}
          />
        </>
      )}

      {results && (
        <table className="profile-table">
          <thead>
            <tr>
              <th>Variable</th>
              <th>Type</th>
              <th>Bins</th>
              <th>IV</th>
              <th>Strength</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {results.map((r) => {
              const detail = project.artifacts.binning?.variables[r.variable];
              const isExpanded = expanded === r.variable;
              const isEditing = editing === r.variable;
              return (
                <Fragment key={r.variable}>
                  <tr>
                    <td>{r.variable}</td>
                    <td>{r.kind}</td>
                    <td>{r.n_bins}</td>
                    <td>{r.iv.toFixed(4)}</td>
                    <td>{ivStrength(r.iv)}</td>
                    <td className="button-row">
                      {detail && (
                        <>
                          <button
                            type="button"
                            onClick={() => {
                              setExpanded(isExpanded ? null : r.variable);
                              setEditing(null);
                            }}
                          >
                            {isExpanded ? "Hide" : "View bins"}
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              setEditing(isEditing ? null : r.variable);
                              setExpanded(null);
                            }}
                          >
                            {isEditing ? "Cancel edit" : "Edit bins"}
                          </button>
                        </>
                      )}
                    </td>
                  </tr>
                  {isExpanded && detail && (
                    <tr>
                      <td colSpan={6}>
                        <table className="profile-table">
                          <thead>
                            <tr>
                              <th>Bin</th>
                              <th>N</th>
                              <th>% of total</th>
                              <th>Bad rate</th>
                              <th>WOE</th>
                            </tr>
                          </thead>
                          <tbody>
                            {detail.bins.map((b) => (
                              <tr key={b.label}>
                                <td>{b.label}</td>
                                <td>{b.n_total}</td>
                                <td>{b.pct_of_total}%</td>
                                <td>{b.bad_rate_pct}%</td>
                                <td>{b.woe}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        <p className="muted">WOE per bin</p>
                        <BarChart data={detail.bins.map((b) => ({ label: b.label, value: b.woe }))} formatValue={(v) => v.toFixed(4)} />
                      </td>
                    </tr>
                  )}
                  {isEditing && detail && (
                    <tr>
                      <td colSpan={6}>
                        <BinEditor
                          projectId={project.id}
                          detail={detail}
                          onSaved={handleEditSaved}
                          onCancel={() => setEditing(null)}
                        />
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
