import { certifications } from "@/data/portfolio";

export default function CertificationList() {
  return (
    <ul className="cert-list">
      {certifications.map((cert) => (
        <li key={cert.name} className="plain-card">
          <div className="plain-card-title">{cert.name}</div>
          <p>
            {cert.org} / {cert.year}
          </p>
        </li>
      ))}
    </ul>
  );
}
