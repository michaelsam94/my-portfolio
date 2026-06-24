import { impactMetrics } from "@/data/portfolio";

export default function ImpactGrid() {
  return (
    <div className="metric-grid">
      {impactMetrics.map((metric) => (
        <article key={`${metric.value}-${metric.label}`} className="metric-card">
          <strong>{metric.value}</strong>
          <span>{metric.label}</span>
          <p>{metric.detail}</p>
        </article>
      ))}
    </div>
  );
}
