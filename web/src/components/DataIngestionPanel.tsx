import { useRef, useState } from "react";
import { api } from "../api";
import type { DataIngestionArtifact, DataPreview, ProjectDetail } from "../api";

interface Props {
  project: ProjectDetail;
  onUploaded: (project: ProjectDetail) => void;
}

export default function DataIngestionPanel({ project, onUploaded }: Props) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<DataPreview | null>(null);
  const [showPreview, setShowPreview] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const artifact = project.artifacts.data_ingestion as DataIngestionArtifact | undefined;

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const updated = await api.uploadData(project.id, file);
      onUploaded(updated);
      setPreview(null);
      setShowPreview(false);
    } catch (err) {
      setError(String(err));
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  async function togglePreview() {
    if (showPreview) {
      setShowPreview(false);
      return;
    }
    if (!preview) {
      const data = await api.getDataPreview(project.id, 20);
      setPreview(data);
    }
    setShowPreview(true);
  }

  return (
    <div className="ingestion-panel">
      <div className="upload-row">
        <label className="file-button">
          {uploading ? "Uploading…" : artifact ? "Replace file" : "Upload CSV or Excel file"}
          <input
            ref={fileInput}
            type="file"
            accept=".csv,.xlsx,.xls"
            onChange={handleFileChange}
            disabled={uploading}
            hidden
          />
        </label>
        {artifact && <span className="muted">{artifact.original_filename}</span>}
      </div>

      {error && <p className="error">{error}</p>}

      {artifact && (
        <>
          <p className="muted">
            {artifact.n_rows.toLocaleString()} rows &middot; {artifact.n_columns} columns
          </p>

          <table className="profile-table">
            <thead>
              <tr>
                <th>Column</th>
                <th>Type</th>
                <th>Missing</th>
                <th>Unique</th>
                <th>Summary</th>
              </tr>
            </thead>
            <tbody>
              {artifact.columns.map((col) => (
                <tr key={col.name}>
                  <td>{col.name}</td>
                  <td>{col.kind}</td>
                  <td>
                    {col.missing_count} ({col.missing_pct}%)
                  </td>
                  <td>{col.n_unique}</td>
                  <td className="muted">
                    {col.stats
                      ? `min ${col.stats.min}, median ${col.stats.median}, max ${col.stats.max}`
                      : col.top_values
                        ? col.top_values
                            .slice(0, 3)
                            .map((v) => `${v.value} (${v.pct}%)`)
                            .join(", ")
                        : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <button type="button" onClick={togglePreview}>
            {showPreview ? "Hide raw data preview" : "Show raw data preview"}
          </button>

          {showPreview && preview && (
            <div className="preview-scroll">
              <table className="profile-table">
                <thead>
                  <tr>
                    {preview.columns.map((c) => (
                      <th key={c}>{c}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {preview.rows.map((row, i) => (
                    <tr key={i}>
                      {preview.columns.map((c) => (
                        <td key={c}>{row[c] === null ? "—" : String(row[c])}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
