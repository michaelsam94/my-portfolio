---
title: "Architecture Decision Records"
slug: "software-architecture-decision-records"
description: "Document architecture decisions with ADRs: lightweight templates, when to write them, storage in repo, and avoiding shelfware."
datePublished: "2025-08-07"
dateModified: "2026-07-17"
tags:
  - "Engineering"
keywords: "architecture decision record, ADR template, document architecture decisions, Michael Nygard ADR, architectural decision log, MADR format"
faq:
  - q: "What decisions deserve an ADR?"
    a: "Decisions that are hard to reverse, affect multiple teams, or generate recurring debate: database choice, messaging bus, auth model, monolith vs services split, and public API versioning strategy. Skip ADRs for routine library bumps or formatting choices—over-documenting dilutes attention from decisions that actually constrain the system for years."
  - q: "Where should ADRs live?"
    a: "In the repository beside code—docs/adr/ or adr/ with numbered markdown files versioned with git. Link from README or internal wiki index. ADRs in Confluence alone drift from implementation; repo storage ties decisions to commits that implement them and survives tool migrations."
  - q: "How do I handle superseded decisions?"
    a: "Mark status Superseded by ADR-0012 with link; do not delete old ADRs. History explains why you left Postgres-only for read replicas and prevents new hires from relitigating settled tradeoffs without context. Accepted, Deprecated, Superseded statuses keep the log honest."
---

Three engineers re-debated Kafka versus RabbitMQ because the original choice lived in a departed architect's slide deck. Architecture Decision Records (ADRs) capture context, decision, and consequences in a few hundred words — optimized for the reader six months later asking "why on earth did we do this?" Michael Nygard's format spread because it fits pull requests, not because enterprises love paperwork.

## Minimal template that gets used

```markdown
# ADR-0007: Use PostgreSQL as system of record

## Status
Accepted

## Context
We need ACID transactions for billing and reporting joins.
Team knows Postgres; managed RDS available.

## Decision
PostgreSQL 16 on RDS as primary datastore.
Read replicas for analytics after Q3.

## Consequences
+ Strong consistency, mature tooling
- Horizontal write scaling limited; revisit sharding if >10k TPS
```

Number sequentially (`0001`, `0002`). Title is searchable. Keep the whole ADR under one printed page — if it grows longer, split into decision plus linked spike document.

## What deserves an ADR

Write ADRs for decisions that are **hard to reverse**, **cross-team**, or **debate-prone**: database choice, messaging bus, auth model, monolith versus services split, public API versioning strategy, multi-region active-active. Skip ADRs for routine library bumps, formatter choices, or sprint-level implementation details — over-documenting dilutes attention from decisions that constrain the system for years.

## When to write in the workflow

Open ADR pull request **before** or **alongside** implementation PR for significant forks. Reviewers comment on decision merit separately from code style. Retroactive ADRs help onboarding when documenting existing system — label `Accepted (documenting existing)` so readers know timing.

Disagreements in PR comments become Context paragraph edits — not Slack loss when the thread archives.

## MADR and considered options

Markdown Any Decision Records add optional sections: decision drivers, considered options, pros/cons tables. Useful for contentious picks:

| Option | Pros | Cons |
|--------|------|------|
| Kafka | Throughput, log retention | Ops complexity, team skill gap |
| RabbitMQ | Team familiarity, routing | Lower throughput ceiling |

Skip MADR ceremony for obvious choices — "use HTTPS" does not need a workshop.

## Linking code and ADRs

Reference ADR in commit message: `Implement read replica routing (ADR-0007)`. Code search finds rationale. ADR links to spike branch or proof-of-concept PR. When implementation diverges from ADR consequences, supersede the ADR — do not let docs lie.

## Superseding without deleting

Mark status **Superseded by [ADR-0012](adr/0012-eventbridge.md)** — never delete old ADRs. History explains why you left Postgres-only for read replicas and prevents new hires from relitigating settled tradeoffs without context. Status values: Proposed, Accepted, Deprecated, Superseded.

## Avoiding the ADR graveyard

- Name real alternatives you rejected — "we considered Mongo" without why it lost is useless
- Record **measurable** consequences ("expect 20ms added latency on read path")
- Review ADRs in quarterly architecture sync — supersede when reality diverged
- Assign owner in ADR header — orphaned Proposed ADRs older than 30 days get accepted or rejected in sync

## Tools: adr-tools, Log4brains, or plain markdown

`adr new "Use Redis for session store"` scaffolds files in `doc/adr/`. Log4brains builds static site from ADR folder for internal publishing. Plain markdown in `docs/adr/` works — tooling is optional; git history is mandatory.

## Team topology and ADRs

When Team Topologies stream-aligned teams own services, ADRs at service repo level beat central architecture committee queue. Platform team publishes ADRs for paved road choices; product teams ADR local deviations with platform review.

## Relationship to RFCs and design docs

