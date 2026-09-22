import { Fragment, useState } from "react";
import { api } from "../api";
import type { ProjectDetail, SampleMetrics, StabilityResult, ValidationArtifact } from "../api";
import HistogramChart from "./HistogramChart";
import LineChart from "./LineChart";
import RocChart from "./RocChart";

interface Props {
  project: ProjectDetail;
  onSaved: (project: ProjectDetail) => void;
}

function psiSeverity(index: number): string {
  if (index < 0.1) return "stable";
  if (index < 0.25) return "moderate shift";
  return "significant shift";
}

function SampleMetricsRow({ label, metrics }: { label: string; metrics: SampleMetrics | null }) {
  if (!metrics) {
    return (
      <tr>
        <td>{label}</td>
        <td colSpan={5} className="muted">
          no data
        </td>
      </tr>
    );
  }
  return (
    <tr>
      <td>{label}</td>
      <td>{metrics.n_total}</td>
      <td>{metrics.bad_rate_pct}%</td>
      <td>{metrics.ks}</td>
      <td>{metrics.auc}</td>
      <td>{metrics.gini}</td>
    </tr>
  );
}

function StabilityTable({ result }: { result: StabilityResult }) {
  return (
    <table className="profile-table">
      <thead>
        <tr>
          <th>Bucket</th>
          <th>Reference %</th>
          <th>Comparison %</th>
          <th>Contribution</th>
        </tr>
      </thead>
      <tbody>
        {result.buckets.map((b) => (
          <tr key={b.bucket}>
            <td>{b.bucket}</td>
            <td>{b.reference_pct}%</td>
            <td>{b.comparison_pct}%</td>
            <td>{b.contribution}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function ValidationPanel({ project, onSaved }: Props) {
  const [result, setResult] = useState<ValidationArtifact | null>(project.artifacts.validation ?? null);
  const [expandedCsi, setExpandedCsi] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const scalingReady = project.step_status["scaling"] === "complete";

  async function handleRun() {
    setBusy(true);
    setError(null);
    try {
      const r = await api.runValidation(project.id);
      setResult(r);
      onSaved(await api.getProject(project.id));
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  if (!scalingReady) {
    return <p className="muted">Build the scorecard first.</p>;
  }

  return (
    <div className="ingestion-panel">
      {error && <p className="error">{error}</p>}

      <div className="button-row">
        <button type="button" onClick={handleRun} disabled={busy}>
          Run validation
        </button>
      </div>

      {result && (
        <>
          <table className="profile-table">
            <thead>
              <tr>
                <th>Sample</th>
                <th>N</th>
                <th>Bad rate</th>
                <th>KS</th>
                <th>AUC</th>
                <th>Gini</th>
              </tr>
            </thead>
            <tbody>
              <SampleMetricsRow label="Train" metrics={result.train} />
              <SampleMetricsRow label="Test" metrics={result.test} />
              <SampleMetricsRow label="OOT" metrics={result.oot} />
            </tbody>
          </table>

          <p className="muted">ROC curve (train)</p>
          <RocChart points={result.roc_train} />

          {result.score_histogram_train && result.score_histogram_train.length > 0 && (
            <>
              <p className="muted">Score distribution (train)</p>
              <HistogramChart bins={result.score_histogram_train} />
            </>
          )}

          <p className="muted">Calibration curve — actual bad rate by score bucket (train, riskiest first)</p>
          <LineChart
            points={result.decile_table_train.map((row, i) => ({
              x: i,
              y: row.bad_rate_pct,
              label: row.score_range,
            }))}
            yLabel="bad rate %"
          />

          <p className="muted">Decile / lift table (train, riskiest first)</p>
          <table className="profile-table">
            <thead>
              <tr>
                <th>Score range</th>
                <th>N</th>
                <th>Bad</th>
                <th>Bad rate</th>
                <th>% of total bad</th>
              </tr>
            </thead>
            <tbody>
              {result.decile_table_train.map((row) => (
                <tr key={row.score_range}>
                  <td>{row.score_range}</td>
                  <td>{row.n_total}</td>
                  <td>{row.n_bad}</td>
                  <td>{row.bad_rate_pct}%</td>
                  <td>{row.pct_of_total_bad}%</td>
                </tr>
              ))}
            </tbody>
          </table>

          <p className="muted">
            PSI (test vs train): {result.psi_test_vs_train.index} — {psiSeverity(result.psi_test_vs_train.index)}
          </p>
          <StabilityTable result={result.psi_test_vs_train} />

          {result.psi_oot_vs_train && (
            <>
              <p className="muted">
                PSI (OOT vs train): {result.psi_oot_vs_train.index} — {psiSeverity(result.psi_oot_vs_train.index)}
              </p>
              <StabilityTable result={result.psi_oot_vs_train} />
            </>
          )}

          <p className="muted">Characteristic Stability Index (CSI) per variable, test vs train</p>
          <table className="profile-table">
            <thead>
              <tr>
                <th>Variable</th>
                <th>CSI</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(result.csi_test_vs_train).map(([variable, stability]) => {
                const isExpanded = expandedCsi === variable;
                return (
                  <Fragment key={variable}>
                    <tr>
                      <td>{variable}</td>
                      <td>{stability.index}</td>
                      <td>
                        <button type="button" onClick={() => setExpandedCsi(isExpanded ? null : variable)}>
                          {isExpanded ? "Hide" : "View"}
                        </button>
                      </td>
                    </tr>
                    {isExpanded && (
                      <tr>
                        <td colSpan={3}>
                          <StabilityTable result={stability} />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}
