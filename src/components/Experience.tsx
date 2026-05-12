import { motion } from "framer-motion";
import { experience } from "../data/portfolio";
import {
  scrollCard,
  scrollCardList,
  scrollListViewport,
} from "../motion/scrollReveal";
import "./Experience.css";

export default function Experience() {
  return (
    <section className="section experience" id="experience">
      <motion.h2
        className="section-title"
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-80px" }}
        transition={{ duration: 0.5 }}
      >
        Experience
      </motion.h2>
      <motion.div
        className="experience-list"
        variants={scrollCardList}
        initial="hidden"
        whileInView="show"
        viewport={scrollListViewport}
      >
        {experience.map((job) => (
          <motion.article
            key={job.company + job.period}
            className="experience-card glass-card"
            variants={scrollCard}
            whileHover={{ y: -3, transition: { duration: 0.22, ease: [0.22, 1, 0.36, 1] } }}
          >
            <div className="experience-header">
              <span className="experience-icon" aria-hidden>{job.icon}</span>
              <div>
                <h3 className="experience-role">{job.role}</h3>
                <p className="experience-company">{job.company}</p>
                <p className="experience-meta">
                  {job.period} · {job.location}
                </p>
              </div>
            </div>
            <p className="experience-desc">{job.description}</p>
            <div className="experience-tags">
              {job.tags.map((tag) => (
                <span key={tag} className="tag">{tag}</span>
              ))}
            </div>
          </motion.article>
        ))}
      </motion.div>
    </section>
  );
}
