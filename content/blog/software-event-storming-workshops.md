---
title: "Event Storming Workshops"
slug: "software-event-storming-workshops"
description: "Run event storming workshops: facilitation, sticky note flow, hot spots, and turning domain discovery into actionable backlog."
datePublished: "2025-08-22"
dateModified: "2025-08-22"
tags: ["DDD", "Workshops", "Discovery", "Collaboration"]
keywords: "event storming workshop, domain discovery, Alberto Brandolini, big picture event storming, process modeling, hot spot DDD"
faq:
  - q: "Who must attend an event storming session?"
    a: "Include people who know the business rules—not only engineers. Domain experts, support leads, product managers, and senior engineers who've seen production incidents. Skip large passive audiences; eight to twelve active participants works. Decisions emerge from contested sticky notes, not from spectators nodding."
  - q: "How long does a useful workshop take?"
    a: "Big picture storming needs half a day minimum; process-level modeling of one flow can fit three hours with prep. Stop when energy drops—better schedule a follow-up than rush hollow conclusions. Remote sessions work with Miro/FigJam if facilitator enforces one-speaker-at-a-time on hot spots."
  - q: "What deliverable should we leave with?"
    a: "Photographed board, list of hot spots (open questions), candidate bounded contexts, and prioritized backlog items—often spikes on ambiguous rules or ACL boundaries. The value is shared language and discovered gaps, not a polished UML diagram nobody opens."
---

The backlog said "build refund API." Nobody agreed whether partial refunds applied to bundled SKUs until legal joined a whiteboard for ninety minutes. Event storming—Alberto Brandolini's workshop format—maps business processes as domain events on sticky notes: `OrderPlaced`, `PaymentCaptured`, `RefundIssued`. Commands and actors attach; hot spots mark confusion. It is the fastest path from tribal knowledge to a model the room believes—not a consultant's diagram imposed afterward.

## Formats

| Type | Scope | Duration |
|------|-------|----------|
| Big Picture | Whole business | 1–2 days |
| Process | Single journey | 2–4 hours |
| Design Level | Implementation | Follow-up |

Start big picture unless scope is one feature.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.
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

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.
## Remote tips

Prepare Miro template with swim lanes. Timer boxes per segment. Domain expert's voice wins tie-breaks on terminology—engineers document, not override.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.
## From wall to code

Cluster events into bounded context candidates. Draw context map relationships. Translate hot spots into ADRs or spikes:

- "Can refund exceed captured amount?" → ADR + rule tests
- "Legacy ERP status sync" → ACL spike

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.
## Common failures

- Engineers dominate; experts stay quiet—facilitator redirects questions
- Jumping to microservices on day one—stay domain-level
- No photos or export—board erased, knowledge lost

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.
## When not to event storm

Tiny feature with known CRUD and one developer—overkill. Re-storm when entering new market or after major regulatory change.

Facilitator redirects domain experts when engineers dominate terminology disputes. Photograph board and export hot spots with owners before erasing.

Remote: Miro template plus strict one-speaker rule on red stickies. Stop when energy drops—schedule follow-up rather than hollow conclusions.

Big picture before process-level unless scope is single feature.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

Document the decision, owner, and rollback path in your team wiki the same week you ship. Future you will not remember which environment variable toggled the behavior unless it is written next to the runbook entry and linked from the alert. That habit costs ten minutes per change and saves hours when pagination or auth misbehaves under a single large tenant.


Run the change through your standard PR checklist: tests, observability, and a two-minute rollback drill in staging. Small operational habits accumulate into systems that survive on-call nights without heroics.


Share a short write-up in your engineering channel after rollout: what shipped, what metric you watch, and who owns follow-up. That closes the loop for teammates who were not in the PR and surfaces gaps in docs before the next person repeats the same investigation.


Prefer boring, repeatable process over one heroic migration weekend.


Treat operational readiness as part of definition-of-done: dashboards, alerts, runbook links, and a named owner. Skipping those steps ships code that works in demo and fails quietly in production until a customer or auditor finds the gap. Schedule the next workshop before the board is erased so momentum does not depend on one facilitator's calendar.

## Resources

- [Event Storming (official site)](https://www.eventstorming.com/)
- [Alberto Brandolini: Introducing Event Storming](https://leanpub.com/introducing_eventstorming)
- [Event Storming cheat sheet (DDD Crew)](https://github.com/ddd-crew/event-storming)
- [Miro Event Storming template](https://miro.com/templates/event-storming/)
- [Virtual Event Storming guide](https://www.eventstorming.com/virtual-event-storming/)
