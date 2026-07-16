---
title: "Rebase vs Merge"
slug: "git-rebase-vs-merge"
description: "Merge preserves branch history; rebase rewrites commits for linear history. When to use each, team rules, and recovering from rebase mistakes."
datePublished: "2025-04-28"
dateModified: "2025-04-28"
tags: ["Career", "Git", "Workflow", "DevOps"]
keywords: "git rebase vs merge, linear history, squash merge, interactive rebase, git workflow"
faq:
  - q: "Should I rebase or merge main into my feature branch?"
    a: "Rebase before merge creates linear history and cleaner bisect—preferred on private branches never pushed shared. Merge main into feature preserves exact history and avoids rewriting published commits—safer for collaborative branches."
  - q: "Is squash merge the same as rebase?"
    a: "Squash merge combines PR commits into one commit on main—linear main history but loses granular PR commits on default branch. Rebase replays each commit; squash collapses them. Both avoid merge commits on trunk; semantics differ for cherry-pick and revert."
  - q: "Can I recover after a bad rebase?"
    a: "Yes—git reflog keeps old HEAD positions. git reset --hard HEAD@{n} before force-push restores state. After force-push, recovery needs teammate clones or reflog on remote if available."
---

Two senior engineers argued rebase vs merge for twenty minutes in a PR comment thread. Both were right for different constraints: rebase gives readable `git log main`; merge preserves the fact that work happened in parallel on a branch. Team policy beats individual preference here.

## What merge does

```bash
git checkout feature
git merge main
```

Creates merge commit combining histories—diamond graph preserved.

```bash
git checkout main
git merge --no-ff feature
```

`--no-ff` keeps explicit merge commit even if fast-forward possible—documents branch integration point.

**Pros:** no history rewrite; safe for shared branches; accurate timeline.

**Cons:** cluttered log; harder bisect through merge bubbles.

## What rebase does

```bash
git checkout feature
git rebase main
```

Replays feature commits atop latest main—linear sequence as if you started from today's main.

**Pros:** clean log; easier `git log --oneline`; reviewable commit series.

**Cons:** rewrites SHAs—never rebase commits others pulled without coordination.

## Golden rule

**Do not rebase public shared branches.** If anyone else commits on `feature/login`, merging is safer. Rebase only local or sole-owner branches before PR.

## Pull request strategies on GitHub

| Strategy | Result on main |
|----------|----------------|
| Merge commit | all commits + merge node |
| Squash and merge | one commit per PR |
| Rebase and merge | each PR commit replayed linearly |

Many teams use **squash and merge** on main for one changelog line per PR, **rebase** locally while developing.

## Interactive rebase for cleanup

Before PR:

```bash
git rebase -i main
```

Squash WIP commits, reword messages to Conventional Commits, drop debug commits.

```
pick a1b2c3 feat(auth): add login form
squash d4e5f6 fix typo
reword g7h8i9 fix(auth): handle timeout
```

Result: professional commit series reviewers can follow.

## Conflict handling

Rebase stops at each conflicting commit:

```bash
# fix files
git add .
git rebase --continue
# or abort
git rebase --abort
```

Merge conflicts during rebase differ from merge—conflicts replay per commit, sometimes repeatedly. Prefer small commits during rebase.

## Updating feature branch with main

Option A — merge:

```bash
git merge origin/main
```

Option B — rebase (solo branch):

```bash
git fetch origin
git rebase origin/main
git push --force-with-lease
```

`--force-with-lease` refuses push if remote has unexpected commits—safer than `--force`.

## Revert implications

Revert merge commit needs `-m 1` parent specification. Rebased linear history simplifies `git revert <sha>` per commit.

## Team policy template

Document in CONTRIBUTING.md:

1. `main` is protected; PR required
2. Squash merge to main
3. Rebase allowed on feature branches before review
4. No force-push to shared branches except feature with `--force-with-lease`
5. Release branches merge only, no rebase

Consistency matters more than which side "wins."

## Release branch exception

Mobile release train may use short-lived release branch merging to main via merge commit—preserves release stabilization commits visibly. Trunk-based purists still keep branch under 48 hours.

## Conflict psychology

Rebase conflicts replay per commit—multiple conflicts feel painful but produce cleaner history. Merge conflict once on merge commit—one painful moment.

## Teaching juniors

Diagram branch graphs on whiteboard—visual learners grasp `--ff-only` vs merge commit faster than prose.

## Automation

GitHub "Update branch" button merges main into PR—convenient but adds merge commits; prefer rebase button if enabled org-wide.


## Signed commits and rebase

Rebase replays commits—GPG signatures invalidated unless configured to resign. Teams using signed commits policy should document whether merge-only trunk preserves signatures.

## Bisect workflow

Linear history from rebase simplifies `git bisect`—merge-heavy main may skip merge commits with `--no-merges` first-parent walk; understand your graph before bisecting production regression.

## Pair programming and shared branches

Two developers on same branch should merge main, not rebase, if both pushed—coordinate verbally before any force-push.

## Bot automation

Dependabot PRs flood merge queue—auto-merge squash with conventional title keeps trunk readable despite high PR volume.

## Graph visualizer

Use \`git log --oneline --graph --all\` in team docs screenshots—onboarding material showing merge vs rebase outcomes reduces abstract confusion for junior developers learning trunk workflow first week.

## Rollout guidance

Team offsite agrees merge policy written within 24 hours—verbal consensus fades. GitHub branch settings enforce policy technically not only culturally—branch protection prevents merge commits if squash-only policy chosen.

## Team practices

Shipping Git Rebase Vs Merge in production taught our team that documentation beats hero demos. We wrote runbooks covering failure modes, on-call steps, and rollback triggers before the second release, not after the first outage.

When reviewing PRs touching Git Rebase Vs Merge, we ask for measurable outcomes: latency, crash rate, or support ticket volume—not subjective feels faster. If metrics are unavailable, the PR includes a DevTools trace or load test snippet proving the change.

Onboarding engineers paste a checklist into their first Git Rebase Vs Merge PR description: environment setup verified, tests added or updated, accessibility spot-checked, and release notes drafted for user-visible changes.

We keep a living FAQ in the repo wiki for Git Rebase Vs Merge questions repeated in Slack more than twice. FAQ entries link to source files and Slack threads, reducing tribal knowledge and repeated explanations in code review.

Cross-functional review includes design for UX-facing work, security for auth or storage, and platform for native bridges. Git Rebase Vs Merge spans layers; skipping reviewers recreated bugs we fixed months ago.

Document team policy in CONTRIBUTING.md — mixed rebase/merge workflows create duplicate commits and broken bisect history.

## Resources

- [Git merge documentation](https://git-scm.com/docs/git-merge)
- [Git rebase documentation](https://git-scm.com/docs/git-rebase)
- [Atlassian rebase vs merge guide](https://www.atlassian.com/git/tutorials/merging-vs-rebasing)
- [GitHub merge options](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges)
- [Pro Git book — rebasing](https://git-scm.com/book/en/v2/Git-Branching-Rebasing)
