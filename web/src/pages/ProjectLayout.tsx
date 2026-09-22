import { useEffect, useState } from "react";
import { Outlet, useParams } from "react-router-dom";
import { api } from "../api";
import type { ProjectDetail } from "../api";
import Sidebar from "../components/Sidebar";

export interface ProjectOutletContext {
  project: ProjectDetail;
  setProject: (project: ProjectDetail) => void;
}

export default function ProjectLayout() {
  const { id } = useParams<{ id: string }>();
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    api.getProject(id).then(setProject).catch((e) => setError(String(e)));
  }, [id]);

  if (error) return <p className="error page-padding">{error}</p>;
  if (!project) return <p className="page-padding">Loading…</p>;

  return (
    <div className="app-shell">
      <Sidebar project={project} />
      <main className="main-content">
        <Outlet context={{ project, setProject } satisfies ProjectOutletContext} />
      </main>
    </div>
  );
}
