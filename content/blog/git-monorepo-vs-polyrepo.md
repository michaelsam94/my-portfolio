---
title: "Monorepo vs Polyrepo"
slug: "git-monorepo-vs-polyrepo"
description: "One repository for many services vs repository per service. Trade-offs in CI, ownership, versioning, and when each model fits your team."
datePublished: "2025-04-25"
dateModified: "2025-04-25"
tags: ["Career", "Git", "Architecture", "DevOps"]
keywords: "monorepo vs polyrepo, multi-repo strategy, monorepo CI, repository structure, microservices repos"
faq:
  - q: "Does monorepo mean monolith?"
    a: "No. A monorepo stores many independent deployables—services, apps, libraries—in one Git repository. Deployments can still be separate artifacts with independent release cadences via path-based CI triggers."
  - q: "What is the biggest downside of monorepos?"
    a: "CI complexity and permission granularity. Without affected-build tooling, every commit runs every test. Large clones hurt developer laptops unless sparse checkout and remote caching are configured."
  - q: "When is polyrepo clearly better?"
    a: "Strict regulatory boundaries, acquired products with separate legal ownership, open-source libraries with public issue trackers isolated from proprietary code, or teams that rarely share code and conflict on release schedules."
---

We debated monorepo for a year while three teams copy-pasted protobuf definitions. Polyrepo felt "clean" until shared library v2 sat unreleased for six weeks because nobody owned the release train. Monorepo is not virtue; it is a coordination technology with costs.

## Definitions

**Monorepo** — multiple projects in one Git repository (Google, Meta scale, or startup with `apps/` and `packages/`).

**Polyrepo** — each service, app, or library has its own repository and lifecycle.

Hybrid exists: polyrepo with shared packages published to npm/Maven and versioned SemVer.

## Monorepo advantages

**Atomic changes** — API break in shared lib + consumer fixes in one PR. No cross-repo PR dance.

**Single source of truth** — one CI config pattern, one linter version, one Dependabot policy (with path filters).

**Refactoring visibility** — rename symbol; grep entire company codebase in one clone.

**Consistent tooling** — Bazel, Nx, Turborepo, Melos, Gradle composite builds scale with repo size.

## Monorepo challenges

**CI cost** — naive `npm test` at root runs everything. Fix with affected detection:

```yaml
# pseudo: only test packages touched since main
nx affected -t test --base=origin/main
```

**Access control** — GitHub CODEOWNERS per path; not as strong as separate repo ACLs for classified data.

**Clone size** — history grows. Partial clone, sparse checkout, and monorepo-friendly hosts (GitHub, GitLab) mitigate.

**Blast radius** — broken main blocks everyone—trunk-based discipline and feature flags required.

## Polyrepo advantages

**Clear ownership** — repo equals team boundary; permissions simple.

**Independent velocity** — team ships without coordinating global CI queue.

**Smaller clones** — faster onboarding for single-service contractors.

**Open source boundaries** — public repo without leaking private siblings.

## Polyrepo challenges

**Dependency drift** — shared client published v3; service A upgrades, service B lags six months.

**Cross-cutting changes** — security patch across ten repos means ten PRs, ten merge queues.

**Discovery** — "does anyone already solve X?" harder across org.

## Decision framework

Choose **monorepo** when:

- Shared code is core to daily work
- Teams refactor across service boundaries often
- You invest in affected-build CI
- Single product org with aligned release culture

Choose **polyrepo** when:

- Services share little code
- Legal/regulatory isolation required
- Teams fully autonomous with stable APIs
- Open-source/public-private split is sharp

## Hybrid patterns

- **Monorepo for apps + libs; polyrepo for infra** — common at mid-size
- **Internal package registry** — polyrepo services consume versioned artifacts from monorepo build
- **Meta monorepo + read-only mirrors** — rare, enterprise legacy

## Migration notes

Polyrepo → monorepo: preserve history with `git filter-repo` merge or subtree merge; communicate clone size change.

Monorepo → split: extract service with history filter; plan dependency extraction first.

## Tooling worth the investment

| Tool | Ecosystem |
|------|-----------|
| Nx, Turborepo | JS/TS |
| Bazel | polyglot large scale |
| Gradle composite | JVM/Android |
| Melos | Dart/Flutter |
| pants | Python/JVM |

Without tooling, monorepos become CI nightmares—tooling is not optional at scale.

## Access and compliance

Regulated data in specific services may legally require separate repo with restricted ACL—even if code duplication hurts. Monorepo path permissions (GitHub, GitLab) help but are not audit-grade isolation.

## Developer onboarding time

Measure time-to-first-PR: monorepo clone + sparse checkout vs polyrepo three-repo clone. Optimize with documentation and devcontainer.

## Dependency update velocity

Monorepo: one PR bumps lodash everywhere. Polyrepo: ten PRs or automated bot flood—configure grouping policies on Dependabot.

## Exit strategy

Document how to extract service from monorepo if team spins out—`git filter-repo` runbook prevents panic during reorg.


## Cost modeling

Estimate engineer hours per month spent on cross-repo PR coordination vs monorepo CI maintenance—quantify trade-off for leadership. Numbers beat religion in architecture reviews.

## Security scanning

Monorepo enables one Dependabot/Snyk scan configuration with path filters; polyrepo multiplies alert noise unless centralized dashboard aggregates repos.

## Contractor access

External agencies often get polyrepo access to single service repo only—monorepo path-based ACL may suffice or may not meet vendor contract; legal weighs in.

## Event-driven future

Message bus between services reduces need for shared code repos—polyrepo plus well-versioned protobuf schemas in artifact registry hybrid grows popular in microservice mature orgs.

## Open source contribution

External contributors fork monorepo intimidated by size—good first issue labels on small packages lower barrier; sparse checkout docs in CONTRIBUTING first paragraph.

## Rollout guidance

ADR repository strategy revisits annual all-hands engineering—org changes faster than ADRs update; stale ADR worse than none triggers quarterly doc freshness ticket.

## Team practices

Shipping Git Monorepo Vs Polyrepo in production taught our team that documentation beats hero demos. We wrote runbooks covering failure modes, on-call steps, and rollback triggers before the second release, not after the first outage.

When reviewing PRs touching Git Monorepo Vs Polyrepo, we ask for measurable outcomes: latency, crash rate, or support ticket volume—not subjective feels faster. If metrics are unavailable, the PR includes a DevTools trace or load test snippet proving the change.

Onboarding engineers paste a checklist into their first Git Monorepo Vs Polyrepo PR description: environment setup verified, tests added or updated, accessibility spot-checked, and release notes drafted for user-visible changes.

We keep a living FAQ in the repo wiki for Git Monorepo Vs Polyrepo questions repeated in Slack more than twice. FAQ entries link to source files and Slack threads, reducing tribal knowledge and repeated explanations in code review.

Cross-functional review includes design for UX-facing work, security for auth or storage, and platform for native bridges. Git Monorepo Vs Polyrepo spans layers; skipping reviewers recreated bugs we fixed months ago.

Staging soaks 24 hours for risky changes while dashboards watch error rates.canary cohorts internal staff first, then five percent production, then full rollout if crash-free sessions hold within baseline tolerance.

## Resources

- [Monorepo.tools comparison](https://monorepo.tools/)
- [Google monorepo paper (Trunk Based Development)](https://trunkbaseddevelopment.com/)
- [Nx documentation](https://nx.dev/)
- [Turborepo handbook](https://turbo.build/repo/docs)
- [Git partial clone](https://git-scm.com/docs/partial-clone)
