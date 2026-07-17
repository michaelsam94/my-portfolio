---
title: "RAG: Dead Letter Queue Handling"
slug: "rag-dead-letter-queue-handling"
description: "Dead letter queue patterns for RAG ingestion and async pipelines — classification, replay safety, poison message isolation, and operator workflows."
datePublished: "2024-11-10"
dateModified: "2026-07-17"
tags: ["AI", "Rag", "Dead"]
keywords: "rag, dead, letter, queue, ai, production, engineering, architecture"
faq:
  - q: "When should a failed RAG ingestion message go to the DLQ instead of retrying?"
    a: "After exhausting bounded retries with exponential backoff, when the failure is non-transient (schema validation, unsupported MIME type, auth permanently revoked), or when retrying would amplify cost (repeated embedding API calls on a 50MB corrupt PDF). Transient network blips should retry in-place; structural problems should land in the DLQ quickly."
  - q: "How do you replay DLQ messages without duplicating vectors?"
    a: "Use deterministic document IDs derived from source URI plus content hash. Upserts replace existing vectors; replays become idempotent. Log replay batch IDs and require explicit operator approval for bulk replays exceeding a threshold."
  - q: "What metadata belongs on every DLQ envelope?"
    a: "Original payload reference, failure reason code, stack trace or API error body, retry count, first-failure timestamp, pipeline stage (parse, chunk, embed, upsert), corpus ID, and tenant ID. Without stage and corpus, operators cannot prioritize or route fixes."
---
At 2 a.m. the embedding queue depth flatlined—not because ingestion caught up, but because three thousand PDF parse failures were retried until they exhausted max attempts and vanished. No alert fired. The DLQ existed as a Kafka topic name in a diagram, but nothing consumed it, classified failures, or prevented the same broken export from re-entering the pipeline every nightly sync. By morning, half the legal corpus was missing from the index and nobody knew which documents failed or why.

Dead letter queues are not a graveyard for sad messages. In RAG ingestion—document fetch, parse, chunk, embed, upsert—they are the control plane for poison messages, schema drift, and upstream data quality regressions. Treat the DLQ as a first-class product surface with schemas, dashboards, replay tooling, and ownership, not as a default topic config you set once in Terraform.

## Where DLQs sit in RAG pipelines

Typical async ingestion fans out across stages, each with different failure semantics:

```
[Source sync] → [Parse/OCR] → [Chunk] → [Embed] → [Upsert index]
                    ↓              ↓         ↓           ↓
                  DLQ-parse    DLQ-chunk  DLQ-embed  DLQ-upsert
```

A monolithic DLQ hides whether failures are fixable (bad OCR on one scan) or systemic (embedding API quota exhausted). Stage-specific DLQs—or a unified DLQ with a mandatory `stage` attribute—let operators filter and batch-fix.

Messages should enter the DLQ with structured failure codes, not raw exception strings:

| Code | Meaning | Typical action |
|------|---------|----------------|
| `PARSE_UNSUPPORTED_MIME` | File type not in allowlist | Skip or extend parser |
| `PARSE_PASSWORD_PROTECTED` | Encrypted PDF | Request unlocked export |
| `CHUNK_EMPTY` | Zero tokens after strip | Inspect source or OCR |
| `EMBED_RATE_LIMIT` | 429 from provider | Delayed replay |
| `EMBED_CONTEXT_LENGTH` | Chunk exceeds model limit | Re-chunk with smaller window |
| `UPSERT_CONFLICT` | Version mismatch on ID | Reconcile index state |

## Retry policy before the DLQ

Retries belong in the hot path; the DLQ is the terminal state after retries are exhausted. For RAG workloads:

- **Transient failures** (network timeout, 503 from embedding API): retry 3–5 times with full jitter, cap total retry window at 15–30 minutes.
- **Rate limits**: respect `Retry-After` headers; use a delay queue rather than burning retry budget immediately.
- **Permanent failures** (validation, auth): fail fast to DLQ on first attempt—retries waste money and obscure dashboards.

Embedding a 200-page PDF costs real dollars. Retry budgets should be per-message and per-tenant, with circuit breakers when error rates spike across a corpus sync batch.

## DLQ envelope schema

Standardize the wrapper so tooling works across corpora:

```json
{
  "dlq_id": "dlq_01J8XK2M4N",
  "original_topic": "rag.ingest.chunked",
  "stage": "embed",
  "corpus_id": "legal-contracts-us",
  "tenant_id": "acme-corp",
  "document_ref": "s3://corpus/legal/2025/NDA-template-v4.pdf",
  "content_hash": "sha256:9f3c...",
  "attempt_count": 5,
  "first_failed_at": "2026-07-16T22:14:03Z",
  "last_failed_at": "2026-07-16T22:47:11Z",
  "failure_code": "EMBED_CONTEXT_LENGTH",
  "failure_detail": "Chunk 847 exceeded 8192 token limit (9214 tokens)",
  "payload_ref": "s3://dlq/payloads/01J8XK2M4N.json"
}
```

Store large payloads in object storage; the DLQ message carries a pointer. Kafka message size limits are not your friend when failed payloads include base64 attachments.

## Poison message detection

