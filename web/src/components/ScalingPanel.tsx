import { useState } from "react";
import { api } from "../api";
import type { ProjectDetail, Scorecard } from "../api";

interface Props {
  project: ProjectDetail;
  onSaved: (project: ProjectDetail) => void;
}

export default function ScalingPanel({ project, onSaved }: Props) {
  const existing = project.artifacts.scaling;
  const [pdo, setPdo] = useState(existing?.config.pdo ?? 20);
  const [baseScore, setBaseScore] = useState(existing?.config.base_score ?? 600);
  const [baseOdds, setBaseOdds] = useState(existing?.config.base_odds ?? 50);
  const [scorecard, setScorecard] = useState<Scorecard | null>(existing ?? null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const modelingReady = project.step_status["modeling"] === "complete";

  async function handleRun() {
    setBusy(true);
    setError(null);
    try {
      const result = await api.runScaling(project.id, { pdo, base_score: baseScore, base_odds: baseOdds });
      setScorecard(result);
      onSaved(await api.getProject(project.id));
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  if (!modelingReady) {
    return <p className="muted">Fit a model first.</p>;
  }

  return (
    <div className="ingestion-panel">
      <label>
        PDO (points to double the odds)
        <input type="number" value={pdo} onChange={(e) => setPdo(parseFloat(e.target.value))} />
      </label>
      <label>
        Base score
        <input type="number" value={baseScore} onChange={(e) => setBaseScore(parseFloat(e.target.value))} />
      </label>
      <label>
        Base odds (good:bad at base score)
        <input type="number" value={baseOdds} onChange={(e) => setBaseOdds(parseFloat(e.target.value))} />
      </label>

      {error && <p className="error">{error}</p>}

      <div className="button-row">
        <button type="button" onClick={handleRun} disabled={busy}>
          Build scorecard
        </button>
      </div>

      {scorecard && (
        <>
          <table className="profile-table">
            <tbody>
              <tr>
                <td>Base points</td>
                <td>{scorecard.base_points}</td>
              </tr>
              <tr>
                <td>Score range</td>
                <td>
                  {scorecard.min_score} – {scorecard.max_score}
                </td>
              </tr>
              <tr>
                <td>Training score distribution</td>
                <td>
                  mean {scorecard.train_score_distribution.mean}, median {scorecard.train_score_distribution.median}, std{" "}
                  {scorecard.train_score_distribution.std}
                </td>
              </tr>
            </tbody>
          </table>

          {scorecard.variables.map((v) => (
            <div key={v.variable}>
              <p className="muted">
                <strong>{v.variable}</strong> (coefficient {v.coefficient.toFixed(4)})
              </p>
              <table className="profile-table">
                <thead>
                  <tr>
                    <th>Bin</th>
                    <th>WOE</th>
                    <th>Points</th>
                  </tr>
                </thead>
                <tbody>
                  {v.bins.map((b) => (
                    <tr key={b.label}>
                      <td>{b.label}</td>
                      <td>{b.woe}</td>
                      <td>{b.points}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </>
      )}
    </div>
  );
}
