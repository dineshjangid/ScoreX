export interface ChartSeries<T> {
  key: string;
  label: string;
  color: string;
  data: T;
}

export default function SeriesLegend<T>({ series }: { series: ChartSeries<T>[] }) {
  if (series.length < 2) return null;
  return (
    <div className="chart-legend">
      {series.map((s) => (
        <span key={s.key} className="chart-legend-item">
          <span className="legend-swatch" style={{ background: s.color }} />
          {s.label}
        </span>
      ))}
    </div>
  );
}
