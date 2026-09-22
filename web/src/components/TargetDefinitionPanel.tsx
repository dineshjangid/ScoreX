import { useState } from "react";
import { api } from "../api";
import type { ColumnProfile, ProjectDetail, TargetMode, TargetSummary } from "../api";

interface Props {
  project: ProjectDetail;
  columns: ColumnProfile[];
  onSaved: (project: ProjectDetail) => void;
}

function ValuePicker({
  column,
  selected,
  onChange,
}: {
  column: ColumnProfile | undefined;
  selected: string[];
  onChange: (values: string[]) => void;
}) {
  if (column?.distinct_values) {
    return (
      <div className="checkbox-list">
        {column.distinct_values.map((v) => (
          <label key={v.value} className="checkbox-item">
            <input
              type="checkbox"
              checked={selected.includes(v.value)}
              onChange={(e) => {
                if (e.target.checked) onChange([...selected, v.value]);
                else onChange(selected.filter((s) => s !== v.value));
              }}
            />
            {v.value} <span className="muted">({v.count})</span>
          </label>
        ))}
      </div>
    );
  }
  return (
    <input
      type="text"
      placeholder="Comma-separated values"
      value={selected.join(",")}
      onChange={(e) => onChange(e.target.value.split(",").map((s) => s.trim()).filter(Boolean))}
    />
  );
}

export default function TargetDefinitionPanel({ project, columns, onSaved }: Props) {
  const existing = project.artifacts.target_definition?.definition;
  const [targetColumn, setTargetColumn] = useState(existing?.target_column ?? columns[0]?.name ?? "");
  const [mode, setMode] = useState<TargetMode>(existing?.mode ?? "values");
  const [badValues, setBadValues] = useState<string[]>(existing?.bad_values ?? []);
  const [threshold, setThreshold] = useState<string>(existing?.threshold?.toString() ?? "");
  const [excludeColumn, setExcludeColumn] = useState<string>(existing?.exclude_column ?? "");
  const [excludeValues, setExcludeValues] = useState<string[]>(existing?.exclude_values ?? []);
  const [summary, setSummary] = useState<TargetSummary | null>(project.artifacts.target_definition?.summary ?? null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const targetCol = columns.find((c) => c.name === targetColumn);
  const excludeCol = columns.find((c) => c.name === excludeColumn);

  function buildBody() {
    return {
      target_column: targetColumn,
      mode,
      bad_values: mode === "values" ? badValues : [],
      threshold: mode === "threshold" ? parseFloat(threshold) : null,
      exclude_values: excludeValues,
      exclude_column: excludeColumn || null,
    };
  }

  async function handlePreview() {
    setBusy(true);
    setError(null);
    try {
      setSummary(await api.previewTarget(project.id, buildBody()));
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleSave() {
    setBusy(true);
    setError(null);
    try {
      setSummary(await api.saveTarget(project.id, buildBody()));
      onSaved(await api.getProject(project.id));
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="ingestion-panel">
      <label>
        Target column
        <select value={targetColumn} onChange={(e) => setTargetColumn(e.target.value)}>
          {columns.map((c) => (
            <option key={c.name} value={c.name}>
              {c.name} ({c.kind})
            </option>
          ))}
        </select>
      </label>

      <label>
        Mode
        <select value={mode} onChange={(e) => setMode(e.target.value as TargetMode)}>
          <option value="values">Bad values (categorical / binary)</option>
          <option value="threshold">Threshold (bad if value &ge; threshold)</option>
        </select>
      </label>

      {mode === "values" ? (
        <div>
          <p className="muted">Select the value(s) that mean "bad":</p>
          <ValuePicker column={targetCol} selected={badValues} onChange={setBadValues} />
        </div>
      ) : (
        <label>
          Threshold
          <input type="number" value={threshold} onChange={(e) => setThreshold(e.target.value)} />
        </label>
      )}

      <label>
        Exclude/indeterminate column (optional)
        <select value={excludeColumn} onChange={(e) => setExcludeColumn(e.target.value)}>
          <option value="">— none —</option>
          {columns.map((c) => (
            <option key={c.name} value={c.name}>
              {c.name} ({c.kind})
            </option>
          ))}
        </select>
      </label>

      {excludeColumn && (
        <div>
          <p className="muted">Values on "{excludeColumn}" to exclude from good/bad:</p>
          <ValuePicker column={excludeCol} selected={excludeValues} onChange={setExcludeValues} />
        </div>
      )}

      {error && <p className="error">{error}</p>}

      <div className="button-row">
        <button type="button" onClick={handlePreview} disabled={busy}>
          Preview
        </button>
        <button type="button" onClick={handleSave} disabled={busy}>
          Save target definition
        </button>
      </div>

      {summary && (
        <table className="profile-table">
          <tbody>
            <tr>
              <td>Total</td>
              <td>{summary.n_total}</td>
            </tr>
            <tr>
              <td>Good</td>
              <td>{summary.n_good}</td>
            </tr>
            <tr>
              <td>Bad</td>
              <td>{summary.n_bad}</td>
            </tr>
            <tr>
              <td>Excluded</td>
              <td>{summary.n_excluded}</td>
            </tr>
            <tr>
              <td>Bad rate</td>
              <td>{summary.bad_rate_pct}%</td>
            </tr>
          </tbody>
        </table>
      )}
    </div>
  );
}
