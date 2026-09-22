import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import type { ProjectSummary, ScorecardType } from "../api";

export default function ProjectList() {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [name, setName] = useState("");
  const [scorecardType, setScorecardType] = useState<ScorecardType>("application");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  function refresh() {
    setLoading(true);
    api
      .listProjects()
      .then(setProjects)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }

  useEffect(refresh, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    const project = await api.createProject(name.trim(), scorecardType);
    setName("");
    navigate(`/projects/${project.id}`);
  }

  async function handleDelete(id: string) {
    await api.deleteProject(id);
    refresh();
  }

  return (
    <div className="page">
      <h1 className="page-title">ScoreX</h1>

      <form className="card" onSubmit={handleCreate}>
        <h2>New project</h2>
        <label>
          Name
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Q3 Application Scorecard" />
        </label>
        <label>
          Scorecard type
          <select value={scorecardType} onChange={(e) => setScorecardType(e.target.value as ScorecardType)}>
            <option value="application">Application</option>
            <option value="behavioural">Behavioural</option>
          </select>
        </label>
        <button type="submit">Create project</button>
      </form>

      {loading && <p>Loading…</p>}
      {error && <p className="error">{error}</p>}

      <ul className="project-list">
        {projects.map((p) => (
          <li key={p.id} className="card">
            <Link to={`/projects/${p.id}`}>
              <strong>{p.name}</strong>
              <span className="badge">{p.scorecard_type}</span>
            </Link>
            <span className="muted">updated {new Date(p.updated_at).toLocaleString()}</span>
            <button className="danger" onClick={() => handleDelete(p.id)}>
              Delete
            </button>
          </li>
        ))}
        {!loading && projects.length === 0 && <p className="muted">No projects yet — create one above.</p>}
      </ul>
    </div>
  );
}
