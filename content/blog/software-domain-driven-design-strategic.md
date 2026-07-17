---
title: "Strategic DDD and Bounded Contexts"
slug: "software-domain-driven-design-strategic"
description: "Apply strategic Domain-Driven Design: bounded contexts, context maps, ubiquitous language, and aligning teams with subdomains."
datePublished: "2025-08-15"
dateModified: "2026-07-17"
tags:
  - "Engineering"
keywords: "strategic domain driven design, bounded context, context map, core subdomain, ubiquitous language, DDD team topology"
faq:
  - q: "What is a bounded context in practice?"
    a: "A bounded context is a boundary within which a domain model and ubiquitous language are consistent. Customer means something different in Sales versus Support—that is two contexts, not one mega Customer entity with forty nullable fields. Code modules, team ownership, and ideally deployment units align to context boundaries over time."
  - q: "How do I identify subdomains?"
    a: "Interview domain experts and map capabilities: core (competitive advantage), supporting ( necessary but not differentiating), generic (buy or outsource—email, payments). Core subdomains deserve best engineers and rich models; generic ones should not consume custom architecture passion. Event storming workshops surface natural clusters."
  - q: "What goes on a context map?"
    a: "Boxes for each bounded context and lines showing integration relationships: ACL, shared kernel, customer-supplier, conformist, open host service. The map is sociotechnical—who publishes language, who adapts, where translation happens. Update it when partnerships or org structure changes."
---

Every team called it "the account" but Billing meant ledger identity, CRM meant sales prospect, and Auth meant login credential — one database table, three incompatible mental models. Strategic Domain-Driven Design does not start with entities and repositories; it starts with linguistics and boundaries. Bounded contexts delimit where terms mean one thing; context maps show how contexts relate without pretending one unified enterprise model exists.

## Ubiquitous language

Product, engineering, and domain experts share vocabulary in workshops:

- **Policy** (Insurance): contract terms, not IAM policy
- **Quote** (Sales): priced offer, not string literal

Code names match speech: `IssuePolicyCommand`, not `ProcessDataRequest`. Glossary wiki maintained by product — engineers propose PRs when terms shift.

## Subdomain classification

```
Core:        underwriting rules engine
Supporting:  agent commission calculation
Generic:     payment capture (Stripe)
```

Invest modeling depth proportional to classification. Do not build custom payment kernel when Stripe is generic subdomain — your competitive advantage lives in underwriting, not PCI scope.

## Drawing bounded contexts

Start messy on whiteboard — refine to modules:

```
[Quoting] --ACL--> [Legacy Rating Engine]
[Policy Admin] --events--> [Billing]
[Claims] customer-supplier [Policy Admin]
```

Relationships dictate integration style: Anti-Corruption Layer for legacy, published language for stable APIs, conformist when upstream owns the model and you adapt.

## Context map workshops

Run event storming quarterly with product and engineering. Orange stickies (domain events), blue (commands), yellow (aggregates). Pink stickies (conflicts) often mark context boundaries. Update context map when org restructures — stale maps mislead new architects more than no map.

## Team alignment and Conway's law

One team per context where possible. Two teams one context breeds model schism — merge conflicts in ubiquitous language, incompatible shortcuts. Temporary shared ownership needs explicit governance and merge cadence for glossary.

## Evolution from monolith

Modular monolith enforces package-private boundaries between contexts before network boundaries. ArchUnit or custom lint: `@Deprecated crossContext` for illegal imports from quoting into billing internals. Extract microservice when scaling or team boundary proves need — not as day-one default.

## Anti-pattern: unified canonical model

Enterprise data model committees shipping XSD for all divisions move pain to integration without solving semantic mismatch. Prefer explicit translation at edges via ACL over one true `Customer` table with forty nullable columns.

## Core vs supporting investment

Core subdomain gets best engineers and rich models; supporting gets adequate quality; generic gets buy or thin adapter. Roadmap arguments reference subdomain map — "that feature is generic email, use SendGrid" ends debate.

## When to skip heavy DDD

Small product with one clear domain — over-partitioning contexts adds meetings without reducing bugs. Revisit when onboarding confusion or cross-team integration defects spike.

## Context map in repo

Store `docs/context-map.md` or PNG from workshop with date and attendees. Link from README. New service proposals reference which contexts they touch — architecture review starts from map, not blank whiteboard.

Strategic DDD aligns language, boundaries, and teams before tactical patterns — entities and repositories mean little if "customer" still means three different things in one standup.

## Partnership patterns on context maps

**Customer-supplier:** downstream context depends on upstream roadmap — negotiate SLAs for API changes. **Conformist:** downstream accepts upstream model wholesale — use when upstream is external vendor. **Open host service:** publish language with documentation — internal platform pattern.

## Physical versus logical boundaries

Bounded contexts start logical — separate packages in monolith. Physical separation (services) comes later when scaling or team boundaries require independent deploy. Premature service extraction without context clarity multiplies translation bugs.

## Event storming facilitation tips

Timebox 90 minutes; invite product owner and senior engineer minimum. Start with domain event stickies left-to-right timeline. Identify aggregates where commands attach. End with candidate context boundaries — do not force final map in one session.

## Legacy system ACL placement

Every legacy integration gets Anti-Corruption Layer at boundary — never leak legacy field names (`CUST_NBR`) into core domain. ACL team owns translation tests when legacy releases change.

## Measuring DDD adoption success

Fewer cross-team bugs on integration contracts. Faster onboarding when glossary answers "what is a policy." Reduced nullable-column tables — bounded contexts split schemas. Qualitative survey after six months.

## Relationship to microservices

Microservice per bounded context is idealized — practical systems share databases during migration. Context map still valuable when services share Postgres schema with schema-per-context naming discipline.

Strategic DDD is a communication and alignment tool first — code structure follows once language and boundaries stabilize across product and engineering.

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

## Practical follow-through (5)

Ship the smallest vertical slice first — one route, one widget, one index configuration — with rollback documented before expanding scope. Baseline the user-visible metric this work protects (latency, recall, conversion, task success rate) for seven days before change and seven days after in your largest market.

Compare canary p75 to control before full rollout. Exercise edge paths manually: refresh, back navigation, double-submit, offline mode, and keyboard-only flows. When assumptions change — traffic doubles, vendor upgrades, org restructure — revisit whether the original design still fits; quiet periods hide drift until the next incident.

## Glossary in repo

Maintain `docs/glossary.md` beside code. PRs introducing domain terms update glossary in same merge.

## Remote event storming tips

Use FigJam timers and a dedicated facilitator — 90 minutes maximum. Export the context map PNG into `docs/` in the same PR as glossary updates so the map stays versioned with code.

## Team topologies mapping

Stream-aligned teams own one bounded context — complicated subgraphs get enabling teams for ACL tooling. Document in context map which squad answers PagerDuty for each integration edge.

## Ubiquitous language glossary

Glossary PRs required when introducing new domain term in API — product and engineering share review. Prevents `Policy` meaning insurance contract in one service and authorization rule in another.

## Context map workshops

Run event storming quarterly with product and engineering. Pink stickies (conflicts) often mark context boundaries. Update the context map when org restructures — stale maps mislead new architects more than no map.

## Event storming quarterly

Refresh context map after org restructure — stale boundaries mislead architects more than no map.
