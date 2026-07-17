#!/usr/bin/env python3
"""Rewrite 50 llm-p* blog posts: unique deep dives, topic FAQs, no wave2 template."""
from __future__ import annotations

import json
import re
import textwrap
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
PROGRESS = ROOT / "scripts" / "humanize-progress" / "batch-p50.json"
DATE_MOD = "2026-07-17"
TARGET_WORDS = 1200
WORD_PAT = re.compile(r"\b[\w'-]+\b")
BANNED = ("## Problem framing", "Copying a tutorial without matching your constraints")

SLUGS = [
    "llm-pci-dss-scope-reduction",
    "llm-performance-budget-ci-gate",
    "llm-personalization-signals-ranking",
    "llm-pii-tokenization-vault",
    "llm-pkce-public-clients",
    "llm-pod-security-standards",
    "llm-poison-message-detection",
    "llm-policy-as-code-opa",
    "llm-postmortem-blameless-culture",
    "llm-preemptible-workload-checkpoint",
    "llm-pricing-optimization-dynamic",
    "llm-probabilistic-early-expiration",
    "llm-producer-acknowledgment-tradeoffs",
    "llm-progressive-delivery-metrics",
    "llm-protobuf-evolution-compatibility",
    "llm-provenance-content-credentials",
    "llm-pseudo-localization-testing",
    "llm-query-plan-analysis",
    "llm-query-understanding-nlu",
    "llm-rate-limit-token-bucket",
    "llm-reconciliation-batch-jobs",
    "llm-refresh-token-rotation-detect",
    "llm-replay-attack-prevention",
    "llm-replication-lag-monitoring",
    "llm-reranker-latency-budget",
    "llm-responsible-ai-review",
    "llm-reverse-etl-activation",
    "llm-row-level-security-policies",
    "llm-runbook-as-code",
    "llm-runtime-security-falco",
    "llm-saga-orchestration-choreography",
    "llm-same-site-cookie-policy",
    "llm-sanctions-screening-api",
    "llm-sbom-generation-ci",
    "llm-scheduled-job-leader-election",
    "llm-schema-migration-zero-downtime",
    "llm-schema-registry-avro",
    "llm-scope-minimization-principle",
    "llm-screen-reader-live-regions",
    "llm-scroll-driven-animations-css",
    "llm-secrets-scanning-precommit",
    "llm-semantic-layer-metrics",
    "llm-server-components-cache-revalidate",
    "llm-serverless-cold-start-mitigation",
    "llm-service-account-least-privilege",
    "llm-service-mesh-mtls-strict",
    "llm-serving-quantization-awq-gptq",
    "llm-serving-speculative-decoding-draft",
    "llm-serving-structured-output-outlines",
    "llm-serving-tensor-parallelism",
]

# Agent posts already humanized — adapt to llm-* focus
ADAPT_FROM_AGENT = {
    "llm-sbom-generation-ci",
    "llm-scheduled-job-leader-election",
    "llm-schema-migration-zero-downtime",
    "llm-schema-registry-avro",
    "llm-scope-minimization-principle",
    "llm-screen-reader-live-regions",
    "llm-scroll-driven-animations-css",
    "llm-secrets-scanning-precommit",
    "llm-semantic-layer-metrics",
    "llm-server-components-cache-revalidate",
    "llm-serverless-cold-start-mitigation",
    "llm-service-account-least-privilege",
    "llm-service-mesh-mtls-strict",
}


def word_count(text: str) -> int:
    return len(WORD_PAT.findall(text))


def yaml_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def parse_frontmatter(raw: str) -> tuple[str, str]:
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return "", raw
    return parts[1], parts[2]


def first_heading(body: str) -> str:
    for line in body.splitlines():
        if line.startswith("## "):
            return line[3:].strip()
    return ""


def adapt_agent_post(slug: str) -> tuple[dict, str]:
    agent_slug = slug.replace("llm-", "agent-", 1)
    raw = (BLOG / f"{agent_slug}.md").read_text()
    fm, body = parse_frontmatter(raw)

    title_m = re.search(r'title:\s*"([^"]+)"', fm)
    desc_m = re.search(r'description:\s*"([^"]+)"', fm)
    pub_m = re.search(r'datePublished:\s*"([^"]+)"', fm)
    tags_m = re.search(r"tags:\n((?:\s+-\s+\"[^\"]+\"\n)+)", fm)
    tags_list = re.findall(r'-\s*"([^"]+)"', tags_m.group(1)) if tags_m else []

    title = title_m.group(1) if title_m else slug
    title = re.sub(r"^AI Agents:\s*", "", title)
    title = title.replace("Agent ", "LLM ").replace("Agents ", "LLM ")

    body = body.replace("agent-platform", "llm-platform")
    body = body.replace("agent orchestrator", "LLM gateway")
    body = body.replace("Agent orchestrator", "LLM gateway")
    body = body.replace("agent microservices", "LLM microservices")
    body = body.replace("Agent microservices", "LLM microservices")
    body = body.replace("agent runtime", "LLM runtime")
    body = body.replace("Agent eval", "LLM eval")
    body = body.replace("agent eval", "LLM eval")
    body = body.replace("agent session", "user session")
    body = body.replace("Agent session", "User session")
    body = body.replace("agent-svc", "llm-svc")
    body = body.replace("agent-api", "llm-api")
    body = body.replace("agent-", "llm-")
    body = body.replace("/agent-", "/llm-")
    body = re.sub(r"\bagent\b", "LLM service", body, flags=re.IGNORECASE)
    body = re.sub(r"\bagents\b", "LLM services", body, flags=re.IGNORECASE)

    faq = parse_faq_from_fm(fm) or faq_for_slug(slug)
    for item in faq:
        item["q"] = item["q"].replace("agent", "LLM").replace("Agent", "LLM")
        item["a"] = item["a"].replace("agent", "LLM").replace("Agent", "LLM")

    meta = {
        "title": title,
        "slug": slug,
        "description": desc_m.group(1) if desc_m else f"{title}: production patterns for LLM/RAG teams.",
        "datePublished": pub_m.group(1) if pub_m else DATE_MOD,
        "tags": tags_list[:5] if tags_list else tags_for_slug(slug),
        "keywords": slug.replace("-", ", ") + ", production, engineering",
        "faq": faq,
    }
    return meta, body.strip()


