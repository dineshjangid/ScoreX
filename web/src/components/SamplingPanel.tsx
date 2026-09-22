import { useState } from "react";
import { api } from "../api";
import type { ColumnProfile, ProjectDetail, SamplingSummary } from "../api";

interface Props {
  project: ProjectDetail;
  columns: ColumnProfile[];
  onSaved: (project: ProjectDetail) => void;
}

export default function SamplingPanel({ project, columns, onSaved }: Props) {
  const existing = project.artifacts.sampling?.config;
  const [testSize, setTestSize] = useState(existing?.test_size ?? 0.3);
  const [ootSize, setOotSize] = useState(existing?.oot_size ?? 0);
  const [dateColumn, setDateColumn] = useState(existing?.date_column ?? "");
  const [randomState, setRandomState] = useState(existing?.random_state ?? 42);
  const [summary, setSummary] = useState<SamplingSummary | null>(project.artifacts.sampling?.summary ?? null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const targetReady = project.step_status["target_definition"] === "complete";

  async function handleRun() {
    setBusy(true);
    setError(null);
    try {
      const result = await api.saveSampling(project.id, {
        test_size: testSize,
        oot_size: ootSize,
        date_column: dateColumn || null,
        random_state: randomState,
      });
      setSummary(result);
      onSaved(await api.getProject(project.id));
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  if (!targetReady) {
    return <p className="muted">Define and save the target first.</p>;
  }

  return (
    <div className="ingestion-panel">
      <label>
        Test size (fraction held out for testing)
        <input type="number" step="0.05" min="0" max="0.9" value={testSize} onChange={(e) => setTestSize(parseFloat(e.target.value))} />
      </label>
      <label>
        Out-of-time size (fraction, 0 to skip)
        <input type="number" step="0.05" min="0" max="0.9" value={ootSize} onChange={(e) => setOotSize(parseFloat(e.target.value))} />
      </label>
      <label>
        Date column for OOT split (optional — random split if omitted)
        <select value={dateColumn} onChange={(e) => setDateColumn(e.target.value)}>
          <option value="">— none (random) —</option>
          {columns.map((c) => (
            <option key={c.name} value={c.name}>
              {c.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        Random seed
        <input type="number" value={randomState} onChange={(e) => setRandomState(parseInt(e.target.value, 10))} />
      </label>

      {error && <p className="error">{error}</p>}

      <div className="button-row">
        <button type="button" onClick={handleRun} disabled={busy}>
          Run split
        </button>
      </div>

      {summary && (
        <table className="profile-table">
          <thead>
            <tr>
              <th>Sample</th>
              <th>N</th>
              <th>Good</th>
              <th>Bad</th>
              <th>Bad rate</th>
            </tr>
          </thead>
          <tbody>
            {(["train", "test", "oot", "excluded"] as const).map((key) => (
              <tr key={key}>
                <td>{key}</td>
                <td>{summary[key].n_total}</td>
                <td>{summary[key].n_good}</td>
                <td>{summary[key].n_bad}</td>
                <td>{summary[key].bad_rate_pct}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
