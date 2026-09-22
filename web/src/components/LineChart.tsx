interface Point {
  x: number;
  y: number;
  label: string;
}

interface Props {
  points: Point[];
  width?: number;
  height?: number;
  yLabel?: string;
}

/** A simple line+dot chart, y from 0 to max(data). x is just point order (categorical buckets). */
export default function LineChart({ points, width = 560, height = 220, yLabel }: Props) {
  const pad = { top: 16, right: 16, bottom: 40, left: 40 };
  const plotWidth = width - pad.left - pad.right;
  const plotHeight = height - pad.top - pad.bottom;
  const maxY = Math.max(...points.map((p) => p.y), 1e-9) * 1.15;

  const toX = (i: number) => pad.left + (points.length > 1 ? (i / (points.length - 1)) * plotWidth : plotWidth / 2);
  const toY = (y: number) => pad.top + plotHeight - (y / maxY) * plotHeight;

  const path = points.map((p, i) => `${i === 0 ? "M" : "L"} ${toX(i)} ${toY(p.y)}`).join(" ");

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label="line chart">
      <line x1={pad.left} y1={pad.top} x2={pad.left} y2={pad.top + plotHeight} stroke="var(--border)" />
      <line x1={pad.left} y1={pad.top + plotHeight} x2={pad.left + plotWidth} y2={pad.top + plotHeight} stroke="var(--border)" />
      {yLabel && (
        <text x={4} y={pad.top} fontSize="10" fill="var(--text)">
          {yLabel}
        </text>
      )}
      <path d={path} fill="none" stroke="var(--accent)" strokeWidth={2} />
      {points.map((p, i) => (
        <g key={i}>
          <circle cx={toX(i)} cy={toY(p.y)} r={3.5} fill="var(--accent)">
            <title>{`${p.label}: ${p.y}`}</title>
          </circle>
          <text
            x={toX(i)}
            y={height - 12}
            fontSize="9"
            fill="var(--text)"
            textAnchor="middle"
            transform={`rotate(-30 ${toX(i)} ${height - 12})`}
          >
            {p.label}
          </text>
        </g>
      ))}
    </svg>
  );
}
