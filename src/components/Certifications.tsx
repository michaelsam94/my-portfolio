import { motion } from "framer-motion";
import { certifications } from "../data/portfolio";
import "./Certifications.css";

export default function Certifications() {
  return (
    <section className="section certifications" id="certifications">
      <motion.h2
        className="section-title"
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-80px" }}
        transition={{ duration: 0.5 }}
      >
        Certifications
      </motion.h2>
      <motion.ul
        className="cert-list"
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-60px" }}
        transition={{ duration: 0.5 }}
      >
        {certifications.map((c) => (
          <li key={c.name} className="cert-item glass-card">
            <span className="cert-name">{c.name}</span>
            <span className="cert-meta">{c.org} {c.year !== "—" ? `· ${c.year}` : ""}</span>
          </li>
        ))}
      </motion.ul>
    </section>
  );
}
