import { useOutletContext } from "react-router-dom";
import AuditTrailPanel from "../components/AuditTrailPanel";
import type { ProjectOutletContext } from "./ProjectLayout";

export default function AuditTrailPage() {
  const { project } = useOutletContext<ProjectOutletContext>();

  return (
    <div className="step-page">
      <div className="step-page-header">
        <h1>Audit Trail</h1>
      </div>
      <div className="card step-card">
        <AuditTrailPanel projectId={project.id} />
      </div>
    </div>
  );
}
