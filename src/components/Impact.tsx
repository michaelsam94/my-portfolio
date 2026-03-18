import { motion } from "framer-motion";
import { impact } from "../data/portfolio";
import "./Impact.css";

const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.08 },
  },
};

const stat = {
  hidden: { opacity: 0, scale: 0.95 },
  show: { opacity: 1, scale: 1 },
};

export default function Impact() {
  return (
    <section className="section impact">
      <motion.h2
        className="section-title"
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-80px" }}
        transition={{ duration: 0.5 }}
      >
        Impact at a Glance
      </motion.h2>
      <motion.div
        className="impact-grid"
        variants={container}
        initial="hidden"
        whileInView="show"
        viewport={{ once: true, margin: "-60px" }}
      >
        {impact.map(({ value, label }) => (
          <motion.div key={label} className="impact-card glass-card" variants={stat}>
            <span className="impact-value">{value}</span>
            <span className="impact-label">{label}</span>
          </motion.div>
        ))}
      </motion.div>
    </section>
  );
}
