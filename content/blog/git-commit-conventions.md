---
title: "Conventional Commits"
slug: "git-commit-conventions"
description: "Conventional Commits standardize message format for readable history and automated changelogs. Types, scopes, breaking changes, and CI enforcement."
datePublished: "2025-04-22"
dateModified: "2025-04-22"
tags: ["Career", "Git", "Workflow", "DevOps"]
keywords: "Conventional Commits, commit message format, semantic versioning commits, commitlint, changelog automation"
faq:
  - q: "What is the Conventional Commits format?"
    a: "type(optional scope): description. Optional body and footer. Breaking changes use ! after type or BREAKING CHANGE: in footer. Example: feat(auth): add OAuth2 login."
  - q: "Which commit types should my team use?"
    a: "Common types: feat, fix, docs, style, refactor, perf, test, chore, ci, build. Align with tools—semantic-release maps feat to minor and fix to patch. Document team-specific scopes like api, ui, android."
  - q: "Do Conventional Commits require semantic-release?"
    a: "No. Readable history is valuable alone. Pairing with semantic-release, changesets, or standard-version automates version bumps and CHANGELOG generation from commit messages."
---

Release notes used to be archaeology—`git log` between tags full of "fix stuff" and "WIP." Conventional Commits turned the log into structured data: `feat(checkout): add Apple Pay` becomes a minor bump and a changelog line without anyone copy-pasting from merged PR titles.

The [Conventional Commits specification](https://www.conventionalcommits.org/) defines a lightweight convention: `<type>[optional scope]: <description>`.

## Message structure

```
feat(auth): support passkey login

Add WebAuthn registration and assertion flows for
enterprise accounts.

Closes #482

BREAKING CHANGE: session cookies now HttpOnly-only;
client JS can no longer read auth_token.
```

Parts:

- **type** — nature of change
- **scope** — optional subsystem in parentheses
- **description** — imperative mood, lowercase, no period
- **body** — optional context
- **footer** — issues, co-authors, breaking notes

Breaking change shorthand:

```
feat(api)!: remove v1 endpoints
```

## Common types

| Type | Semver impact | Use |
|------|---------------|-----|
| feat | minor | new feature |
| fix | patch | bug fix |
| perf | patch | performance |
| refactor | none* | code change without behavior |
| docs | none | documentation only |
| test | none | tests only |
| chore | none | tooling, deps |
| ci | none | pipeline changes |

*Tools may treat as patch—configure policy.

## Scopes that help

```
feat(billing): ...
fix(android): ...
refactor(auth): ...
```

Scopes power filtered changelogs:

```markdown
### Features (billing)
- add invoice PDF export
```

Avoid scope explosion—ten scopes max per repo usually suffices.

## Pull request workflow

Squash merge teams: PR title becomes commit message—enforce conventional title in GitHub rules.

Merge commit teams: require each commit conventional or squash on merge.

```yaml
# .github/workflows/commitlint.yml
- uses: wagoid/commitlint-github-action@v6
```

With `commitlint.config.js`:

```javascript
module.exports = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'scope-enum': [2, 'always', ['api', 'ui', 'auth', 'deps']],
  },
};
```

## Linking to issues

```
fix(payments): handle Stripe webhook timeout

Fixes #901
```

GitHub auto-closes linked issues on merge.

## Automated versioning

semantic-release configuration:

```json
{
  "branches": ["main"],
  "plugins": [
    "@semantic-release/commit-analyzer",
    "@semantic-release/release-notes-generator",
    "@semantic-release/changelog",
    "@semantic-release/github"
  ]
}
```

`feat` on main → minor release; `fix` → patch; `BREAKING CHANGE` → major.

## Human benefits without automation

Even manual releases gain:

- `git log --grep=feat(auth)` finds feature history
- reviewers scan type prefix quickly
- bisect skips docs-only commits when labeled `docs:`

## Anti-patterns

- `fixed bug` — no type, no scope
- `feat: misc updates` — vague description
- mixing unrelated changes—split commits
- `chore: huge refactor + feature` — pick primary type or split

## Scope ownership

CODEOWNERS maps scope to team:

```
/packages/api/ @backend-team
/apps/web/ @frontend-team
```

commitlint `scope-enum` matches CODEOWNERS prefixes—PR title lint enforces routing.

## Squash merge message quality

GitHub uses PR title as squash commit—train contributors to write conventional PR titles. Body holds detail; title holds semantic type.

## Release notes automation

```markdown
## Features
${features}

## Bug Fixes
${fixes}
```

Generated from commits since last tag—human edits intro paragraph only.

## Exceptions

Revert commits use `revert:` prefix per spec. Chore commits skipping CI with `[skip ci]` only when truly docs-only—avoid skipping tests on typo fixes that touch code.


## Monorepo commit scopes

In monorepos, scope equals package or app name:

```
feat(app/checkout): add express pay
fix(packages/api): handle 429 retry
```

Melos and changesets read scopes for changelog grouping—align scope list with workspace package names in commitlint config.

## Revert and hotfix conventions

```
revert: feat(auth): passkey login
fix(prod): patch session timeout (#911)
```

Hotfix branches still use conventional commits—release automation depends on parsing.

## Educating contributors

PR template checkbox: "Title follows Conventional Commits." Link to internal examples of good vs bad titles. First-time contributors fail CI once, read doc, rarely fail again—cheaper than rewriting history.

## Interaction with squash merge

When squashing, ensure PR body lists breaking changes—squash commit message becomes single changelog entry; detail belongs in body for release notes context.

## Signed-off-by and DCO

Some open source projects require Signed-off-by trailer in addition to conventional type—both can coexist in commit footer without conflict.

## Rollout guidance

Commit convention enforcement week one warning only CI comment week two block—soft rollout reduces contributor frustration sudden merge block Friday afternoon.

## Team practices

Shipping Git Commit Conventions in production taught our team that documentation beats hero demos. We wrote runbooks covering failure modes, on-call steps, and rollback triggers before the second release, not after the first outage.

When reviewing PRs touching Git Commit Conventions, we ask for measurable outcomes: latency, crash rate, or support ticket volume—not subjective feels faster. If metrics are unavailable, the PR includes a DevTools trace or load test snippet proving the change.

Onboarding engineers paste a checklist into their first Git Commit Conventions PR description: environment setup verified, tests added or updated, accessibility spot-checked, and release notes drafted for user-visible changes.

We keep a living FAQ in the repo wiki for Git Commit Conventions questions repeated in Slack more than twice. FAQ entries link to source files and Slack threads, reducing tribal knowledge and repeated explanations in code review.

Cross-functional review includes design for UX-facing work, security for auth or storage, and platform for native bridges. Git Commit Conventions spans layers; skipping reviewers recreated bugs we fixed months ago.

Staging soaks 24 hours for risky changes while dashboards watch error rates.canary cohorts internal staff first, then five percent production, then full rollout if crash-free sessions hold within baseline tolerance.

Post-release we schedule a short retro even on smooth launches—what signal caught issues early, what was noise. Git Commit Conventions improvements compound when feedback loops stay short and blameless.

Enforce commit format with commitlint in CI, not README pleading — conventional commits enable automated changelogs only when machine-verified.

## Resources

- [Conventional Commits specification](https://www.conventionalcommits.org/)
- [commitlint](https://commitlint.js.org/)
- [semantic-release](https://semantic-release.gitbook.io/)
- [@commitlint/config-conventional](https://www.npmjs.com/package/@commitlint/config-conventional)
- [Angular commit message guidelines (historical basis)](https://github.com/angular/angular/blob/main/contributing-docs/commit-message-guidelines.md)
