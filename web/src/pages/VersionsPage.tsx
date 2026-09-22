import { useOutletContext } from "react-router-dom";
import VersionsPanel from "../components/VersionsPanel";
import type { ProjectOutletContext } from "./ProjectLayout";

export default function VersionsPage() {
  const { project } = useOutletContext<ProjectOutletContext>();

  return (
    <div className="step-page">
      <div className="step-page-header">
        <h1>Model Versions</h1>
      </div>
      <div className="card step-card">
        <VersionsPanel project={project} />
      </div>
    </div>
  );
}
