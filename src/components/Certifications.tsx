import { certifications } from "../data/portfolio";
import "./Certifications.css";

export default function Certifications() {
  return (
    <section className="section certifications" id="certifications">
      <h2 className="section-title">Certifications</h2>
      <ul className="cert-list">
        {certifications.map((c) => (
          <li key={c.name} className="cert-item glass-card">
            <span className="cert-name">{c.name}</span>
            <span className="cert-meta">
              {c.org} {c.year !== "—" ? `· ${c.year}` : ""}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
