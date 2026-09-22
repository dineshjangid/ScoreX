import { useOutletContext } from "react-router-dom";
import BatchScoringPanel from "../components/BatchScoringPanel";
import type { ProjectOutletContext } from "./ProjectLayout";

export default function BatchScoringPage() {
  const { project, setProject } = useOutletContext<ProjectOutletContext>();

  return (
    <div className="step-page">
      <div className="step-page-header">
        <h1>Batch Scoring</h1>
      </div>
      <div className="card step-card">
        <BatchScoringPanel project={project} onSaved={setProject} />
      </div>
    </div>
  );
}
