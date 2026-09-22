import { NavLink } from "react-router-dom";
import { STEP_LABELS, stepOrderFor } from "../api";
import type { ProjectDetail, StepStatus } from "../api";
import UserMenu from "./UserMenu";

const STATUS_ICON: Record<StepStatus, string> = {
  not_started: "",
  in_progress: "◐",
  complete: "✓",
};

export default function Sidebar({ project }: { project: ProjectDetail }) {
  const stepOrder = stepOrderFor(project.scorecard_type);
  // Batch scoring and model versioning are scorecard-specific (they need a
  // fitted logistic model + scaling); Decision Tree projects export
  // directly from their own step page instead.
  const showScorecardTools = project.scorecard_type !== "decision_tree";

  return (
    <nav className="sidebar">
      <div className="sidebar-header">
        <NavLink to="/" className="sidebar-back">
          &larr; All projects
        </NavLink>
        <h2 className="sidebar-title">{project.name}</h2>
        <span className="badge">{project.scorecard_type}</span>
      </div>

      <NavLink
        to={`/projects/${project.id}`}
        end
        className={({ isActive }) => `sidebar-item overview-item ${isActive ? "active" : ""}`}
      >
        Overview
      </NavLink>

      <ol className="sidebar-list">
        {stepOrder.map((step, i) => {
          const status = project.step_status[step] ?? "not_started";
          return (
            <li key={step}>
              <NavLink
                to={`/projects/${project.id}/${step}`}
                className={({ isActive }) => `sidebar-item status-${status} ${isActive ? "active" : ""}`}
              >
                <span className="sidebar-index">{STATUS_ICON[status] || i + 1}</span>
                <span className="sidebar-label">{STEP_LABELS[step]}</span>
              </NavLink>
            </li>
          );
        })}
      </ol>

      <div className="sidebar-section-label">Tools</div>
      <ol className="sidebar-list">
        {showScorecardTools && (
          <>
            <li>
              <NavLink
                to={`/projects/${project.id}/batch-scoring`}
                className={({ isActive }) => `sidebar-item ${isActive ? "active" : ""}`}
              >
                <span className="sidebar-label">Batch Scoring</span>
              </NavLink>
            </li>
            <li>
              <NavLink
                to={`/projects/${project.id}/versions`}
                className={({ isActive }) => `sidebar-item ${isActive ? "active" : ""}`}
              >
                <span className="sidebar-label">Model Versions</span>
              </NavLink>
            </li>
          </>
        )}
        <li>
          <NavLink
            to={`/projects/${project.id}/audit-trail`}
            className={({ isActive }) => `sidebar-item ${isActive ? "active" : ""}`}
          >
            <span className="sidebar-label">Audit Trail</span>
          </NavLink>
        </li>
      </ol>

      <div className="sidebar-spacer" />
      <div className="sidebar-footer">
        <UserMenu />
      </div>
    </nav>
  );
}
