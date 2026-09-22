interface HistogramBin {
  bin_start: number;
  bin_end: number;
  count: number;
}

interface Props {
  bins: HistogramBin[];
  width?: number;
  height?: number;
}

export default function HistogramChart({ bins, width = 560, height = 200 }: Props) {
  const pad = { top: 10, right: 10, bottom: 28, left: 36 };
  const plotWidth = width - pad.left - pad.right;
  const plotHeight = height - pad.top - pad.bottom;
  const maxCount = Math.max(...bins.map((b) => b.count), 1);
  const barWidth = bins.length > 0 ? plotWidth / bins.length : 0;

  const tickIndices = bins.length > 0 ? [0, Math.floor(bins.length / 2), bins.length - 1] : [];

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label="score histogram">
      <line
        x1={pad.left}
        y1={pad.top + plotHeight}
        x2={pad.left + plotWidth}
        y2={pad.top + plotHeight}
        stroke="var(--border)"
      />
      {bins.map((b, i) => {
        const barHeight = (b.count / maxCount) * plotHeight;
        const x = pad.left + i * barWidth;
        const y = pad.top + plotHeight - barHeight;
        return (
          <rect
            key={i}
            x={x + 1}
            y={y}
            width={Math.max(barWidth - 2, 1)}
            height={barHeight}
            fill="var(--accent)"
            opacity={0.75}
          >
            <title>{`${b.bin_start}–${b.bin_end}: ${b.count}`}</title>
          </rect>
        );
      })}
      {tickIndices.map((i) => (
        <text
          key={i}
          x={pad.left + i * barWidth}
          y={height - 8}
          fontSize="10"
          fill="var(--text)"
          textAnchor="middle"
        >
          {bins[i].bin_start}
        </text>
      ))}
      <text x={4} y={pad.top + 8} fontSize="10" fill="var(--text)">
        {maxCount}
      </text>
    </svg>
  );
}
