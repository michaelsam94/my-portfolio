---
title: "Event Storming Workshops"
slug: "software-event-storming-workshops"
description: "Run event storming workshops: facilitation, sticky note flow, hot spots, and turning domain discovery into actionable backlog."
datePublished: "2025-08-22"
dateModified: "2026-07-17"
tags: ["DDD", "Workshops", "Discovery", "Collaboration"]
keywords: "event storming workshop, domain discovery, Alberto Brandolini, big picture event storming, process modeling, hot spot DDD"
faq:
  - q: "Who must attend an event storming session?"
    a: "Include people who know the business rules—not only engineers. Domain experts, support leads, product managers, and senior engineers who've seen production incidents. Skip large passive audiences; eight to twelve active participants works. Decisions emerge from contested sticky notes, not from spectators nodding."
  - q: "How long does a useful workshop take?"
    a: "Big picture storming needs half a day minimum; process-level modeling of one flow can fit three hours with prep. Stop when energy drops—better schedule a follow-up than rush hollow conclusions. Remote sessions work with Miro/FigJam if facilitator enforces one-speaker-at-a-time on hot spots."
  - q: "What deliverable should we leave with?"
    a: "Photographed board, list of hot spots (open questions), candidate bounded contexts, and prioritized backlog items—often spikes on ambiguous rules or ACL boundaries. The value is shared language and discovered gaps, not a polished UML diagram nobody opens."
faqAnswers:
  - question: "When is software event storming workshops the wrong approach?"
    answer: "When a simpler control already covers the risk, or when the operational cost exceeds the benefit for your threat and traffic model."
  - question: "What should we measure for software event storming workshops?"
    answer: "Pair a leading operational signal with a lagging user or risk outcome, reviewed on a fixed cadence with a named owner."
  - question: "How do we roll back software event storming workshops safely?"
    answer: "Keep the prior artifact or config warm, rehearse the revert once in staging, and document the one-command rollback for on-call."
---
The backlog said "build refund API." Nobody agreed whether partial refunds applied to bundled SKUs until legal joined a whiteboard for ninety minutes. Event storming—Alberto Brandolini's workshop format—maps business processes as domain events on sticky notes: `OrderPlaced`, `PaymentCaptured`, `RefundIssued`. Commands and actors attach; hot spots mark confusion. It is the fastest path from tribal knowledge to a model the room believes—not a consultant's diagram imposed afterward.

## Formats

| Type | Scope | Duration |
|------|-------|----------|
| Big Picture | Whole business | 1–2 days |
| Process | Single journey | 2–4 hours |
| Design Level | Implementation | Follow-up |

Start big picture unless scope is one feature.

## Facilitation flow

1. **Chaotic exploration:** orange stickies = domain events, past tense verbs, left-to-right timeline
2. **Enforce timeline:** facilitator walks narrative, asks "what happened before?"
3. **Commands:** blue stickies = actions causing events
4. **Actors/policies:** yellow = humans, pink = systems, green = policies reacting to events
5. **Hot spots:** red stickies on arguments—do not resolve live if blocked; assign owner

```
[Place Order] → OrderPlaced → [Capture Payment] → PaymentCaptured
                                    ↓
                              PaymentFailed (hot spot: retry?)
```

## Remote tips

Prepare Miro template with swim lanes. Timer boxes per segment. Domain expert's voice wins tie-breaks on terminology—engineers document, not override.

## From wall to code

Cluster events into bounded context candidates. Draw context map relationships. Translate hot spots into ADRs or spikes:

- "Can refund exceed captured amount?" → ADR + rule tests
- "Legacy ERP status sync" → ACL spike

## Common failures

- Engineers dominate; experts stay quiet—facilitator redirects questions
- Jumping to microservices on day one—stay domain-level
- No photos or export—board erased, knowledge lost

## When not to event storm

Tiny feature with known CRUD and one developer—overkill. Re-storm when entering new market or after major regulatory change.

Facilitator redirects domain experts when engineers dominate terminology disputes. Photograph board and export hot spots with owners before erasing.

Remote: Miro template plus strict one-speaker rule on red stickies. Stop when energy drops—schedule follow-up rather than hollow conclusions.

Big picture before process-level unless scope is single feature.