def parse_faq_from_fm(fm: str) -> list[dict]:
    if "Copying a tutorial without matching your constraints" in fm:
        return []
    faqs = []
    for m in re.finditer(
        r'- q: "((?:\\.|[^"\\])*)"\s*\n\s*a: "((?:\\.|[^"\\])*)"', fm
    ):
        faqs.append({"q": m.group(1), "a": m.group(2)})
    return faqs if len(faqs) >= 4 else []


def faq_for_slug(slug: str) -> list[dict]:
    """Topic-specific FAQ — 4+ questions per slug."""
    faqs: dict[str, list[tuple[str, str]]] = {
        "llm-pci-dss-scope-reduction": [
            ("Does sending prompts to OpenAI put us in PCI scope?", "Only if cardholder data (PAN, CVV, sensitive auth data) enters prompts, logs, embeddings, or vendor retention. Scope reduction means tokenizing at a PCI-listed vault before any LLM path sees payment data."),
            ("Can RAG over support tickets expand PCI scope?", "Yes — if tickets ever stored full card numbers and those chunks are indexed. Scrub PAN patterns at ingest, block PCI-like sequences in chunkers, and segment indexes so payment flows never feed general assistants."),
            ("What architecture minimizes PCI scope for LLM checkout assist?", "Browser → payment vault tokenization → your API stores tokens only → LLM sees redacted summaries ('card ending 4242') → logs scrub PAN regex → retention measured in days."),
            ("Do fine-tuning pipelines inherit PCI scope?", "If training data includes CHD, the training bucket, notebooks, and model artifacts become in-scope. Exclude payment text from fine-tune corpora entirely or use synthetic data."),
        ],
        "llm-performance-budget-ci-gate": [
            ("What belongs in an LLM app performance budget?", "First-token latency, total generation time, client bundle size for chat UI, embedding API p95, and RAG retrieval round-trip — not just Lighthouse scores on marketing pages."),
            ("Should CI fail on LLM latency regressions?", "Gate staging deploys on synthetic chat flows with fixed prompts and max latency thresholds. Provider variance means use relative regression vs baseline branch, not absolute SLA in CI."),
            ("How do performance budgets interact with model upgrades?", "Re-baseline budgets when swapping models — a faster 8B may beat a slower 70B on p95 even if quality differs. Track quality and latency budgets together."),
            ("Can Lighthouse CI cover LLM-heavy SPAs?", "Partially — measure shell load and hydration. Complement with custom Playwright traces that time send → first token → render complete for chat routes."),
        ],
        "llm-personalization-signals-ranking": [
            ("Which signals are safe to feed LLM rankers?", "Prefer aggregated behavior (category affinity, recency buckets) over raw PII. Hash stable IDs for cross-session joins; never put email or name into prompt context for ranking."),
            ("How do you avoid filter bubbles in LLM personalization?", "Blend exploration slots (10–20%), cap repetition of same document IDs, and log when personalization overrides diversity — product should tune this, not infra silently."),
            ("Cold start: what signals work on day one?", "Content metadata, popularity decay, locale, and explicit onboarding preferences. Delay behavioral signals until you have enough events to avoid noise."),
            ("Should personalization live in retrieval or generation?", "Retrieval — rerank and filter candidates before they hit the context window. Personalizing generation alone burns tokens on documents the user would never click."),
        ],
        "llm-pii-tokenization-vault": [
            ("Vault tokenization vs regex redaction before LLM calls?", "Regex misses context ('my number is four one four…'). Vault tokenization replaces identifiers with reversible tokens at the gateway; detokenize only on break-glass support paths."),
            ("Can vector indexes store tokenized PII?", "Tokens may still be reversible — prefer one-way hashes for lookup keys. If embeddings must include names, use format-preserving tokens and restrict index access."),
            ("How do you debug LLM failures without detokenizing logs?", "Log token IDs, field types, and correlation keys. Support tools detokenize with dual control and audit trail — never in production log pipelines."),
            ("Does tokenization satisfy GDPR right-to-erasure?", "Only if vault supports crypto-shredding or token deletion that breaks linkage. Map token lifecycle to data subject requests explicitly."),
        ],
        "llm-pkce-public-clients": [
            ("Why is PKCE mandatory for LLM mobile and SPA clients?", "Public clients cannot hold secrets. PKCE binds authorization codes to a one-time verifier, blocking interception on custom URL schemes and localhost redirects."),
            ("Should the LLM backend exchange codes on behalf of mobile apps?", "Yes — but verify code_verifier server-side. Never trust mobile-only exchange without PKCE validation even if the IdP is permissive."),
            ("Common PKCE mistakes in AI product launches?", "Reusing verifiers, storing verifiers in localStorage, sharing one OAuth client ID between SPA and confidential server apps."),
            ("Does PKCE replace refresh token rotation?", "No — PKCE protects authorization code grant. Refresh tokens still need rotation, binding, and reuse detection for long-lived LLM sessions."),
        ],
        "llm-pod-security-standards": [
            ("Which PSS profile fits GPU inference pods?", "Often baseline with restricted capabilities — read-only root FS where possible, drop ALL caps unless CUDA runtime requires specifics. Privileged inference pods are a last resort with documented exception."),
            ("How do sidecars (guardrails, tokenizers) affect pod security?", "Whole pod inherits worst case — each container needs hardened securityContext. Avoid privileged init containers that mutate model weights at runtime."),
            ("Should batch embedding jobs use different PSS than serving?", "Training/embedding may need writable volumes; still forbid privileged and hostPath. Document Pod Security Admission exemptions with expiry."),
            ("Do LLM sandboxes belong in the same namespace as inference?", "No — isolate untrusted code execution in separate namespace with deny-all network except egress proxy."),
        ],
        "llm-poison-message-detection": [
            ("What makes a queue message 'poison' in LLM pipelines?", "Repeated processing failures — malformed JSON tool output, oversized payloads crashing workers, or toxic content triggering guardrail exceptions in a loop."),
            ("DLQ vs skip-with-counter for poison messages?", "DLQ after N attempts with alert; skip-with-counter only for known benign duplicates. LLM jobs are expensive — don't retry poison 50 times burning tokens."),
            ("How do you detect poison without blocking good traffic?", "Track failure rate per message fingerprint (hash of payload schema + first 1KB). Spike on single fingerprint = poison; spike globally = upstream bug."),
            ("Should poison detection inspect LLM responses?", "Yes for async enrichment queues — if model returns unparseable structure 5× for same input hash, quarantine input and page pipeline owner."),
        ],
        "llm-policy-as-code-opa": [
            ("What policies belong in OPA for LLM gateways?", "Model allowlists, region/data residency, max token budgets per tenant, tool invocation rules, and prompt injection heuristics — things security owns cross-cutting."),
            ("How do you test Rego for LLM requests?", "Table-driven tests with fixtures: tenant tier, model, region, tool list. CI fails if disallowed model or cross-region call slips through."),
            ("Can OPA add too much latency to inference?", "Evaluate once per request at gateway — not per token. Keep bundles small, warm sidecars, target sub-5ms policy eval."),
            ("OPA vs application code for business rules?", "OPA for security/compliance gates; app code for product rules that change weekly. Don't put pricing logic in Rego."),
        ],
        "llm-postmortem-blameless-culture": [
            ("What changes in postmortems when LLM features fail?", "Include model version, prompt template hash, retrieval index generation, and token spend — not just 'API returned 500'. Hallucination incidents need content forensics."),
            ("How blameless works when prompt injection caused data exposure?", "Focus on missing controls (scope, DLP), not 'user attacked us.' Action items on gates, not on scolding the on-call engineer who merged the PR."),
            ("Should postmortems publish prompt text?", "Redact — store full prompt in restricted incident vault, public postmortem gets structure and timeline only."),
            ("Blameless vs accountability for AI launches?", "Teams own systems; individuals aren't punished for surfacing mistakes. Executives still accountable for shipping without eval gates — that's organizational, not personal blame."),
        ],
        "llm-preemptible-workload-checkpoint": [
            ("Which LLM workloads fit preemptible VMs?", "Batch embedding, offline eval suites, fine-tuning jobs — not interactive serving. Spot/preemptible saves 60–80% if checkpointing works."),
            ("How often should embedding jobs checkpoint?", "Every N shards or M minutes — whichever comes first. Persist cursor (last doc ID, batch offset) to object storage, not local disk."),
            ("Preemption during model download on startup?", "Bake models into images or cache on persistent volume. Cold start on spot without cache loses minutes every preemption."),
            ("Kubernetes spot with LLM GPU nodes?", "Use PodDisruptionBudgets for serving separately; batch jobs tolerate preemption with job-level retry and idempotent writes."),
        ],
        "llm-pricing-optimization-dynamic": [
            ("Dynamic pricing for LLM API products — what signals?", "Utilization, queue depth, model cost, tenant tier, and time-of-day. Surge pricing for premium models during peak; discounts for off-peak batch."),
            ("How to avoid surprising customers with dynamic LLM pricing?", "Cap rate changes per billing period, give 30-day notice on structural changes, show real-time cost estimate in UI before send."),
            ("Cache hits and dynamic pricing?", "If prefix cache reduces provider cost, decide whether savings pass to customer — document margin policy. Cached tokens often bill differently upstream."),
            ("Regulatory concerns with dynamic AI pricing?", "Some jurisdictions require price transparency for consumers. B2B contracts may forbid mid-contract unit price changes — encode in billing engine."),
        ],
        "llm-probabilistic-early-expiration": [
            ("Why probabilistic TTL for LLM response cache?", "Uniform expiry causes stampedes — all keys expire at :00 and thundering herd hits origin. Probabilistic early expiration spreads recompute load."),
            ("What cache entries benefit most?", "RAG retrieval results, embedding vectors for stable documents, and system prompt prefixes with long TTL."),
            ("How to tune early expiration probability?", "Start with beta distribution on remaining TTL — recompute when random draw exceeds threshold. Measure origin QPS variance vs hit rate."),
            ("Interaction with semantic cache?", "Semantic similarity cache needs version keys — probabilistic expiry on wrong embedding model version causes silent stale answers."),
        ],
        "llm-producer-acknowledgment-tradeoffs": [
            ("Kafka acks=all for LLM event pipelines?", "Use acks=all when downstream billing or audit depends on event — prompt logs, usage metering. Tolerate acks=1 only for best-effort analytics."),
            ("Tradeoff: latency vs durability for chat events?", "User-visible path can async fire-and-forget to analytics with acks=1; billing events need transactional outbox + acks=all."),
            ("Min in-sync replicas for LLM telemetry?", "min.insync.replicas=2 on production clusters — single broker ack is not durability."),
            ("Idempotency with at-least-once producers?", "Always — LLM clients retry. Consumers dedupe by (request_id, event_type) in warehouse or stream processor."),
        ],
        "llm-progressive-delivery-metrics": [
            ("Which metrics gate LLM canary deploys?", "Error rate, p95 first-token latency, guardrail block rate, eval score on golden set, and cost per request — not just HTTP 200."),
            ("Flagger vs custom analysis for model rollouts?", "Flagger works for k8s traffic split; model changes need offline eval gate before canary + online comparison of quality metrics."),
            ("How long should LLM canaries bake?", "Longer than CRUD — 24–48h to catch diurnal traffic patterns and edge prompts. Short canaries miss weekend-only use cases."),
            ("Rollback triggers for bad model deploy?", "Automated rollback on eval regression >2%, latency p95 +30%, or spike in user thumbs-down — wired to deployment controller."),
        ],
        "llm-protobuf-evolution-compatibility": [
            ("Protobuf rules for LLM gRPC serving APIs?", "Never renumber fields. Add optional fields for new generation params (temperature, max_tokens). Use oneof for polymorphic tool definitions."),
            ("How do breaking proto changes affect mobile LLM clients?", "Old apps in the wild — serve dual handlers or proto version negotiation. Breaking wire format = forced app update."),
            ("JSON transcoding for LLM REST gateways?", "Proto JSON mapping differs from typical REST — document enum and timestamp formats for SDK consumers."),
            ("Buf breaking change detection in CI?", "Run buf breaking against main for inference.proto — block PRs that rename or change field types."),
        ],
        "llm-provenance-content-credentials": [
            ("C2PA for LLM-generated images in products?", "Sign outputs with model ID, prompt hash (not raw prompt), and timestamp. Helps trust labels; not cryptographic proof against all deepfakes."),
            ("Should RAG answers carry source provenance?", "Yes — cite chunk IDs, document versions, and retrieval timestamp in structured metadata for UI and audit."),
            ("Content credentials for fine-tuning data?", "Track dataset version, license, and PII scrub pass in manifest — provenance for model cards and compliance."),
            ("User-facing vs internal provenance?", "Users see simplified 'Generated with AI' + sources; internal logs retain full credential chain for investigations."),
        ],
        "llm-pseudo-localization-testing": [
            ("Pseudo-loc before shipping LLM chat UI internationally?", "Essential — German compound strings break narrow buttons; RTL breaks streaming token layout. Pseudo-loc expands strings 30–40% to catch truncation early."),
            ("Does pseudo-loc affect LLM prompt testing?", "Test UI shell separately from model output language. Pseudo-loc validates layout; model i18n needs real locale eval sets."),
            ("Automate pseudo-loc in CI?", "Build flavor with elongated strings, screenshot diff or Playwright layout assertions on chat components."),
            ("Streaming text and pseudo-loc?", "Simulate longer tokens in mock stream to stress reflow during typewriter effect — English-length mocks hide CJK line-break bugs."),
        ],
        "llm-query-plan-analysis": [
            ("When should LLM features trigger SQL EXPLAIN reviews?", "Any new RAG metadata filter, hybrid search join, or analytics on chat logs — before production, not after slow query alerts."),
            ("pgvector + btree: common plan mistakes?", "Missing index on tenant_id + vector column — seq scan across all tenants. Analyze plans with production-scale row counts."),
            ("How do LLM-generated SQL tools affect query plans?", "Dangerous — enforce read-only role, statement timeout, and EXPLAIN-only dry-run mode for agent SQL tools."),
            ("Plan regression detection in CI?", "Record plan hash for critical queries; fail if seq scan appears where index scan existed on main."),
        ],
        "llm-query-understanding-nlu": [
            ("NLU before retrieval vs end-to-end LLM?", "Lightweight intent + entity extraction reduces bad retrievals — 'cancel subscription' shouldn't fetch billing FAQ. LLM reranks after structured routing."),
            ("How many intents for enterprise RAG?", "Start 15–30 coarse intents, merge noisy ones. Too many intents = brittle classifiers; too few = wrong retrieval bucket."),
            ("Multilingual query understanding?", "Language-id first route; per-locale intent models or multilingual embeddings with locale-specific synonyms table."),
            ("Confidence thresholds for routing?", "Below threshold → clarifying question or broad search, not forced intent. Log low-confidence for labeling loop."),
        ],
        "llm-rate-limit-token-bucket": [
            ("Token bucket vs fixed window for LLM APIs?", "Token bucket allows burst (user sends 3 quick messages) while enforcing average RPM/TPM. Fixed window causes cliff effects at window boundaries."),
            ("Limit input tokens, output tokens, or both?", "Both — output caps prevent runaway generation costs. Input caps block context stuffing attacks."),
            ("Per-user vs per-tenant vs per-API-key limits?", "Layer all three — tenant prevents one customer exhausting shared pool; user prevents one bad script inside tenant."),
            ("How to communicate rate limits in streaming APIs?", "Return 429 with Retry-After; for streams, emit error event before connection close so clients don't hang."),
        ],
        "llm-reconciliation-batch-jobs": [
            ("Why reconcile LLM usage logs vs billing?", "Provider invoices, internal meter, and Stripe often drift — async drops, retry duplicates, cached token accounting differences."),
            ("Reconciliation frequency for AI billing?", "Daily automated diff; monthly human review of unmatched rows over materiality threshold."),
            ("Idempotency keys in reconciliation?", "Match on (request_id, provider, model) — hash payloads if IDs missing from legacy paths."),
            ("What to do with systematic drift?", "Fix meter bug, issue credits, don't silently absorb — finance and eng need shared dashboard."),
        ],
        "llm-refresh-token-rotation-detect": [
            ("Refresh token rotation for long LLM chat sessions?", "Issue new refresh on each use; detect reuse as theft signal — revoke family and force re-auth."),
            ("SPA + LLM backend: where store refresh tokens?", "HttpOnly secure cookies on backend domain — not localStorage. BFF pattern exchanges tokens server-side."),
            ("Rotation grace period for mobile?", "Short overlap (30s) for parallel requests during rotation — log reuse within grace vs outside."),
            ("Detect refresh reuse with prompt injection exfil?", "If attacker steals refresh from XSS, rotation limits window — pair with SameSite cookies and CSP."),
        ],
        "llm-replay-attack-prevention": [
            ("Replay risks on LLM tool invocation APIs?", "Signed requests with timestamp + nonce — reject replays outside 5-minute skew window."),
            ("Webhooks from LLM providers?", "Verify signature per event ID; store processed IDs in Redis with TTL to dedupe retries."),
            ("Idempotency-Key header for chat completions?", "Same key within 24h returns cached response — prevents double-charge on client retries."),
            ("Nonce storage at scale?", "Bloom filter + exact set hybrid for recent window; partition by tenant."),
        ],
        "llm-replication-lag-monitoring": [
            ("Why replication lag matters for RAG?", "Stale replica serves old document index metadata — user asks about new policy, RAG retrieves superseded chunk."),
            ("Lag SLI for read replicas behind LLM features?", "Alert when lag >30s for metadata DB; >5min for analytics replicas feeding eval dashboards."),
            ("Prompt cache vs DB lag?", "Separate concerns — cache invalidation must tie to write primary success, not replica catch-up."),
            ("Postgres logical replication for multi-region LLM?", "Route writes to primary region; reads local with lag-aware routing for strong consistency paths."),
        ],
        "llm-reranker-latency-budget": [
            ("How much latency budget for cross-encoder rerank?", "Typical RAG: 200–400ms for top-20 rerank on CPU; GPU batch if p95 matters. Total retrieval+rerank often capped at 500ms."),
            ("Rerank top-K vs rerank all retrieved?", "Rerank 20–50 max — linear cost in cross-encoders. Two-stage: bi-encoder retrieves 100, cross-encoder reranks 25."),
            ("Skip rerank when?", "Low-stakes FAQ with high bi-encoder confidence; latency SLO under 200ms total."),
            ("Measure rerank in production?", "Span per stage: embed query, vector search, rerank, assemble context — tail latency often lives in rerank batch queue."),
        ],
        "llm-responsible-ai-review": [
            ("What triggers responsible AI review before launch?", "New use case touching healthcare, minors, hiring, credit, or automated decisions — plus any customer-facing persona with emotional dependency."),
            ("RAI review vs security review?", "Security asks 'can it be hacked'; RAI asks 'should we ship it' — harm scenarios, bias evals, human oversight plan."),
            ("Documentation for RAI gate?", "Model card, intended use, out-of-scope uses, eval results on demographic slices, escalation path to human."),
            ("Who signs off?", "Cross-functional — legal, policy, eng, product. Not just the ML lead."),
        ],
        "llm-reverse-etl-activation": [
            ("Reverse ETL for LLM product analytics?", "Sync warehouse segments (power users, churn risk) to CRM or feature flags — trigger proactive assistant tips, not spam."),
            ("Hightouch/Census + LLM feature flags?", "Activate 'show copilot' for accounts with high support ticket volume — data from dbt model to LaunchDarkly."),
            ("PII in reverse ETL to SaaS?", "Hash or tokenize before sync; map only fields needed for activation."),
            ("Latency expectations?", "Hourly sync fine for marketing activation; real-time needs stream — don't block chat on warehouse freshness."),
        ],
        "llm-row-level-security-policies": [
            ("RLS for multi-tenant RAG metadata?", "Postgres RLS on documents table by tenant_id — connection sets app.current_tenant from JWT. Prevents retrieval SQL bugs from cross-tenant leak."),
            ("RLS vs application-level filtering?", "Defense in depth — RLS catches ORM mistakes. App still filters for performance."),
            ("Service account bypass for embedding jobs?", "Separate role with BYPASSRLS only for batch indexer with audit — not for online serving connection pool."),
            ("Testing RLS?", "Integration tests connect as tenant A, assert tenant B rows invisible — run in CI."),
        ],
        "llm-runbook-as-code": [
            ("Runbooks as code for LLM incidents?", "Markdown in repo + executable scripts linked from runbook — 'high token spend' runbook runs cost attribution query."),
            ("Version runbooks with deploys?", "When model or prompt version changes, runbook references specific rollback commands — git blame for ops docs."),
            ("Automated runbook triggers?", "Alert fires → optional auto-remediation (disable model via flag) → human follows doc for root cause."),
            ("Runbook linting?", "Check links, required sections (symptom, verify, mitigate, escalate), and that on-call rotation in PagerDuty matches doc owner."),
        ],
        "llm-runtime-security-falco": [
            ("Falco rules for LLM inference pods?", "Detect unexpected shell spawn, outbound connections to non-allowlisted domains, and sensitive file reads (/etc/shadow, cloud metadata)."),
            ("False positives on model load?", "Whitelist read patterns for /models/* and known CUDA libs — tune rules per base image."),
            ("Falco vs Pod Security Admission?", "PSA prevents bad config at admit; Falco detects runtime drift (crypto miner dropped in)."),
            ("Response to Falco LLM alerts?", "Isolate pod network, snapshot memory if policy allows, rotate credentials — don't kill silently without triage."),
        ],
        "llm-saga-orchestration-choreography": [
            ("Saga for multi-step LLM workflows?", "Long flows (research → draft → approve → send) need compensating actions — cancel draft if send fails, don't leave orphan records."),
            ("Orchestration vs choreography for RAG pipelines?", "Orchestrator for user-visible flows with deadlines; choreography (events) for async indexing pipeline stages."),
            ("Saga state and LLM non-determinism?", "Persist model outputs at each step — replay compensation with stored text, not re-call model."),
            ("Temporal for LLM sagas?", "Good fit — durable timers, human approval signals, visibility UI for stuck workflows."),
        ],
        "llm-same-site-cookie-policy": [
            ("SameSite for LLM session cookies?", "Lax for session on same site; None+Secure only if cross-site embed — avoid None if chat is same-origin."),
            ("Cross-site widget embedding chat?", "If marketing site embeds assistant on different subdomain, configure cookie Domain and SameSite explicitly — test Safari ITP."),
            ("SameSite and OAuth state cookies?", "Strict or Lax on state/nonce cookies to block CSRF on OAuth callback."),
            ("Partitioned cookies (CHIPS) for third-party LLM widgets?", "Third-party embed context may need Partitioned attribute — test login persistence."),
        ],
        "llm-sanctions-screening-api": [
            ("When must LLM fintech flows call sanctions API?", "Before onboarding, before outbound payments, and before executing agent-initiated transfers — not after."),
            ("Screening LLM-extracted names from documents?", "OCR + NER names still need OFAC/sanctions list match — model extraction is not compliance."),
            ("False positive handling in automated flows?", "Queue for human review; don't auto-block forever on fuzzy name match without audit trail."),
            ("Latency budget for sanctions in chat UX?", "Pre-cache frequent checks; async for non-blocking paths; sync only when legally required before transaction commit."),
        ],
        "llm-sbom-generation-ci": [
            ("Why SBOM in CI for LLM services?", "Python deps, CUDA base images, model weights, and tokenizer libs carry CVEs — SBOM diff on every PR catches supply chain drift."),
            ("Include model weights in SBOM?", "Yes — manual CycloneDX component with SHA256 and HuggingFace revision; auto scanners miss .safetensors."),
            ("Fail build on critical CVE in torch?", "Gate with waivers and expiry — ML stacks lag patches; document accepted risk vs silent ignore."),
            ("SPDX vs CycloneDX for LLM?", "CycloneDX for CI tooling; convert to SPDX for enterprise procurement if required."),
        ],
        "llm-scheduled-job-leader-election": [
            ("Why not run embedding refresh on every replica?", "Duplicate jobs multiply GPU cost and can corrupt indexes — one leader per schedule tick."),
            ("Postgres advisory lock vs Redis for LLM cron?", "Postgres if you already depend on it and jobs run every few minutes; Redis for faster failover with proper fencing."),
            ("Leader dies mid embedding job?", "Checkpoint shards; idempotent index writes; or use queue where leader only enqueues one message."),
            ("K8s Lease API for LLM batch?", "Native on cluster — holderIdentity ties to pod; renewTime visible in kubectl."),
        ],
        "llm-schema-migration-zero-downtime": [
            ("Zero-downtime migration for chat history tables?", "Expand-contract: add nullable column, dual-write, backfill, switch reads, drop old — never block writes during LLM peak hours."),
            ("Migrating vector column dimensions?", "New column or table, re-embed in background, blue/green index swap — in-place ALTER on 10M vectors is downtime."),
            ("Lock timeouts during migration?", "Use gh-ost or pg_repack patterns; LLM apps hold long connections — set lock_timeout low and retry."),
            ("Feature flags for schema-dependent code?", "Deploy readers tolerant of old+new schema before migration step — roll forward safely."),
        ],
        "llm-schema-registry-avro": [
            ("Avro for LLM event streaming?", "Usage events, audit logs, and eval results benefit from schema evolution — backward compatible readers on Kafka."),
            ("Schema for nested tool call payloads?", "Use records with optional fields; avoid breaking rename on tool_name — add alias in schema."),
            ("Registry compatibility mode?", "BACKWARD for consumers upgrading first; FULL for strict pipelines — pick per topic."),
            ("JSON schema for LLM outputs vs Avro events?", "Different layers — Avro for telemetry bus; JSON Schema for model output validation at API."),
        ],
        "llm-scope-minimization-principle": [
            ("Scope minimization for LLM tool APIs?", "Each session gets minimum tools — research read-only, executor one write tool. Default deny at dispatch layer."),
            ("Scope in system prompt enough?", "No — models ignore under injection. Enforce in code before tool execution."),
            ("User admin → LLM admin mistake?", "Derive capabilities from user permissions intersected with task intent — not full admin graph."),
            ("OAuth downscoped tokens for LLM?", "Mint 30-minute tokens with narrow scopes per session — never pass user refresh token to runtime."),
        ],
        "llm-screen-reader-live-regions": [
            ("Live regions for streaming LLM tokens?", "aria-live='polite' on response container — throttle updates (300ms) or screen readers interrupt constantly."),
            ("Assertive vs polite for errors?", "Errors and guardrail blocks: assertive once; streaming content: polite."),
            ("Chat history and virtualized lists?", "Announce new message on send complete, not every token — balance accessibility vs noise."),
            ("Testing with NVDA/VoiceOver?", "Automated aXe catches missing live regions; manual test required for streaming cadence."),
        ],
        "llm-scroll-driven-animations-css": [
            ("Scroll-driven animations for LLM marketing pages?", "CSS scroll-timeline for reveal effects without JS scroll listeners — better INP on doc-heavy landing pages."),
            ("Progress bar for long generation?", "Prefer determinate progress from server events; scroll-linked animations decorative only."),
            ("Fallback without scroll-timeline?", "@supports guard — static layout for Firefox older builds."),
            ("Performance on mobile doc pages?", "GPU-friendly properties only (transform, opacity); avoid animating height during scroll."),
        ],
        "llm-secrets-scanning-precommit": [
            ("Pre-commit secret scan for LLM repos?", "Block OpenAI keys, HuggingFace tokens, and .env in commits — gitleaks/trufflehog in hook."),
            ("False positives on test fixtures?", "Allowlist hashed secrets in tests; never real keys even 'revoked.'"),
            ("Scan prompt templates?", "Templates sometimes embed example API keys — use placeholders only."),
            ("CI vs pre-commit?", "Both — pre-commit catches early; CI catches --no-verify bypass with full history scan on main."),
        ],
        "llm-semantic-layer-metrics": [
            ("Semantic layer for LLM usage metrics?", "dbt metrics on token spend, latency p95, eval pass rate — single definition for BI and exec dashboards."),
            ("Metric grain for AI products?", "Per tenant, model, feature flag, and prompt_version — avoid unsliceable aggregates."),
            ("Semantic layer vs raw OpenTelemetry?", "OTel for ops realtime; semantic layer for business metrics with tested SQL and lineage."),
            ("Cube/MetricFlow with LLM data?", "Expose same metrics to natural-language BI tools with guardrails — validated metrics only."),
        ],
        "llm-server-components-cache-revalidate": [
            ("revalidateTag for LLM admin dashboards?", "Tag cached RSC segments by model config version — invalidate on prompt deploy without full site rebuild."),
            ("Cache personalized chat in RSC?", "Don't — cache static shell, stream dynamic chat client-side or via Route Handler."),
            ("revalidatePath after CMS update for RAG docs?", "Trigger webhook from CMS to revalidate doc pages and bust retrieval cache key."),
            ("Stale-while-revalidate for public AI docs?", "Yes for marketing content; no for compliance text without version indicator."),
        ],
        "llm-serverless-cold-start-mitigation": [
            ("Cold starts on LLM proxy Lambdas?", "Provisioned concurrency on hot paths; keep model on dedicated GPU service — don't run inference in Lambda."),
            ("Minimize cold start for auth BFF?", "Smaller bundle, esbuild tree-shake, avoid importing full SDK — init duration dominates without GPU."),
            ("SnapStart for Java LLM gateways?", "If stuck on JVM stack — SnapStart helps; Python/Node prefer slim handlers."),
            ("Warmup pings ethical?", "Scheduled EventBridge ping acceptable for SLA; document cost vs user-facing latency."),
        ],
        "llm-service-account-least-privilege": [
            ("LLM service account sprawl?", "Separate SA for inference, indexing, and admin — not one god SA for all k8s workloads."),
            ("Cloud IAM for S3 model buckets?", "Inference SA read-only on model path; training SA write to staging prefix only."),
            ("Workload Identity binding?", "One K8s SA → one GCP/AWS IAM role — map minimally per deployment."),
            ("Rotate SA keys?", "Prefer workload identity over long-lived keys; if keys exist, 90-day rotation automated."),
        ],
        "llm-service-mesh-mtls-strict": [
            ("STRICT mTLS between LLM microservices?", "Orchestrator, retrieval, embedding, guardrail — east-west carries session context; encrypt and authenticate every hop."),
            ("PERMISSIVE migration steps?", "Inject sidecars, verify 100% mTLS traffic metric, flip STRICT in staging, then prod."),
            ("Sandbox pods in mesh?", "Isolate untrusted execution outside mesh or DENY all except egress gateway."),
            ("Debug mTLS without disabling?", "Kiali metrics, istioctl analyze — never global PERMISSIVE in prod as permanent fix."),
        ],
        "llm-serving-quantization-awq-gptq": [
            ("AWQ vs GPTQ for production LLM serving?", "AWQ often better accuracy at 4-bit on recent GPUs; GPTQ broader tooling support. Benchmark your model on target hardware."),
            ("When not to quantize?", "Small models already fit FP16 with headroom — quantization ops add complexity for marginal gain."),
            ("Quantization and structured output?", "Validate JSON/schema adherence post-quant — some models degrade format compliance at 4-bit."),
            ("vLLM/TGI quantization flags?", "Load AWQ/GPTQ checkpoints natively — don't quantize at runtime on every pod start."),
        ],
        "llm-serving-speculative-decoding-draft": [
            ("Speculative decoding when worth it?", "When draft model is much faster and acceptance rate >60% — good for 70B + 7B draft pairs on same GPU pool."),
            ("Draft model selection?", "Same tokenizer family preferred; smaller model trained similarly — random small model may reject everything."),
            ("Latency vs throughput tradeoff?", "Spec decode helps per-request latency on large models; batch-heavy workloads may prefer continuous batching alone."),
            ("Measure acceptance rate?", "Metric rejected_tokens / draft_tokens — tune draft size if rate collapses."),
        ],
        "llm-serving-structured-output-outlines": [
            ("Outlines vs JSON mode for LLM APIs?", "Outlines/grammar constraints guarantee syntax — JSON mode is best-effort on some models. Use FSM-backed generation for parsers."),
            ("Regex outlines for tool calls?", "Define tool argument grammar in Outlines or lm-format-enforcer — reduces retry loops on malformed JSON."),
            ("Performance cost of constrained decoding?", "Small overhead vs free generation — usually cheaper than retry + re-prompt on parse failure."),
            ("Compatibility with streaming?", "Partial JSON streaming possible with incremental parsers — full constraint harder mid-stream."),
        ],
        "llm-serving-tensor-parallelism": [
            ("When tensor parallelism required?", "Model too large for single GPU memory — split layers across 2–8 GPUs on same node."),
            ("TP vs pipeline parallelism?", "TP for low-latency interactive; PP for very deep models where TP communication dominates."),
            ("NVLink requirement?", "TP all-reduce across PCIe is slow — prefer A100/H100 NVLink pairs for production TP."),
            ("Tensor parallel size and batching?", "vLLM TP size must divide head count; scale replicas for QPS, TP for model fit."),
        ],
    }
    items = faqs.get(slug, [])
    if len(items) < 4:
        topic = slug.replace("llm-", "").replace("-", " ")
        items = [
            (f"What problem does {topic} solve in LLM production?", f"It closes gaps where failures appear as cost spikes, latency regressions, or compliance findings — not clear error messages."),
            (f"When should teams implement {topic}?", "Before scaling traffic or passing enterprise security review — retrofitting is expensive."),
            (f"How do we verify {topic} works?", "Define leading metrics (deny rate, cache hit, lag seconds) and lagging metrics (incidents, invoice drift)."),
            (f"Smallest useful slice of {topic}?", "One service, one environment, with rollback and observability before fleet-wide rollout."),
        ]
    return [{"q": q, "a": a} for q, a in items[:5]]


