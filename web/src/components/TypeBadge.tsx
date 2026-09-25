import type { ScorecardType } from "../api";

export const TYPE_LABEL: Record<ScorecardType, string> = {
  application: "Application",
  behavioural: "Behavioural",
  decision_tree: "Decision Tree",
};

export default function TypeBadge({ type }: { type: ScorecardType }) {
  return <span className={`badge type-badge type-${type}`}>{TYPE_LABEL[type]}</span>;
}
