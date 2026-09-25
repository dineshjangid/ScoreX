import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { STEP_LABELS, api } from "../api";
import type { ProjectListItem, ScorecardType } from "../api";
import Modal from "../components/Modal";
import TypeBadge, { TYPE_LABEL } from "../components/TypeBadge";
import UserMenu from "../components/UserMenu";

const SCORECARD_TYPES: { value: ScorecardType; label: string; description: string }[] = [
  { value: "application", label: "Application", description: "Score new applicants at origination" },
  { value: "behavioural", label: "Behavioural", description: "Score existing customers on repayment behaviour" },
  { value: "decision_tree", label: "Decision Tree", description: "Build strategy/policy trees for segmentation" },
];

type SortKey = "name" | "type" | "stage" | "updated";
type SortDir = "asc" | "desc";
type ViewMode = "table" | "cards";

const VIEW_STORAGE_KEY = "csw.projectList.view";

function loadView(): ViewMode {
  try {
    return localStorage.getItem(VIEW_STORAGE_KEY) === "cards" ? "cards" : "table";
  } catch {
    return "table";
  }
}

function saveView(view: ViewMode) {
  try {
    localStorage.setItem(VIEW_STORAGE_KEY, view);
  } catch {
    // Storage unavailable (private window etc.) — the toggle still works for this visit.
  }
}

const RELATIVE = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });

function relativeTime(iso: string): string {
  const seconds = (new Date(iso).getTime() - Date.now()) / 1000;
  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ["year", 31536000],
    ["month", 2592000],
    ["week", 604800],
    ["day", 86400],
    ["hour", 3600],
    ["minute", 60],
  ];
  for (const [unit, size] of units) {
    if (Math.abs(seconds) >= size) return RELATIVE.format(Math.round(seconds / size), unit);
  }
  return "just now";
}

function stageLabel(p: ProjectListItem): string {
  return p.current_step ? STEP_LABELS[p.current_step] ?? p.current_step : "Complete";
}

function formatMetric(v: number | null): string {
  return v === null ? "—" : v.toFixed(2);
}

function compareProjects(a: ProjectListItem, b: ProjectListItem, key: SortKey): number {
  switch (key) {
    case "name":
      return a.name.localeCompare(b.name);
    case "type":
      return TYPE_LABEL[a.scorecard_type].localeCompare(TYPE_LABEL[b.scorecard_type]);
    case "stage":
      return a.steps_completed / a.steps_total - b.steps_completed / b.steps_total;
    case "updated":
      return new Date(a.updated_at).getTime() - new Date(b.updated_at).getTime();
  }
}

