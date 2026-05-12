import { projects, type Project } from "../data/portfolio";
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
      <div className={cardClass}>
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
      </div>
    );
  }

  return (
    <a href={proj.link} target="_blank" rel="noopener noreferrer" className={cardClass}>
      {body}
    </a>
  );
}

export default function Projects() {
  return (
    <section className="section projects" id="projects">
      <h2 className="section-title">Projects</h2>
      <div className="projects-grid">
        {projects.map((proj) => (
          <ProjectCard key={proj.name} proj={proj} />
        ))}
      </div>
    </section>
  );
}
