import { motion } from "framer-motion";
import { projects } from "../data/portfolio";
import "./Projects.css";

const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.06 },
  },
};

const card = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0 },
};

export default function Projects() {
  return (
    <section className="section projects" id="projects">
      <motion.h2
        className="section-title"
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-80px" }}
        transition={{ duration: 0.5 }}
      >
        Projects
      </motion.h2>
      <motion.div
        className="projects-grid"
        variants={container}
        initial="hidden"
        whileInView="show"
        viewport={{ once: true, margin: "-60px" }}
      >
        {projects.map((proj) => (
          <motion.a
            key={proj.name}
            href={proj.link}
            target="_blank"
            rel="noopener noreferrer"
            className={`projects-card glass-card ${proj.highlight ? "highlight" : ""}`}
            variants={card}
            whileHover={{ y: -4 }}
            whileTap={{ scale: 0.99 }}
          >
            {proj.highlight && <span className="projects-badge">Featured</span>}
            <p className="projects-company">{proj.company}</p>
            <h3 className="projects-name">{proj.name}</h3>
            <p className="projects-desc">{proj.description}</p>
            <div className="projects-tags">
              {proj.tags.map((tag) => (
                <span key={tag} className="tag">{tag}</span>
              ))}
            </div>
          </motion.a>
        ))}
      </motion.div>
    </section>
  );
}