export default function ProjectList() {
  const [projects, setProjects] = useState<ProjectListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<ScorecardType | "all">("all");
  const [sort, setSort] = useState<{ key: SortKey; dir: SortDir }>({ key: "updated", dir: "desc" });
  const [view, setView] = useState<ViewMode>(loadView);
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState<ProjectListItem | null>(null);
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

  function changeView(next: ViewMode) {
    setView(next);
    saveView(next);
  }

  function toggleSort(key: SortKey) {
    setSort((s) =>
      s.key === key ? { key, dir: s.dir === "asc" ? "desc" : "asc" } : { key, dir: key === "name" || key === "type" ? "asc" : "desc" }
    );
  }

  const counts = { all: projects.length } as Record<ScorecardType | "all", number>;
  for (const t of SCORECARD_TYPES) counts[t.value] = projects.filter((p) => p.scorecard_type === t.value).length;

  const query = search.trim().toLowerCase();
  const visibleProjects = projects
    .filter((p) => typeFilter === "all" || p.scorecard_type === typeFilter)
    .filter((p) => p.name.toLowerCase().includes(query))
    .sort((a, b) => (sort.dir === "asc" ? 1 : -1) * compareProjects(a, b, sort.key));

  function sortHeader(key: SortKey, label: string, className = "") {
    const active = sort.key === key;
    return (
      <th className={className} aria-sort={active ? (sort.dir === "asc" ? "ascending" : "descending") : "none"}>
        <button type="button" className="sort-button" onClick={() => toggleSort(key)}>
          {label}
          <span className="sort-indicator" aria-hidden="true">
            {active ? (sort.dir === "asc" ? "▲" : "▼") : ""}
          </span>
        </button>
      </th>
    );
  }

  return (
    <div className="home-shell">
      <header className="home-topbar">
        <div className="home-brand">
          <h1 className="page-title">CSW</h1>
          <span className="muted home-tagline">Credit Scorecards Workbench</span>
        </div>
        <div className="home-topbar-actions">
          <button type="button" className="primary" onClick={() => setCreating(true)}>
            + New project
          </button>
          <UserMenu />
        </div>
      </header>

      <section className="home-module">
        <div className="project-toolbar">
          <div className="filter-chips" role="group" aria-label="Filter by type">
            {[{ value: "all" as const, label: "All" }, ...SCORECARD_TYPES].map((t) => (
              <button
                key={t.value}
                type="button"
                className={`chip ${t.value !== "all" ? `type-${t.value}` : ""} ${typeFilter === t.value ? "selected" : ""}`}
                aria-pressed={typeFilter === t.value}
                onClick={() => setTypeFilter(t.value)}
              >
                {t.label} <span className="chip-count">{counts[t.value]}</span>
              </button>
            ))}
          </div>
          <div className="project-toolbar-right">
            <input
              type="search"
              className="search-input"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search projects…"
              aria-label="Search projects by name"
            />
            <div className="view-toggle" role="group" aria-label="View">
              <button type="button" className={view === "table" ? "selected" : ""} aria-pressed={view === "table"} onClick={() => changeView("table")}>
                Table
              </button>
              <button type="button" className={view === "cards" ? "selected" : ""} aria-pressed={view === "cards"} onClick={() => changeView("cards")}>
                Cards
              </button>
            </div>
          </div>
        </div>

        {loading && <p className="muted">Loading…</p>}
        {error && <p className="error">{error}</p>}

        {!loading && projects.length === 0 && !error && (
          <div className="empty-state">
            <h2>No projects yet</h2>
            <p className="muted">Start an Application, Behavioural, or Decision Tree project.</p>
            <button type="button" className="primary" onClick={() => setCreating(true)}>
              + New project
            </button>
          </div>
        )}
        {!loading && projects.length > 0 && visibleProjects.length === 0 && (
          <p className="muted empty-filter">No projects match your search or filter.</p>
        )}

        {visibleProjects.length > 0 && view === "table" && (
          <div className="project-table-wrap">
            <table className="project-table">
              <thead>
                <tr>
                  {sortHeader("name", "Name")}
                  {sortHeader("type", "Type", "col-type")}
                  {sortHeader("stage", "Stage")}
                  <th className="col-editor">Last edited by</th>
                  {sortHeader("updated", "Updated", "col-updated")}
                  <th className="col-champion">Champion</th>
                  <th className="col-actions">
                    <span className="visually-hidden">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {visibleProjects.map((p) => (
                  <tr key={p.id} onClick={() => navigate(`/projects/${p.id}`)}>
                    <td className="col-name">
                      <Link to={`/projects/${p.id}`} onClick={(e) => e.stopPropagation()}>
                        {p.name}
                      </Link>
                    </td>
                    <td className="col-type">
                      <TypeBadge type={p.scorecard_type} />
                    </td>
                    <td className="col-stage">
                      <StageCell project={p} />
                    </td>
                    <td className="col-editor muted">{p.last_edited_by ?? "—"}</td>
                    <td className="col-updated muted" title={new Date(p.updated_at).toLocaleString()}>
                      {relativeTime(p.updated_at)}
                    </td>
                    <td className="col-champion">
                      <ChampionCell project={p} />
                    </td>
                    <td className="col-actions" onClick={(e) => e.stopPropagation()}>
                      <RowMenu project={p} onOpen={() => navigate(`/projects/${p.id}`)} onDelete={() => setDeleting(p)} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {visibleProjects.length > 0 && view === "cards" && (
          <div className="project-grid">
            {visibleProjects.map((p) => (
              <div key={p.id} className="project-card">
                <div className="project-card-top">
                  <TypeBadge type={p.scorecard_type} />
                  <RowMenu project={p} onOpen={() => navigate(`/projects/${p.id}`)} onDelete={() => setDeleting(p)} />
                </div>
                <Link to={`/projects/${p.id}`} className="project-card-name">
                  {p.name}
                </Link>
                <StageCell project={p} />
                {p.champion && <ChampionCell project={p} />}
                <div className="project-card-meta muted" title={new Date(p.updated_at).toLocaleString()}>
                  {relativeTime(p.updated_at)}
                  {p.last_edited_by && <> · {p.last_edited_by}</>}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <Modal open={creating} onClose={() => setCreating(false)} title="New project">
        <NewProjectForm onCreated={(id) => navigate(`/projects/${id}`)} onCancel={() => setCreating(false)} />
      </Modal>

      <Modal open={deleting !== null} onClose={() => setDeleting(null)} title="Delete project">
        {deleting && (
          <DeleteProjectForm
            project={deleting}
            onCancel={() => setDeleting(null)}
            onDeleted={() => {
              setDeleting(null);
              refresh();
            }}
          />
        )}
      </Modal>
    </div>
  );
}

function StageCell({ project }: { project: ProjectListItem }) {
  const done = project.current_step === null;
  const pct = Math.round((100 * project.steps_completed) / project.steps_total);
  return (
    <div className="stage">
      <div className="stage-text">
        <span className={done ? "stage-done" : ""}>{stageLabel(project)}</span>
        <span className="muted">
          {project.steps_completed}/{project.steps_total}
        </span>
      </div>
      <div
        className="progress"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={project.steps_total}
        aria-valuenow={project.steps_completed}
        aria-label={`${project.steps_completed} of ${project.steps_total} steps complete`}
      >
        <div className={`progress-fill ${done ? "done" : ""}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function ChampionCell({ project }: { project: ProjectListItem }) {
  const c = project.champion;
  if (!c) return <span className="muted">—</span>;
  return (
    <span className="champion">
      <span className="champion-version">
        v{c.version_number}
        {c.label && <> · {c.label}</>}
      </span>
      <span className="muted">
        KS {formatMetric(c.train_ks)} · Gini {formatMetric(c.train_gini)}
      </span>
    </span>
  );
}

function RowMenu({ project, onOpen, onDelete }: { project: ProjectListItem; onOpen: () => void; onDelete: () => void }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onPointerDown(e: PointerEvent) {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div className="row-menu" ref={rootRef}>
      <button
        type="button"
        className="icon-button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`Actions for ${project.name}`}
        onClick={() => setOpen((o) => !o)}
      >
        ⋯
      </button>
      {open && (
        <div className="popover-menu" role="menu">
          <button type="button" role="menuitem" className="popover-menu-item" onClick={onOpen}>
            Open
          </button>
          <button
            type="button"
            role="menuitem"
            className="popover-menu-item danger-item"
            onClick={() => {
              setOpen(false);
              onDelete();
            }}
          >
            Delete…
          </button>
        </div>
      )}
    </div>
  );
}

function NewProjectForm({ onCreated, onCancel }: { onCreated: (id: string) => void; onCancel: () => void }) {
  const [name, setName] = useState("");
  const [scorecardType, setScorecardType] = useState<ScorecardType>("application");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setSubmitting(true);
    try {
      const project = await api.createProject(name.trim(), scorecardType);
      onCreated(project.id);
    } catch (err) {
      setError(String(err));
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="modal-form">
      <label>
        Name
        <input autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Q3 Application Scorecard" />
      </label>

      <div className="radio-field">
        <span className="radio-field-label">Scorecard type</span>
        <div className="radio-group radio-group-stacked">
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

      {error && <p className="error">{error}</p>}

      <div className="modal-actions">
        <button type="button" className="secondary" onClick={onCancel}>
          Cancel
        </button>
        <button type="submit" className="primary" disabled={!name.trim() || submitting}>
          {submitting ? "Creating…" : "Create project"}
        </button>
      </div>
    </form>
  );
}

function DeleteProjectForm({
  project,
  onCancel,
  onDeleted,
}: {
  project: ProjectListItem;
  onCancel: () => void;
  onDeleted: () => void;
}) {
  const [confirmation, setConfirmation] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const matches = confirmation.trim() === project.name;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!matches) return;
    setSubmitting(true);
    try {
      await api.deleteProject(project.id);
      onDeleted();
    } catch (err) {
      setError(String(err));
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="modal-form">
      <p>
        This permanently deletes <strong>{project.name}</strong> for everyone in the workspace. This can't be
        undone.
      </p>
      <label>
        Type the project name to confirm
        <input autoFocus value={confirmation} onChange={(e) => setConfirmation(e.target.value)} placeholder={project.name} />
      </label>
      {error && <p className="error">{error}</p>}
      <div className="modal-actions">
        <button type="button" className="secondary" onClick={onCancel}>
          Cancel
        </button>
        <button type="submit" className="danger-solid" disabled={!matches || submitting}>
          {submitting ? "Deleting…" : "Delete project"}
        </button>
      </div>
    </form>
  );
}