Prefer boring, repeatable process over one heroic migration weekend.

Treat operational readiness as part of definition-of-done: dashboards, alerts, runbook links, and a named owner. Skipping those steps ships code that works in demo and fails quietly in production until a customer or auditor finds the gap. Schedule the next workshop before the board is erased so momentum does not depend on one facilitator's calendar.

## Facilitation fixes that save workshops

Silent sticky-note round (5 min) before discussion prevents loudest VP from anchoring wrong aggregates. End with one vertical slice mapped to repo folders — assign ADR owner before room clears. Export Miro within 24h; guest links expire and you lose the timeline photo that auditors actually read during SOC interviews.

## Facilitation fixes that save workshops

Silent sticky-note round (5 min) before discussion prevents loudest VP from anchoring wrong aggregates. End with one vertical slice mapped to repo folders — assign ADR owner before room clears. Export Miro within 24h; guest links expire and you lose the timeline photo that auditors actually read during SOC interviews.

## Field metrics and rollback

Capture baseline p75 error rate and latency on tier-1 routes before merge. Compare seven days post-deploy sliced by mobile and region. Document rollback in PR and runbook.

## Resources

- [Event Storming (official site)](https://www.eventstorming.com/)
- [Alberto Brandolini: Introducing Event Storming](https://leanpub.com/introducing_eventstorming)
- [Event Storming cheat sheet (DDD Crew)](https://github.com/ddd-crew/event-storming)
- [Miro Event Storming template](https://miro.com/templates/event-storming/)
- [Virtual Event Storming guide](https://www.eventstorming.com/virtual-event-storming/)

## Architecture decisions around software event storming workshops

Architecture work around software event storming workshops is mostly about boundaries and change cost. Draw the context map before naming folders. If two teams deploy on different cadences, a shared mutable model will become the incident factory.

Practical rules for software event storming workshops:
- Prefer modular monolith seams you can extract later over premature microservices
- Encode ubiquitous language in types and test names, not slide decks
- Event contracts versioned; consumers tolerate additive changes only
- Feature toggles have owners and burn-down dates — permanent toggles are config debt

Workshop output should include a decision record: context, options, chosen path, and the metric that would force a revisit.

| Signal | Target | Alarm |
|--------|--------|-------|
| Plan apply time | Team-defined SLO | Page on burn rate |
| Drift open count | Baseline − noise | Ticket if sustained |
| Failed policy checks | Budget cap | Weekly review |

## Ownership and on-call for software event storming workshops

Reviewers should challenge assumptions encoded in software event storming workshops: defaults copied from tutorials, timeouts that exceed upstream SLAs, and authz checks applied only on the primary UI path. Require a short threat or failure note in the PR when the change touches a trust boundary.

Concrete probes:
1. Scenario C for software event storming workshops: traffic 3× baseline — prove autoscaling or shedding keeps the golden journey healthy.
2. Scenario A for software event storming workshops: partial dependency outage — prove clients degrade gracefully and retries do not amplify load.
3. Scenario B for software event storming workshops: bad config shipped — prove rollback within the declared RTO without data corruption.

## Rollout sequence that worked for software event storming workshops

Roll out software event storming workshops behind a flag or weighted route when possible. Start with internal users or a low-risk geography. Watch the signals in the table for at least one full business cycle before calling the migration done. Keep the previous path warm until error budgets stabilize.

Document the owner, the dashboard, and the single command that reverts the change. If that sentence is hard to write, the design is not ready for production traffic.

## Observability cardinality around software event storming workshops

Detail 1 (641): for software event storming workshops, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When observability cardinality around software event storming workshops becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break software event storming workshops, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about software event storming workshops: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.

## Caching interactions with software event storming workshops

Detail 2 (136): for software event storming workshops, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When caching interactions with software event storming workshops becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break software event storming workshops, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about software event storming workshops: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.

## Multi-tenant concerns in software event storming workshops

Detail 3 (240): for software event storming workshops, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When multi-tenant concerns in software event storming workshops becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break software event storming workshops, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about software event storming workshops: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.

## Compliance evidence for software event storming workshops

Detail 4 (967): for software event storming workshops, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When compliance evidence for software event storming workshops becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break software event storming workshops, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about software event storming workshops: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.