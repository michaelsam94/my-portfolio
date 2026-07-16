---
title: "Writing Design Docs That Get Read"
slug: "career-writing-design-docs"
description: "Design docs align teams before code is written. Structure docs with problem statements, options with tradeoffs, and clear recommendations. Write for skimmers and reviewers who have 15 minutes."
datePublished: "2025-01-13"
dateModified: "2025-01-13"
tags: ["Career", "Engineering", "Documentation"]
keywords: "engineering design doc, RFC template, technical design document, architecture decision record, design review document"
faq:
  - q: "When should I write a design doc?"
    a: "Write a design doc when the change affects multiple teams, introduces a new system or pattern, has significant irreversibility (database schema, public API), or requires a decision with meaningful tradeoffs. Skip docs for bug fixes, small features following established patterns, and changes contained to one file."
  - q: "How long should a design doc be?"
    a: "Two to four pages for most decisions. One page for small changes. If it's longer than six pages, split into a summary doc and appendices. Reviewers won't read a 20-page doc — they'll skim the summary and miss critical details buried on page 14."
  - q: "What is the difference between a design doc and an ADR?"
    a: "A design doc is a forward-looking proposal seeking feedback before implementation — it includes options, tradeoffs, and open questions. An Architecture Decision Record (ADR) is a retrospective record of a decision already made, capturing context and rationale for future readers. Many teams write a design doc first, then extract an ADR after approval."
---

The rewrite that took three months because nobody agreed on the approach. The migration that broke production because the team didn't know about the edge case in module four. Both preventable with a design doc that took four hours to write and got reviewed before a line of code shipped. Design docs aren't bureaucracy — they're the cheapest place to find flaws in an architecture.

## Template that works

```markdown
# Title: [Verb] [System] [Goal]
# Author: [name] | Status: Draft / In Review / Approved
# Reviewers: [names] | Date: YYYY-MM-DD

## Problem
[2-3 paragraphs: what's broken or missing, why now, what happens if we don't solve it]

## Goals / Non-Goals
**Goals:**
- [Measurable outcome 1]
- [Measurable outcome 2]

**Non-Goals:**
- [Explicitly out of scope — prevents scope creep in review]

## Current State
[How it works today. Diagram if helpful. Link to relevant code.]

## Proposed Solution
[Your recommendation. Architecture diagram. Key data flows.]

## Alternatives Considered
| Option | Pros | Cons | Why rejected |
|--------|------|------|-------------|
| A: ... | ... | ... | ... |
| B: ... | ... | ... | Selected |

## Detailed Design
[APIs, schema changes, sequence diagrams, error handling, migration plan]

## Rollout Plan
[Phases, feature flags, rollback strategy, monitoring]

## Open Questions
- [ ] [Question needing reviewer input]
- [ ] [Decision deferred to implementation]

## Appendix
[Performance estimates, detailed schemas, research links]
```

## Writing for skimmers

Reviewers spend 10–15 minutes. Front-load the decision:

1. **Title** tells them the topic
2. **Problem + Proposed Solution** in the first page
3. **Alternatives** show you considered options (builds trust)
4. **Open Questions** tell them where to focus feedback

Use diagrams for anything with more than two components. A 5-box diagram replaces three paragraphs and survives skimming.

## Options and tradeoffs

Never present one option. Present at least two:

```markdown
### Option A: Event-driven sync via Kafka
- Pro: Decoupled, scales independently
- Con: New infrastructure, operational complexity
- Effort: 4 weeks

### Option B: Direct API calls with retry
- Pro: Simple, uses existing infra
- Con: Tight coupling, cascading failures
- Effort: 1 week

### Recommendation: Option A
The coupling risk in Option B has caused two incidents this quarter.
The 3-week investment pays for itself in reduced on-call burden.
```

Reviewers trust recommendations backed by rejected alternatives more than single-option proposals.

## Getting useful feedback

Share the doc 24–48 hours before the review meeting. Ask specific questions:

```markdown
## Questions for reviewers
1. Is the rollback plan sufficient for the schema migration?
2. Does the caching strategy handle cache invalidation on write?
3. Are we missing a compliance requirement for PII handling?
```

Vague "please review" gets vague "looks good." Specific questions get specific answers.

## Common mistakes

| Mistake | Fix |
|---------|-----|
| Solution before problem | Write problem first, even if you know the answer |
| No non-goals | Explicitly exclude scope |
| Implementation details too early | Focus on what and why, not every class name |
| No rollout plan | Reviewers ask "how do we ship this safely?" |
| Doc never updated after review | Mark status Approved, link to implementation PR |

## ADR for the record

After approval, capture the decision:

```markdown
# ADR-042: Use Kafka for order event sync

## Status: Accepted

## Context
Order service and warehouse service need reliable event delivery...

## Decision
Use Kafka with transactional outbox pattern.

## Consequences
+ Reliable delivery, existing Kafka ops team
- 4 week implementation, new topic to monitor
```

ADRs live in the repo (`docs/adr/042-kafka-order-sync.md`) — searchable forever.

## When not to write a doc

- Following an established pattern ("add CRUD endpoint like the other 12")
- Time-sensitive hotfix (write retro doc after)
- Exploratory spike (write findings, not a proposal)

My threshold: if I'd want input from someone outside the immediate task, it gets a doc.

## Review process that actually works

A design doc without a review ritual becomes shelfware:

1. **Author posts** — link in `#eng-design`, tag 2–3 required reviewers + optional stakeholders
2. **48-hour comment window** — async comments on specific sections, not meeting ambush
3. **Office hour** — optional 30-min sync for unresolved threads only
4. **Decision recorded** — Approved / Approved with changes / Needs revision
5. **ADR filed** — within 24h of approval

Required reviewers should include someone who will **operate** the system, not only peers who wrote similar code. SRE rejection at design time beats production surprise at launch.

## Sizing docs to scope

| Scope | Doc length | Reviewers | Timeline |
|-------|------------|-----------|----------|
| Single service change | 2–4 pages | 2 | 2–3 days |
| Cross-team integration | 6–10 pages | 4–6 | 1 week |
| Platform / architecture | 10–15 pages | 6+ | 2 weeks |

Oversized docs don't get read. If you're past 15 pages, split into "overview" plus linked deep-dives per component. The overview doc is what executives and adjacent teams read.

## Stakeholder-specific sections

Add a short section per audience — same doc, different entry points:

- **Product:** user impact, rollout timeline, feature flags
- **Security:** threat model, data flows, auth changes
- **Legal/compliance:** PII handling, retention, audit requirements
- **Support:** customer-visible changes, rollback user experience

One paragraph each prevents the "legal found out at launch" failure mode.

## Post-implementation accountability

Link the implementation PR to the design doc. After ship, add a **"What we learned"** section:

- Estimates vs actuals
- Deviations from plan and why
- Metrics to watch first 30 days

This closes the loop for the next engineer writing a similar doc. Pair with [running effective meetings](https://blog.michaelsam94.com/career-running-effective-meetings/) — design review meetings should review, not discover.

## Production checklist

- [ ] Problem statement written before proposed solution
- [ ] At least two alternatives with rejection reasons
- [ ] Non-goals section prevents scope creep in review
- [ ] ADR filed within 24h of approval
- [ ] Post-implementation "what we learned" section added after ship

## Resources

- [Google design doc guide (internal, leaked versions widely referenced)](https://www.industrialempathy.com/posts/design-doc-a-design-doc/)
- [Architecture Decision Records (Nygard)](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)
- [StaffEng — Writing and Communication](https://staffeng.com/guides/work-on-what-matters/)
- [RFC process (IETF model adapted for teams)](https://www.industrialempathy.com/posts/rfcs-and-design-docs/)
- [Markdown diagram tools (Mermaid)](https://mermaid.js.org/)