def title_for_slug(slug: str) -> str:
    special = {
        "llm-pci-dss-scope-reduction": "PCI DSS Scope Reduction for LLM Payment Flows",
        "llm-performance-budget-ci-gate": "Performance Budget CI Gates for LLM Applications",
        "llm-pii-tokenization-vault": "PII Tokenization Vaults Before LLM Inference",
        "llm-pkce-public-clients": "PKCE for Public LLM Client Applications",
        "llm-pod-security-standards": "Pod Security Standards for LLM Inference Workloads",
        "llm-policy-as-code-opa": "Policy-as-Code with OPA for LLM Gateways",
        "llm-sbom-generation-ci": "SBOM Generation in CI for LLM Services",
        "llm-serving-quantization-awq-gptq": "AWQ and GPTQ Quantization for LLM Serving",
        "llm-serving-speculative-decoding-draft": "Speculative Decoding with Draft Models in Production",
        "llm-serving-structured-output-outlines": "Structured Output with Outlines and Grammar Constraints",
        "llm-serving-tensor-parallelism": "Tensor Parallelism for Large Model Serving",
    }
    if slug in special:
        return special[slug]
    core = slug.replace("llm-", "").replace("-", " ")
    return " ".join(w.upper() if w in ("pci", "dss", "pii", "pkce", "opa", "sbom", "mtls", "nlu", "avro", "awq", "gptq", "css", "ci") else w.title() for w in core.split())


