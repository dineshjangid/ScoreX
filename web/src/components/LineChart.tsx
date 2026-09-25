import { useState } from "react";
import SeriesLegend, { type ChartSeries } from "./SeriesLegend";

interface Props {
  // Shared categorical x buckets (e.g. score ranges); each series has one
  // value per bucket, or null where that sample has no rows.
  labels: string[];
  series: ChartSeries<(number | null)[]>[];
  yLabel: string;
  formatValue?: (v: number) => string;
  width?: number;
  height?: number;
}

function niceMax(v: number): number {
  if (v <= 0) return 1;
  const magnitude = 10 ** Math.floor(Math.log10(v));
  const step = [1, 2, 2.5, 5, 10].find((m) => m * magnitude >= v) ?? 10;
  return step * magnitude;
}

/** Multi-series line chart over shared categorical buckets, with a hover crosshair. */
export default function LineChart({ labels, series, yLabel, formatValue = (v) => String(v), width = 560, height = 260 }: Props) {
  const [hover, setHover] = useState<number | null>(null);
  const pad = { top: 14, right: 16, bottom: 56, left: 48 };
  const plotWidth = width - pad.left - pad.right;
  const plotHeight = height - pad.top - pad.bottom;
  const values = series.flatMap((s) => s.data.filter((v): v is number => v !== null));
  const maxY = niceMax(Math.max(...values, 0) * 1.05);
  const yTicks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * maxY);

  const toX = (i: number) => pad.left + (labels.length > 1 ? (i / (labels.length - 1)) * plotWidth : plotWidth / 2);
  const toY = (y: number) => pad.top + plotHeight - (y / maxY) * plotHeight;

  function pathFor(data: (number | null)[]): string {
    let d = "";
    let pen = false;
    data.forEach((v, i) => {
      if (v === null) {
        pen = false;
        return;
      }
      d += `${pen ? "L" : "M"} ${toX(i)} ${toY(v)} `;
      pen = true;
    });
    return d;
  }

  function onMove(e: React.MouseEvent<SVGSVGElement>) {
    if (labels.length === 0) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * width;
    const step = labels.length > 1 ? plotWidth / (labels.length - 1) : plotWidth;
    const i = Math.round((x - pad.left) / step);
    setHover(i >= 0 && i < labels.length ? i : null);
  }

  // Label every bucket when they fit, otherwise every other one.
  const labelEvery = labels.length > 12 ? 2 : 1;

  return (
    <figure className="chart">
      <SeriesLegend series={series} />
      <div className="chart-plot">
        <svg
          width={width}
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label={yLabel}
          onMouseMove={onMove}
          onMouseLeave={() => setHover(null)}
        >
          {yTicks.map((t) => (
            <g key={t}>
              <line x1={pad.left} y1={toY(t)} x2={pad.left + plotWidth} y2={toY(t)} className="chart-grid" />
              <text x={pad.left - 6} y={toY(t) + 3} className="chart-tick" textAnchor="end">
                {formatValue(Number(t.toFixed(2)))}
              </text>
            </g>
          ))}
          <text
            x={10}
            y={pad.top + plotHeight / 2}
            className="chart-axis-label"
            textAnchor="middle"
            transform={`rotate(-90 10 ${pad.top + plotHeight / 2})`}
          >
            {yLabel}
          </text>
          {labels.map((label, i) =>
            i % labelEvery === 0 ? (
              <text
                key={i}
                x={toX(i)}
                y={pad.top + plotHeight + 14}
                className="chart-tick"
                textAnchor="end"
                transform={`rotate(-35 ${toX(i)} ${pad.top + plotHeight + 14})`}
              >
                {label}
              </text>
            ) : null
          )}
          {series.map((s) => (
            <path key={s.key} d={pathFor(s.data)} fill="none" stroke={s.color} className="chart-line" />
          ))}
          {hover !== null && (
            <g pointerEvents="none">
              <line x1={toX(hover)} y1={pad.top} x2={toX(hover)} y2={pad.top + plotHeight} className="chart-crosshair" />
              {series.map((s) => {
                const v = s.data[hover];
                return v === null || v === undefined ? null : (
                  <circle key={s.key} cx={toX(hover)} cy={toY(v)} r={4} fill={s.color} className="chart-dot" />
                );
              })}
            </g>
          )}
        </svg>
        {hover !== null && (
          <div
            className="chart-tooltip"
            style={toX(hover) > width * 0.6 ? { right: width - toX(hover) + 12, top: pad.top } : { left: toX(hover) + 12, top: pad.top }}
          >
            <div className="chart-tooltip-title">{labels[hover]}</div>
            {series.map((s) => {
              const v = s.data[hover];
              return (
                <div key={s.key} className="chart-tooltip-row">
                  <span className="legend-swatch" style={{ background: s.color }} />
                  {s.label}
                  <span className="chart-tooltip-value">{v === null || v === undefined ? "—" : formatValue(v)}</span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </figure>
  );
}
