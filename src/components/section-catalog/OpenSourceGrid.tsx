import { openSourceHighlights } from "@/data/portfolio";

export default function OpenSourceGrid() {
  return (
    <div className="question-grid">
      {openSourceHighlights.map((item) => (
        <a key={item.href} className="plain-card" href={item.href} target="_blank" rel="noopener noreferrer">
          <span className="project-meta">{item.meta}</span>
          <h3>{item.title}</h3>
          <p>{item.description}</p>
        </a>
      ))}
    </div>
  );
}