def desc_for_slug(slug: str, title: str) -> str:
    descs = {
        "llm-pci-dss-scope-reduction": "Keep cardholder data out of LLM prompts, logs, and RAG indexes: tokenization boundaries, network segmentation, and audit evidence that satisfies QSA reviews.",
        "llm-performance-budget-ci-gate": "Enforce first-token latency, bundle size, and RAG round-trip budgets in CI with Playwright traces and regression gates before LLM features ship.",
        "llm-poison-message-detection": "Detect and quarantine poison messages in LLM async pipelines: DLQ patterns, fingerprint-based failure tracking, and stopping token-burn retry loops.",
        "llm-serving-tensor-parallelism": "Split oversized models across GPUs with tensor parallelism: NVLink topology, vLLM configuration, and when TP beats pipeline or replica scaling.",
    }
    return descs.get(slug, f"{title}: production patterns, tradeoffs, and operational guidance for LLM/RAG teams at scale.")


def tags_for_slug(slug: str) -> list[str]:
    prefix_map = {
        "pci": ["Security", "Compliance", "LLM"],
        "pii": ["Security", "Privacy", "LLM"],
        "pkce": ["Security", "OAuth", "LLM"],
        "pod": ["Kubernetes", "Security", "LLM"],
        "sbom": ["Security", "CI/CD", "LLM"],
        "serving": ["ML Ops", "Inference", "LLM"],
        "schema": ["Database", "Backend", "LLM"],
        "server": ["Web", "Next.js", "LLM"],
        "scroll": ["Web", "CSS", "Frontend"],
        "screen": ["Accessibility", "Frontend", "LLM"],
        "semantic": ["Data", "Analytics", "LLM"],
        "saga": ["Architecture", "Backend", "LLM"],
        "sanctions": ["Compliance", "Fintech", "LLM"],
    }
    key = slug.split("-")[1] if slug.startswith("llm-") else "llm"
    return prefix_map.get(key, ["LLM", "Production", "Engineering"])


