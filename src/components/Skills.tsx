import { motion } from "framer-motion";
import { skills } from "../data/portfolio";
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

const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.04 },
  },
};

const item = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0 },
};

export default function Skills() {
  return (
    <section className="section skills" id="skills">
      <motion.h2
        className="section-title"
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-80px" }}
        transition={{ duration: 0.5 }}
      >
        Skills
      </motion.h2>
      <motion.div
        className="skills-grid"
        variants={container}
        initial="hidden"
        whileInView="show"
        viewport={{ once: true, margin: "-60px" }}
      >
        {groups.map((group) => (
          <motion.div key={group.title} className="skills-group glass-card" variants={item}>
            <h3 className="skills-group-title">{group.title}</h3>
            <div className="skills-tags">
              {group.items.map((skill) => (
                <span key={skill} className="tag">{skill}</span>
              ))}
            </div>
          </motion.div>
        ))}
      </motion.div>
    </section>
  );
}
