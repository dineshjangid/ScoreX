import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, STEP_LABELS, STEP_ORDER } from "../api";
import type { ProjectDetail as ProjectDetailType } from "../api";

export default function ProjectDetail() {
  const { id } = useParams<{ id: string }>();
  const [project, setProject] = useState<ProjectDetailType | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    api.getProject(id).then(setProject).catch((e) => setError(String(e)));
  }, [id]);

  if (error) return <p className="error">{error}</p>;
  if (!project) return <p>Loading…</p>;

  return (
    <div className="page">
      <Link to="/">&larr; All projects</Link>
      <h1>{project.name}</h1>
      <p className="badge">{project.scorecard_type}</p>

      <ol className="step-list">
        {STEP_ORDER.map((step, i) => {
          const status = project.step_status[step] ?? "not_started";
          return (
            <li key={step} className={`step ${status}`}>
              <span className="step-index">{i + 1}</span>
              <span className="step-label">{STEP_LABELS[step]}</span>
              <span className="step-status">{status.replace("_", " ")}</span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
