---
title: "Affected-Only Builds in a Monorepo"
slug: "ci-cd-monorepo-affected-builds"
description: "Run CI only on monorepo packages touched by a change using dependency graphs, path filters, and tools like Nx, Turborepo, or Bazel."
datePublished: "2025-03-04"
dateModified: "2025-03-04"
tags: ["DevOps", "CI/CD"]
keywords: "monorepo CI, affected builds, Nx affected, Turborepo filter, path filters, dependency graph CI"
faq:
  - q: "What is an affected-only build?"
    a: "An affected-only build analyzes which packages or modules changed in a commit and runs tests, lint, and builds only for those packages plus anything that depends on them transitively. A one-line fix in a shared UI library triggers builds for the library and the three apps that import it, but not the unrelated backend service. This cuts CI time from tens of minutes to minutes on large repos."
  - q: "How do path filters differ from dependency-graph analysis?"
    a: "Path filters match changed file paths against glob patterns—fast and simple, but they miss transitive impact when a shared package changes. Dependency-graph tools read package manifests and build graphs to compute the full downstream set. Use path filters for coarse skipping and graph tools when packages have complex interdependencies."
  - q: "Does affected CI work on the default branch?"
    a: "On main, many teams run full builds for release confidence while using affected builds on PRs. Alternatively, nightly full builds plus affected PR builds balance speed and coverage. Never skip integration tests that require the full system unless you have a separate scheduled pipeline that exercises everything."
---

A monorepo with forty packages and a CI pipeline that builds all forty on every push will eventually train your team to avoid pushing. I have watched PR cycle times climb from twenty minutes to two hours because nobody wanted to touch the shared lint config. Affected-only builds fix this by answering one question before any compile starts: which parts of the graph actually need to run?

## The dependency graph is the source of truth

Every affected-build tool ultimately builds a directed graph: nodes are packages or targets, edges are import or build dependencies. When `packages/auth` changes, the tool walks downstream edges and marks every reachable node as affected. Upstream packages—things `auth` depends on—usually do not rebuild unless their outputs changed.

```json
// turbo.json
{
  "tasks": {
    "build": {
      "dependsOn": ["^build"],
      "outputs": ["dist/**"]
    },
    "test": {
      "dependsOn": ["build"]
    }
  }
}
```

The `^build` syntax means "build my dependencies first." Turborepo, Nx, and Bazel all express similar concepts with different syntax, but the graph semantics are identical.

## Turborepo: filter by git diff

On a PR, compare against the merge base and run only affected packages:

```bash
npx turbo run test lint build \
  --filter="...[origin/main]" \
  --concurrency=10
```

The `...[origin/main]` filter means "packages changed since main plus dependents." First run on a cold cache still builds affected nodes; subsequent runs hit Turborepo's local and remote cache for unchanged task outputs.

For explicit package scoping:

```bash
turbo run test --filter=@acme/web...  # web and its deps
turbo run test --filter=...@acme/ui    # everything depending on ui
```

## Nx affected commands

Nx computes affected projects from the default base branch:

```bash
npx nx affected -t test,lint,build --base=origin/main
```

Nx also supports **implicit dependencies**—linking a root ESLint config to all projects without a package import. Configure these in `nx.json` or project metadata; otherwise a `.eslintrc` change won't trigger the lint tasks you expect.

```json
{
  "implicitDependencies": {
    ".eslintrc.json": "*",
    "tsconfig.base.json": "*"
  }
}
```

## GitHub Actions path filters (coarse layer)

Path filters skip entire workflows when no relevant files changed. They do not understand package graphs, but they are free and instant:

```yaml
on:
  pull_request:
    paths:
      - 'packages/**'
      - 'pnpm-lock.yaml'
      - '.github/workflows/ci.yml'
```

Combine path filters with graph tools: path filter avoids spinning up a runner when only `docs/` changed; the graph tool decides which packages to test when `packages/` did change.

## Handling shared infrastructure changes

Some changes affect everything: root `tsconfig`, CI config, Docker base images, shared Babel preset. Tag these as global triggers:

```yaml
# .github/workflows/ci.yml
- name: Detect global change
  id: global
  run: |
    if git diff --name-only origin/main... | grep -qE '^(tsconfig|\.github)/'; then
      echo "global=true" >> $GITHUB_OUTPUT
    fi

- name: Full build on global change
  if: steps.global.outputs.global == 'true'
  run: npx turbo run test build

- name: Affected build
  if: steps.global.outputs.global != 'true'
  run: npx turbo run test build --filter="...[origin/main]"
```

Without this escape hatch, a TypeScript version bump in root config runs tests on zero packages while everything is actually broken.

## Remote caching makes affected builds faster

Affected builds reduce *how many* tasks run. Remote caching reduces *how long each task takes*. The combination is multiplicative: three affected packages × cache hit = seconds instead of minutes.

Push cache from main, read from PRs. Set `TURBO_TOKEN` and `TURBO_TEAM` (or Nx Cloud equivalent) in CI secrets. Local developers get the same cache hits when running affected commands before push.

## What affected builds cannot skip

End-to-end tests that span multiple packages often need a full deploy preview, not an affected unit test run. Contract tests between services should run when either side of the contract changes—model this as an explicit dependency edge, not an implicit "hope someone runs it."

Security scans and license checks on the full dependency tree belong on a schedule or on main merges, not gated behind affected logic that might miss a transitive vulnerability in an untouched package.

## Nx/Turborepo affected detection

```bash
npx turbo run build test --filter=[origin/main...HEAD]
```

Build only changed packages and dependents — 50-package monorepo builds in 2 minutes instead of 45. Cache task outputs remotely for CI speedup.

## Common production mistakes

Teams get monorepo affected builds wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

CI/CD for monorepo affected builds breaks merges when pipeline secrets rotate without updating OIDC trust, cache keys ignore lockfile changes, and deployment gates check build success but not smoke tests.

## Debugging and triage workflow

When monorepo affected builds misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Turborepo filtering documentation](https://turbo.build/repo/docs/core-concepts/monorepos/filtering)
- [Nx affected commands](https://nx.dev/nx-api/nx/documents/affected)
- [GitHub Actions path filters](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions#onpushpull_requestpull_request_pathspaths-ignore)
- [Bazel query for affected targets](https://bazel.build/query/guide)
