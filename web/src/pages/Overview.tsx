import { Link, useOutletContext } from "react-router-dom";
import { STEP_LABELS, stepOrderFor } from "../api";
import TypeBadge from "../components/TypeBadge";
import type { ProjectOutletContext } from "./ProjectLayout";

export default function Overview() {
  const { project } = useOutletContext<ProjectOutletContext>();
  const stepOrder = stepOrderFor(project.scorecard_type);

  const target = project.artifacts.target_definition?.summary;
  const validation = project.artifacts.validation?.train;
  const scaling = project.artifacts.scaling;
  const finalModel = project.artifacts.final_model_selection;
  const tree = project.artifacts.decision_tree;

  const stats: { label: string; value: string }[] = [];
  if (target) stats.push({ label: "Bad rate", value: `${target.bad_rate_pct}%` });
  if (finalModel) {
    stats.push({ label: "Final model", value: finalModel.source === "logistic" ? "Logistic" : finalModel.algorithm });
  }
  if (validation) {
    stats.push({ label: "Train KS", value: `${validation.ks}` });
    stats.push({ label: "Train AUC", value: `${validation.auc}` });
    stats.push({ label: "Train Gini", value: `${validation.gini}` });
  }
  if (scaling && "min_score" in scaling) {
    stats.push({ label: "Score range", value: `${scaling.min_score}–${scaling.max_score}` });
  }
  if (tree) {
    const nodes = Object.values(tree.nodes);
    stats.push({ label: "Tree nodes", value: String(nodes.length) });
    stats.push({ label: "Leaves", value: String(nodes.filter((n) => n.is_leaf).length) });
    stats.push({ label: "Depth", value: String(Math.max(...nodes.map((n) => n.depth))) });
  }

  const nComplete = stepOrder.filter((s) => project.step_status[s] === "complete").length;

  return (
    <div className="step-page">
      <div className="step-page-header">
        <h1>Overview</h1>
      </div>

      <div className="card">
        <dl className="meta-grid">
          <dt>Scorecard type</dt>
          <dd>
            <TypeBadge type={project.scorecard_type} />
          </dd>
          <dt>Created</dt>
          <dd>{new Date(project.created_at).toLocaleString()}</dd>
          <dt>Last updated</dt>
          <dd>{new Date(project.updated_at).toLocaleString()}</dd>
          <dt>Progress</dt>
          <dd>{nComplete} / {stepOrder.length} steps complete</dd>
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
        {stepOrder.map((step, i) => {
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
