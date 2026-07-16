---
title: "Sustainable On-Call Rotations"
slug: "incident-response-oncall-rotations"
description: "Design on-call rotations that don't burn people out: fair scheduling, alert quality, escalation paths, compensation, and measuring on-call health."
datePublished: "2025-07-07"
dateModified: "2025-07-07"
tags: ["DevOps", "Incidents", "Architecture", "Performance"]
keywords: "on-call rotation best practices, sustainable on-call, alert fatigue, PagerDuty rotation, on-call compensation, incident escalation"
faq:
  - q: "How long should an on-call shift be?"
    a: "One week is the most common and generally sustainable if alert volume is managed. Shorter shifts (2-3 days) work for high-page teams but increase handoff overhead. Avoid month-long rotations — fatigue compounds and people go dangerously deep into sleep debt. Include a follow-the-sun option for global teams."
  - q: "How many pages per shift is too many?"
    a: "Industry guidance suggests more than 2-3 pages per night or more than 5-7 per week indicates an alert quality problem, not an on-call staffing problem. If your on-call engineer can't sleep through most nights, fix the alerts before adding more people to the rotation."
  - q: "Should on-call engineers get extra compensation?"
    a: "Yes. On-call is work availability, and it has real costs — disrupted sleep, cancelled plans, cognitive load during the day after a bad night. Compensation varies (flat stipend, per-page bonus, time off in lieu), but unpaid on-call is a retention killer and a liability risk."
---

I've seen two on-call cultures. One where pages were rare, actionable, and followed by time off if the night was bad. Engineers volunteered for extra shifts. The other where the primary on-call got 15 pages a night, half were false positives, and nobody fixed the alerts because "that's just how it is." Guess which team had 40% annual attrition. On-call isn't a necessary evil — it's a system you design, and most burnout is a design failure, not a people failure.

## Rotation structure

A workable rotation for a team of 6-8 engineers:

```
Week 1: Alice (primary), Bob (secondary)
Week 2: Bob (primary), Carol (secondary)
Week 3: Carol (primary), Dave (secondary)
...
```

Rules:
- **Primary** responds to all pages. **Secondary** is backup if primary doesn't ack in 5 minutes.
- **Minimum 2 weeks off** between shifts for the same person
- **No on-call during PTO** — swap shifts explicitly, don't "just check your phone"
- **Handoff ritual** — 15-minute sync at rotation change: open incidents, known issues, recent deploys

For global teams, follow-the-sun avoids 3 AM pages:

```
UTC 00:00-08:00 → APAC team
UTC 08:00-16:00 → EU team
UTC 16:00-00:00 → US team
```

Each region owns their window. Escalation crosses regions only for SEV-1.

## Alert quality is the root fix

Bad on-call almost always means bad alerts:

| Bad alert | Fix |
|-----------|-----|
| CPU > 80% | CPU > 95% for 10 minutes, or better: alert on user-facing latency |
| Disk space < 20% | Auto-scale or auto-clean; page at 5% only |
| Any 500 error | Rate threshold: >1% error rate for 5 min |
| "Service restarted" | Log it, don't page — unless restart loop |
| Identical alert every 5 min | Deduplicate; send one page, re-page if unacked |

Run an **alert audit** quarterly:

1. Export all pages from the last 90 days
2. Tag each: actionable / false positive / duplicate / wrong severity
3. Fix or delete anything below 50% actionable rate
4. Target: 90%+ actionable pages

```sql
-- Example: PagerDuty analytics export
SELECT alert_name,
       COUNT(*) as total_pages,
       SUM(CASE WHEN action = 'resolved_without_escalation' THEN 1 ELSE 0 END) as self_resolved
FROM pages
WHERE created_at > NOW() - INTERVAL '90 days'
GROUP BY alert_name
ORDER BY total_pages DESC;
```

Alerts that page more than twice a week without action are broken. Fix or remove them.

## Severity and escalation

Define severities with response expectations:

| Severity | Response time | Example | Who pages |
|----------|--------------|---------|-----------|
| SEV-1 | 5 min | Full outage, data loss | Primary + secondary + manager |
| SEV-2 | 15 min | Degraded service, no workaround | Primary |
| SEV-3 | Next business day | Minor issue, workaround exists | Ticket, no page |
| SEV-4 | Scheduled | Cosmetic, tech debt | Backlog |

Escalation path:

```
Page primary → (5 min no ack) → Page secondary → (10 min) → Page IC/manager → (15 min) → Executive notification
```

Automate escalation in PagerDuty/Opsgenie. Don't rely on someone remembering to call their manager.

## Runbooks for every pageable alert

Every alert that pages must link to a runbook:

```markdown
# Alert: HighErrorRate — checkout-service

## What this means
Error rate on POST /checkout exceeded 1% for 5 minutes.

## First steps
1. Check Grafana dashboard: https://grafana/d/checkout
2. Recent deploys? → Consider rollback
3. Downstream payment service healthy? → Check /health

## Escalation
If not resolved in 30 min, escalate to #checkout-team Slack channel.
```

An alert without a runbook is a wake-up call with no instructions.

## Measuring on-call health

Track these metrics per rotation:

- **Pages per shift** — target: <2 per night, <7 per week
- **After-hours hours spent** — time from page to resolution
- **Sleep disruption score** — pages between midnight and 6 AM
- **Actionable rate** — % of pages that required real work
- **Post-incident toil tickets** — action items that prevent repeat pages

Survey the team monthly:

1. "I felt prepared to handle pages this rotation" (1-5)
2. "Alert quality has improved over the last quarter" (1-5)
3. "I would trade on-call shifts with colleagues fairly" (1-5)

Scores below 3 on any question = systemic problem, not individual.

## Compensation and recovery

Concrete policies that work:

- **Stipend** — flat weekly amount for being on-call, regardless of page count
- **Time off in lieu** — bad night (>2 hours after midnight) → next day starts at noon or take a half-day
- **No meetings** day after a SEV-1 night
- **Voluntary swap market** — easy shift trading without manager approval

Unpaid on-call is extracting free labor and it shows in retention data.

## Common production mistakes

Teams get incident response oncall rotations wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of incident response oncall rotations fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When incident response oncall rotations misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Google SRE — Being On-Call](https://sre.google/sre-book/being-on-call/) — Google's on-call philosophy and practices
- [PagerDuty On-Call Best Practices](https://www.pagerduty.com/resources/learn/on-call-best-practices/) — rotation design and escalation
- [Increment — On-Call Issue](https://increment.com/on-call/) — industry perspectives on sustainable on-call
- [Alert Quality Management (Google CRE)](https://sre.google/workbook/alerting-on-slos/) — alerting on SLOs instead of symptoms
