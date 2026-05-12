import { motion } from "../lib/motion";
import { skills } from "../data/portfolio";
import {
  scrollCardCompact,
  scrollCardListDense,
  scrollListViewport,
} from "../motion/scrollReveal";
import "./Skills.css";

const groups = [
  { title: "Mobile", items: skills.mobile },
  { title: "Architecture", items: skills.architecture },
  { title: "Jetpack", items: skills.jetpack },
  { title: "Async & DI", items: skills.async },
  { title: "Networking", items: skills.networking },
  { title: "Media & IoT", items: skills.media },
  { title: "AI & Emerging", items: skills.emerging },
  { title: "DevOps & QA", items: skills.devops },
  { title: "Tooling & extensions", items: skills.tooling },
];

export default function Skills() {
  return (
    <section
      className="section skills"
      id="skills"
      aria-labelledby="skills-heading"
    >
      <motion.h2
        id="skills-heading"
        className="section-title"
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-80px" }}
        transition={{ duration: 0.5 }}
      >
        Skills
      </motion.h2>
      <motion.p
        className="skills-intro"
        initial={{ opacity: 0, y: 10 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-80px" }}
        transition={{ duration: 0.45 }}
      >
        Technologies, platforms, and practices I use in production work—listed as plain text so search engines
        and visitors can browse the same vocabulary (Android, Kotlin, Flutter, architecture, networking, quality,
        and tooling).
      </motion.p>
      <motion.div
        className="skills-grid"
        variants={scrollCardListDense}
        initial="hidden"
        whileInView="show"
        viewport={scrollListViewport}
      >
        {groups.map((group) => (
          <motion.div
            key={group.title}
            className="skills-group glass-card"
            variants={scrollCardCompact}
            whileHover={{ y: -3, transition: { duration: 0.22, ease: [0.22, 1, 0.36, 1] } }}
          >
            <h3 className="skills-group-title">{group.title}</h3>
            <ul className="skills-tags" role="list">
              {group.items.map((skill) => (
                <li key={skill} className="skills-tag-item">
                  <span className="tag">{skill}</span>
                </li>
              ))}
            </ul>
          </motion.div>
        ))}
      </motion.div>
    </section>
  );
}
