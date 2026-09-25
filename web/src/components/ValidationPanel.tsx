import { Fragment, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { DecileRow, ProjectDetail, SampleCurves, SampleKey, SampleMetrics, StabilityResult, ValidationArtifact } from "../api";
import LineChart from "./LineChart";
import RocChart from "./RocChart";
import type { ChartSeries } from "./SeriesLegend";

interface Props {
  project: ProjectDetail;
  onSaved: (project: ProjectDetail) => void;
}

const SAMPLES: { key: SampleKey; label: string; color: string }[] = [
  { key: "train", label: "Train", color: "var(--series-train)" },
  { key: "test", label: "Test", color: "var(--series-test)" },
  { key: "oot", label: "OOT", color: "var(--series-oot)" },
];

// A test/OOT Gini more than this fraction below train's is flagged as a
// likely sign of overfitting (or, for OOT, population drift).
const GINI_DROP_WARNING = 0.1;

function psiSeverity(index: number): string {
  if (index < 0.1) return "stable";
  if (index < 0.25) return "moderate shift";
  return "significant shift";
}

function giniDrop(train: SampleMetrics, other: SampleMetrics): number {
  return train.gini > 0 ? (train.gini - other.gini) / train.gini : 0;
}

function SampleMetricsRow({ label, metrics, train }: { label: string; metrics: SampleMetrics | null; train: SampleMetrics }) {
  if (!metrics) {
    return (
      <tr>
        <td>{label}</td>
        <td colSpan={6} className="muted">
          no data
        </td>
      </tr>
    );
  }
  const isTrain = metrics === train;
  const drop = giniDrop(train, metrics);
  return (
    <tr>
      <td>{label}</td>
      <td>{metrics.n_total.toLocaleString()}</td>
      <td>{metrics.bad_rate_pct}%</td>
      <td>{metrics.ks}</td>
      <td>{metrics.auc}</td>
      <td>{metrics.gini}</td>
      <td>
        {isTrain ? (
          <span className="muted">—</span>
        ) : drop > GINI_DROP_WARNING ? (
          <span className="status-flag warning">⚠ {(drop * 100).toFixed(1)}% lower</span>
        ) : (
          <span className="status-flag ok">✓ {drop >= 0 ? `${(drop * 100).toFixed(1)}% lower` : `${(-drop * 100).toFixed(1)}% higher`}</span>
        )}
      </td>
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

function DecileTable({ rows }: { rows: DecileRow[] }) {
  return (
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
        {rows.map((row) => (
          <tr key={row.score_range}>
            <td>{row.score_range}</td>
            <td>{row.n_total.toLocaleString()}</td>
            <td>{row.n_bad.toLocaleString()}</td>
            <td>{row.n_total ? `${row.bad_rate_pct}%` : "—"}</td>
            <td>{row.pct_of_total_bad}%</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// Validation results saved before per-sample curves existed only carry
// train charts; present those as a train-only `samples` map.
function curvesOf(result: ValidationArtifact): Partial<Record<SampleKey, SampleCurves>> {
  if (result.samples) return result.samples;
  return {
    train: {
      roc: result.roc_train,
      decile_table: result.decile_table_train,
      score_histogram: result.score_histogram_train ?? [],
    },
  };
}

export default function ValidationPanel({ project, onSaved }: Props) {
  const [result, setResult] = useState<ValidationArtifact | null>(project.artifacts.validation ?? null);
  const [expandedCsi, setExpandedCsi] = useState<string | null>(null);
  const [decileSample, setDecileSample] = useState<SampleKey>("train");
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

  const curves = result ? curvesOf(result) : {};
  const available = SAMPLES.filter((s) => curves[s.key]);
  const legacy = result !== null && !result.samples;
  const bucketLabels = curves.train?.decile_table.map((r) => r.score_range) ?? [];
  const histogramLabels = curves.train?.score_histogram.map((b) => String(b.bin_start)) ?? [];
  const shownDecileSample = curves[decileSample] ? decileSample : "train";

  const rocSeries: ChartSeries<SampleCurves["roc"]>[] = available.map((s) => ({ ...s, data: curves[s.key]!.roc }));
  const calibrationSeries: ChartSeries<(number | null)[]>[] = available.map((s) => ({
    ...s,
    data: curves[s.key]!.decile_table.map((r) => (r.n_total > 0 ? r.bad_rate_pct : null)),
  }));
  const distributionSeries: ChartSeries<(number | null)[]>[] = available.map((s) => {
    const bins = curves[s.key]!.score_histogram;
    const n = bins.reduce((sum, b) => sum + b.count, 0);
    return { ...s, data: bins.map((b) => b.pct ?? (n ? Math.round((b.count / n) * 10000) / 100 : 0)) };
  });

  return (
    <div className="ingestion-panel">
      {error && <p className="error">{error}</p>}

      <div className="button-row">
        <button type="button" onClick={handleRun} disabled={busy}>
          {busy ? "Running…" : "Run validation"}
        </button>
        <Link to={`/projects/${project.id}/modeling`} className="button-like secondary-link">
          ← Back to Model Building to tune
        </Link>
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
                <th>Gini vs train</th>
              </tr>
            </thead>
            <tbody>
              <SampleMetricsRow label="Train" metrics={result.train} train={result.train} />
              <SampleMetricsRow label="Test" metrics={result.test} train={result.train} />
              <SampleMetricsRow label="OOT" metrics={result.oot} train={result.train} />
            </tbody>
          </table>
          <p className="muted">
            A Gini more than {GINI_DROP_WARNING * 100}% below train is flagged: on Test it usually means overfitting,
            on OOT it can also mean population drift (check PSI/CSI below).
          </p>

          {legacy && (
            <p className="notice">These results were saved before per-sample charts existed. Re-run validation to see Test and OOT.</p>
          )}

          <div className="chart-layout">
            <section className="chart-card">
              <h3>ROC curve</h3>
              <RocChart series={rocSeries} />
            </section>
            <section className="chart-card chart-card-wide">
              <h3>Calibration — bad rate by score bucket</h3>
              <p className="muted chart-note">Buckets are train deciles, riskiest first; test and OOT use the same cut points.</p>
              <LineChart labels={bucketLabels} series={calibrationSeries} yLabel="Bad rate %" formatValue={(v) => `${v}%`} />
            </section>
            <section className="chart-card chart-card-wide">
              <h3>Score distribution</h3>
              <p className="muted chart-note">Share of each sample by score, on the train score range.</p>
              <LineChart labels={histogramLabels} series={distributionSeries} yLabel="% of sample" formatValue={(v) => `${v}%`} />
            </section>
          </div>

          <div className="section-header">
            <h3>Decile / lift table</h3>
            <div className="view-toggle" role="group" aria-label="Sample">
              {available.map((s) => (
                <button
                  key={s.key}
                  type="button"
                  className={shownDecileSample === s.key ? "selected" : ""}
                  aria-pressed={shownDecileSample === s.key}
                  onClick={() => setDecileSample(s.key)}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>
          <DecileTable rows={curves[shownDecileSample]!.decile_table} />

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

          <p className="muted">Characteristic Stability Index (CSI) per variable, vs train</p>
          <table className="profile-table">
            <thead>
              <tr>
                <th>Variable</th>
                <th>CSI test</th>
                {result.csi_oot_vs_train && <th>CSI OOT</th>}
                <th></th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(result.csi_test_vs_train).map(([variable, stability]) => {
                const isExpanded = expandedCsi === variable;
                const oot = result.csi_oot_vs_train?.[variable];
                const colSpan = result.csi_oot_vs_train ? 4 : 3;
                return (
                  <Fragment key={variable}>
                    <tr>
                      <td>{variable}</td>
                      <td>{stability.index}</td>
                      {result.csi_oot_vs_train && <td>{oot ? oot.index : "—"}</td>}
                      <td>
                        <button type="button" onClick={() => setExpandedCsi(isExpanded ? null : variable)}>
                          {isExpanded ? "Hide" : "View"}
                        </button>
                      </td>
                    </tr>
                    {isExpanded && (
                      <tr>
                        <td colSpan={colSpan}>
                          <p className="muted">Test vs train</p>
                          <StabilityTable result={stability} />
                          {oot && (
                            <>
                              <p className="muted">OOT vs train</p>
                              <StabilityTable result={oot} />
                            </>
                          )}
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
