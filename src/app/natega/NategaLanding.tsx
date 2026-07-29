import fs from "node:fs";
import path from "node:path";
import Link from "next/link";
import NategaSearch from "./NategaSearch";
import { nategaContent, type NategaLocale } from "./nategaContent";

type Manifest = {
  count: number;
  nameShards: Record<string, string>;
  seatPrefixes: string[];
  scoreStats: Record<string, {
    rankWithRepetition: number;
    rankWithoutRepetition: number;
    sameScoreCount: number;
  }>;
};

function getManifest(): Manifest {
  return JSON.parse(
    fs.readFileSync(path.join(process.cwd(), "public", "natega-data", "manifest.json"), "utf8"),
  ) as Manifest;
}

export default function NategaLanding({ locale }: { locale: NategaLocale }) {
  const content = nategaContent[locale];
  const manifest = getManifest();
  const canonical = `https://natega.michaelsam94.com${content.path}`;
  const structuredData = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "WebApplication",
        name: content.title,
        url: canonical,
        applicationCategory: "EducationalApplication",
        operatingSystem: "Any",
        inLanguage: content.lang,
        description: content.intro,
        isAccessibleForFree: true,
      },
      {
        "@type": "FAQPage",
        mainEntity: content.faqs.map(([question, answer]) => ({
          "@type": "Question",
          name: question,
          acceptedAnswer: { "@type": "Answer", text: answer },
        })),
      },
    ],
  };

  return (
    <main className="natega-page" dir={content.dir} lang={content.lang}>
      <section className="natega-shell">
        <nav className="natega-language-nav" aria-label="Language">
          <Link href="https://natega.michaelsam94.com/" hrefLang="ar">العربية</Link>
          <Link href="https://natega.michaelsam94.com/en/" hrefLang="en">English</Link>
          <Link href="https://natega.michaelsam94.com/franko/" hrefLang="en-EG">Franco</Link>
        </nav>
        <div className="natega-kicker">{content.kicker}</div>
        <h1>{content.title}</h1>
        <p className="natega-intro">{content.intro}</p>
        <NategaSearch manifest={manifest} locale={locale} />

        <section className="natega-seo-section" aria-labelledby="natega-guide">
          <h2 id="natega-guide">{content.guideTitle}</h2>
          <ol>{content.guide.map((item) => <li key={item}>{item}</li>)}</ol>
        </section>
        <section className="natega-seo-section" aria-labelledby="natega-about">
          <h2 id="natega-about">{content.aboutTitle}</h2>
          <p>{content.about}</p>
        </section>
        <section className="natega-seo-section" aria-labelledby="natega-faq">
          <h2 id="natega-faq">{content.faqTitle}</h2>
          <div className="natega-faq-list">
            {content.faqs.map(([question, answer]) => (
              <details key={question}>
                <summary>{question}</summary>
                <p>{answer}</p>
              </details>
            ))}
          </div>
        </section>
      </section>
      <script type="application/ld+json">{JSON.stringify(structuredData)}</script>
    </main>
  );
}
