import { SITE_ORIGIN } from "../config/site";
import { allSkillsFlat, profile } from "../data/portfolio";

const PERSON_ID = `${SITE_ORIGIN}/#person`;
const SKILLS_SECTION_ID = `${SITE_ORIGIN}/#skills`;

/**
 * ItemList JSON-LD for every portfolio skill so crawlers can associate this page with those terms.
 * Must stay aligned with visible skills in `Skills`.
 */
export default function SkillsStructuredData() {
  const graph = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "ItemList",
        "@id": `${SITE_ORIGIN}/#portfolio-skills`,
        name: `${profile.name} — technical skills`,
        description:
          "Software engineering, Android, Flutter, and related tools and practices listed on this portfolio.",
        url: SKILLS_SECTION_ID,
        about: { "@id": PERSON_ID },
        numberOfItems: allSkillsFlat.length,
        itemListElement: allSkillsFlat.map((name, i) => ({
          "@type": "ListItem",
          position: i + 1,
          item: {
            "@type": "Thing",
            name,
          },
        })),
      },
    ],
  };

  return (
    <script
      type="application/ld+json"
      // eslint-disable-next-line react/no-danger -- JSON-LD requires raw script output
      dangerouslySetInnerHTML={{ __html: JSON.stringify(graph) }}
    />
  );
}
