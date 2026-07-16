---
title: "Writing Blameless Postmortems"
slug: "postmortems-blameless-culture"
description: "Write postmortems that improve systems: blameless culture, timeline construction, action items that stick, and templates that engineering teams actually use."
datePublished: "2026-04-09"
dateModified: "2026-04-09"
tags: ["DevOps", "SRE", "Incident Response", "Culture"]
keywords: "blameless postmortem, incident postmortem template, SRE postmortem, incident review culture, action items postmortem"
faq:
  - q: "What does blameless mean in a postmortem?"
    a: "Focus on systemic causes and process gaps, not punishing individuals for mistakes. 'The engineer deployed without review' becomes 'Our deploy pipeline allowed single-approver merges to production.' People act within system constraints; fix the constraints."
  - q: "Who should write the postmortem?"
    a: "An incident commander or rotating scribe who participated but maintains neutrality. The on-call engineer who fixed the incident contributes timeline facts; a facilitator prevents defensive framing. Distribute writing within the team over time."
  - q: "How many action items should a postmortem produce?"
    a: "Three to seven prioritized, owned, dated items. Fifty unchecked boxes mean the postmortem failed. Each item maps to a ticket with an engineer owner and severity. If the same root cause repeats, previous action items weren't effective — escalate priority."
---

The first postmortem I wrote named an engineer who typo'd a config. It never got shared widely. The second, rewritten blamelessly, identified that prod config wasn't validated in CI and had no diff review — we fixed that in a week. Same incident, different outcome. Blameless postmortems aren't about being nice; they're about getting honest timelines so fixes address why the system allowed failure.

## Anatomy of a useful postmortem

1. **Summary** — one paragraph: what broke, user impact, duration
2. **Impact** — metrics: error rate, revenue, customers affected, SLA burn
3. **Timeline** — UTC timestamps, detection → mitigation → resolution
4. **Root cause** — technical chain, not person chain
5. **Contributing factors** — why detection was slow, why rollback failed
6. **What went well** — reinforce good instincts
7. **Action items** — owned, prioritized, tracked
8. **Lessons learned** — optional narrative for humans

Skip lengthy background unless context is non-obvious.

## Timeline that tells the truth

```
2026-04-08 14:02 UTC — Deploy v2.4.1 completes (Git SHA abc123)
2026-04-08 14:07 UTC — PagerDuty: checkout error rate > 5%
2026-04-08 14:09 UTC — On-call acknowledges, opens war room
2026-04-08 14:15 UTC — Hypothesis: DB migration lock; ruled out
2026-04-08 14:22 UTC — Identified feature flag default change in v2.4.1
2026-04-08 14:24 UTC — Flag disabled; error rate normalizes
2026-04-08 14:30 UTC — Incident resolved; monitoring green
```

Link Grafana snapshots, deploy records, Slack thread exports. Future you won't remember.

## Blameless language examples

| Blameful | Blameless |
|----------|-----------|
| "Jane forgot to run migration" | "Migration didn't run automatically; manual step undocumented" |
| "Ops clicked wrong button" | "Runbook ambiguous between staging and prod endpoints" |
| "Developer shipped buggy code" | "Test suite lacked case for empty cart edge condition" |

Assume everyone acted rationally given information and tools available.

## Action items that don't rot

Bad: "Improve monitoring" — unowned, unmeasurable.

Good:
```
| Action | Owner | Priority | Due | Ticket |
| Add checkout error rate SLO alert | @alex | P1 | Apr 15 | INC-442 |
| Feature flags default-off in CI test | @sam | P2 | Apr 22 | INC-443 |
| Runbook: flag kill switch steps | @platform | P2 | Apr 20 | INC-444 |
```

Review open postmortem actions in weekly platform meeting. Close or re-prioritize — stale actions erode trust.

## Severity-based depth

| Severity | Postmortem required | Review meeting |
|----------|--------------------|--------------------|
| SEV1 — major outage | Yes, 5 business days | Required, cross-team |
| SEV2 — degraded | Yes, 10 business days | Team + stakeholders |
| SEV3 — minor | Optional short form | Team async |
| Near miss | Encouraged | Blameless learning |

