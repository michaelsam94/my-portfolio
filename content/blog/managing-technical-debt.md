---
title: "Managing Technical Debt Without Stopping Delivery"
slug: "managing-technical-debt"
description: "How to manage technical debt without a big rewrite: track it honestly, refactor incrementally with the strangler fig pattern, and pay it down while still shipping features."
datePublished: "2026-06-11"
dateModified: "2026-07-17"
tags:
keywords: "technical debt, refactoring, code quality, debt management, legacy code, strangler fig, incremental refactoring"
faq:
  - q: "Should we stop feature work to pay down technical debt?"
    a: "Almost never with a big-bang freeze. Rewrites-from-scratch have a brutal failure rate and stall delivery for months. Instead, pay debt down incrementally — allocate a steady slice of capacity, and refactor the code you're already touching for a feature so cleanup rides along with delivery."
  - q: "What is the strangler fig pattern?"
    a: "It's a way to replace a legacy system gradually. You route traffic through a facade, build new functionality alongside the old, and migrate piece by piece until the old system is fully surrounded and can be removed — no risky single cutover."
  - q: "How do I convince the business to invest in technical debt?"
    a: "Translate debt into outcomes the business cares about: slower delivery, more incidents, longer onboarding. Track the interest — time lost to workarounds and bugs in specific areas — so the case is concrete rather than 'the code is ugly.'"
---
"Technical debt" is the most abused phrase in software. It gets stretched to cover code someone dislikes, decisions made before they joined, and any refactor they'd rather be doing than the feature they're assigned. That vagueness is a problem, because when everything is debt, nothing gets prioritized, and the genuinely dangerous debt hides among the merely unfashionable. Managing technical debt well starts with being honest about what it actually is and what it's costing you.

Ward Cunningham's original metaphor is precise and worth reclaiming: debt is what you take on when you ship code that's not-quite-right in order to learn or deliver faster *now*, planning to fix it later. Like financial debt, a bit of it is leverage — it gets you to market. The danger is the *interest*: the ongoing tax of working around the shortcut. Debt you never service compounds until the interest payments consume all your delivery capacity.

## Not all debt is equal

The single most useful move is to stop treating debt as one undifferentiated pile. Some of it is high-interest and dangerous; most of it is cosmetic and harmless. A quadrant I find genuinely useful is Fowler's distinction between deliberate/inadvertent and prudent/reckless debt, but for day-to-day triage I sort debt by two axes: how much it's costing now, and how likely it is to bite.

| | Low blast radius | High blast radius |
|---|---|---|
| **Rarely touched** | ignore it (it's fine) | document, watch, don't touch |
| **Frequently touched** | fix opportunistically | prioritize actively |

The counterintuitive cell is the bottom-left: ugly code in a hot path is a real problem, while ugly code in a module nobody has opened in three years is *not debt worth paying* — it works, it's stable, and refactoring it is pure risk with no return. The instinct to "clean up" stable code is where a lot of well-meaning effort gets wasted. Spend your refactoring budget where the code churns and where a failure hurts.

## Track the interest, not the ugliness

To prioritize debt you have to make it visible, and "this code is bad" is not a measurement. What's measurable is the interest: where do engineers repeatedly lose time to workarounds, where do bugs cluster, which files does every incident seem to touch?

Concrete signals I track: change-failure rate by area (which modules break when you touch them), time-to-first-commit for new hires in each part of the codebase, and the recurring "we can't do X because of Y" comments in planning. Git history is a goldmine here — files with high churn *and* high bug density are your highest-interest debt, and you can find them mechanically rather than by opinion. When you can say "we lose roughly two days a sprint to the auth module's quirks," you have a business case. "The auth code is gross" gets deprioritized every time, and should.

## Pay it down while shipping

The temptation, once debt is visible, is the Big Rewrite: freeze features, rebuild the rotten thing cleanly, ship it triumphantly. This almost always ends badly. Rewrites take far longer than estimated, the new system re-learns every edge case the old one encoded, and the business starves for features the entire time. I've watched more than one rewrite get cancelled halfway, leaving two half-working systems instead of one.

The alternative is incremental. Two techniques carry most of the load:

**The Boy Scout rule / opportunistic refactoring.** Leave code a little better than you found it. When a feature takes you into a messy function, clean *that* function as part of the work. Debt gets paid down exactly where delivery is already happening, so it never competes with features for a separate budget. Over months this compounds quietly, and the hot paths — the ones you touch most — improve fastest, which is precisely where you want the improvement.

**A steady, small allocation.** Reserve a consistent slice of each cycle — say 15–20% — for debt the opportunistic approach won't reach. Not a heroic "debt sprint" (those signal the debt got out of hand and rarely repeat), but a sustainable, boring, permanent line item. Consistency beats intensity; a fixed small tax paid every sprint keeps debt flat, while sporadic big pushes let it grow between them.

## The strangler fig for the big stuff

Some debt is too large for opportunistic cleanup — a legacy subsystem, an aging service, a data model that no longer fits. For those, the strangler fig pattern replaces the Big Rewrite with a gradual, low-risk migration. The name comes from the vine that grows around a tree until it can stand on its own and the original is gone.

Mechanically: put a facade in front of the old system, then build new functionality behind that facade while incrementally redirecting slices of traffic from old to new. The old and new run side by side; you migrate one capability at a time and delete the old piece once nothing routes to it.

```
        ┌───────────┐   route by capability
client ─▶│  facade   │──┬──▶ legacy system  (shrinking)
        └───────────┘  └──▶ new system     (growing)
```

[Feature flags](https://blog.michaelsam94.com/feature-flags-trunk-based-development/) make this controllable — you flip a capability from old to new for 1% of traffic, watch, then widen — and it pairs naturally with the [expand-contract approach to schema change](https://blog.michaelsam94.com/zero-downtime-database-migrations/) when the migration touches the database. The result is that a scary replacement becomes a series of small, reversible, individually-shippable steps, each delivering value on its own. If the migration stalls, you're left with a working hybrid, not a smoking crater.

## Make the invisible visible to the business

The hardest part of debt management is usually not technical — it's the conversation with people who see only the feature backlog. Framing matters. "Refactor the payment module" is an easy no. "We're spending two days a sprint working around the payment module, and change-failure rate there is triple the rest of the codebase" reframes it as the delivery and reliability problem it actually is. Tie debt to the metrics leadership already tracks — velocity, incident rate, time-to-market — and it stops being an engineering indulgence.

Managing technical debt isn't about achieving clean code; it's about keeping the codebase's carrying cost low enough that you can keep delivering. Triage ruthlessly so you only pay down debt that's actually charging interest, refactor incrementally so cleanup rides alongside features, use the strangler fig for the big replacements, and make the cost legible to the people who fund the work. Done steadily, none of it requires stopping delivery — which is the whole point. This is the same pragmatism I bring to [architecture work generally](https://michaelsam94.com/): the goal is a system you can keep changing, not a museum piece.

## Resources

- [Martin Fowler — Technical Debt](https://martinfowler.com/bliki/TechnicalDebt.html)
- [Martin Fowler — Technical Debt Quadrant](https://martinfowler.com/bliki/TechnicalDebtQuadrant.html)
- [Martin Fowler — StranglerFigApplication](https://martinfowler.com/bliki/StranglerFigApplication.html)
- [Ward Cunningham — Debt Metaphor (video)](https://wiki.c2.com/?WardExplainsDebtMetaphor)
- [Martin Fowler — Opportunistic Refactoring](https://martinfowler.com/bliki/OpportunisticRefactoring.html)
- [Google Engineering Practices — Code Review](https://google.github.io/eng-practices/review/)