def body_for_slug(slug: str) -> str:
    """Generate unique body via topic-specific builder."""
    try:
        from _rewrite_p50_bodies import build_body  # noqa: WPS433

        return build_body(slug)
    except ImportError:
        from humanize_batch_08 import build_body as fallback_build  # noqa: WPS433
        from humanize_batch_08 import domain_for, title_from_slug

        return fallback_build(slug, title_from_slug(slug), domain_for(slug))


def _expand_body(slug: str, body: str) -> str:
    try:
        from _rewrite_p50_bodies import expand_body  # noqa: WPS433

        return expand_body(slug, body)
    except ImportError:
        from humanize_batch_08 import expand_to_target, domain_for, title_from_slug

        return expand_to_target(
            body, title_from_slug(slug), slug, domain_for(slug), TARGET_WORDS
        )


def build_frontmatter(meta: dict) -> str:
    tags = "\n".join(f'  - "{yaml_escape(t)}"' for t in meta["tags"])
    faqs = "\n".join(
        f'  - q: "{yaml_escape(f["q"])}"\n    a: "{yaml_escape(f["a"])}"'
        for f in meta["faq"]
    )
    return f"""---
title: "{yaml_escape(meta['title'])}"
slug: "{meta['slug']}"
description: "{yaml_escape(meta['description'])}"
datePublished: "{meta['datePublished']}"
dateModified: "{DATE_MOD}"
tags:
{tags}
keywords: "{yaml_escape(meta['keywords'])}"
faq:
{faqs}
---"""


