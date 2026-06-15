import { citations } from "../data/citations";
import "./Citations.css";

export default function Citations() {
  return (
    <section
      id="citations"
      className="citations-section"
      aria-labelledby="citations-title"
    >
      <div className="citations-heading">
        <p className="section-kicker">Sources and bibliography</p>
        <h2 id="citations-title" className="section-title">
          Claims backed by references
        </h2>
        <p>
          The portfolio combines first-party project metrics with external
          search, structured-data, and crawler documentation so technical SEO,
          GEO, and AEO claims can be checked from primary sources.
        </p>
      </div>

      <ol className="citations-list">
        {citations.map((citation) => (
          <li className="citation-card" key={citation.url}>
            <cite>
              <a href={citation.url} target="_blank" rel="noreferrer">
                {citation.title}
              </a>
              <span>{citation.publisher}</span>
            </cite>
            <p>{citation.supports}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}
