import { useEffect, useState } from "react";
import { api } from "../api";
import type { AuditLogEntry } from "../api";

interface Props {
  projectId: string;
}

export default function AuditTrailPanel({ projectId }: Props) {
  const [entries, setEntries] = useState<AuditLogEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getAuditLog(projectId)
      .then(setEntries)
      .catch((e) => setError(String(e)));
  }, [projectId]);

  if (error) return <p className="error">{error}</p>;
  if (!entries) return <p className="muted">Loading…</p>;

  return (
    <div className="ingestion-panel">
      <p className="muted">Every recorded action taken on this project, most recent first.</p>
      {entries.length === 0 ? (
        <p className="muted">No activity recorded yet.</p>
      ) : (
        <table className="profile-table">
          <thead>
            <tr>
              <th>When</th>
              <th>User</th>
              <th>Role</th>
              <th>Action</th>
              <th>Detail</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e) => (
              <tr key={e.id}>
                <td className="muted">{new Date(e.created_at).toLocaleString()}</td>
                <td>{e.username}</td>
                <td>
                  <span className="badge">{e.role}</span>
                </td>
                <td>
                  <code>{e.action}</code>
                </td>
                <td>{e.detail ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
