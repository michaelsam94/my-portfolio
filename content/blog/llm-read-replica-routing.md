---
title: "Read Replica Routing"
slug: "llm-read-replica-routing"
description: "Route agent read traffic to replicas without breaking session consistency: lag-aware routing for RAG retrieval, sticky primary for tool writes, and failover patterns when replicas fall behind."
datePublished: "2024-12-15"
dateModified: "2026-07-17"
tags:
keywords: "llm, read, replica, routing, ai, production, engineering, architecture"
faq:
  - q: "How much replication lag is acceptable for agent RAG retrieval?"
    a: "For document search over published content, 1–5 seconds is usually fine if agents never answer 'did my upload succeed?' from a replica. For session memory or permission checks, route to primary or use lag ceiling under 500ms. Measure per replica — lag is not uniform."
  - q: "Should vector similarity search run on replicas?"
    a: "Yes, when queries are read-only and documents are eventually consistent. pgvector HNSW indexes replicate like any index; heavy ANN queries belong off the primary. Invalidate or warm caches when embeddings bulk-update."
  - q: "What breaks when an agent reads its own write from a replica?"
    a: "Classic failure: user uploads a file, agent immediately searches, replica hasn't received the row yet, agent says 'I can't find that document.' Route post-write reads to primary for a short session window or block until replication catches up."
  - q: "How do you test replica routing without production traffic?"
    a: "Inject artificial lag with pg_sleep on replica apply, or use delayed standbys in staging. Run agent evals that upload-then-query in one session and assert document visibility. Chaos-test replica promotion during active sessions."
---
Read Replica Routing is one of those topics that looks straightforward in a slide deck and gets complicated the first time traffic spikes or an auditor asks how you know it works. In ai systems, the difference between "we implemented it" and "we can operate it" shows up in metrics, incident history, and how confidently new engineers change the code.
## Implementation patterns

A practical baseline for read replica routing in ai stacks:

1. **Model the happy path minimally** — ship the smallest flow that satisfies the user story with correct semantics.
2. **Add failure paths next** — timeouts, retries with jitter, circuit breaking, and compensating actions.
3. **Instrument before optimizing** — measure p50/p95 latency, error budgets, and saturation; tune from evidence.
4. **Document operational playbooks** — what to check, what to rollback, who owns downstream dependencies.

For code structure, keep side effects at the edges and core logic pure where possible. Pure functions are trivial to test; IO at the boundary is trivial to mock. That split makes llm read replica routing changes safer because business rules stay isolated from transport details.

```typescript
// Read Replica Routing: typed boundary + structured errors
export async function handleReadReplicaRouting(input: Input): Promise<Result> {
  const parsed = schema.safeParse(input);
  if (!parsed.success) throw new ValidationError(parsed.error);
  const span = tracer.startSpan("llm-read-replica-routing");
  try {
    return await repo.execute(parsed.data);
  } finally {
    span.end();
  }
}

```


## Operational concerns

Alert on user-visible symptoms for read replica routing — error rate, latency SLO burn, queue depth — not on every internal counter. Noise desensitizes on-call engineers.

Production llm read replica routing work is mostly operability: dashboards, alerts, runbooks, and ownership. Define SLOs that reflect user experience — availability, latency, correctness — not vanity metrics. Alerts should page on symptoms (SLO burn) and ticket on causes (error logs), avoiding noise that trains teams to ignore pages.

Rollouts for read replica routing benefit from progressive delivery: canary by percentage or by tenant cohort, with automatic rollback when error rate or latency regresses beyond thresholds. Pair deploys with feature flags so you can disable logic paths without redeploying.

Capacity planning ties directly to cost and reliability. Measure peak QPS, payload sizes, fan-out factor, and dependency limits. Load test with production-shaped traffic; synthetic "hello world" tests miss queue backlogs and downstream contention.

## Security and compliance angles

Even when read replica routing is not "security software," it participates in your trust boundary. Apply least privilege to service accounts, rotate credentials, and validate all inputs at the trust perimeter. For regulated workloads, maintain an audit trail that answers who changed what, when, and from where.

Secrets belong in managed stores — not environment variables checked into templates. For PII-adjacent flows, minimize retention and prefer tokenization over copying raw fields. Document data flows for llm read replica routing so security reviews do not rely on tribal knowledge.

## Testing strategy