A poison message fails every consumer that touches it—often because of a parser bug triggered by one malformed file, not because the file itself is unprocessable. Signals:

- Same `document_ref` appears in DLQ from multiple consumer instances with identical stack traces.
- DLQ rate spikes correlated with a single upstream export batch ID.
- Replay attempts fail with the same error within seconds.

Quarantine poison suspects in a `DLQ-quarantine` topic after two identical replay failures. Open a ticket automatically with the stack trace and sample payload hash. Do not auto-replay quarantined messages until a code fix ships.

## Replay workflows operators actually use

Replay is dangerous without guardrails. Duplicated vectors waste storage; wrong replays during an incident amplify load on an already failing embedding endpoint.

Safe replay checklist:

1. **Filter** by `failure_code`, `corpus_id`, and time window—never blind full-topic replay.
2. **Dry-run** count: how many messages, estimated embedding cost, expected duration.
3. **Idempotency keys**: document ID = hash(source URI + content hash + chunk index).
4. **Rate limit** replay throughput to a fraction of normal ingestion capacity.
5. **Audit log** who approved replay, which filter, how many succeeded/failed.

```python
def replay_filter(messages, *, codes: set[str], since: datetime, corpus: str):
    eligible = [
        m for m in messages
        if m["failure_code"] in codes
        and m["corpus_id"] == corpus
        and m["first_failed_at"] >= since.isoformat()
    ]
    return eligible  # operator confirms count before publish to replay topic
```

Provide a CLI and a minimal internal UI. Engineers will not SSH into Kafka during incidents if the tooling requires six manual steps.

## Observability and alerting

Metrics that matter:

- `dlq_messages_total` by stage, failure_code, corpus_id
- `dlq_age_seconds` p95 — how long messages sit unprocessed
- `dlq_replay_success_rate`
- Ratio of DLQ volume to successful ingest volume (spike = upstream regression)

Alert when DLQ insert rate exceeds baseline for 15 minutes, when any customer-facing corpus has >1% of a sync batch in DLQ, or when `dlq_age_seconds` p95 exceeds your SLA (e.g., 24 hours for non-critical corpora, 4 hours for production support KB).

Dashboards should show sample failure_detail strings—not aggregated counts alone. Operators need to see "9214 tokens" not just `EMBED_CONTEXT_LENGTH: 847`.

## Security and tenancy

DLQ payloads may contain document excerpts, API keys in error bodies, or PII from failed redaction steps. Encrypt DLQ topics at rest, restrict consume permissions to pipeline operators, and redact secrets in `failure_detail` before persistence.

Multi-tenant RAG must tag every DLQ message with `tenant_id`. Replay tooling enforces tenant-scoped filters so one operator cannot accidentally re-ingest another tenant's quarantined documents into a shared index namespace.

## DLQ-driven quality loops

The DLQ is a free data quality signal. Weekly, aggregate top failure codes per corpus and feed them back to source system owners: "412 PDFs failed OCR this month—your scanner settings changed." Product teams prioritize parser support for MIME types that accumulate volume.

Close the loop in sprint planning. If `CHUNK_EMPTY` dominates a corpus, fix OCR upstream rather than adding retry hacks downstream.

A well-run DLQ turns silent data loss into visible, actionable backlog. The legal corpus incident ends when parse failures surface in a dashboard within minutes, carry enough context to fix without archaeology, and replay safely without duplicating half your vector index.

## Prioritization and SLA tiers

Not every DLQ message deserves equal urgency. Tag messages with **business tier** at ingest: `tier=0` for executive-facing corpora pages on four-hour replay SLA; `tier=2` for experimental indexes reviewed weekly. Operators sort dashboards by `tier`, `failure_code`, and `dlq_age_seconds`—not FIFO, which leaves critical legal sync failures buried under bulk OCR noise.

Automated triage rules route `EMBED_RATE_LIMIT` to delayed replay queues with exponential scheduling, while `PARSE_PASSWORD_PROTECTED` opens tickets to source system owners with document URI and contact from connector config. Reduce human toil for predictable failure classes.

## Metrics that justify DLQ investment

Finance asks why you run separate Kafka topics and a replay UI. Answer with **prevented duplicate embedding cost** (replay idempotency vs blind re-ingest), **mean time to detect corpus gap** (DLQ alert vs user report), and **percentage of sync batches with >0.1% DLQ rate** trending down as parsers improve. DLQ is insurance with receipts—show the claims you did not pay because poison messages never reached the index silently.

## Integration with on-call rotations

Page DLQ burn rate alerts to the **corpus owner team**, not generic infra on-call, when `failure_code` indicates source data issues (`PARSE_PASSWORD_PROTECTED`, `CHUNK_EMPTY`). Platform on-call handles broker outages and consumer lag. Routing rules in PagerDuty/Opsgenie parse DLQ envelope JSON from alert payload—wrong routing wastes minutes during sync incidents.

Run **monthly DLQ game days**: inject synthetic poison messages into staging, verify alert fires, replay succeeds, and ledger prevents duplicate index entries. Game day results feed reliability OKRs with pass/fail criteria documented in Confluence or internal wiki linked from runbooks.
