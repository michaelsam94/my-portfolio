import { certifications } from "@/data/portfolio";

export default function CertificationList() {
  return (
    <ul className="cert-list">
      {certifications.map((cert) => (
        <li key={cert.name} className="plain-card">
          <h3>{cert.name}</h3>
          <p>
            {cert.org} / {cert.year}
          </p>
        </li>
      ))}
    </ul>
  );
}
