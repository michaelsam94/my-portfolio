---
title: "AI Agents: Subresource Integrity for LLM Web Clients"
slug: "agent-subresource-integrity-hashes"
description: "Pin CDN scripts with SRI hashes — especially SDK bundles that handle API keys and streaming parsers."
datePublished: "2025-10-08"
dateModified: "2026-07-17"
tags:
  - "AI"
  - "Security"
  - "Web"
  - "SRI"
keywords: "subresource integrity, SRI, CDN security, LLM SDK"
faq:
  - q: "When should teams prioritize Subresource Integrity for LLM Web Clients?"
    a: "When LLM chat widgets load third-party JavaScript from CDNs."
  - q: "What is the most common mistake with SRI hashes?"
    a: "SRI on static assets but not on dynamically versioned SDK loader URLs."
  - q: "How do we know Subresource Integrity for LLM Web Clients is working?"
    a: "Define a leading metric for SRI hashes (error rate, stale read rate, recall, verification failures) and a lagging metric (incidents, invoice variance, audit findings). Review both in weekly ops, not only after escalations."
---
A CDN compromise could have swapped the chat SDK — no integrity attributes on script tags.

Pin CDN scripts with SRI hashes — especially SDK bundles that handle API keys and streaming parsers.

## The production story behind SRI hashes

SRI on static assets but not on dynamically versioned SDK loader URLs. Teams usually discover the gap only after a finance reconcile, a security review, or a slow metric drift that nobody pages until customers notice. Subresource Integrity for LLM Web Clients is load-bearing once traffic, tenants, or compliance requirements grow past the pilot.

The pattern is predictable: demo-grade wiring ships in a sprint; production adds retries, partial failures, multi-tenant isolation, and humans who double-click submit. Sri Hashes is how you convert that chaos into an invariant someone can operate.

## Designing subresource integrity for llm web clients for real constraints

Name three boundaries on a whiteboard: **ingress** (who triggers work), **enforcement** (where invariants are checked), and **evidence** (what you log for audits). For SRI hashes, enforcement must be synchronous on the critical path — advisory checks in notebooks are not controls.

Platform owns shared defaults; product owns domain configuration. Orphan ownership is how regressions return silently after launch.

Write a one-page decision record: what you rejected, what metrics gate rollback, and which environments may diverge. Link dashboards from the runbook header so on-call does not search Slack for URLs during an incident.

## Implementation walkthrough

Ship the smallest production slice first: one tenant, one region, one workflow — with rollback documented before widening scope. Automate rotation, rebuilds, and reconciles so on-call never hand-edits SRI hashes during an incident.

Integration tests should mirror production topology — single-region staging is not enough if users are global. For client apps, exercise offline, process death, and token rotation — not only office Wi-Fi happy paths.

```python
# Operational hook — SRI hashes
def apply_subresource_integrity_hashes(ctx):
    validate_preconditions(ctx)
    result = execute(ctx)
    emit_metrics(result)
    return result
```

## Platform depth

Platform teams own defaults and libraries; product teams own domain config. Document interfaces where SRI hashes gates handoffs to downstream owners.
Review after every magnitude change in traffic or model swap — assumptions drift silently.

## Failure modes worth rehearsing

- Missing idempotency when clients retry.
- Implicit defaults that differ between staging and production.
- Dashboards green while user-visible SLO burns.
- Credential or metadata rotation without overlap window.
- Schema or index change without blue-green validation.

Document for each: drop, retry, dead-letter, or fail-closed — and test under production-shaped load.

## Metrics and alerts

Leading indicators: error rate on SRI hashes, queue age, validation failure rate, stale read rate. Lagging indicators: incidents, audit findings, invoice disputes. Slice by tenant tier during rollout — global averages hide bad canaries.

## Day-two operations

Runbooks fit one page: symptom, dashboard, mitigation, rollback. Assign an owner team; SRI hashes regresses when orphaned. Pick one tier-1 workflow this week, put enforcement on the critical path, add one leading metric, and game-day the top failure mode above.

## Production hardening

Pin versions affecting SRI hashes. Progressive rollout: internal tenants → canary → full promote. Keep previous config hot-swappable one release.

## Handoff and ownership

Subresource Integrity for LLM Web Clients touches multiple teams — name DRIs in the service catalog. New hires should rollback safely using only the runbook within week one.

