---
title: "Strategic DDD and Bounded Contexts"
slug: "software-domain-driven-design-strategic"
description: "Apply strategic Domain-Driven Design: bounded contexts, context maps, ubiquitous language, and aligning teams with subdomains."
datePublished: "2025-08-15"
dateModified: "2025-08-15"
tags: ["DDD", "Architecture", "Team Design", "Bounded Context"]
keywords: "strategic domain driven design, bounded context, context map, core subdomain, ubiquitous language, DDD team topology"
faq:
  - q: "What is a bounded context in practice?"
    a: "A bounded context is a boundary within which a domain model and ubiquitous language are consistent. Customer means something different in Sales versus Support—that is two contexts, not one mega Customer entity with forty nullable fields. Code modules, team ownership, and ideally deployment units align to context boundaries over time."
  - q: "How do I identify subdomains?"
    a: "Interview domain experts and map capabilities: core (competitive advantage), supporting ( necessary but not differentiating), generic (buy or outsource—email, payments). Core subdomains deserve best engineers and rich models; generic ones should not consume custom architecture passion. Event storming workshops surface natural clusters."
  - q: "What goes on a context map?"
    a: "Boxes for each bounded context and lines showing integration relationships: ACL, shared kernel, customer-supplier, conformist, open host service. The map is sociotechnical—who publishes language, who adapts, where translation happens. Update it when partnerships or org structure changes."
---

Every team called it "the account" but Billing meant ledger identity, CRM meant sales prospect, and Auth meant login credential—one database table, three incompatible mental models. Strategic Domain-Driven Design does not start with entities and repositories; it starts with linguistics and boundaries. Bounded contexts delimit where terms mean one thing; context maps show how contexts relate without pretending one unified enterprise model exists.


## Ubiquitous language

Product, engineering, and experts share vocabulary in workshops:

- **Policy** (Insurance): contract terms, not IAM policy
- **Quote** (Sales): priced offer, not string literal

Code names match speech: `IssuePolicyCommand`, not `ProcessDataRequest`. Glossary wiki maintained by product.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Subdomain classification

```
Core:        underwriting rules engine
Supporting:  agent commission calculation
Generic:     payment capture (Stripe)
```

Invest modeling depth proportional to classification. Do not build custom payment kernel.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Drawing bounded contexts

Start messy on whiteboard— refine to modules:

```
[Quoting] --ACL--> [Legacy Rating Engine]
[Policy Admin] --events--> [Billing]
[Claims] customer-supplier [Policy Admin]
```

Relationships dictate integration style from prior post on ACL.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Team alignment

Conway's law applies: one team per context where possible. Two teams one context breeds model schism. Temporary shared ownership needs explicit governance and merge cadence for glossary.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Evolution from monolith

Modular monolith enforces package-private boundaries between contexts before network boundaries. `@Deprecated crossContext` lint for illegal imports.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Anti-pattern: unified canonical model

Enterprise data model committees shipping XSD for all divisions move pain to integration without solving semantic mismatch. Prefer explicit translation at edges.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.


Small product with one clear domain—over-partitioning contexts adds meetings. Revisit when onboarding confusion or cross-team bugs spike.

Context map updated when partnerships or org structure changes. Shared kernel stays minimal—generic IDs and money, not dumping ground for shared business rules.

Conway's law: two teams one context breeds model schism. Event storming before drawing microservice boundaries.

Small single-domain products skip over-partitioning—revisit when onboarding confusion spikes.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

Document the decision, owner, and rollback path in your team wiki the same week you ship. Future you will not remember which environment variable toggled the behavior unless it is written next to the runbook entry and linked from the alert. That habit costs ten minutes per change and saves hours when pagination or auth misbehaves under a single large tenant.



Run the change through your standard PR checklist: tests, observability, and a two-minute rollback drill in staging. Small operational habits accumulate into systems that survive on-call nights without heroics.


Share a short write-up in your engineering channel after rollout: what shipped, what metric you watch, and who owns follow-up. That closes the loop for teammates who were not in the PR and surfaces gaps in docs before the next person repeats the same investigation.


Prefer boring, repeatable process over one heroic migration weekend.


Treat operational readiness as part of definition-of-done: dashboards, alerts, runbook links, and a named owner. Skipping those steps ships code that works in demo and fails quietly in production until a customer or auditor finds the gap.

## Resources

- [Domain-Driven Design (Eric Evans)](https://www.domainlanguage.com/ddd/)
- [Bounded Context (Martin Fowler)](https://martinfowler.com/bliki/BoundedContext.html)
- [Context Map (DDD community)](https://github.com/ddd-crew/context-mapping)
- [Team Topologies (Skelton & Pais)](https://teamtopologies.com/)
- [Domain-Driven Design Distilled (Vaughn Vernon)](https://vaughnvernon.com/)
