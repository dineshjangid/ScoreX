import type { ModelCandidate, SampleKey } from "../../api";
import { GINI_DROP_WARNING, giniDrop, kindLabel, settingsSummary } from "./format";

interface Props {
  candidates: ModelCandidate[];
  busyId: string | null;
  highlightIds: string[];
  onActivate: (candidate: ModelCandidate) => void;
  onDelete: (candidate: ModelCandidate) => void;
}

function gini(c: ModelCandidate, sample: SampleKey) {
  const g = c.sample_metrics[sample]?.gini;
  return g === undefined ? <span className="muted">—</span> : g.toFixed(3);
}

export default function CandidatesTable({ candidates, busyId, highlightIds, onActivate, onDelete }: Props) {
  if (candidates.length === 0) {
    return <p className="muted">No candidates yet — fit a logistic or ML model below and it will appear here.</p>;
  }
  return (
    <div className="table-scroll">
      <table className="profile-table candidates-table">
        <thead>
          <tr>
            <th>Model</th>
            <th>Settings</th>
            <th className="num">Vars</th>
            <th className="num">Train Gini</th>
            <th className="num">Test Gini</th>
            <th className="num">OOT Gini</th>
            <th>
              Test vs train
            </th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {candidates.map((c) => {
            const drop = giniDrop(c.sample_metrics, "test");
            return (
              <tr key={c.id} className={`${c.is_active ? "active-row" : ""} ${highlightIds.includes(c.id) ? "new-row" : ""}`}>
                <td title={`Fitted ${new Date(c.created_at).toLocaleString()} by ${c.created_by}`}>
                  <strong>{kindLabel(c.kind)}</strong>
                  {c.is_active && <span className="badge active-badge">Active</span>}
                </td>
                <td className="muted settings-cell">{settingsSummary(c)}</td>
                <td className="num" title={c.variables.join(", ")}>
                  {c.variables.length}
                </td>
                <td className="num">{gini(c, "train")}</td>
                <td className="num">{gini(c, "test")}</td>
                <td className="num">{gini(c, "oot")}</td>
                <td>
                  {drop === null ? (
                    <span className="muted">—</span>
                  ) : drop > GINI_DROP_WARNING ? (
                    <span className="status-flag warning">⚠ −{(drop * 100).toFixed(1)}%</span>
                  ) : (
                    <span className="status-flag ok">✓ {drop >= 0 ? "−" : "+"}{Math.abs(drop * 100).toFixed(1)}%</span>
                  )}
                </td>
                <td className="row-actions">
                  {!c.is_active && (
                    <>
                      <button type="button" onClick={() => onActivate(c)} disabled={busyId !== null}>
                        {busyId === c.id ? "Switching…" : "Activate"}
                      </button>
                      <button
                        type="button"
                        className="icon-button"
                        onClick={() => onDelete(c)}
                        disabled={busyId !== null}
                        aria-label={`Delete ${kindLabel(c.kind)} candidate`}
                        title="Delete candidate"
                      >
                        &times;
                      </button>
                    </>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
