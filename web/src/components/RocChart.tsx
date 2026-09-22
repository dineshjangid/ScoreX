import type { RocPoint } from "../api";

interface Props {
  points: RocPoint[];
  size?: number;
}

export default function RocChart({ points, size = 220 }: Props) {
  const pad = 24;
  const plot = size - pad * 2;
  const toX = (fpr: number) => pad + fpr * plot;
  const toY = (tpr: number) => pad + (1 - tpr) * plot;

  const path = points.map((p, i) => `${i === 0 ? "M" : "L"} ${toX(p.fpr)} ${toY(p.tpr)}`).join(" ");

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label="ROC curve">
      <line x1={pad} y1={pad} x2={pad} y2={size - pad} stroke="var(--border)" />
      <line x1={pad} y1={size - pad} x2={size - pad} y2={size - pad} stroke="var(--border)" />
      <line x1={toX(0)} y1={toY(0)} x2={toX(1)} y2={toY(1)} stroke="var(--border)" strokeDasharray="4 4" />
      <path d={path} fill="none" stroke="var(--accent)" strokeWidth={2} />
    </svg>
  );
}
