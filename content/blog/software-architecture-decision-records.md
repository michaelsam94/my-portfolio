---
title: "Architecture Decision Records"
slug: "software-architecture-decision-records"
description: "Document architecture decisions with ADRs: lightweight templates, when to write them, storage in repo, and avoiding shelfware."
datePublished: "2025-08-07"
dateModified: "2025-08-07"
tags: ["Architecture", "Documentation", "Engineering Process", "ADR"]
keywords: "architecture decision record, ADR template, document architecture decisions, Michael Nygard ADR, architectural decision log, MADR format"
faq:
  - q: "What decisions deserve an ADR?"
    a: "Decisions that are hard to reverse, affect multiple teams, or generate recurring debate: database choice, messaging bus, auth model, monolith vs services split, and public API versioning strategy. Skip ADRs for routine library bumps or formatting choices—over-documenting dilutes attention from decisions that actually constrain the system for years."
  - q: "Where should ADRs live?"
    a: "In the repository beside code—docs/adr/ or adr/ with numbered markdown files versioned with git. Link from README or internal wiki index. ADRs in Confluence alone drift from implementation; repo storage ties decisions to commits that implement them and survives tool migrations."
  - q: "How do I handle superseded decisions?"
    a: "Mark status Superseded by ADR-0012 with link; do not delete old ADRs. History explains why you left Postgres-only for read replicas and prevents new hires from relitigating settled tradeoffs without context. Accepted, Deprecated, Superseded statuses keep the log honest."
---

Three engineers re-debated Kafka versus RabbitMQ because the original choice lived in a departed architect's slide deck. Architecture Decision Records (ADRs) capture context, decision, and consequences in a few hundred words—optimized for the reader six months later asking "why on earth did we do this?" Michael Nygard's format spread because it fits pull requests, not because enterprises love paperwork.


## Minimal template

```markdown
# ADR-0007: Use PostgreSQL as system of record

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.
## Status
Accepted

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.
## Context
We need ACID transactions for billing and reporting joins.
Team knows Postgres; managed RDS available.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.
Decision:
PostgreSQL 16 on RDS as primary datastore.
Read replicas for analytics after Q3.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.
Consequences:
+ Strong consistency, mature tooling
- Horizontal write scaling limited; revisit sharding if >10k TPS
```

Number sequentially (`0001`, `0002`). Title is searchable.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## When to write

Open ADR PR *before* or alongside implementation PR for significant forks. Reviewers comment on decision merit separately from code style. Retroactive ADRs help onboarding when documenting existing system—label `Accepted (documenting existing)`.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## MADR variant

Markdown Any Decision Records add optional sections: decision drivers, considered options, pros/cons tables. Useful for contentious picks; skip for obvious choices.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Linking code

Reference ADR in commit message: `Implement read replica routing (ADR-0007)`. Code search finds rationale. Conversely, ADR links to spike branch or POC PR.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Avoiding ADR graveyard

- Keep under one page
- Name real alternatives you rejected
- Record measurable consequences ("expect 20ms added latency")
- Review ADRs in quarterly architecture sync—supersede when reality diverges

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Team workflow

```
Proposal PR → discussion → Accepted ADR merged → implementation PRs
```

Disagreements documented in PR comments become Context edits—not Slack loss.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.


adr-tools (`adr new`), Log4brains static site, or plain markdown. No mandatory SaaS.

ADR PR before or alongside implementation for significant forks. Status Superseded links forward—never delete history.

Keep under one page. Name real alternatives rejected. Record measurable consequences. Quarterly architecture sync supersedes stale ADRs when reality diverged.

adr-tools or Log4brains optional—markdown in repo is enough.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Resources

- [Documenting Architecture Decisions (Michael Nygard)](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)
- [adr.github.io](https://adr.github.io/)
- [MADR template](https://adr.github.io/madr/)
- [Thoughtworks Technology Radar: ADRs](https://www.thoughtworks.com/radar/techniques/lightweight-architecture-decision-records)
- [AWS Prescriptive Guidance: ADR process](https://docs.aws.amazon.com/prescriptive-guidance/latest/architectural-decision-records/welcome.html)
