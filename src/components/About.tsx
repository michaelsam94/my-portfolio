import { motion } from "framer-motion";
import { about } from "../data/portfolio";
import "./About.css";

const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.08 },
  },
};

const item = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0 },
};

export default function About() {
  return (
    <section className="section about" id="about">
      <motion.h2
        className="section-title"
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-80px" }}
        transition={{ duration: 0.5 }}
      >
        About
      </motion.h2>
      <motion.div
        className="about-content glass-card"
        variants={container}
        initial="hidden"
        whileInView="show"
        viewport={{ once: true, margin: "-60px" }}
      >
        <motion.p className="about-summary" variants={item}>
          {about.summary}
        </motion.p>
        <ul className="about-highlights">
          {about.highlights.map((line, i) => (
            <motion.li key={i} variants={item}>
              {line}
            </motion.li>
          ))}
        </ul>
      </motion.div>
    </section>
  );
}
