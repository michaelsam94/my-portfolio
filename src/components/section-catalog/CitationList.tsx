import { citations } from "@/data/citations";

export default function CitationList() {
  return (
    <ol className="citation-list">
      {citations.map((citation) => (
        <li key={citation.url} className="plain-card">
          <h3>
            <a href={citation.url} target="_blank" rel="noreferrer">
              {citation.title}
            </a>
          </h3>
          <p className="project-meta">{citation.publisher}</p>
          <p>{citation.supports}</p>
        </li>
      ))}
    </ol>
  );
}
