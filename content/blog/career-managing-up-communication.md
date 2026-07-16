---
title: "Managing Up as an Engineer"
slug: "career-managing-up-communication"
description: "Managing up means communicating progress, risks, and needs clearly to your manager. Write concise status updates, escalate blockers early, and align your work with team priorities without being told what to do."
datePublished: "2024-12-29"
dateModified: "2024-12-29"
tags: ["Career", "Engineering", "Communication"]
keywords: "managing up engineer, status updates manager, engineering communication, escalate blockers, manager alignment, engineering career"
faq:
  - q: "What does managing up mean for engineers?"
    a: "Managing up is proactively communicating with your manager — sharing progress, surfacing risks before they become surprises, asking for decisions when blocked, and aligning your work with team priorities. It's not manipulation or politics; it's making your manager effective at supporting you and representing the team."
  - q: "How often should I update my manager?"
    a: "Weekly written updates for most ICs, plus immediate escalation for blockers that won't resolve within a day. If your manager has to ask 'what's the status on X?' you've under-communicated. If you're sending hourly updates, you've over-communicated. Match cadence to your manager's preference — ask directly."
  - q: "How do I escalate a blocker without looking incompetent?"
    a: "Escalate early with context: what you're trying to do, what you've tried, what's blocking you, and what decision or resource you need. Escalating on day 3 of a 5-day task is responsible. Escalating on day 5 with no prior mention is a surprise — surprises erode trust."
---

Your manager can't help you if they don't know you're stuck. They can't represent the team to leadership if they don't know what's shipping. Managing up isn't about playing politics — it's the communication discipline that prevents "why didn't anyone tell me?" conversations in sprint reviews and postmortems. The best engineers I work with make their managers look prepared, not because they flatter, but because information flows before it's requested.

## The weekly update format

Five minutes to write, saves thirty minutes of 1:1:

```
## Done this week
- Shipped payment retry logic (PR #412, deployed to prod)
- Fixed memory leak in image cache (PR #418)

## In progress
- Migration to new search index — 70% complete, on track for Friday

## Blocked / needs decision
- API rate limit for partner X undefined — need PM decision by Wed

## Next week
- Complete search migration
- Start webhook signature verification
```

Done / In progress / Blocked / Next. No prose. Your manager scans it in 60 seconds.

## Escalation template

When stuck, send this — don't wait for the 1:1:

```
Blocker: [one line]
Impact: [what can't proceed, deadline at risk?]
Tried: [what you've attempted]
Need: [specific decision, access, or person]
Timeline: [when you need resolution]
```

Example:

```
Blocker: Staging DB doesn't have the new orders table — migration not applied.
Impact: Can't test payment flow E2E; Friday deploy at risk.
Tried: Checked #infra, ran migration manually (permission denied).
Need: DBA to apply migration 20241201_add_orders to staging.
Timeline: Need by EOD Wednesday.
```

Specific, actionable, no blame.

## Aligning without being micromanaged

Understand your manager's priorities:

1. What does leadership care about this quarter? (Revenue, reliability, velocity?)
2. What is your manager measured on?
3. How does your current task map to those?

If you can't draw the line from your work to team goals, ask in your 1:1. Engineers who understand the "why" make better tradeoff decisions without approval on every choice.

## What managers wish you'd tell them earlier

- Estimates were wrong and the task will slip
- A dependency team isn't delivering
- Production issue you mitigated but didn't fully fix
- You're underwater and need to drop something
- A design decision has risk they should know about

Bad news early is manageable. Bad news in the sprint demo is a credibility hit.

## 1:1 preparation

Your 1:1 is your meeting, not your manager's status check. Bring:

- One topic you want feedback on (technical approach, career growth)
- One process improvement suggestion
- Blockers from your weekly update (don't repeat the whole update verbally)

Avoid using 1:1s only for status — that's what written updates are for.

## Saying no with context

When overloaded:

```
I can take on the webhook work, but it means the search migration
slips to next sprint. Which is higher priority?
```

Forcing a priority tradeoff is managing up. Quietly working weekends and missing both deadlines is not.

## Building trust over time

Trust compounds from:
- Consistent weekly updates (even when progress is slow)
- Early escalation (never surprises)
- Following through on commitments (or renegotiating early)
- Representing problems with proposed solutions

After six months of this, your manager gives you more autonomy because they've learned your judgment is reliable.

## Escalation timing and format

Escalate early with structure — managers hate surprises, not problems:

```
Subject: [Escalation] Search migration blocked — need decision by Friday

Situation: Elasticsearch cluster upgrade failed on staging. Rollback works;
forward migration hits mapping conflict on nested fields.

Impact: Search migration slips minimum 1 sprint. Checkout search unaffected
(prod still on old cluster).

Options:
A) Manual reindex with mapping rewrite (3 days eng, low risk)
B) Skip upgrade, patch security CVE differently (1 day, medium risk)
C) Defer migration, accept CVE exposure until Q2 (0 eng days, high risk)

Recommendation: Option A. Need your call on accepting 1-sprint slip.
```

Escalate when: deadline at risk, cross-team blocker unresolved >48 hours, scope change needed, or external dependency failure. Don't escalate: normal technical decisions within your authority.

## Managing managers who micromanage

If your manager asks for daily verbal updates despite written ones:

1. **Proactively send written updates** before they ask — reduce anxiety
2. **Ask directly:** "Would a daily Slack summary replace the standup check-in?"
3. **Demonstrate reliability** on small commitments before asking for autonomy on large ones
4. **Document decisions** in shared docs — manager can verify without interrupting you

Micromanagement often signals trust deficit or manager anxiety about visibility to their boss. Written updates address both.

## Cross-functional communication

Your manager isn't your only stakeholder. Brief PM, design, and ops contacts directly on changes affecting them:

```
To PM (Slack, 3 sentences):
Shipped webhook retry logic. Failed deliveries now retry 3× with backoff.
You'll see fewer "missed webhook" support tickets. Dashboard metric
"webhook_success_rate" added to admin panel.
```

Don't make your manager relay every update — they'll appreciate you handling lateral communication.

## Failure modes

- **Surprise bad news in 1:1** — manager can't help; escalate early in writing
- **Status-only 1:1s** — wasted time; use written updates for status
- **Saying yes to everything** — quiet burnout; force priority tradeoffs explicitly
- **No written record** — "I told you in Slack" disputes; use durable docs for decisions
- **Managing up only when in trouble** — trust never builds; communicate consistently

## Production checklist

- Weekly written update sent before 1:1 (even when progress is slow)
- Escalations include situation, impact, options, and recommendation
- 1:1 agenda prepared with feedback topics, not status recap
- Cross-functional stakeholders briefed directly on relevant changes
- Priority tradeoffs explicit when overloaded — never silent weekend work
- Decisions documented in shared location manager can reference

## Resources

- [Julie Zhuo — The Making of a Manager](https://www.juliezhuo.com/book/manager/)
- [Lara Hogan — Resilient Management](https://larahogan.me/books/resilient-management/)
- [Staff Engineer — Writing and Communication](https://staffeng.com/guides/work-on-what-matters/)
- [Basecamp — How to communicate status](https://basecamp.com/guides/how-we-communicate)
- [Radical Candor framework (Kim Scott)](https://www.radicalcandor.com/)
