import { useEffect, useState } from "react";
import { api } from "../api";
import type { ProjectDetail, VersionDetail, VersionSummary } from "../api";

interface Props {
  project: ProjectDetail;
}

function fmt(v: number | null): string {
  return v === null || v === undefined ? "—" : String(v);
}

export default function VersionsPanel({ project }: Props) {
  const [versions, setVersions] = useState<VersionSummary[] | null>(null);
  const [label, setLabel] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [compareDetails, setCompareDetails] = useState<[VersionDetail, VersionDetail] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const modelReady = project.step_status["modeling"] === "complete" && project.step_status["scaling"] === "complete";

  function refresh() {
    api.listVersions(project.id).then(setVersions).catch((e) => setError(String(e)));
  }

  useEffect(refresh, [project.id]);

  async function handleSave() {
    setBusy(true);
    setError(null);
    try {
      await api.createVersion(project.id, label.trim() || null);
      setLabel("");
      refresh();
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleSetChampion(id: string) {
    await api.setChampion(project.id, id);
    refresh();
  }

  async function handleDelete(id: string) {
    await api.deleteVersion(project.id, id);
    setSelected((prev) => prev.filter((s) => s !== id));
    setCompareDetails(null);
    refresh();
  }

  function toggleSelect(id: string) {
    setCompareDetails(null);
    setSelected((prev) => {
      if (prev.includes(id)) return prev.filter((s) => s !== id);
      if (prev.length >= 2) return [prev[1], id];
      return [...prev, id];
    });
  }

  async function handleCompare() {
    if (selected.length !== 2) return;
    setBusy(true);
    setError(null);
    try {
      const [a, b] = await Promise.all([api.getVersion(project.id, selected[0]), api.getVersion(project.id, selected[1])]);
      setCompareDetails([a, b]);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="ingestion-panel">
      <p className="muted">
        Save the current binning/selection/model/scorecard as a labeled snapshot, then compare any two versions
        side by side. One version can be marked "champion" (the one currently trusted/deployed).
      </p>

      {!modelReady && <p className="muted">Fit a model and build the scorecard first.</p>}

      {modelReady && (
        <>
          <label>
            Label (optional)
            <input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="e.g. Wider age bins, PDO 25" />
          </label>
          <div className="button-row">
            <button type="button" onClick={handleSave} disabled={busy}>
              Save current build as new version
            </button>
          </div>
        </>
      )}

      {error && <p className="error">{error}</p>}

      {versions && versions.length > 0 && (
        <table className="profile-table">
          <thead>
            <tr>
              <th>Compare</th>
              <th>Version</th>
              <th>Label</th>
              <th>Champion</th>
              <th>Created</th>
              <th>N vars</th>
              <th>Train AUC</th>
              <th>Train KS</th>
              <th>Train Gini</th>
              <th>Score range</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {versions.map((v) => (
              <tr key={v.id}>
                <td>
                  <input type="checkbox" checked={selected.includes(v.id)} onChange={() => toggleSelect(v.id)} />
                </td>
                <td>v{v.version_number}</td>
                <td>{v.label ?? "—"}</td>
                <td>
                  {v.is_champion ? (
                    <span className="status-pill status-complete">champion</span>
                  ) : (
                    <button type="button" onClick={() => handleSetChampion(v.id)}>
                      Make champion
                    </button>
                  )}
                </td>
                <td className="muted">{new Date(v.created_at).toLocaleString()}</td>
                <td>{v.n_variables}</td>
                <td>{fmt(v.train_auc)}</td>
                <td>{fmt(v.train_ks)}</td>
                <td>{fmt(v.train_gini)}</td>
                <td>{v.score_range ?? "—"}</td>
                <td>
                  <button className="danger" type="button" onClick={() => handleDelete(v.id)}>
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {versions && versions.length === 0 && <p className="muted">No versions saved yet.</p>}

      <div className="button-row">
        <button type="button" onClick={handleCompare} disabled={selected.length !== 2 || busy}>
          Compare selected ({selected.length}/2)
        </button>
      </div>

      {compareDetails && (
        <table className="profile-table">
          <thead>
            <tr>
              <th>Metric</th>
              <th>v{compareDetails[0].version_number} {compareDetails[0].label ?? ""}</th>
              <th>v{compareDetails[1].version_number} {compareDetails[1].label ?? ""}</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Variables</td>
              <td>{compareDetails[0].snapshot.modeling?.variables.join(", ") ?? "—"}</td>
              <td>{compareDetails[1].snapshot.modeling?.variables.join(", ") ?? "—"}</td>
            </tr>
            <tr>
              <td>N variables</td>
              <td>{compareDetails[0].n_variables}</td>
              <td>{compareDetails[1].n_variables}</td>
            </tr>
            <tr>
              <td>Train AUC</td>
              <td>{fmt(compareDetails[0].train_auc)}</td>
              <td>{fmt(compareDetails[1].train_auc)}</td>
            </tr>
            <tr>
              <td>Train KS</td>
              <td>{fmt(compareDetails[0].train_ks)}</td>
              <td>{fmt(compareDetails[1].train_ks)}</td>
            </tr>
            <tr>
              <td>Train Gini</td>
              <td>{fmt(compareDetails[0].train_gini)}</td>
              <td>{fmt(compareDetails[1].train_gini)}</td>
            </tr>
            <tr>
              <td>Test AUC</td>
              <td>{fmt(compareDetails[0].snapshot.validation?.test?.auc ?? null)}</td>
              <td>{fmt(compareDetails[1].snapshot.validation?.test?.auc ?? null)}</td>
            </tr>
            <tr>
              <td>PSI (test vs train)</td>
              <td>{fmt(compareDetails[0].snapshot.validation?.psi_test_vs_train?.index ?? null)}</td>
              <td>{fmt(compareDetails[1].snapshot.validation?.psi_test_vs_train?.index ?? null)}</td>
            </tr>
            <tr>
              <td>Score range</td>
              <td>{compareDetails[0].score_range ?? "—"}</td>
              <td>{compareDetails[1].score_range ?? "—"}</td>
            </tr>
            <tr>
              <td>PDO / base score / base odds</td>
              <td>
                {compareDetails[0].snapshot.scaling
                  ? `${compareDetails[0].snapshot.scaling.config.pdo} / ${compareDetails[0].snapshot.scaling.config.base_score} / ${compareDetails[0].snapshot.scaling.config.base_odds}`
                  : "—"}
              </td>
              <td>
                {compareDetails[1].snapshot.scaling
                  ? `${compareDetails[1].snapshot.scaling.config.pdo} / ${compareDetails[1].snapshot.scaling.config.base_score} / ${compareDetails[1].snapshot.scaling.config.base_odds}`
                  : "—"}
              </td>
            </tr>
          </tbody>
        </table>
      )}
    </div>
  );
}
