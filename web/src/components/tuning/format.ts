import { ML_ALGORITHM_LABELS } from "../../api";
import type { MLAlgorithm, ModelCandidate, SampleMetricsMap } from "../../api";

// A test/OOT Gini more than this fraction below train is flagged as likely
// overfitting (same threshold as the Validation step).
export const GINI_DROP_WARNING = 0.1;

export function kindLabel(kind: string): string {
  return kind === "logistic" ? "Logistic" : ML_ALGORITHM_LABELS[kind as MLAlgorithm] ?? kind;
}

export function giniDrop(metrics: SampleMetricsMap | null | undefined, sample: "test" | "oot"): number | null {
  const train = metrics?.train?.gini;
  const other = metrics?.[sample]?.gini;
  if (train === undefined || other === undefined || train <= 0) return null;
  return (train - other) / train;
}

export function settingsSummary(candidate: Pick<ModelCandidate, "kind" | "settings">): string {
  const s = candidate.settings as Record<string, number | string | null | string[]>;
  if (candidate.kind === "logistic") {
    return s.penalty && s.penalty !== "none" ? `${String(s.penalty).toUpperCase()} α=${s.alpha}` : "No penalty";
  }
  const parts = [`${s.n_estimators} trees`, `depth ${s.max_depth}`];
  if (s.learning_rate != null) parts.push(`lr ${s.learning_rate}`);
  if (s.subsample != null) parts.push(`subsample ${s.subsample}`);
  if (s.min_samples_leaf != null) parts.push(`min leaf ${s.min_samples_leaf}`);
  if (s.l2_reg != null) parts.push(`L2 ${s.l2_reg}`);
  return parts.join(" · ");
}
