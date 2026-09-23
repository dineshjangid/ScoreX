import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import type { ProjectSummary, ScorecardType } from "../api";
import UserMenu from "../components/UserMenu";

const SCORECARD_TYPES: { value: ScorecardType; label: string; description: string }[] = [
  { value: "application", label: "Application", description: "Score new applicants at origination" },
  { value: "behavioural", label: "Behavioural", description: "Score existing customers on repayment behaviour" },
  { value: "decision_tree", label: "Decision Tree", description: "Build strategy/policy trees for segmentation" },
];

type SortOption = "updated" | "name";

export default function ProjectList() {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [name, setName] = useState("");
  const [scorecardType, setScorecardType] = useState<ScorecardType>("application");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<ScorecardType | "all">("all");
  const [sortBy, setSortBy] = useState<SortOption>("updated");
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

  const visibleProjects = projects
    .filter((p) => typeFilter === "all" || p.scorecard_type === typeFilter)
    .filter((p) => p.name.toLowerCase().includes(search.trim().toLowerCase()))
    .sort((a, b) =>
      sortBy === "name" ? a.name.localeCompare(b.name) : new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
    );

  return (
    <div className="home-shell">
      <header className="home-header home-header-row">
        <div>
          <h1 className="page-title">ScoreX</h1>
          <p className="muted">Build, validate, and export credit risk scorecards.</p>
        </div>
        <UserMenu />
      </header>

      <section className="card home-module">
        <h2>New project</h2>
        <form onSubmit={handleCreate} className="new-project-form">
          <label>
            Name
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Q3 Application Scorecard" />
          </label>

          <div className="radio-field">
            <span className="radio-field-label">Scorecard type</span>
            <div className="radio-group">
              {SCORECARD_TYPES.map((t) => (
                <label key={t.value} className={`radio-card ${scorecardType === t.value ? "selected" : ""}`}>
                  <input
                    type="radio"
                    name="scorecardType"
                    value={t.value}
                    checked={scorecardType === t.value}
                    onChange={() => setScorecardType(t.value)}
                  />
                  <span className="radio-card-title">{t.label}</span>
                  <span className="radio-card-desc muted">{t.description}</span>
                </label>
              ))}
            </div>
          </div>

          <button type="submit">Create project</button>
        </form>
      </section>

      <section className="home-module">
        <h2>Your projects</h2>
        {loading && <p className="muted">Loading…</p>}
        {error && <p className="error">{error}</p>}

        {projects.length > 0 && (
          <div className="project-filters">
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by name…"
              aria-label="Search projects by name"
            />
            <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value as ScorecardType | "all")}>
              <option value="all">All types</option>
              {SCORECARD_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
            <select value={sortBy} onChange={(e) => setSortBy(e.target.value as SortOption)}>
              <option value="updated">Sort: last updated</option>
              <option value="name">Sort: name</option>
            </select>
          </div>
        )}

        <div className="project-grid">
          {visibleProjects.map((p) => (
            <div key={p.id} className="project-card">
              <button className="delete-corner" onClick={() => handleDelete(p.id)} aria-label={`Delete ${p.name}`}>
                &times;
              </button>
              <Link to={`/projects/${p.id}`} className="project-card-link">
                <span className="badge">{p.scorecard_type}</span>
                <strong className="project-card-name">{p.name}</strong>
                <span className="muted">updated {new Date(p.updated_at).toLocaleString()}</span>
              </Link>
            </div>
          ))}
        </div>

        {!loading && projects.length === 0 && <p className="muted">No projects yet — create one above.</p>}
        {!loading && projects.length > 0 && visibleProjects.length === 0 && (
          <p className="muted">No projects match your search/filter.</p>
        )}
      </section>
    </div>
  );
}
