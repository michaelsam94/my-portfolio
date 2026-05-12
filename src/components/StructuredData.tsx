import { portfolioFaq } from "../data/portfolio";

/** FAQPage JSON-LD must match visible FAQ copy in `About`. */
export default function StructuredData() {
  const faqLd = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: portfolioFaq.map((f) => ({
      "@type": "Question",
      name: f.question,
      acceptedAnswer: {
        "@type": "Answer",
        text: f.answer,
      },
    })),
  };

  return (
    <script
      type="application/ld+json"
      // eslint-disable-next-line react/no-danger -- JSON-LD requires raw script output
      dangerouslySetInnerHTML={{ __html: JSON.stringify(faqLd) }}
    />
  );
}
