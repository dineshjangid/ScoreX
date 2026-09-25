import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import type { DownstreamSettings, ModelCandidate, ProjectDetail } from "../api";
import CandidatesTable from "./tuning/CandidatesTable";
import LogisticTuningCard from "./tuning/LogisticTuningCard";
import MLTuningCard from "./tuning/MLTuningCard";
import { kindLabel } from "./tuning/format";

interface Props {
  project: ProjectDetail;
  onSaved: (project: ProjectDetail) => void;
}

function describeSettings(settings: DownstreamSettings): string {
  const parts = [`Final model: ${settings.final_model_algorithm === "logistic" ? "logistic scorecard" : kindLabel(settings.final_model_algorithm ?? "")}`];
  if (settings.final_model_algorithm === "logistic" && settings.scaling) {
    const s = settings.scaling;
    parts.push(`PDO ${s.pdo} · ${s.base_score} at ${s.base_odds}:1`);
  }
  return parts.join(" · ");
}

export default function ModelingPanel({ project, onSaved }: Props) {
  const navigate = useNavigate();
  const [candidates, setCandidates] = useState<ModelCandidate[]>([]);
  const [settings, setSettings] = useState<DownstreamSettings>({ final_model_algorithm: null, scaling: null });
  const [highlightIds, setHighlightIds] = useState<string[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [rebuilding, setRebuilding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectionReady = project.step_status["variable_selection"] === "complete";

  const loadCandidates = useCallback(async () => {
    const result = await api.getModelCandidates(project.id);
    setCandidates(result.candidates);
    setSettings(result.downstream_settings);
  }, [project.id]);

  useEffect(() => {
    if (selectionReady) loadCandidates().catch((e) => setError(String(e)));
  }, [selectionReady, loadCandidates]);

  async function afterChange(newIds: string[]) {
    setHighlightIds(newIds);
    onSaved(await api.getProject(project.id));
    await loadCandidates();
  }

  async function handleActivate(candidate: ModelCandidate) {
    setBusyId(candidate.id);
    setError(null);
    try {
      await api.activateCandidate(project.id, candidate.id);
      await afterChange([]);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusyId(null);
    }
  }

  async function handleDelete(candidate: ModelCandidate) {
    if (!window.confirm(`Delete this ${kindLabel(candidate.kind)} candidate? This can't be undone.`)) return;
    setError(null);
    try {
      const result = await api.deleteCandidate(project.id, candidate.id);
      setCandidates(result.candidates);
    } catch (err) {
      setError(String(err));
    }
  }

  async function handleRebuild() {
    setRebuilding(true);
    setError(null);
    try {
      await api.rebuildDownstream(project.id);
      onSaved(await api.getProject(project.id));
      navigate(`/projects/${project.id}/validation`);
    } catch (err) {
      setError(String(err));
      setRebuilding(false);
    }
  }

  if (!selectionReady) {
    return <p className="muted">Run variable selection first.</p>;
  }

  const hasModel = Boolean(project.artifacts.modeling);
  const downstreamStale = hasModel && project.step_status["final_model_selection"] !== "complete";
  const canRebuild = settings.final_model_algorithm !== null;

  return (
    <div className="tuning-panel">
      {hasModel && (
        <div className={`rebuild-bar ${downstreamStale ? "stale" : ""}`}>
          {downstreamStale ? (
            <>
              <div>
                <strong>The active model changed.</strong>{" "}
                {canRebuild
                  ? "Final Model Selection, Scaling and Validation need re-running."
                  : "Continue to Final Model Selection to carry it forward."}
                {canRebuild && <div className="muted small-note">Rebuild uses your last settings — {describeSettings(settings)}.</div>}
              </div>
              {canRebuild ? (
                <button type="button" className="primary" onClick={handleRebuild} disabled={rebuilding}>
                  {rebuilding ? "Rebuilding…" : "Rebuild & validate →"}
                </button>
              ) : (
                <Link to={`/projects/${project.id}/final_model_selection`} className="button-like">
                  Final Model Selection →
                </Link>
              )}
            </>
          ) : (
            <>
              <span>
                ✓ Final Model Selection, Scaling and Validation are up to date with the active models.
              </span>
              <Link to={`/projects/${project.id}/validation`} className="button-like secondary-link">
                View validation →
              </Link>
            </>
          )}
        </div>
      )}
      {error && <p className="error">{error}</p>}

      <section className="card tuning-card">
        <div className="tuning-card-header">
          <h2>Candidates</h2>
          <span className="muted">
            Every fit is kept. One candidate per model type is active — Final Model Selection chooses among the active ones.
            A new fit never replaces an active one on its own.
          </span>
        </div>
        <CandidatesTable
          candidates={candidates}
          busyId={busyId}
          highlightIds={highlightIds}
          onActivate={handleActivate}
          onDelete={handleDelete}
        />
      </section>

      <LogisticTuningCard
        key={`logistic-${project.artifacts.modeling?.candidate_id ?? "none"}`}
        project={project}
        onFitted={(model) => afterChange(model.candidate_id ? [model.candidate_id] : [])}
      />
      <MLTuningCard project={project} onFitted={(result) => afterChange(result.new_candidate_ids)} />
    </div>
  );
}
