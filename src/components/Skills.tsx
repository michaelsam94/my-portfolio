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

export default function Skills() {
  return (
    <section
      className="section skills"
      id="skills"
      aria-labelledby="skills-heading"
    >
      <h2 id="skills-heading" className="section-title">
        Skills
      </h2>
      <p className="skills-intro">
        Technologies, platforms, and practices I use in production work—listed as plain text so search engines
        and visitors can browse the same vocabulary (Android, Kotlin, Flutter, architecture, networking, quality,
        and tooling).
      </p>
      <div className="skills-grid">
        {groups.map((group) => (
          <div key={group.title} className="skills-group glass-card">
            <h3 className="skills-group-title">{group.title}</h3>
            <ul className="skills-tags" role="list">
              {group.items.map((skill) => (
                <li key={skill} className="skills-tag-item">
                  <span className="tag">{skill}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </section>
  );
}