RFCs explore problem space before decision; ADR records outcome. Spike code belongs linked from ADR, not pasted inline. Design docs for one feature are not ADRs — ADRs capture durable constraints affecting multiple features.

## Anti-patterns

- ADRs written only for audit checkbox after implementation shipped
- Generic consequences ("better scalability") without numbers or tradeoff honesty
- Storing ADRs only in Confluence — drifts from code, dies on tool migration
- Endless Proposed status — ambiguous decisions hurt more than wrong accepted ones

## Example consequence honesty

Bad: "Improves performance." Good: "Cuts p95 read latency from 80ms to 35ms in load test; adds 15ms write latency due to synchronous replication; ops must monitor replication lag alert."

ADRs are organizational memory with git blame — cheap to write, expensive to omit when the architect leaves and the bus factor hits one.

## ADR review in architecture sync

Monthly or quarterly sync agenda item: list Proposed ADRs older than 30 days — accept, reject, or request revision. Rejected ADRs get status Rejected with reason — prevents zombie proposals.

## Integrating with RFC process

Large initiatives: RFC explores options (2 pages), ADR records decision (1 page), implementation follows. RFC comments inform ADR Context section — link RFC PR in ADR header.

## Measuring ADR effectiveness

Qualitative signal: new hires stop asking "why Kafka" in Slack — they read ADR-0004. Quantitative: count repeated architecture debates in meeting notes — should decrease for documented decisions.

## Security-sensitive decisions

Auth model, encryption, and data residency choices always get ADRs — audit trail for compliance questions. Link to threat model diagram when security ADR references trust boundaries.

## Platform team ADR catalog

Platform publishes ADRs for org-wide defaults (Kubernetes ingress, observability stack). Product teams reference platform ADRs in local ADRs: "Conforms to ADR-PLAT-003 logging standard."

## Localization for global teams

ADRs written in English with glossary for domain terms — translate summary bullets for regional engineering leads if language barrier blocks adoption. Full ADR translation rarely worth cost.

Architecture Decision Records work when they are short, honest, versioned beside code, and reviewed like production changes — shelfware ADRs in Confluence nobody reads are worse than no ADRs because they create false confidence.

## Practical follow-through (1)

Ship the smallest vertical slice first — one route, one widget, one index configuration — with rollback documented before expanding scope. Baseline the user-visible metric this work protects (latency, recall, conversion, task success rate) for seven days before change and seven days after in your largest market.

Compare canary p75 to control before full rollout. Exercise edge paths manually: refresh, back navigation, double-submit, offline mode, and keyboard-only flows. When assumptions change — traffic doubles, vendor upgrades, org restructure — revisit whether the original design still fits; quiet periods hide drift until the next incident.

## Practical follow-through (2)

Ship the smallest vertical slice first — one route, one widget, one index configuration — with rollback documented before expanding scope. Baseline the user-visible metric this work protects (latency, recall, conversion, task success rate) for seven days before change and seven days after in your largest market.

Compare canary p75 to control before full rollout. Exercise edge paths manually: refresh, back navigation, double-submit, offline mode, and keyboard-only flows. When assumptions change — traffic doubles, vendor upgrades, org restructure — revisit whether the original design still fits; quiet periods hide drift until the next incident.

## Practical follow-through (3)

Ship the smallest vertical slice first — one route, one widget, one index configuration — with rollback documented before expanding scope. Baseline the user-visible metric this work protects (latency, recall, conversion, task success rate) for seven days before change and seven days after in your largest market.

Compare canary p75 to control before full rollout. Exercise edge paths manually: refresh, back navigation, double-submit, offline mode, and keyboard-only flows. When assumptions change — traffic doubles, vendor upgrades, org restructure — revisit whether the original design still fits; quiet periods hide drift until the next incident.

## Practical follow-through (4)

Ship the smallest vertical slice first — one route, one widget, one index configuration — with rollback documented before expanding scope. Baseline the user-visible metric this work protects (latency, recall, conversion, task success rate) for seven days before change and seven days after in your largest market.

Compare canary p75 to control before full rollout. Exercise edge paths manually: refresh, back navigation, double-submit, offline mode, and keyboard-only flows. When assumptions change — traffic doubles, vendor upgrades, org restructure — revisit whether the original design still fits; quiet periods hide drift until the next incident.

## Supersede workflow

New ADR marks old as Superseded with link — never delete rejected decisions. Git history plus ADR tombstones prevent relitigating settled debates every hiring wave.

## Architecture review cadence

Biweekly 30-minute ADR triage: accept, reject, or request revision on Proposed entries — stale Proposed status older than 30 days fails lint job.

## ADR numbering and links

Reference ADR numbers in commit messages (`implements ADR-0012`). Supersede, never delete — link forward from old to new. Proposed ADRs older than 30 days should be accepted or rejected in architecture sync, not left ambiguous.

## PR template ADR link

Require ADR number for persistence and messaging changes — reviewers verify decision context before code.
