import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, STEP_LABELS, STEP_ORDER } from "../api";
import type { ProjectDetail as ProjectDetailType } from "../api";
import DataIngestionPanel from "../components/DataIngestionPanel";
import SamplingPanel from "../components/SamplingPanel";
import TargetDefinitionPanel from "../components/TargetDefinitionPanel";

// Which steps have a built implementation to expand into. Steps not listed
// here render as a plain row until their engine module ships.
const IMPLEMENTED_STEPS = new Set(["data_ingestion", "target_definition", "sampling"]);

export default function ProjectDetail() {
  const { id } = useParams<{ id: string }>();
  const [project, setProject] = useState<ProjectDetailType | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    api.getProject(id).then(setProject).catch((e) => setError(String(e)));
  }, [id]);

  if (error) return <p className="error">{error}</p>;
  if (!project) return <p>Loading…</p>;

  const columns = project.artifacts.data_ingestion?.columns ?? [];

  function renderStepBody(step: string) {
    if (!project) return null;
    switch (step) {
      case "data_ingestion":
        return <DataIngestionPanel project={project} onUploaded={setProject} />;
      case "target_definition":
        return columns.length > 0 ? (
          <TargetDefinitionPanel project={project} columns={columns} onSaved={setProject} />
        ) : (
          <p className="muted">Upload a dataset first.</p>
        );
      case "sampling":
        return <SamplingPanel project={project} columns={columns} onSaved={setProject} />;
      default:
        return null;
    }
  }

  return (
    <div className="page">
      <Link to="/">&larr; All projects</Link>
      <h1>{project.name}</h1>
      <p className="badge">{project.scorecard_type}</p>

      <ol className="step-list">
        {STEP_ORDER.map((step, i) => {
          const status = project.step_status[step] ?? "not_started";
          const implemented = IMPLEMENTED_STEPS.has(step);
          const isExpanded = expanded === step;
          return (
            <li key={step} className={`step ${status}`}>
              <button
                type="button"
                className="step-row"
                onClick={() => implemented && setExpanded(isExpanded ? null : step)}
                disabled={!implemented}
              >
                <span className="step-index">{i + 1}</span>
                <span className="step-label">{STEP_LABELS[step]}</span>
                <span className="step-status">{status.replace("_", " ")}</span>
                {implemented && <span className="chevron">{isExpanded ? "−" : "+"}</span>}
              </button>
              {implemented && isExpanded && <div className="step-body">{renderStepBody(step)}</div>}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
