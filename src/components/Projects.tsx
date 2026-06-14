import { projects, workSlug, type Project } from "../data/portfolio";
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

  const externalLinks = "links" in proj ? proj.links : [{ label: "View project", href: proj.link }];

  // Flagship projects have a static case-study page at /work/<slug> (see scripts/build-blog.mjs).
  // Render them as a div so the in-app case-study link can sit alongside external links.
  if (proj.highlight) {
    return (
      <div className={cardClass}>
        {body}
        <div className="projects-card-links">
          <a href={`/work/${workSlug(proj.name)}/`} className="projects-footer-link projects-casestudy">
            Case study →
          </a>
          {externalLinks.map((l) => (
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