def process_slug(slug: str) -> dict:
    path = BLOG / f"{slug}.md"
    if not path.exists():
        return {"slug": slug, "status": "skipped", "words": 0, "reason": "missing_file"}

    if slug in ADAPT_FROM_AGENT:
        meta, body = adapt_agent_post(slug)
        if word_count(body) < TARGET_WORDS:
            body = _expand_body(slug, body)
    else:
        old_fm, _ = parse_frontmatter(path.read_text())
        pub_m = re.search(r'datePublished:\s*"([^"]+)"', old_fm)
        meta = {
            "title": title_for_slug(slug),
            "slug": slug,
            "description": desc_for_slug(slug, title_for_slug(slug)),
            "datePublished": pub_m.group(1) if pub_m else DATE_MOD,
            "tags": tags_for_slug(slug),
            "keywords": slug.replace("-", ", ") + ", production, engineering",
            "faq": faq_for_slug(slug),
        }
        body = body_for_slug(slug)

    full = build_frontmatter(meta) + "\n" + body.strip() + "\n"
    banned_hit = any(b in full for b in BANNED)
    wc = word_count(full)

    if wc < TARGET_WORDS:
        body = _expand_body(slug, body)
        full = build_frontmatter(meta) + "\n" + body.strip() + "\n"
        wc = word_count(full)

    path.write_text(full, encoding="utf-8")
    return {
        "slug": slug,
        "status": "rewritten",
        "words": wc,
        "first_heading": first_heading(body),
        "banned_template": banned_hit,
    }


def main():
    PROGRESS.parent.mkdir(parents=True, exist_ok=True)
    results = []
    rewritten = skipped = 0
    for slug in SLUGS:
        r = process_slug(slug)
        results.append(r)
        if r["status"] == "rewritten":
            rewritten += 1
        else:
            skipped += 1

    samples = [
        {"slug": r["slug"], "words": r["words"], "first_heading": r.get("first_heading", "")}
        for r in results
        if r["status"] == "rewritten"
    ][:8]

    summary = {
        "rewritten": rewritten,
        "skipped": skipped,
        "samples": samples,
        "under_1200": [r for r in results if r.get("words", 0) < TARGET_WORDS],
    }
    PROGRESS.write_text(json.dumps({"results": results, "summary": summary}, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    if summary["under_1200"]:
        raise SystemExit(f"{len(summary['under_1200'])} posts under {TARGET_WORDS} words")


if __name__ == "__main__":
    main()
