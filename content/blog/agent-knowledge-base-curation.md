---
title: "AI Agents: Knowledge Base Curation"
slug: "agent-knowledge-base-curation"
description: "How to curate agent knowledge bases for RAG—source ingestion, chunk quality gates, freshness SLAs, eval harnesses, and governance workflows that keep answers accurate under change."
datePublished: "2025-04-30"
dateModified: "2025-04-30"
tags: ["AI", "Agent", "Knowledge"]
keywords: "knowledge base curation, RAG pipeline, chunk quality, document freshness, agent knowledge, embedding versioning, content governance"
faq:
  - q: "What belongs in an agent knowledge base versus general search index?"
    a: "Knowledge bases hold authoritative, agent-consumable content: policies, runbooks, product specs, and support articles with explicit freshness metadata. General search indexes mix marketing pages, stale wikis, and duplicate PDFs. Curation means whitelisting sources, normalizing structure, and rejecting documents that fail quality gates before they reach embedding."
  - q: "How often should teams re-embed knowledge base content?"
    a: "Re-embed on content hash change, not on a fixed calendar. Track source ETag, last-modified, or CMS publish version. Full re-index weekly is fine for small corpora; large tenants should use incremental CDC from the CMS or object store with tombstone propagation when documents retire."
  - q: "What chunking strategy works best for agent retrieval?"
    a: "Hybrid: structure-aware splits on headings and tables for docs, sliding windows with 10–15% overlap for prose, parent-child linking so agents retrieve small chunks but hydrate full sections. Hard-cap token size to your embedder limit minus metadata overhead. Never chunk without storing source URI, section path, and content hash on every vector."
  - q: "How do you measure knowledge base curation quality?"
    a: "Run a golden-set eval weekly: precision@k, answer faithfulness, citation accuracy, and stale-answer rate when ground truth changed in the last 30 days. Alert when any source's median chunk age exceeds its SLA or when duplicate-near-duplicate ratio crosses 5%. Production user thumbs-down on cited answers is the lagging indicator—fix the pipeline before that spikes."
---
A support agent answered confidently that refunds take fourteen days. Finance had changed the policy to seven days three weeks earlier; the CMS was updated, but the nightly embed job skipped pages without `lastModified` bumps because the editor republished in place without touching metadata. The agent cited a chunk from February. Nobody owned curation—only ingestion. Knowledge base curation is the discipline that keeps RAG pipelines honest: what enters the index, how it is split, when it expires, and who approves changes before users see wrong answers dressed in citations.

## Sources of truth and ingestion boundaries

Curated knowledge bases start with an explicit **source registry**, not a recursive web crawl:

| Source type | Ingestion mode | Freshness signal | Typical SLA |
|-------------|----------------|------------------|-------------|
| CMS articles | Webhook + poll fallback | `published_at`, version id | 15 minutes |
| PDF runbooks | Object store event | S3 etag, content hash | 1 hour |
| API docs (OpenAPI) | CI artifact on merge | Git SHA | On deploy |
| Slack export | Batch (discouraged) | Export timestamp | Manual only |
| Confluence | App connector | Page version | 30 minutes |

Reject sources that cannot emit reliable change signals. Wikis with anonymous edits and no audit trail belong in search, not in agent ground truth.

```python
from dataclasses import dataclass
from enum import Enum

class SourceTier(str, Enum):
    AUTHORITATIVE = "authoritative"   # agent may cite as policy
    REFERENCE = "reference"           # cite with disclaimer
    DEPRECATED = "deprecated"         # tombstone only

@dataclass
class KnowledgeSource:
    source_id: str
    uri: str
    tier: SourceTier
    owner_team: str
    max_staleness_hours: int
    content_hash: str | None = None

def should_ingest(source: KnowledgeSource, new_hash: str) -> bool:
    if source.tier == SourceTier.DEPRECATED:
        return False
    return source.content_hash != new_hash
```

Every document carries `source_id`, `content_hash`, `ingested_at`, and `expires_at` computed from tier SLA. Downstream retrieval filters expired chunks before ranking.

## Chunking and structure preservation

Naive fixed-token splits destroy tables, numbered procedures, and cross-references. Production pipelines preserve document structure:

