import { motion } from "framer-motion";
import { projects, type Project } from "../data/portfolio";
import {
  scrollCard,
  scrollCardList,
  scrollListViewport,
} from "../motion/scrollReveal";
import "./Projects.css";

function ProjectCard({ proj }: { proj: Project }) {
  const cardClass = `projects-card glass-card ${proj.highlight ? "highlight" : ""}`;
  const body = (
    <>
      {proj.highlight && <span className="projects-badge">Featured</span>}
      <p className="projects-company">{proj.company}</p>
      <h3 className="projects-name">{proj.name}</h3>
      <p className="projects-desc">{proj.description}</p>
      <div className="projects-tags">
        {proj.tags.map((tag) => (
          <span key={tag} className="tag">
            {tag}
          </span>
        ))}
      </div>
    </>
  );

  if ("links" in proj) {
    return (
      <motion.div
        className={cardClass}
        variants={scrollCard}
        whileHover={{ y: -4, transition: { duration: 0.22, ease: [0.22, 1, 0.36, 1] } }}
        whileTap={{ scale: 0.99 }}
      >
        {body}
        <div className="projects-card-links">
          {proj.links.map((l) => (
            <a
              key={l.href}
              href={l.href}
              target="_blank"
              rel="noopener noreferrer"
              className="projects-footer-link"
            >
              {l.label}
            </a>
          ))}
        </div>
      </motion.div>
    );
  }

  return (
    <motion.a
      href={proj.link}
      target="_blank"
      rel="noopener noreferrer"
      className={cardClass}
      variants={scrollCard}
      whileHover={{ y: -4, transition: { duration: 0.22, ease: [0.22, 1, 0.36, 1] } }}
      whileTap={{ scale: 0.99 }}
    >
      {body}
    </motion.a>
  );
}

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
        variants={scrollCardList}
        initial="hidden"
        whileInView="show"
        viewport={scrollListViewport}
      >
        {projects.map((proj) => (
          <ProjectCard key={proj.name} proj={proj} />
        ))}
      </motion.div>
    </section>
  );
}
