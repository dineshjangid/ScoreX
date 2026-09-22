import { Link, useOutletContext } from "react-router-dom";
import { STEP_LABELS, STEP_ORDER } from "../api";
import type { ProjectOutletContext } from "./ProjectLayout";

export default function Overview() {
  const { project } = useOutletContext<ProjectOutletContext>();

  const target = project.artifacts.target_definition?.summary;
  const validation = project.artifacts.validation?.train;
  const scaling = project.artifacts.scaling;

  const stats: { label: string; value: string }[] = [];
  if (target) stats.push({ label: "Bad rate", value: `${target.bad_rate_pct}%` });
  if (validation) {
    stats.push({ label: "Train KS", value: `${validation.ks}` });
    stats.push({ label: "Train AUC", value: `${validation.auc}` });
    stats.push({ label: "Train Gini", value: `${validation.gini}` });
  }
  if (scaling) stats.push({ label: "Score range", value: `${scaling.min_score}–${scaling.max_score}` });

  const nComplete = STEP_ORDER.filter((s) => project.step_status[s] === "complete").length;

  return (
    <div className="step-page">
      <div className="step-page-header">
        <h1>Overview</h1>
      </div>

      <div className="card">
        <dl className="meta-grid">
          <dt>Scorecard type</dt>
          <dd className="badge">{project.scorecard_type}</dd>
          <dt>Created</dt>
          <dd>{new Date(project.created_at).toLocaleString()}</dd>
          <dt>Last updated</dt>
          <dd>{new Date(project.updated_at).toLocaleString()}</dd>
          <dt>Progress</dt>
          <dd>{nComplete} / {STEP_ORDER.length} steps complete</dd>
        </dl>
      </div>

      {stats.length > 0 && (
        <div className="stat-row">
          {stats.map((s) => (
            <div className="stat-tile" key={s.label}>
              <span className="stat-value">{s.value}</span>
              <span className="stat-label">{s.label}</span>
            </div>
          ))}
        </div>
      )}

      <div className="module-grid">
        {STEP_ORDER.map((step, i) => {
          const status = project.step_status[step] ?? "not_started";
          return (
            <Link key={step} to={`/projects/${project.id}/${step}`} className={`module-card status-${status}`}>
              <span className="module-index">{i + 1}</span>
              <span className="module-label">{STEP_LABELS[step]}</span>
              <span className={`status-pill status-${status}`}>{status.replace("_", " ")}</span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
