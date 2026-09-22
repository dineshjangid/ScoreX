import { NavLink } from "react-router-dom";
import { STEP_LABELS, STEP_ORDER } from "../api";
import type { ProjectDetail, StepStatus } from "../api";

const STATUS_ICON: Record<StepStatus, string> = {
  not_started: "",
  in_progress: "◐",
  complete: "✓",
};

export default function Sidebar({ project }: { project: ProjectDetail }) {
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
        {STEP_ORDER.map((step, i) => {
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
    </nav>
  );
}
