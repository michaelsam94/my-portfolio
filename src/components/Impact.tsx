import { motion } from "framer-motion";
import { impact } from "../data/portfolio";
import {
  scrollCardList,
  scrollListViewport,
  scrollEase,
} from "../motion/scrollReveal";
import "./Impact.css";

const scrollStat = {
  hidden: { opacity: 0, y: 22, scale: 0.94 },
  show: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { duration: 0.48, ease: scrollEase },
  },
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
        variants={scrollCardList}
        initial="hidden"
        whileInView="show"
        viewport={scrollListViewport}
      >
        {impact.map(({ value, label }) => (
          <motion.div key={label} className="impact-card glass-card" variants={scrollStat}>
            <span className="impact-value">{value}</span>
            <span className="impact-label">{label}</span>
          </motion.div>
        ))}
      </motion.div>
    </section>
  );
}
