import "./Impact.css";

const metrics = [
  {
    value: "10+",
    label: "years shipping software",
    detail: "Android, Kotlin, React, infrastructure, EV charging, and tooling.",
  },
  {
    value: "4+",
    label: "years leading engineers",
    detail: "Hands-on technical leadership, delivery ownership, and mentoring.",
  },
  {
    value: "120k+",
    label: "commerce users supported",
    detail: "Production marketplace and storefront work at real user scale.",
  },
  {
    value: "240+",
    label: "merchants enabled",
    detail: "B2B commerce flows, onboarding, and operational app delivery.",
  },
  {
    value: "99.9%",
    label: "uptime owned",
    detail: "Reliable production systems with monitoring and incident response.",
  },
  {
    value: "70%",
    label: "faster store operations",
    detail: "Workflow improvements for repeated mobile and commerce tasks.",
  },
  {
    value: "50k+",
    label: "app users reached",
    detail: "Consumer Android features, performance work, and release delivery.",
  },
  {
    value: "100+",
    label: "vendor flows improved",
    detail: "Operational automation and mobile UX improvements for vendors.",
  },
];

const proofPoints = [
  "20% faster API responses on commerce systems",
  "30% lower crash rate across production mobile releases",
  "50% faster onboarding in vendor workflows",
  "4-6 second EV charging session setup targets",
];

export default function Impact() {
  return (
    <section id="impact" className="impact-section" aria-labelledby="impact-title">
      <div className="impact-heading">
        <p className="section-kicker">Measured outcomes</p>
        <h2 id="impact-title" className="section-title">
          Impact at a Glance
        </h2>
        <p className="impact-summary">
          The portfolio is backed by concrete delivery numbers across mobile,
          commerce, infrastructure, and EV charging systems.
        </p>
      </div>

      <div className="impact-grid">
        {metrics.map((metric) => (
          <article className="impact-card" key={`${metric.value}-${metric.label}`}>
            <strong>{metric.value}</strong>
            <span>{metric.label}</span>
            <p>{metric.detail}</p>
          </article>
        ))}
      </div>

      <ul className="impact-proof" aria-label="Additional quantified proof points">
        {proofPoints.map((point) => (
          <li key={point}>{point}</li>
        ))}
      </ul>
    </section>
  );
}
