import { about, portfolioFaq } from "../data/portfolio";
import "./About.css";

export default function About() {
  return (
    <section className="section about" id="about">
      <h2 className="section-title">About</h2>
      <div className="about-content glass-card">
        <p className="about-summary">{about.summary}</p>
        <ul className="about-highlights">
          {about.highlights.map((line, i) => (
            <li key={i}>{line}</li>
          ))}
        </ul>
        <div className="about-faq">
          <h3 className="about-faq-title">Quick answers</h3>
          <dl className="about-faq-list">
            {portfolioFaq.map((f) => (
              <div key={f.question} className="about-faq-item">
                <dt>{f.question}</dt>
                <dd>{f.answer}</dd>
              </div>
            ))}
          </dl>
        </div>
      </div>
    </section>
  );
}
