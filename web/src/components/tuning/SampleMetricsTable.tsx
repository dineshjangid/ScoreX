import type { SampleMetricsMap } from "../../api";
import { GINI_DROP_WARNING, giniDrop } from "./format";

const ROWS = [
  { key: "train", label: "Train" },
  { key: "test", label: "Test" },
  { key: "oot", label: "OOT" },
] as const;

/** KS/AUC/Gini per sample for one fit, with the Gini drop vs train flagged. */
export default function SampleMetricsTable({ metrics }: { metrics: SampleMetricsMap }) {
  return (
    <table className="profile-table compact-table">
      <thead>
        <tr>
          <th>Sample</th>
          <th>N</th>
          <th>KS</th>
          <th>AUC</th>
          <th>Gini</th>
          <th>Gini vs train</th>
        </tr>
      </thead>
      <tbody>
        {ROWS.map(({ key, label }) => {
          const m = metrics[key];
          if (!m) {
            return (
              <tr key={key}>
                <td>{label}</td>
                <td colSpan={5} className="muted">
                  no data
                </td>
              </tr>
            );
          }
          const drop = key === "train" ? null : giniDrop(metrics, key);
          return (
            <tr key={key}>
              <td>{label}</td>
              <td>{m.n_total.toLocaleString()}</td>
              <td>{m.ks}</td>
              <td>{m.auc}</td>
              <td>{m.gini}</td>
              <td>
                {drop === null ? (
                  <span className="muted">—</span>
                ) : drop > GINI_DROP_WARNING ? (
                  <span className="status-flag warning">⚠ {(drop * 100).toFixed(1)}% lower</span>
                ) : (
                  <span className="status-flag ok">✓ within {(GINI_DROP_WARNING * 100).toFixed(0)}%</span>
                )}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
