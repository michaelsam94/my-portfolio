import { experience } from "../data/portfolio";
import "./Experience.css";

export default function Experience() {
  return (
    <section className="section experience" id="experience">
      <h2 className="section-title">Experience</h2>
      <div className="experience-list">
        {experience.map((job) => (
          <article key={job.company + job.period} className="experience-card glass-card">
            <div className="experience-header">
              <span className="experience-icon" aria-hidden>
                {job.icon}
              </span>
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
                <span key={tag} className="tag">
                  {tag}
                </span>
              ))}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