Unit tests cover pure logic: validation, mapping, state transitions, and edge cases. Contract tests protect API boundaries that read replica routing depends on. Integration tests with real containers — databases, brokers, sandboxes — catch configuration mistakes mocks hide.

For critical ai paths, add property-based or fuzz testing where generative input explores weird combinations. Replay production traffic (sanitized) into staging before large refactors. Chaos experiments — dependency latency, partial outages — validate that retries and fallbacks actually work.

## Migration and evolution

Legacy systems rarely block greenfield designs; they constrain sequencing. Strangle llm read replica routing functionality behind a stable interface, migrate callers incrementally, and delete old paths once traffic drops to zero. Maintain a migration tracker with explicit decommission dates so "temporary" bridges do not ossify.

Versioning policy should be boring: additive changes only in minor versions, breaking changes only with deprecation windows and communication. Where read replica routing spans mobile, web, and backend, coordinate release trains so clients never lead servers into incompatible states.

## Resources

- [platform.openai.com/docs/](https://platform.openai.com/docs/)

- [python.langchain.com/docs/](https://python.langchain.com/docs/)

- [www.anthropic.com/research](https://www.anthropic.com/research)

- [huggingface.co/docs](https://huggingface.co/docs)

- [arxiv.org/list/cs.AI/recent](https://arxiv.org/list/cs.AI/recent)

## Production notes for LLM stacks

When `llm-read-replica-routing` sits on an inference or RAG path, treat user prompts and retrieved chunks as untrusted input. Log correlation IDs and policy decisions—not raw prompts—in production telemetry. Gate risky operations behind explicit authorization at the gateway, not inside ad-hoc tool handlers.

Roll out changes with shadow mode first: record what **would** have happened under the new rule without blocking traffic. Compare deny rates, latency impact, and false positives for at least one business week before enforcing. Pair enforcement with a runbook entry: symptom, dashboard, rollback (feature flag or config), and owner.

Load-test with production-shaped concurrency. LLM workloads burst differently from CRUD APIs—tail latency and token throttling dominate. If `read replica routing` protects an invariant (security, billing, data residency), prove the invariant with an automated test that fails CI when someone removes the check.

## What teams get wrong

Teams copy a reference architecture without matching their compliance tier, then discover in audit that logs, backups, or support exports reintroduced the data they thought they had eliminated. Another pattern: shipping the demo integration without idempotency, then fighting duplicate side effects when clients retry on model timeouts.

Document the tradeoff you chose—strictness vs recall, cost vs quality, sync vs async—and the metric that tells you if the choice still holds six months later.

## Production notes for LLM stacks

When `llm-read-replica-routing` sits on an inference or RAG path, treat user prompts and retrieved chunks as untrusted input. Log correlation IDs and policy decisions—not raw prompts—in production telemetry. Gate risky operations behind explicit authorization at the gateway, not inside ad-hoc tool handlers.

Roll out changes with shadow mode first: record what **would** have happened under the new rule without blocking traffic. Compare deny rates, latency impact, and false positives for at least one business week before enforcing. Pair enforcement with a runbook entry: symptom, dashboard, rollback (feature flag or config), and owner.

Load-test with production-shaped concurrency. LLM workloads burst differently from CRUD APIs—tail latency and token throttling dominate. If `read replica routing` protects an invariant (security, billing, data residency), prove the invariant with an automated test that fails CI when someone removes the check.

## What teams get wrong

Teams copy a reference architecture without matching their compliance tier, then discover in audit that logs, backups, or support exports reintroduced the data they thought they had eliminated. Another pattern: shipping the demo integration without idempotency, then fighting duplicate side effects when clients retry on model timeouts.

Document the tradeoff you chose—strictness vs recall, cost vs quality, sync vs async—and the metric that tells you if the choice still holds six months later.


For `llm-read-replica-routing`, treat observability and security controls as part of the user experience: silent failures erode trust faster than explicit error messages. Instrument deny paths, measure tail latency, and review dashboards with on-call weekly.

For `llm-read-replica-routing`, treat observability and security controls as part of the user experience: silent failures erode trust faster than explicit error messages. Instrument deny paths, measure tail latency, and review dashboards with on-call weekly.

For `llm-read-replica-routing`, treat observability and security controls as part of the user experience: silent failures erode trust faster than explicit error messages. Instrument deny paths, measure tail latency, and review dashboards with on-call weekly.
