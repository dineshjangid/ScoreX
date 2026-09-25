import { useState } from "react";
import type { RocPoint } from "../api";
import SeriesLegend, { type ChartSeries } from "./SeriesLegend";

interface Props {
  series: ChartSeries<RocPoint[]>[];
  size?: number;
}

// Linear interpolation of TPR at a given FPR along one ROC curve.
function tprAt(points: RocPoint[], fpr: number): number | null {
  if (points.length === 0) return null;
  for (let i = 1; i < points.length; i++) {
    const a = points[i - 1];
    const b = points[i];
    if (fpr <= b.fpr) {
      if (b.fpr === a.fpr) return b.tpr;
      return a.tpr + ((fpr - a.fpr) / (b.fpr - a.fpr)) * (b.tpr - a.tpr);
    }
  }
  return points[points.length - 1].tpr;
}

export default function RocChart({ series, size = 280 }: Props) {
  const [hoverFpr, setHoverFpr] = useState<number | null>(null);
  const pad = { top: 12, right: 12, bottom: 36, left: 46 };
  const plot = size - pad.left - pad.right;
  const toX = (fpr: number) => pad.left + fpr * plot;
  const toY = (tpr: number) => pad.top + (1 - tpr) * plot;
  const ticks = [0, 0.25, 0.5, 0.75, 1];

  function onMove(e: React.MouseEvent<SVGSVGElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * size;
    const fpr = (x - pad.left) / plot;
    setHoverFpr(fpr >= 0 && fpr <= 1 ? fpr : null);
  }

  return (
    <figure className="chart">
      <SeriesLegend series={series} />
      <div className="chart-plot">
        <svg
          width={size}
          height={plot + pad.top + pad.bottom}
          viewBox={`0 0 ${size} ${plot + pad.top + pad.bottom}`}
          role="img"
          aria-label="ROC curve by sample"
          onMouseMove={onMove}
          onMouseLeave={() => setHoverFpr(null)}
        >
          {ticks.map((t) => (
            <g key={t}>
              <line x1={toX(t)} y1={toY(0)} x2={toX(t)} y2={toY(1)} className="chart-grid" />
              <line x1={toX(0)} y1={toY(t)} x2={toX(1)} y2={toY(t)} className="chart-grid" />
              <text x={toX(t)} y={toY(0) + 14} className="chart-tick" textAnchor="middle">
                {t}
              </text>
              <text x={pad.left - 6} y={toY(t) + 3} className="chart-tick" textAnchor="end">
                {t}
              </text>
            </g>
          ))}
          <text x={pad.left + plot / 2} y={plot + pad.top + 32} className="chart-axis-label" textAnchor="middle">
            False positive rate
          </text>
          <text
            x={10}
            y={pad.top + plot / 2}
            className="chart-axis-label"
            textAnchor="middle"
            transform={`rotate(-90 10 ${pad.top + plot / 2})`}
          >
            True positive rate
          </text>
          <line x1={toX(0)} y1={toY(0)} x2={toX(1)} y2={toY(1)} className="chart-reference" />
          {series.map((s) => (
            <path
              key={s.key}
              d={s.data.map((p, i) => `${i === 0 ? "M" : "L"} ${toX(p.fpr)} ${toY(p.tpr)}`).join(" ")}
              fill="none"
              stroke={s.color}
              className="chart-line"
            />
          ))}
          {hoverFpr !== null && (
            <g pointerEvents="none">
              <line x1={toX(hoverFpr)} y1={toY(0)} x2={toX(hoverFpr)} y2={toY(1)} className="chart-crosshair" />
              {series.map((s) => {
                const tpr = tprAt(s.data, hoverFpr);
                return tpr === null ? null : (
                  <circle key={s.key} cx={toX(hoverFpr)} cy={toY(tpr)} r={4} fill={s.color} className="chart-dot" />
                );
              })}
            </g>
          )}
        </svg>
        {hoverFpr !== null && (
          <div
            className="chart-tooltip"
            style={hoverFpr > 0.55 ? { right: size - toX(hoverFpr) + 12, top: pad.top } : { left: toX(hoverFpr) + 12, top: pad.top }}
          >
            <div className="chart-tooltip-title">FPR {hoverFpr.toFixed(2)}</div>
            {series.map((s) => {
              const tpr = tprAt(s.data, hoverFpr);
              return (
                <div key={s.key} className="chart-tooltip-row">
                  <span className="legend-swatch" style={{ background: s.color }} />
                  {s.label}
                  <span className="chart-tooltip-value">{tpr === null ? "—" : `TPR ${tpr.toFixed(2)}`}</span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </figure>
  );
}
