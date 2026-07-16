---
title: "Service Scorecards and Maturity"
slug: "platform-engineering-scorecards"
description: "Build service scorecards that drive improvement: DORA metrics, reliability tiers, security baselines, and maturity models without becoming a blame spreadsheet."
datePublished: "2026-02-23"
dateModified: "2026-02-23"
tags: ["Platform Engineering", "SRE", "Metrics", "DevOps"]
keywords: "service scorecard, engineering maturity model, DORA metrics, service catalog metrics, platform engineering KPIs"
faq:
  - q: "What should a service scorecard measure?"
    a: "Production readiness signals: deployment frequency, lead time, change failure rate, MTTR (DORA), SLO compliance, on-call coverage, dependency freshness, security scan results, and documentation existence. Tailor weights by service tier — payments APIs score differently than internal cron jobs."
  - q: "How do scorecards differ from service catalogs?"
    a: "A catalog answers 'what exists and who owns it.' A scorecard answers 'how healthy and mature is it.' Catalogs are descriptive metadata; scorecards are evaluative metrics usually derived automatically from CI, observability, and incident systems."
  - q: "How do you prevent scorecards from becoming a blame tool?"
    a: "Frame as improvement tracking, not performance reviews. Publish team-level aggregates, not individual rankings. Pair low scores with platform support and golden path investments — if 80% of services fail a check, fix the template, not the teams."
---

Leadership asked for a "service health dashboard." Platform built a spreadsheet. Teams gamed it by marking docs "complete" with a one-line README. Six months later nobody opened the spreadsheet. Scorecards work when metrics are **automatically collected**, **tier-appropriate**, and **connected to help** — not when they're manual checkbox audits updated quarterly.

## Scorecard vs maturity model

**Scorecard:** point-in-time grades per service (`api-checkout: B`, `legacy-batch: D`).

**Maturity model:** defined levels (1–4) per capability area with criteria for advancement.

```
Service: api-checkout (Tier 1 — customer-facing)
├── Reliability:    Level 3  (SLO defined, error budget policy)
├── Security:       Level 4  (SAST, dependency scan, secrets scan pass)
├── Observability:  Level 3  (tracing, dashboards, runbook linked)
├── CI/CD:          Level 4  (automated deploy, canary, rollback tested)
└── Documentation:  Level 2  (API docs yes, on-call runbook stale)
```

Levels map to concrete checks — not subjective "feels mature."

## Tier-based requirements

Not every service needs the same bar:

| Tier | Examples | SLO required | On-call | Canary deploy |
|------|----------|--------------|---------|---------------|
| 1 | Checkout, auth | Yes | 24/7 | Yes |
| 2 | Internal APIs | Yes | Business hours | Recommended |
| 3 | Batch, analytics | Best effort | Next day | No |

Scorecard weights Tier 1 failures heavier. Failing "has README" on a Tier 3 cron matters less than missing SLO on checkout.

## Automate data collection

Manual scorecards die. Wire sources:

```yaml
# Scorecard check definitions (Backstage Scorecards plugin style)
checks:
  - id: has_slo
    name: SLO Defined
    type: json-rules
    successCondition: metadata.annotations['acme.com/slo-target'] != null

  - id: ci_passing
    name: CI Green
    type: github
    filter: 'state == "success" && branch == "main"'

  - id: vuln_critical_zero
    name: No Critical CVEs
    type: sonarqube
    successCondition: metrics.critical_vulnerabilities == 0
```

Backstage Scorecards, Cortex, or custom jobs querying Prometheus, PagerDuty, and GitHub APIs. Same data feeds service catalog and executive dashboards.

## DORA metrics on scorecards

Four keys from Accelerate research:

- **Deployment frequency** — how often deploys hit prod
- **Lead time for changes** — commit to prod duration
- **Change failure rate** — deploys causing incidents
- **MTTR** — recovery time

Collect from CI/CD and incident tooling. Compare teams to themselves over time, not against Netflix on day one.

Low deployment frequency + low failure rate sometimes means fear, not quality — scorecards should flag "no deploys in 30 days" as amber for Tier 1 services.

## Presenting results constructively

**Team dashboards, not wall of shame.** Show "3 services below Tier 1 observability threshold" with links to platform office hours.

**Improvement campaigns.** Quarter theme: "100% Tier 1 services have runbooks." Platform ships runbook template; scorecard tracks adoption.

**Executive rollup.** Percentage of Tier 1 services at Level 3+ per capability — trends over quarters.

Avoid tying scorecard grades to individual performance reviews. Gaming follows instantly.

## Maturity advancement path

Define what Level N+1 requires and who helps:

```
Observability Level 2 → 3:
  Requires: distributed tracing on all HTTP handlers
  Platform provides: OpenTelemetry SDK bump in golden path template
  Team action: merge platform PR or adopt manually
  Deadline: none — tracked on scorecard
```

Platform owns making advancement easy. Product teams own prioritization against feature work — visibility creates negotiation data, not mandates.

## Common failure modes

**Too many checks.** Start with 8–12 high-signal checks. Expand when adoption stabilizes.

**Stale automated data.** Broken GitHub integration shows all services failing CI — credibility gone.

**Checks without owners.** Each check maps to a team that fixes failures (platform for CI template, security for CVE scan).

**Ignoring context.** Legacy mainframe adapter won't have canary deploy — exclude or separate track.

## Avoiding metric gaming

When scorecards tie to performance reviews, teams optimize metrics not systems — 100% doc coverage with empty stubs. Prefer automated technical checks over self-reported fields. Human review only for subjective maturity levels with calibration sessions across teams.

## Operational notes

Integrate scorecard API with incident retros — repeated incidents on low-scoring services prioritize platform investment. Correlation beats guessing which teams need golden path upgrades.

Review scorecard weights annually — over-weighting documentation maturity starves reliability investment when teams optimize README length instead of SLO coverage.

Weight scorecard metrics by user pain — 100% test coverage matters less than deploy frequency if releases take two weeks.

## Scorecard metrics that matter

| Metric | Target |
|--------|--------|
| Deploy frequency | > 1/week per service |
| Lead time for changes | < 1 day |
| MTTR | < 1 hour |
| Change failure rate | < 5% |

DORA metrics per team, not vanity "100% doc coverage" — executives understand deployment frequency; they don't understand linter scores.

## Common production mistakes

Teams get scorecards wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of scorecards fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When scorecards misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Backstage Scorecards plugin](https://backstage.io/docs/features/software-catalog/scorecards/)
- [DORA metrics guide](https://dora.dev/guides/dora-metrics/)
- [Google SRE — service level objectives](https://sre.google/sre-book/service-level-objectives/)
- [Cortex service catalog platform](https://www.cortex.io/post/getting-started-with-service-maturity)
- [Accelerate book (Forsgren, Humble, Kim)](https://itrevolution.com/product/accelerate/)
