---
title: "Why Small Pull Requests Win"
slug: "code-review-pull-request-size"
description: "Large pull requests slow reviews, hide bugs, and block releases. Practical limits, splitting strategies, and metrics that keep PRs reviewable."
datePublished: "2025-03-16"
dateModified: "2025-03-16"
tags: ["Career", "Engineering"]
keywords: "small pull requests, PR size, code review speed, stack diffs, incremental delivery"
faq:
  - q: "What is a good maximum pull request size?"
    a: "Aim for 200–400 lines of meaningful diff, excluding generated files and lockfiles. Review quality drops sharply beyond 400 lines—studies from SmartBear and internal metrics at many companies show defect detection rates fall as diff size grows. If a change needs more, split by layer: schema migration first, then API, then UI."
  - q: "How do I split a large feature into multiple PRs?"
    a: "Use feature flags or dark launches so incomplete work ships inert. Merge scaffolding and interfaces first, then implementations behind the flag. Each PR should be independently deployable and revertible. Stack PRs with Graphite or git branch chains when later PRs depend on earlier ones still in review."
  - q: "Does small PR policy slow down development?"
    a: "It shifts time from waiting on reviews and fixing review-round bugs to upfront planning. Net cycle time usually drops because merges happen daily instead of weekly. The perceived slowdown is real only when teams lack splitting skills—train on stacked PRs once and the habit sticks."
---

The 2,000-line pull request is a confidence trick. It looks like productivity—one big merge, feature done—but the review is performative, the bugs hide in line 1,847, and the author waits four days for "LGTM" from someone who skimmed the title. Small PRs are not a virtue signal; they are a throughput optimization backed by measurable review quality data.

## Review quality degrades with diff size

SmartBear's analysis of Cisco code review data found optimal inspection rates around 200–400 lines per session. Beyond that, reviewers miss defects at an increasing rate. Your team's anecdote matches: the giant refactor PR that introduced a production incident always had "I trust you, ship it" energy in the comments.

The mechanism is cognitive load. A reviewer holding a mental model of auth, billing, and UI changes simultaneously cannot trace edge cases in any of them. Smaller diffs mean one mental model, one question: "Is this auth change correct?"

## Set explicit limits

Publish a team norm with teeth:

- **Target:** under 300 lines changed (excluding generated)
- **Hard ask:** over 600 lines requires written justification in PR description
- **Bot warning:** CI comments when diff exceeds threshold (Danger, GitHub Action)

```yaml
# .github/workflows/pr-size.yml
- uses: actions/github-script@v7
  with:
    script: |
      const files = await github.rest.pulls.listFiles({ ... });
      const lines = files.data.reduce((s, f) => s + f.additions + f.deletions, 0);
      if (lines > 600) {
        github.rest.issues.createComment({
          issue_number: context.issue.number,
          body: `⚠️ PR has ${lines} changed lines. Consider splitting.`
        });
      }
```

Limits without enforcement become suggestions. Automate the nudge.

## Splitting strategies that work

**Vertical slices by user-visible behavior.** Instead of "backend PR then frontend PR" for a new settings page, ship read-only display first (API + UI), then edit capability, then validation. Each slice is testable and demoable.

**Horizontal layers with contracts.** Merge the interface or proto definition first. Consumers compile against it; implementation PR follows. Requires discipline on backward-compatible API additions.

**Mechanical vs behavioral separation.** Rename/refactor PR with zero behavior change merges fast and reduces noise in the feature PR that follows. Reviewers trust pure renames when tests pass unchanged.

**Feature flags.** Incomplete logic behind `if (featureEnabled)` merges to main without exposing users. Flag removal is a small final PR.

## Stacked pull requests

When PR B genuinely depends on unmerged PR A, stacking beats one mega-PR:

```bash
git checkout -b feature-part-1
# commit, push, open PR #101

git checkout -b feature-part-2
# commit on top of part-1, push, open PR #102 targeting part-1 branch
```

Tools like Graphite, git-town, or GitHub's native stacked PR support rebase the stack when #101 gets review comments. The author fixes once at the bottom; changes flow up.

## What counts in the line limit

Exclude from size metrics:

- Lockfile updates (`package-lock.json`, `yarn.lock`)
- Generated protobuf, GraphQL, OpenAPI output
- Snapshots updated intentionally by test runs
- Bulk license or copyright header additions

Include everything a human must read for correctness. A 50-line logic change buried in 800 lines of regenerated code is still a 50-line review—but verify the generation inputs, not every generated line.

## Author habits for small PRs

**Commit granularity.** Small commits make splitting retroactively possible. One commit per logical unit lets you cherry-pick or branch mid-stack.

**Daily merge goal.** If your PR is not merged in two days, it is too big or blocked—split or escalate, do not accumulate.

**Draft PRs early.** Open a draft at 100 lines for direction feedback before investing in 800 lines of wrong approach.

## Reviewer habits for small PRs

Small PRs deserve fast turnaround—same-day first review. That reciprocal speed reinforces the culture: authors split because reviewers actually read.

Do not expand scope during review ("while you're here, can you also..."). New work is a new PR or a follow-up ticket linked in merge commit.

## Metrics worth tracking

- Median PR size (lines changed)
- Time from open to first review
- Time from open to merge
- Revert rate by PR size bucket

If reverts cluster in 1000+ line PRs, you have data for the next team meeting slide.

## When a large PR is acceptable

Rare cases exist: initial open-source release, generated migration from another system, mechanical codemod from an automated tool with proven output. Even then, split by directory or module when possible. The justification belongs in the description with explicit reviewer instructions: "Only review `src/auth/`; rest is autogenerated."

## Common production mistakes

Teams get pull request size wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of pull request size fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When pull request size misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Google eng-practices — Small CLs](https://google.github.io/eng-practices/review/developer/small-cls.html)
- [Graphite stacked PRs guide](https://graphite.dev/docs)
- [SmartBear — Best Kept Secrets of Peer Code Review](https://smartbear.com/learn/code-review/best-practices-for-peer-code-review/)
- [GitHub pull request size bots (danger-js)](https://danger.systems/js/)