## Further reading

- [OpenTelemetry docs](https://opentelemetry.io/docs/)
- [OWASP Cheat Sheet Series](https://cheatsheetseries.owasp.org/)

## Operating SRI hashes after scale events (review 1)

Traffic doublings, model swaps, and enterprise SSO enablement invalidate assumptions in the original design. Quarterly on-call reviews should update thresholds from recent incidents — not only the primary author's memory.

When subresource integrity for llm web clients touches billing, auth, or retrieval, schedule a cross-team review after every major launch. Platform, product, security, and finance should agree on what the leading metric is and who owns rollback.

Game days to run: dependency slow-down, duplicate webhook delivery, index swap rollback, IdP cert rotation dry-run. Measure time-to-mitigate, not only time-to-detect. When providers change streaming or auth semantics without a deploy on your side, error-class metrics should catch drift within hours.

Document one concrete lesson from each game day in the runbook header — future on-call should not rediscover the same failure mode.


## Operating SRI hashes after scale events (review 2)

Traffic doublings, model swaps, and enterprise SSO enablement invalidate assumptions in the original design. Quarterly on-call reviews should update thresholds from recent incidents — not only the primary author's memory.

When subresource integrity for llm web clients touches billing, auth, or retrieval, schedule a cross-team review after every major launch. Platform, product, security, and finance should agree on what the leading metric is and who owns rollback.

Game days to run: dependency slow-down, duplicate webhook delivery, index swap rollback, IdP cert rotation dry-run. Measure time-to-mitigate, not only time-to-detect. When providers change streaming or auth semantics without a deploy on your side, error-class metrics should catch drift within hours.

Document one concrete lesson from each game day in the runbook header — future on-call should not rediscover the same failure mode.


## Operating SRI hashes after scale events (review 3)

Traffic doublings, model swaps, and enterprise SSO enablement invalidate assumptions in the original design. Quarterly on-call reviews should update thresholds from recent incidents — not only the primary author's memory.

When subresource integrity for llm web clients touches billing, auth, or retrieval, schedule a cross-team review after every major launch. Platform, product, security, and finance should agree on what the leading metric is and who owns rollback.

Game days to run: dependency slow-down, duplicate webhook delivery, index swap rollback, IdP cert rotation dry-run. Measure time-to-mitigate, not only time-to-detect. When providers change streaming or auth semantics without a deploy on your side, error-class metrics should catch drift within hours.

Document one concrete lesson from each game day in the runbook header — future on-call should not rediscover the same failure mode.


## Operating SRI hashes after scale events (review 4)

Traffic doublings, model swaps, and enterprise SSO enablement invalidate assumptions in the original design. Quarterly on-call reviews should update thresholds from recent incidents — not only the primary author's memory.

When subresource integrity for llm web clients touches billing, auth, or retrieval, schedule a cross-team review after every major launch. Platform, product, security, and finance should agree on what the leading metric is and who owns rollback.

Game days to run: dependency slow-down, duplicate webhook delivery, index swap rollback, IdP cert rotation dry-run. Measure time-to-mitigate, not only time-to-detect. When providers change streaming or auth semantics without a deploy on your side, error-class metrics should catch drift within hours.

Document one concrete lesson from each game day in the runbook header — future on-call should not rediscover the same failure mode.


## Operating SRI hashes after scale events (review 5)

Traffic doublings, model swaps, and enterprise SSO enablement invalidate assumptions in the original design. Quarterly on-call reviews should update thresholds from recent incidents — not only the primary author's memory.

When subresource integrity for llm web clients touches billing, auth, or retrieval, schedule a cross-team review after every major launch. Platform, product, security, and finance should agree on what the leading metric is and who owns rollback.

Game days to run: dependency slow-down, duplicate webhook delivery, index swap rollback, IdP cert rotation dry-run. Measure time-to-mitigate, not only time-to-detect. When providers change streaming or auth semantics without a deploy on your side, error-class metrics should catch drift within hours.

Document one concrete lesson from each game day in the runbook header — future on-call should not rediscover the same failure mode.


## Resources

- [OpenTelemetry docs](https://opentelemetry.io/docs/)
- [AWS documentation](https://docs.aws.amazon.com/)
