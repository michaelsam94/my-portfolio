"""Rich topic builders for llm-p50."""
from __future__ import annotations
import textwrap

def _T(s): return textwrap.dedent(s).strip()

BUILDERS_PART2 = {
    "llm-pci-dss-scope-reduction": lambda: _T("""The QSA asked one question that stalled the LLM checkout assistant for six weeks: "Show us where cardholder data can enter the prompt path." PCI DSS scope reduction for LLM features is not "we don't store PAN" — it is proving PAN cannot reach prompts, logs, embeddings, fine-tuning corpora, or vendor retention through any path you operate.

## Scope follows data, not intentions

PCI scope is about cardholder data (CHD) and sensitive authentication data. If those values touch a system, that system and connected dependencies enter scope. LLM integrations create new paths: users paste card numbers into chat, support RAG retrieves old tickets with PAN in free text, debug logs capture request bodies, and agents OCR payment screenshots.

Scope reduction means architectural denial: CHD never enters LLM-adjacent systems.

## Reference architecture

Browser flows to a PCI-listed vault for tokenization. Your API stores token only. LLM path sees "Visa ending 4242." Logs carry token ID and last4, never PAN regex matches. RAG indexes exclude payment-intent namespaces entirely.

## RAG and fine-tuning landmines

Support ticket RAG is the silent scope expander. Scrub PAN patterns at ingest with tested regex and block payment namespaces from general indexes. Fine-tuning on ticket exports without scrubbing pulls CHD into training buckets and model artifacts — all in scope.

## Logging discipline

Structured logs must scrub PAN-like sequences. Default deny prompt logging; break-glass with TTL and dual control. OpenTelemetry spans carry payment_token_id, not raw fields.

## Vendor APIs

Using OpenAI or Anthropic does not automatically scope them — you remain responsible for what you send. Contract review must cover retention, training opt-out, and subprocessors.

## Evidence for audits

Maintain data-flow diagrams with vault boundaries, sample redacted logs, RAG ingest policy, and pentest results on "paste PAN in chat" scenarios.

## Gateway enforcement

Reject requests matching PAN heuristics, route payment questions to non-LLM flows, monitor payment_data_blocked_total. Regex-only redaction fails on homoglyphs and spoken digits."""),
    "llm-performance-budget-ci-gate": lambda: _T("""The chat feature shipped green on Lighthouse — and p95 first-token latency regressed from 800ms to 2.4s because nobody budgeted the embedding call, RAG round-trip, and client bundle loading analytics SDKs before send enabled. Performance budget CI gates for LLM apps must cover the path users feel.

## Budget table

First token p95 under 1.2s staging. Full response p95 under 8s for 500 tokens. Client JS on chat route under 350 KB gzip. RAG retrieval p95 under 400ms. Hydration TTI under 2.5s.

## CI with Playwright

Store baseline traces as artifacts. Fail PR when TTFT regresses more than 15 percent vs main on fixed prompts — relative regression catches your changes despite provider variance.

Mark first visible token when SSE arrives — do not only measure full completion unless product requires it.

## Model upgrades

Swapping models changes latency and quality. Re-baseline budgets on model change; run quality eval in same pipeline.

## Bundle discipline

Code-split chat route; lazy-load syntax highlighters. INP suffers when main thread parses huge bundles on first keystroke.

## Org adoption

Platform owns TTFT gates; frontend owns bundle budgets; infra owns GPU queue alerts. Single dashboard for release go/no-go."""),
    "llm-personalization-signals-ranking": lambda: _T("""Personalization for LLM search fails two ways: everyone sees generic ranking, or the system surfaces documents from a misread click months ago. Personalization signals ranking engineers which behavioral features feed retrieval — and which stay out of prompts.

## Signal taxonomy

Explicit: locale, plan tier, onboarding selections. Implicit: recency-weighted clicks, dwell on cited sources, thumbs feedback. Derived: embedding centroid of liked docs. Forbidden: raw email, government ID — even hashed into prompts if reversible.

## Stack placement

Query to NLU to candidate retrieval top 100 to personalization rerank top 20 to optional cross-encoder to context assembly to LLM. Personalize in rerank, not generation.

## Heuristic baseline

Score equals base retrieval plus recency decay minus diversity penalty. Blend 10-20 percent exploration slots.

## Cold start

Day-one users get metadata plus popularity decay. Do not fake behavioral personalization — ask role explicitly.

## Evaluation

Offline NDCG at 10. Online interleaving on task completion, not clicks alone.

## Privacy

GDPR erasure deletes signal keys. Enterprise tenants may disable personalization per contract."""),
    "llm-pii-tokenization-vault": lambda: _T("""Support wanted to log prompts for debug. Legal asked about GDPR. PII tokenization at a vault before any LLM path sends tok_7f3a instead of alice@company.com to models and logs.

## Vault vs redaction

Regex misses homoglyphs and spelled-out phones. Vault detects entities, mints tokens, replaces in LLM-bound text, detokenizes only via audited break-glass.

## Gateway placement

Tokenize before RAG if queries contain PII. Never let raw query hit search logs.

## Vector indexes

Embeddings of tokenized text still leak semantics. Restrict ACL; short TTL on reversible tokens in indexes.

## Debugging

Production logs: token_id, field_type, correlation_id. Support detokenizes with manager approval.

## Vault operations

HA cluster, HSM for regulated tenants, versioned tokens across key rotation.

## Failure modes

Cross-tenant token collision — scope by tenant_id. Vault outage — fail closed vs degrade — document choice."""),
    "llm-pkce-public-clients": lambda: _T("""Mobile LLM apps and SPAs cannot hold OAuth secrets. Without PKCE, intercepted authorization codes on custom URL schemes become full sessions.

## Flow

Generate code_verifier random 43-128 chars. code_challenge equals BASE64URL SHA256 verifier. Authorize with S256 method. Exchange with verifier. Server validates hash.

## Mistakes

Shared client ID for SPA and server. Verifier reuse. Verifier in localStorage. Skipping PKCE on mobile.

## Refresh after PKCE

PKCE protects code grant only. HttpOnly cookies for refresh on BFF. Rotate refresh; detect reuse.

## Testing

Integration tests: missing verifier fails; wrong verifier fails; plain method rejected."""),
    "llm-pod-security-standards": lambda: _T("""GPU inference pods historically ran as root with hostPath mounts because "the model would not load otherwise." Kubernetes Pod Security Standards force explicit choices about capabilities, users, and volumes before a cluster compromise turns your LLM fleet into a cryptominer.

## PSS profiles for inference

Restricted fits stateless API gateways and guardrail sidecars: non-root, drop ALL capabilities, read-only root filesystem, no host namespaces. Baseline is common for GPU inference where read-only root is hard — still forbid privileged and limit capabilities to vendor-documented CUDA needs. Privileged is a last resort with isolated node pools and quarterly exception review.

## Sidecars inherit the weakest link

Tokenizer, OPA, and Envoy sidecars share the pod security context. One privileged init container chmod-ing model weights voids restricted on siblings. Chart templates must enforce securityContext on every container, including one-off CronJobs that refresh embeddings.

```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 10001
  seccompProfile:
    type: RuntimeDefault
containers:
  - name: inference
    securityContext:
      allowPrivilegeEscalation: false
      capabilities:
        drop: ["ALL"]
```

## Sandbox isolation

Code-execution sandboxes for tool use belong in a separate namespace with deny-all NetworkPolicy except egress proxy. Untrusted code must not share a trust fabric with inference pods.

## Admission workflow

CI renders manifests through policy checks blocking privileged: true. Kyverno or PSA dry-run on PR catches regressions before merge.

## GPU pragmatism

Document every capability add with vendor ticket reference. Revisit when CUDA base images update — what required CAP_SYS_ADMIN once may not anymore."""),
    "llm-poison-message-detection": lambda: _T("""One malformed JSON tool payload crashed the worker, requeued, crashed again — forty thousand times overnight. The LLM bill looked like a DDoS you sent yourself. Poison message detection stops infinite retry loops on messages that will never succeed.

## Identifying poison

Poison differs from transient failure. Transient: 503 from model API, network blip — retry with backoff. Poison: schema-valid but toxic payload, permanent NPE on null field in 0.01% of events, guardrail exception loop on specific content hash.

## Fingerprint and DLQ

Track message fingerprint and failure count. After MAX_ATTEMPTS, route to dead-letter queue and alert.

```python
FP = hashlib.sha256(payload[:2048]).hexdigest()

def should_retry(msg, err):
    n = store.incr(f"fail:{FP}", ttl=3600)
    if n >= MAX_ATTEMPTS:
        dlq.publish(msg, reason=str(err))
        return False
    return is_transient(err)
```

## Cost guard

Async enrichment calling models per message needs per-message spend cap. Poison burning tokens each retry is worse than poison crashing fast.

## Ingress validation

Validate size and schema at publish. Align Kafka max.message.bytes with worker memory. Reject at producer when possible.

## DLQ operations

Runbook on first DLQ arrival: inspect payload, fix worker or block fingerprint at ingress, manual replay after fix — never blind replay entire queue."""),
    "llm-policy-as-code-opa": lambda: _T("""Security wanted no GPT-4 in EU without approval. Product wanted YAML flags. Compliance wanted audit proof. Policy-as-code with OPA centralizes LLM gateway rules as versioned Rego — testable in CI, evaluable in milliseconds.

## Policy scope

OPA owns model allowlists by tenant tier, max tokens, tool invocation rules, data residency routing, coarse prompt-injection deny lists. Business pricing stays in application code.

## Example Rego

```rego
package llm.gateway
default allow = false
allow {
  input.model in data.tenant_models[input.tenant.tier]
  input.region == input.tenant.home_region
  input.estimated_input_tokens <= data.limits[input.tenant.tier].max_input
}
```

## Deployment and latency

Sidecar or embedded SDK on gateway. Bundle policies via CI to object storage. Target sub-5ms eval once per request — not per token.

## Testing

Table-driven Rego tests in CI for every tier and region combination. Fail PR if cross-region call allowed.

## Observability

Log policy_decision_id and rule version — not full prompt. Metric opa_denied_total by rule name."""),
    "llm-postmortem-blameless-culture": lambda: _T("""Production **postmortem blameless culture** in LLM stacks needs explicit engineering ownership — not a one-time launch checklist.

## Blameless vs accountability

Blameless means no punishment for surfacing mistakes. Teams own systems; leaders own missing gates. LLM postmortems need model version, prompt hash, index generation, and token spend in the timeline — not just HTTP 500.

## LLM timeline fields

Table stakes: model_id, prompt_version, retrieval index id, feature flags, guardrail block rate delta. Redact prompts in published reports; full text in restricted incident vault.

## Action item quality

Bad: be careful with prompts. Good: prompt changes require eval-ci pass on golden set; block merge on >1% regression.

## Writing culture

No individual names in root cause — system gaps only. AI SEV definitions include wrong-but-plausible harm, not only uptime."""),
    "llm-preemptible-workload-checkpoint": lambda: _T("""Production **preemptible workload checkpoint** in LLM stacks needs explicit engineering ownership — not a one-time launch checklist.

## Workload fit

Good: batch embedding, offline eval, fine-tuning with step checkpoints. Bad: interactive serving.

## Checkpoint design

Persist cursor to S3 every N shards or M minutes — last doc id, batch offset, index version.

## Resume

Idempotent upserts by doc_id and index_version prevent duplicate vectors on replay.

## Spot on Kubernetes

Separate node pools; batch Jobs tolerate preemption; serving uses on-demand or reserved capacity."""),
    "llm-pricing-optimization-dynamic": lambda: _T("""Production **pricing optimization dynamic** in LLM stacks needs explicit engineering ownership — not a one-time launch checklist.

## Signals

Utilization, queue depth, model marginal cost, tenant tier, time-of-day.

## Guardrails

Cap surge multiplier; notify in UI; contract customers exempt from intraday surge.

## Simulation

Replay 30 days billing with proposed rules before deploy.

## Trust

B2C transparency laws and B2B MSAs may forbid silent unit price changes mid-contract."""),
    "llm-probabilistic-early-expiration": lambda: _T("""Production **probabilistic early expiration** in LLM stacks needs explicit engineering ownership — not a one-time launch checklist.

## Problem

Uniform TTL synchronizes expiry — thundering herd on RAG cache.

## Mechanism

Probabilistic refresh before hard TTL spreads recompute load.

## Semantic cache

Include embedding model version in cache key — never probabilistically expire wrong-version entries silently.

## Metrics

cache_early_refresh_total and origin QPS variance guide beta tuning."""),
    "llm-producer-acknowledgment-tradeoffs": lambda: _T("""Production **producer acknowledgment tradeoffs** in LLM stacks needs explicit engineering ownership — not a one-time launch checklist.

## acks=all

Use for billing and audit events — not best-effort analytics.

## Outbox

User response does not wait on Kafka fsync; transactional outbox aligns DB and events.

## Idempotence

enable.idempotence=true on producers; dedupe consumers by request_id.

## Topics

Separate critical and telemetry topics — different acks policies."""),
    "llm-progressive-delivery-metrics": lambda: _T("""Production **progressive delivery metrics** in LLM stacks needs explicit engineering ownership — not a one-time launch checklist.

## Canary basket

Error rate, TTFT p95, golden eval score, guardrail rate, cost per success.

## Two-phase

Offline eval gate before traffic split; online comparison during canary.

## Bake time

24-72h minimum — catch diurnal and weekend prompt patterns.

## Rollback

Automated revert on eval regression >2% or latency p95 +30%."""),
    "llm-protobuf-evolution-compatibility": lambda: _T("""Production **protobuf evolution compatibility** in LLM stacks needs explicit engineering ownership — not a one-time launch checklist.

## Wire rules

Never renumber; add optional fields; reserve deprecated numbers.

## JSON transcoding

Document enum and timestamp formats for REST SDK consumers.

## Buf CI

buf breaking against main on inference.proto.

## Mobile lag

Servers accept old clients missing new fields for 30+ days in wild."""),
    "llm-provenance-content-credentials": lambda: _T("""Production **provenance content credentials** in LLM stacks needs explicit engineering ownership — not a one-time launch checklist.

## Generation metadata

Model ID, prompt hash, timestamp — not raw prompt in user-visible credentials.

## RAG sources

chunk_id, doc version, retrieval time in structured UI metadata.

## C2PA media

Sign generated images with software agent string for trust labels.

## Limits

Provenance deters casual fraud; pair with grounded retrieval for high-stakes domains."""),
    "llm-pseudo-localization-testing": lambda: _T("""Production **pseudo localization testing** in LLM stacks needs explicit engineering ownership — not a one-time launch checklist.

## Expansion

30-40% longer pseudo strings catch clipped buttons in chat UI.

## Streaming

Mock longer tokens in dev to stress typewriter reflow — English mocks hide CJK breaks.

## CI

Playwright screenshot diff with pseudo locale on chat routes.

## Scope

Pseudo-loc tests shell layout; model i18n needs separate locale eval sets."""),
    "llm-query-plan-analysis": lambda: _T("""Production **query plan analysis** in LLM stacks needs explicit engineering ownership — not a one-time launch checklist.

## EXPLAIN triggers

New RAG filters, hybrid joins, any LLM-tool SQL path.

## pgvector

Composite index on tenant_id plus vector column — avoid cross-tenant seq scan.

## Agent SQL

Read-only role, statement_timeout, EXPLAIN-only sandbox mode.

## CI

Fail plan hash regression to seq scan on critical queries."""),
    "llm-query-understanding-nlu": lambda: _T("""Production **query understanding nlu** in LLM stacks needs explicit engineering ownership — not a one-time launch checklist.

## Routing

Intent plus entity extraction before vector search — cancel subscription should not fetch FAQ.

## Intents

Start 15-30 coarse intents; merge noisy ones quarterly.

## Confidence

Below threshold → clarify or broad search; log for labeling loop.

## Multilingual

Language-id first; locale-specific synonym tables."""),
    "llm-rate-limit-token-bucket": lambda: _T("""Production **rate limit token bucket** in LLM stacks needs explicit engineering ownership — not a one-time launch checklist.

## Bucket vs window

Allows burst while enforcing average TPM/RPM.

## Layers

Global pool, tenant quota, user quota, API key — exhaust inner buckets first for clear errors.

## Streaming

Emit 429 with Retry-After before closing SSE.

## Charge model

Debit input at start; reserve max output; refund unused on complete."""),
    "llm-reconciliation-batch-jobs": lambda: _T("""Production **reconciliation batch jobs** in LLM stacks needs explicit engineering ownership — not a one-time launch checklist.

## Daily diff

Internal meter vs provider export vs billing system — ticket unmatched over threshold.

## Keys

Match on request_id and model; hash if legacy lacks IDs.

## Categories

Missing events, duplicates, cached token definition drift, timezone windows.

## Finance

Automated diff plus monthly human sign-off on material adjustments."""),
    "llm-refresh-token-rotation-detect": lambda: _T("""Production **refresh token rotation detect** in LLM stacks needs explicit engineering ownership — not a one-time launch checklist.

## Rotation

New refresh each use; invalidate old; family ID tracks lineage.

## Reuse

Old refresh presented after rotation → revoke family, force login.

## Storage

HttpOnly Secure cookies on BFF — not localStorage.

## Grace

30s overlap for parallel mobile requests; log reuse outside window."""),
    "llm-replay-attack-prevention": lambda: _T("""Production **replay attack prevention** in LLM stacks needs explicit engineering ownership — not a one-time launch checklist.

## Signed requests

HMAC with timestamp and nonce; reject outside 5-minute skew.

## Webhooks

Verify signature; store processed event IDs with TTL.

## Idempotency-Key

Same chat completion key within 24h returns cached response.

## Nonce store

Bloom filter plus exact set for high QPS windows."""),
    "llm-replication-lag-monitoring": lambda: _T("""Production **replication lag monitoring** in LLM stacks needs explicit engineering ownership — not a one-time launch checklist.

## SLI

Alert replay lag >30s on metadata DB serving RAG.

## Consistency

Invalidate cache on primary write success; tag answers with index_version.

## Routing

Strong consistency paths read primary; analytics replicas separate SLI.

## Multi-region

Writes home region; reads local with lag-aware routing."""),
    "llm-reranker-latency-budget": lambda: _T("""Production **reranker latency budget** in LLM stacks needs explicit engineering ownership — not a one-time launch checklist.

## Budget

Often 200-400ms for top-20 cross-encoder on CPU; total retrieval+rerank cap ~500ms interactive.

## Top-K

Retrieve 100; rerank max 20-50 — linear cost in cross-encoder pairs.

## Skip

High bi-encoder margin FAQ bots may skip rerank under 200ms SLO.

## Tracing

Span per stage — tail latency often in rerank queue."""),
    "llm-responsible-ai-review": lambda: _T("""Production **responsible ai review** in LLM stacks needs explicit engineering ownership — not a one-time launch checklist.

## Triggers

Health, finance, hiring, minors, automated external decisions.

## Deliverables

Model card, intended use, eval on demographic slices, human escalation path.

## vs security

Security: can it be hacked. RAI: should we ship it.

## Process

Cross-functional sign-off; re-review on material model change."""),
    "llm-reverse-etl-activation": lambda: _T("""Production **reverse etl activation** in LLM stacks needs explicit engineering ownership — not a one-time launch checklist.

## Pattern

dbt segment → Hightouch → LaunchDarkly or CRM for proactive copilot tips.

## PII

Hash or tokenize before sync to third-party SaaS.

## Latency

Hourly sync OK for activation; do not block chat on warehouse freshness.

## Governance

Data owns model; product owns flag mapping."""),
    "llm-row-level-security-policies": lambda: _T("""Production **row level security policies** in LLM stacks needs explicit engineering ownership — not a one-time launch checklist.

## RLS

ENABLE ROW LEVEL SECURITY on documents; policy on tenant_id from JWT session var.

## Defense

App filters for performance; RLS catches ORM mistakes.

## Indexer

Separate BYPASSRLS role for batch embed jobs — audited only.

## CI

Integration test tenant A cannot see tenant B rows."""),
    "llm-runbook-as-code": lambda: _T("""Production **runbook as code** in LLM stacks needs explicit engineering ownership — not a one-time launch checklist.

## Structure

Symptom, verify script, mitigate flag, escalate path — in git beside executable scripts.

## Versioning

Runbook references rollback for specific model and prompt versions.

## Lint

CI checks required sections and PagerDuty owner match.

## Automation

Optional auto-remediation linked from alert — human follows doc for root cause."""),
    "llm-runtime-security-falco": lambda: _T("""Production **runtime security falco** in LLM stacks needs explicit engineering ownership — not a one-time launch checklist.

## Rules

Unexpected shell in inference pod; metadata service crawl; mining pool outbound.

## vs PSA

PSA at schedule; Falco at runtime drift.

## Response

Network isolate pod; rotate secrets; playbook per alert.

## Tuning

Whitelist model load paths per image version in staging."""),
    "llm-saga-orchestration-choreography": lambda: _T("""Production **saga orchestration choreography** in LLM stacks needs explicit engineering ownership — not a one-time launch checklist.

## Orchestration

Temporal for user-visible multi-step flows with human approval signals.

## Choreography

Events for async indexing pipeline stages.

## Compensation

Persist LLM outputs per step; compensate with stored text not re-invoke model.

## Idempotency

Non-negotiable — election and queues reduce duplicates not eliminate."""),
    "llm-same-site-cookie-policy": lambda: _T("""Production **same site cookie policy** in LLM stacks needs explicit engineering ownership — not a one-time launch checklist.

## Same-origin

SameSite=Lax for session on same-site chat apps.

## Embed

Cross-site widget needs SameSite=None; Secure — test Safari ITP.

## OAuth

Strict or Lax on state cookies for CSRF protection.

## BFF

Refresh on API domain; credentialed calls from SPA with explicit CORS."""),
    "llm-sanctions-screening-api": lambda: _T("""Production **sanctions screening api** in LLM stacks needs explicit engineering ownership — not a one-time launch checklist.

## Timing

Screen before onboarding and before outbound payments — not after LLM extraction.

## LLM role

OCR/NER proposes names; deterministic API matches lists; human queue on fuzzy hits.

## Latency

Sync before wire transfer commit; async only where legal permits.

## Audit

Log screening request ID, list version, override reason."""),
    "llm-serving-quantization-awq-gptq": lambda: _T("""Serving 70B in FP16 needed four A100s; AWQ 4-bit fit one card with 2% eval regression on your benchmark. Quantization trades precision for memory and throughput when validated on target hardware — not when MMLU leaderboard says so.

## AWQ vs GPTQ

AWQ (Activation-aware Weight Quantization) preserves salient weights; often better 4-bit accuracy on recent NVIDIA GPUs. GPTQ has broader tooling and community checkpoints. Benchmark your prompts and RAG eval set on the exact GPU generation you deploy.

## Production loading

Pre-quantized checkpoints loaded natively in vLLM or TGI — do not quantize at every pod cold start.

```python
llm = LLM(model="meta-llama/Llama-3-70B-AWQ", quantization="awq")
```

## Structured output risk

Re-run JSON and schema adherence eval post-quant. Some models lose format compliance at 4-bit where free-form quality looks fine.

## When to skip quantization

Model already fits FP16 on one GPU with headroom; latency dominated by attention memory bandwidth, not capacity.

## Rollout

Canary with offline eval gate, then online quality metrics. Keep FP16 rollback artifact one command away."""),
    "llm-serving-speculative-decoding-draft": lambda: _T("""The 70B target model delivered quality; serial decoding hurt UX. Speculative decoding pairs a small draft model with the target — draft generates K tokens cheaply; target verifies in parallel; accepted tokens advance faster than one big model alone.

## Acceptance rate is the metric

Measure speculative_acceptance_rate = accepted / draft_tokens. Below ~60% net latency may worsen. Tune draft length K when rate collapses.

## Draft model selection

Same tokenizer family preferred; similarly trained smaller checkpoint. Random tiny model yields reject storms and wasted verify compute.

## Latency vs throughput

Interactive chat benefits from spec decode on single large model. Pure batch throughput workloads may prefer continuous batching without draft complexity.

## Hardware pairing

Draft and target on same node reduces verify latency; memory planning must fit both — often draft on same GPU with careful batch sizing.

## Instrumentation

Trace draft_tokens, accepted_tokens, rejected_tokens per request. Compare p95 with spec decode on/off weekly as models update."""),
    "llm-serving-structured-output-outlines": lambda: _T("""JSON mode returned truncated `{ "action": delete` — retried three times, tripled cost. Structured output with Outlines or grammar-constrained decoding enforces syntax during generation, not after parsing failures.

## Grammar-constrained decoding

Compile JSON Schema or regex to finite automaton; mask illegal logits each step — valid JSON when complete.

```python
import outlines
generator = outlines.generate.json(model, UserAction)
result = generator("Classify intent as JSON")
```

## vs provider JSON mode

JSON mode is best-effort on some models. Grammar constraints eliminate parse-retry loops — often lower total latency and cost than hope-and-reparse.

## Tool calling

Define tool argument grammars; reduce malformed tool invocations breaking agent loops.

## Streaming tradeoffs

Full constraint mid-stream is harder; incremental JSON parsers help UX-critical streaming paths.

## Eval

Measure parse failure rate before and after enabling constraints on production sample queries."""),
    "llm-serving-tensor-parallelism": lambda: _T("""Single A100 80GB could not hold 405B weights. Tensor parallelism shards layers across GPUs on one node, all-reducing activations each forward step — memory geometry, not magic scale-out.

## When TP applies

Model exceeds single-GPU memory; interactive serving on one host; NVLink available between GPUs. Scale replicas for QPS; TP for model fit.

## TP vs pipeline parallel

TP splits layers horizontally — low latency when NVLink is fast. Pipeline parallel splits depth — better when TP communication dominates on very deep models.

## vLLM configuration

tensor_parallel_size must divide attention head count.

```bash
vllm serve meta-llama/Llama-3-405B --tensor-parallel-size 8
```

## Hardware reality

TP all-reduce across PCIe is painful — prefer A100/H100 NVLink pairs. Size node pools for sidecar and TP memory overhead.

## Operations

Rolling update TP clusters requires coordinated restart — plan maintenance windows. Monitor NCCL errors and GPU peer connectivity in logs."""),
}
