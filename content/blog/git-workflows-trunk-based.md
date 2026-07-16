---
title: "Trunk-Based Development"
slug: "git-workflows-trunk-based"
description: "Trunk-based development integrates small changes to main frequently with feature flags and short-lived branches. Alternative to long-lived GitFlow release branches."
datePublished: "2025-05-01"
dateModified: "2025-05-01"
tags: ["Career", "Git", "Workflow", "DevOps"]
keywords: "trunk-based development, GitFlow alternative, continuous integration, feature flags, short-lived branches"
faq:
  - q: "How is trunk-based development different from GitFlow?"
    a: "GitFlow uses long-lived develop and release branches with periodic merges to main. Trunk-based keeps main always releasable; developers use short-lived branches or commit directly with feature flags hiding incomplete work. CI runs on every commit to main."
  - q: "Do you need feature flags for trunk-based development?"
    a: "Strongly recommended for changes longer than a day or half-built UI. Flags decouple deploy from release—code merges to main dark until product enables flag. Without flags, only very small incremental slices merge."
  - q: "What branch lifetime is acceptable?"
    a: "Guidance: less than 2 days, ideally hours. Branches exist for code review and CI on PR, not weeks of diverging work. Large features split into incremental PRs behind flags."
---

Release branches lived so long that merging `release/2.4` back to `develop` became a quarterly event with conflict bingo. Trunk-based development—everyone integrates to `main` small and often—sounds chaotic until feature flags and CI make incomplete work invisible to users instead of invisible to Git.

Trunk-based development (TBD) is a source control practice: one mainline branch (trunk) always in deployable state; developers integrate frequently with automated tests gating each commit.

## Core practices

1. **Main is sacred** — always green CI, always shippable
2. **Small batches** — PRs reviewable in minutes, not days
3. **Short-lived branches** — hours to 2 days max
4. **Feature flags** — hide incomplete behavior
5. **Fix forward** — revert or patch main quickly vs long hotfix branches

## Compared to GitFlow

| Aspect | GitFlow | Trunk-based |
|--------|---------|-------------|
| Main branch | release snapshots | continuous integration |
| Feature work | feature → develop | feature → main (fast) |
| Release | release branch stabilization | tag main, optional release branch hours |
| Hotfix | hotfix branch | fix on main, deploy |

GitFlow suits scheduled releases and multiple supported versions. TBD suits continuous delivery web/mobile backends with strong CI.

## Feature flags in practice

```typescript
if (featureFlags.isEnabled('new-checkout', userId)) {
  return <CheckoutV2 />;
}
return <CheckoutV1 />;
```

Merge CheckoutV2 skeleton early—flag off in production. Incrementally add payment methods; enable for internal staff, then 5% canary.

Remove flag after full rollout—dead flag debt is real; track in ticket backlog.

## Branching models within TBD

**Direct to main** — pair programming or high trust; rare in regulated industries.

**PR branches** — most common; merge after review + CI.

**Release branches optional** — cut `release-2025-05-01` from main for stabilization only if mobile store submission needs freeze; hours/days not weeks.

## CI requirements

TBD fails without fast reliable CI:

- Unit + integration under 15 minutes ideal
- Required checks on main
- Preview environments per PR
- Automatic revert on canary regression

Flaky tests are trunk killers—fix or quarantine immediately.

## Code review at trunk pace

Review for:

- Correctness and tests
- Flag default off for risky features
- Backward compatible migrations (expand-contract)

Not for perfect polish delayed three days—iterate on main behind flag.

## Mobile and app store constraints

Stores complicate continuous trunk release—use:

- Trunk still integrates daily
- Release train cuts from main weekly/biweekly
- Remote config toggles features post-approval

Main stays integrated; store cadence decouples partially.

## Migration from GitFlow

1. Stop committing long features to `develop`
2. Point PRs to `main`; make `develop` read-only archive
3. Introduce feature flag service
4. Shorten release branch window each cycle
5. Train on revert culture vs hotfix branches

## Cultural signals

- "Revert first, investigate second" when main breaks
- No "merge Friday" batch integrations
- Monitor lead time and deployment frequency DORA metrics

## Feature flag hygiene

Track flags in registry with owner and removal date:

| Flag | Owner | Created | Remove by |
|------|-------|---------|-----------|
| new-checkout | payments | 2025-03 | 2025-06 |

Stale flags increase binary size and cognitive load—lint dead flag references.

## Pair with continuous deployment

TBD assumes deploy pipeline green on main—if deploy is manual monthly, TBD discipline erodes. Invest in CD before forcing trunk integration frequency.

## Code review load

Small PRs increase PR count—staff review rotation and SLAs prevent bottleneck. Auto-assign based on CODEOWNERS.

## Long-running experiments

A/B tests lasting weeks still merge code behind flag at 0%—branch longevity is not excuse for week-long divergent branches.


## Compliance and audit trails

Regulated industries may require release tags proving what ran in production—trunk still tags `v2.4.1` on main after each deploy; audit reads tags, not long-lived release branches.

## Database migrations on trunk

Expand-contract migrations mandatory—never merge breaking schema change without expand phase deployed first. Trunk frequency makes backward incompatible migrations lethal.

## On-call and trunk health

PagerDuty on main CI failure—trunk-based culture requires fixing red main within hours, not days. Rotate firefighter role weekly.

## Hybrid with GitFlow escape hatch

Some teams run trunk for web daily deploy and short GitFlow for quarterly mobile store—honest about two speeds rather than forcing one model where constraints differ.

## Pair programming on trunk

Two engineers one PR reduces need for long-lived branch—direct trunk commit culture with pair review alternative to async review for risky migrations.

## Rollout guidance

Trunk adoption measured DORA metrics baseline quarter before policy mandate—leadership reviews deployment frequency improvement quarterly justifying continued investment feature flag platform and CI reliability supporting trunk cadence.

## Team practices

Shipping Git Workflows Trunk Based in production taught our team that documentation beats hero demos. We wrote runbooks covering failure modes, on-call steps, and rollback triggers before the second release, not after the first outage.

When reviewing PRs touching Git Workflows Trunk Based, we ask for measurable outcomes: latency, crash rate, or support ticket volume—not subjective feels faster. If metrics are unavailable, the PR includes a DevTools trace or load test snippet proving the change.

Onboarding engineers paste a checklist into their first Git Workflows Trunk Based PR description: environment setup verified, tests added or updated, accessibility spot-checked, and release notes drafted for user-visible changes.

We keep a living FAQ in the repo wiki for Git Workflows Trunk Based questions repeated in Slack more than twice. FAQ entries link to source files and Slack threads, reducing tribal knowledge and repeated explanations in code review.

Cross-functional review includes design for UX-facing work, security for auth or storage, and platform for native bridges. Git Workflows Trunk Based spans layers; skipping reviewers recreated bugs we fixed months ago.

## Resources

- [trunkbaseddevelopment.com](https://trunkbaseddevelopment.com/)
- [Feature flags (Martin Fowler)](https://martinfowler.com/articles/feature-toggles.html)
- [DORA metrics](https://dora.dev/)
- [Accelerate book research basis](https://itrevolution.com/product/accelerate/)
- [Google engineering practices — small CLs](https://google.github.io/eng-practices/review/developer/small-cls.html)
