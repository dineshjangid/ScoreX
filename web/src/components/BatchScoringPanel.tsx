import { useRef, useState } from "react";
import { API_BASE, api } from "../api";
import type { BatchScoringResult, ProjectDetail } from "../api";

interface Props {
  project: ProjectDetail;
  onSaved: (project: ProjectDetail) => void;
}

export default function BatchScoringPanel({ project, onSaved }: Props) {
  const [topN, setTopN] = useState(3);
  const [result, setResult] = useState<BatchScoringResult | null>(project.artifacts.batch_scoring ?? null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const scalingReady = project.step_status["scaling"] === "complete";
  const isMlFinal = project.artifacts.final_model_selection?.source === "ml_benchmark";

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const r = await api.uploadBatch(project.id, file, topN);
      setResult(r);
      onSaved(await api.getProject(project.id));
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  if (!scalingReady) {
    return <p className="muted">Build the scorecard first.</p>;
  }

  const reasonColumns = result ? Array.from({ length: result.top_n }, (_, i) => i + 1) : [];

  return (
    <div className="ingestion-panel">
      <p className="muted">
        Upload a new file of applicants (no target/outcome column needed) to score them with the finished
        {isMlFinal ? " model" : " scorecard"} and get reason codes back.
      </p>

      <label>
        Number of reasons per record
        <input type="number" min="1" max="10" value={topN} onChange={(e) => setTopN(parseInt(e.target.value, 10))} />
      </label>

      <div className="upload-row">
        <label className="file-button">
          {busy ? "Scoring…" : result ? "Upload a different batch" : "Upload batch file"}
          <input ref={fileInput} type="file" accept=".csv,.xlsx,.xls" onChange={handleFileChange} disabled={busy} hidden />
        </label>
        {result && <span className="muted">{result.filename}</span>}
      </div>

      {error && <p className="error">{error}</p>}

      {result && (
        <>
          <table className="profile-table">
            <tbody>
              <tr>
                <td>Rows scored</td>
                <td>{result.n_scored}</td>
              </tr>
              <tr>
                <td>Score distribution</td>
                <td>
                  mean {result.score_distribution.mean}, median {result.score_distribution.median}, min{" "}
                  {result.score_distribution.min}, max {result.score_distribution.max}
                </td>
              </tr>
            </tbody>
          </table>

          <div className="button-row">
            <a
              className="button-like"
              href={`${API_BASE}/projects/${project.id}/batch_scoring/export?top_n=${result.top_n}`}
              target="_blank"
              rel="noreferrer"
            >
              Download full CSV export
            </a>
          </div>

          <p className="muted">Preview:</p>
          <table className="profile-table">
            <thead>
              <tr>
                <th>Row</th>
                <th>Score</th>
                {reasonColumns.map((i) => (
                  <th key={i}>Reason {i}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {result.preview.map((row) => (
                <tr key={row.row_index as number}>
                  <td>{row.row_index as number}</td>
                  <td>{row.score as number}</td>
                  {reasonColumns.map((i) => (
                    <td key={i}>{(row[`reason_${i}`] as string) ?? "—"}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}
