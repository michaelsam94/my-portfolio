# Wave 3 blog generation

- `topics.jsonl` — 1000 unique gap-filling topics (no agent/llm/rag mirrors)
- `../wave3-topics.json` — enriched topic metadata used for generation
- `../humanize-progress/wave3.json` — generation progress report

Posts are written to `content/blog/<slug>.md` with standard frontmatter (title, slug, description, dates, tags, keywords, 3 FAQs), answer-first leads, topic-specific H2s, code samples, and comparison tables.
