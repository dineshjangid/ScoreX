interface BarDatum {
  label: string;
  value: number;
}

interface Props {
  data: BarDatum[];
  width?: number;
  height?: number;
  positiveColor?: string;
  negativeColor?: string;
  formatValue?: (v: number) => string;
}

/**
 * A horizontal bar chart. When data has both positive and negative
 * values (e.g. WOE per bin), bars diverge left/right of a center zero
 * axis. When all values share a sign (e.g. IV, always >= 0), bars grow
 * left-aligned from the axis instead, using the full plot width.
 */
export default function BarChart({
  data,
  width = 480,
  height,
  positiveColor = "var(--green)",
  negativeColor = "var(--amber)",
  formatValue = (v) => v.toFixed(3),
}: Props) {
  const rowHeight = 28;
  const chartHeight = height ?? data.length * rowHeight + 10;
  const labelWidth = 110;
  const valueWidth = 56;
  const plotWidth = width - labelWidth - valueWidth;
  const maxAbs = Math.max(...data.map((d) => Math.abs(d.value)), 1e-9);

  const hasNegative = data.some((d) => d.value < 0);
  const hasPositive = data.some((d) => d.value > 0);
  const diverging = hasNegative && hasPositive;

  const center = diverging ? plotWidth / 2 : 0;
  const scale = (diverging ? center : plotWidth) / maxAbs;

  return (
    <svg width={width} height={chartHeight} viewBox={`0 0 ${width} ${chartHeight}`} role="img" aria-label="bar chart">
      <line x1={labelWidth + center} y1={0} x2={labelWidth + center} y2={chartHeight} stroke="var(--border)" />
      {data.map((d, i) => {
        const y = i * rowHeight + rowHeight / 2;
        const barWidth = Math.abs(d.value) * scale;
        const x = d.value >= 0 ? labelWidth + center : labelWidth + center - barWidth;
        return (
          <g key={d.label}>
            <text x={labelWidth - 8} y={y} textAnchor="end" dominantBaseline="middle" fontSize="11" fill="var(--text)">
              {d.label}
            </text>
            <rect x={x} y={y - 9} width={Math.max(barWidth, 1)} height={18} fill={d.value >= 0 ? positiveColor : negativeColor} rx={2} />
            <text
              x={labelWidth + plotWidth + 8}
              y={y}
              textAnchor="start"
              dominantBaseline="middle"
              fontSize="11"
              fill="var(--text-h)"
            >
              {formatValue(d.value)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
