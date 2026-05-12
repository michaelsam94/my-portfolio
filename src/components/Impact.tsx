import { impact } from "../data/portfolio";
import "./Impact.css";

export default function Impact() {
  return (
    <section className="section impact">
      <h2 className="section-title">Impact at a Glance</h2>
      <div className="impact-grid">
        {impact.map(({ value, label }) => (
          <div key={label} className="impact-card glass-card">
            <span className="impact-value">{value}</span>
            <span className="impact-label">{label}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