Don't skip postmortems on near misses — cheapest learning available.

## Publishing and privacy

Share widely internally — security incidents redact exploit details until patched. Customer-facing status page summary separate from internal technical doc.

Google's public postmortem culture sets expectation: incidents are learning events, not career events.

## Anti-patterns

- **Postmortem as performance review input** — kills honesty
- **Single root cause mandate** — complex failures have contributing graphs
- **No follow-up** — same outage twice is cultural failure
- **Template so long nobody reads it** — two pages max for most incidents
- **Skipping 'what went well'** — teams need reinforcement

## Template starter

```markdown
# Incident: [Title] — [Date]

## Summary
[1 paragraph]

## Impact
- Duration:
- Users affected:
- Error budget consumed:

## Timeline (UTC)
| Time | Event |
|------|-------|

## Root Cause
[Technical description]

## Contributing Factors
- 

## What Went Well
- 

## Action Items
| Item | Owner | Due | Status |
|------|-------|-----|--------|
```

## Executive summaries

Attach one-page executive summary for SEV1 incidents: business impact in dollars, customer segments affected, confidence in root cause, top three preventive actions with dates. Executives read this; engineers read full doc.

## Operational notes

Store postmortems in searchable repository linked from service catalog — new engineers onboarding to a service read past incidents first week. Institutional memory prevents repeating rollback mistakes.

Archive postmortems where new hires will find them during service onboarding.

## Action item tracking

Postmortems fail when action items die in spreadsheets:

```yaml
# action-items.yaml in repo — CI checks due dates
- id: PM-2026-014-01
  incident: PM-2026-014
  description: Add circuit breaker to payment gateway client
  owner: @payments-team
  due: 2026-02-15
  status: open
  verified_by: null  # link to PR or test when done
```

Review open items in weekly eng sync — not the full postmortem, just status. Close items with evidence (merged PR, deployed flag, new alert). "Done" without verification repeats the incident.

## Severity classification

Consistent severity drives response expectations:

| Level | Definition | Postmortem required |
|-------|------------|---------------------|
| SEV1 | Customer-facing outage, data loss | Yes, within 5 business days |
| SEV2 | Degraded service, workaround exists | Yes, within 10 days |
| SEV3 | Internal-only impact | Optional short form |
| SEV4 | Near-miss, no user impact | Optional learning note |

Near-miss postmortems are undervalued — the deployment that *almost* took down production teaches as much as the one that did.

## Facilitation tips

Blameless doesn't mean unstructured. Facilitator responsibilities:

- Stop "who" questions — redirect to "what conditions allowed this"
- Time-box timeline construction to 20 minutes
- Separate "root cause" (technical) from "contributing factors" (organizational)
- End with at least one action item that's not "be more careful"

Invite customer support for user-visible incidents — they see impact engineers miss.

Pair with [career running effective meetings](https://blog.michaelsam94.com/career-running-effective-meetings/) for postmortem meeting structure.

## Production checklist

- [ ] Action items tracked in repo with owners and due dates
- [ ] SEV1 postmortem within 5 business days
- [ ] Timeline in UTC with detection and resolution timestamps
- [ ] Near-miss incidents documented, not only outages
- [ ] Executive summary attached for customer-facing SEV1

## Common production mistakes

Teams get postmortems blameless culture wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of postmortems blameless culture fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [Google SRE — postmortem culture](https://sre.google/sre-book/postmortem-culture/)
- [PagerDuty postmortem guide](https://response.pagerduty.com/after/post_mortem_process/)
- [Etsy Debriefing Facilitation](https://github.com/pagerduty/debrief-facilitation-guide)
- [ISO/IEC 27035 incident management](https://www.iso.org/standard/78973.html)
- [GitLab public postmortems index](https://about.gitlab.com/handbook/engineering/infrastructure/incident-management/postmortems/)