```python
import hashlib
from typing import Iterator

def chunk_markdown(doc_id: str, text: str, max_tokens: int = 512) -> Iterator[dict]:
    sections = split_on_headings(text)  # H1–H3 boundaries
    for path, body in sections:
        if token_count(body) <= max_tokens:
            yield make_chunk(doc_id, path, body)
            continue
        for window in sliding_windows(body, max_tokens, overlap=0.12):
            yield make_chunk(doc_id, path, window)

def make_chunk(doc_id: str, section_path: str, body: str) -> dict:
    content_hash = hashlib.sha256(body.encode()).hexdigest()
    return {
        "doc_id": doc_id,
        "section_path": section_path,
        "text": body,
        "content_hash": content_hash,
        "chunk_id": f"{doc_id}:{content_hash[:16]}",
    }
```

**Parent-child linking** stores small retrieval units while agents hydrate context from parent sections:

```sql
CREATE TABLE kb_chunks (
  chunk_id TEXT PRIMARY KEY,
  doc_id TEXT NOT NULL,
  parent_chunk_id TEXT REFERENCES kb_chunks(chunk_id),
  section_path TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  embedding_version INT NOT NULL,
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at TIMESTAMPTZ
);

CREATE INDEX idx_kb_doc ON kb_chunks(doc_id);
CREATE UNIQUE INDEX idx_kb_hash ON kb_chunks(doc_id, content_hash);
```

When retrieval returns a child chunk, the agent prompt includes the parent section up to token budget—reducing hallucinated gaps in procedures.

## Quality gates before embedding

Not every extracted page deserves vectors. Run **pre-embed gates**:

1. **Language detection** — drop or route non-primary-language docs.
2. **Boilerplate ratio** — nav/footer repetition above 30% triggers re-extraction.
3. **Duplicate detection** — MinHash or simhash against existing corpus; near-duplicates merge or supersede.
4. **PII scan** — block or redact before embed; never rely on retrieval-time filtering alone.
5. **Minimum information density** — empty headings, stub pages, and "TODO" placeholders fail.

```typescript
type GateResult = { pass: boolean; reason?: string };

export function runQualityGates(raw: ExtractedDocument): GateResult {
  if (raw.boilerplateRatio > 0.3) {
    return { pass: false, reason: "high_boilerplate" };
  }
  if (raw.tokenCount < 40) {
    return { pass: false, reason: "stub_document" };
  }
  if (raw.piiFindings.length > 0 && !raw.redacted) {
    return { pass: false, reason: "pii_unresolved" };
  }
  return { pass: true };
}
```

Failed gates land in a **curation queue** for human review—not silent drops. Owners need visibility when authoritative sources fail.

## Freshness, tombstones, and versioning

Stale vectors are worse than missing vectors: they produce confident wrong answers. Implement **tombstone propagation**:

```python
async def handle_cms_unpublish(event: dict, vector_store, db):
    doc_id = event["document_id"]
    await db.execute(
        "UPDATE kb_chunks SET expires_at = now() WHERE doc_id = $1",
        doc_id,
    )
    chunk_ids = await db.fetch("SELECT chunk_id FROM kb_chunks WHERE doc_id = $1", doc_id)
    await vector_store.delete([c["chunk_id"] for c in chunk_ids])
```

Track **embedding model version** separately from content hash. When you upgrade embedders, re-embed authoritative tier first; reference tier can lag behind a feature flag.

Expose freshness in retrieval metadata so agents (or orchestrators) can downgrade stale citations:

```python
def freshness_weight(chunk: dict, now) -> float:
    age_hours = (now - chunk["ingested_at"]).total_seconds() / 3600
    sla = chunk["max_staleness_hours"]
    if age_hours <= sla:
        return 1.0
    # linear decay after SLA; hit zero at 2x SLA
    return max(0.0, 1.0 - (age_hours - sla) / sla)
```

## Human curation workflows

Automation handles volume; humans handle judgment. Minimum workflow for authoritative content:

- **Domain owner** approves source registry entries.
- **Editor** publishes in CMS; webhook triggers ingest.
- **Curator** resolves gate failures and duplicate conflicts weekly.
- **On-call** can freeze a `source_id` during incidents ("do not cite billing FAQ until fixed").

Store curation decisions in an audit log:

```sql
CREATE TABLE kb_curation_events (
  id BIGSERIAL PRIMARY KEY,
  doc_id TEXT,
  actor TEXT NOT NULL,
  action TEXT NOT NULL,  -- approve, reject, deprecate, freeze
  reason TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);
```

Agents should never bypass freeze flags—check at retrieval time, not only at ingest.

## Evaluation harness

Ship a **golden question set** per domain with expected citation URLs and answer rubrics:

| Metric | Target (authoritative) | Alert threshold |
|--------|------------------------|-----------------|
| Citation accuracy | ≥ 95% | < 90% |
| Answer faithfulness | ≥ 92% | < 85% |
| Stale answer rate | < 2% | > 5% |
| Retrieval MRR@5 | domain-specific | −10% week/week |

```python
def eval_citation_accuracy(question: str, retrieved: list, expected_urls: set) -> float:
    cited = {c["source_uri"] for c in retrieved[:5]}
    return len(cited & expected_urls) / max(1, len(expected_urls))
```

Run eval on every embed pipeline deploy and on a schedule. Compare scores across embedding versions before full rollout.

## Security and compliance

Knowledge bases aggregate sensitive material—HR policies, security runbooks, customer data in support tickets. Apply **tenant isolation** at the chunk level: `tenant_id` on every row, enforced in retrieval middleware. Encrypt embeddings at rest if your threat model includes datastore breach.

Retention policies differ by tier: authoritative legal docs may need seven-year retention; ephemeral Slack exports should never enter the authoritative tier. Document lawful basis for personal data in ingested tickets if GDPR applies.

## Operational dashboards

Monitor:

- `kb_ingest_lag_seconds{source}` — time from publish to searchable
- `kb_gate_rejection_total{reason}` — spikes mean upstream CMS or extractor regression
- `kb_stale_chunks_count{tier}` — chunks past `expires_at` still in index (should be zero)
- `kb_duplicate_ratio` — rolling 7-day near-duplicate rate
- `kb_eval_faithfulness` — from nightly golden set

Page when authoritative stale chunk count > 0 for more than one hour—that means tombstone or expiry logic failed.

## Anti-patterns

- **Crawl the whole wiki** without ownership or tier classification.
- **Re-embed everything nightly** regardless of change—wastes compute and hides CDC bugs.
- **Chunk without section paths**—agents cannot cite precisely or hydrate parents.
- **No tombstones on unpublish**—the classic "refund policy" incident.
- **Single global embedder upgrade** without re-eval and canary tenant.

## The takeaway

Knowledge base curation is not metadata hygiene—it is the control plane for agent truthfulness. Register sources explicitly, gate quality before embedding, propagate tombstones on retraction, and measure citation accuracy against golden sets. Ingestion pipelines are commodities; curation workflows and freshness SLAs are what separate agents that cite current policy from agents that cite February.

## FAQ

### What belongs in an agent knowledge base versus general search index?

Knowledge bases hold authoritative, agent-consumable content: policies, runbooks, product specs, and support articles with explicit freshness metadata. General search indexes mix marketing pages, stale wikis, and duplicate PDFs. Curation means whitelisting sources, normalizing structure, and rejecting documents that fail quality gates before they reach embedding.

### How often should teams re-embed knowledge base content?

Re-embed on content hash change, not on a fixed calendar. Track source ETag, last-modified, or CMS publish version. Full re-index weekly is fine for small corpora; large tenants should use incremental CDC from the CMS or object store with tombstone propagation when documents retire.

### What chunking strategy works best for agent retrieval?

Hybrid: structure-aware splits on headings and tables for docs, sliding windows with 10–15% overlap for prose, parent-child linking so agents retrieve small chunks but hydrate full sections. Hard-cap token size to your embedder limit minus metadata overhead. Never chunk without storing source URI, section path, and content hash on every vector.

### How do you measure knowledge base curation quality?

Run a golden-set eval weekly: precision@k, answer faithfulness, citation accuracy, and stale-answer rate when ground truth changed in the last 30 days. Alert when any source's median chunk age exceeds its SLA or when duplicate-near-duplicate ratio crosses 5%. Production user thumbs-down on cited answers is the lagging indicator—fix the pipeline before that spikes.

## Resources

- [platform.openai.com/docs/guides/embeddings](https://platform.openai.com/docs/guides/embeddings) — OpenAI embeddings guide
- [python.langchain.com/docs/concepts/text_splitters](https://python.langchain.com/docs/concepts/text_splitters) — LangChain text splitters
- [www.llamaindex.ai/blog/evaluating-rag-systems](https://www.llamaindex.ai/blog/evaluating-rag-systems) — Evaluating RAG systems
- [docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base.html](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base.html) — Amazon Bedrock knowledge bases
- [arxiv.org/abs/2309.15217](https://arxiv.org/abs/2309.15217) — RAG survey (Gao et al.)
