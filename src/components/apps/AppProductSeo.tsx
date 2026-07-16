import { AD_FREE_TAGLINE, type AppSeoEntry } from "@/data/app-seo";
import "./AppProductSeo.css";

type AppProductSeoProps = {
  title: string;
  seo?: AppSeoEntry;
};

export default function AppProductSeo({ title, seo }: AppProductSeoProps) {
  const answerFirst =
    seo?.answerFirst ??
    `${title} is a free, completely ad-free Android app by Michael Samuel Naeem — no ads, no trackers, no sponsored clutter.`;
  const highlights = seo?.featureHighlights ?? [];
  const faqs = seo?.faqs ?? [
    {
      question: `Is ${title} ad-free?`,
      answer: `Yes. ${title} is completely ad-free — no banner ads, interstitial ads, or sponsored clutter.`,
    },
    {
      question: `Are there ads or trackers in ${title}?`,
      answer: `No. ${title} is built as an ad-free experience. ${AD_FREE_TAGLINE}`,
    },
  ];

  return (
    <section className="app-product-seo" aria-labelledby="app-seo-heading">
      <p className="app-product-seo__eyebrow">Ad-free Android app</p>
      <h2 id="app-seo-heading">What is {title}?</h2>
      <p className="app-seo-answer">{answerFirst}</p>
      <p className="app-product-seo__adfree">
        <strong>Ad-free advantage:</strong> {AD_FREE_TAGLINE} MichaelSam94 apps are built without banner ads,
        interstitial ads, or video ad interruptions.
      </p>

      {highlights.length ? (
        <>
          <h3 className="app-product-seo__subheading">Key capabilities</h3>
          <ul className="app-product-seo__features">
            {highlights.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </>
      ) : null}

      <h3 className="app-product-seo__subheading" id="app-faq-heading">
        Frequently asked questions
      </h3>
      <div className="app-product-seo__faq" role="list">
        {faqs.map((item) => (
          <article key={item.question} className="app-product-seo__faq-item" role="listitem">
            <h4>{item.question}</h4>
            <p>{item.answer}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
