---
title: "Making CI/CD Pipelines Fast"
slug: "fast-cicd-pipelines"
description: "Tactics for faster CI/CD — build caching, test sharding, parallelism, and dependency graphs. Cut a 40-minute pipeline to under ten without cutting corners."
datePublished: "2026-06-29"
dateModified: "2026-06-29"
tags: ["CI/CD", "Developer Experience", "Build Systems", "Testing"]
keywords: "CI/CD, pipeline speed, build caching, parallel tests, faster CI, test sharding, remote cache"
faq:
  - q: "What is the single biggest win for faster CI?"
    a: "Caching — dependency caches and build/test caches. Most pipelines redownload dependencies and rebuild unchanged code on every run. A warm remote cache and correct cache keys often cut pipeline time by half before you touch parallelism."
  - q: "How do I speed up a slow test suite in CI?"
    a: "Shard it. Split tests across N parallel runners so each does 1/N of the work, and balance shards by historical runtime rather than file count. Combine with running only tests affected by the change on pull requests, and keep the full suite for main."
  - q: "Should CI run everything on every commit?"
    a: "Not on every commit. Run a fast affected-only subset on pull requests for quick feedback, and reserve the full matrix — all platforms, all integration tests — for merges to main and nightly runs. This keeps the feedback loop tight without losing coverage."
---

A 40-minute pipeline doesn't cost you 40 minutes. It costs you the context switch, the half-finished thing you started while waiting, the third round of "just one more push to fix the lint," and the creeping team habit of batching up changes because pushing is expensive. Slow CI quietly degrades everything downstream of it. Making CI/CD pipelines fast is one of the highest-leverage things a platform team can do, and most of the wins are unglamorous.

I've taken a few pipelines from "go make coffee" to "done before I've tabbed away," and the pattern is always the same: measure first, then cache, parallelize, and only run what changed.

## Measure before you optimize

You cannot fix what you can't see. Before touching anything, break the pipeline into stages and record where the wall-clock time actually goes. Almost every slow pipeline I've inspected had one or two dominant stages and a long tail that didn't matter. The usual suspects:

- **Dependency resolution** — redownloading node_modules, Gradle deps, or pip packages from scratch.
- **Cold builds** — recompiling code that didn't change.
- **The test suite** — usually the biggest single block, and the one with the most parallelism headroom.
- **Container image builds** — no layer cache, so every layer rebuilds.

Optimize the tall bars, ignore the short ones. Shaving 10 seconds off a 30-second lint stage while a 22-minute test stage sits untouched is motion, not progress.

## Cache aggressively and correctly

Caching is where the first big win lives, and correct cache *keys* are the entire trick. A cache key too broad serves stale artifacts; too narrow and you never get a hit.

For dependencies, key on the lockfile hash so the cache invalidates only when dependencies actually change:

```yaml
# GitHub Actions: cache keyed on the lockfile
- uses: actions/cache@v4
  with:
    path: ~/.gradle/caches
    key: gradle-${{ runner.os }}-${{ hashFiles('**/*.gradle*', 'gradle/libs.versions.toml') }}
    restore-keys: gradle-${{ runner.os }}-
```

For builds, use a *remote* cache so every runner and every developer shares the same artifacts. Gradle's build cache, Bazel's remote cache, Turborepo's remote cache, and `sccache` for Rust/C++ all do this. The effect is dramatic on monorepos: if a module's inputs are unchanged, its output is fetched instead of rebuilt. On one Gradle project, wiring up a remote build cache took a clean CI build from 14 minutes to under 4 on cache hits. If your Android builds are the bottleneck specifically, I've gone deeper on [faster Gradle builds](https://blog.michaelsam94.com/faster-gradle-builds/) elsewhere.

For Docker images, order your Dockerfile from least- to most-frequently-changing and use BuildKit's cache mounts and registry cache so dependency layers survive between runs.

```dockerfile
# syntax=docker/dockerfile:1
FROM node:22-slim
WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci   # cached across builds
COPY . .
RUN npm run build
```

## Parallelize the test suite

Once caching is sorted, the test suite is usually what's left. Two levers:

**Shard across runners.** Split tests into N groups and run them on N machines at once. The naive split by filename is bad — one shard ends up with all the slow integration tests. Balance by *historical runtime* so each shard finishes at roughly the same time. Most test runners and CI providers support timing-based splits now; use them.

**Parallelize within a runner.** Modern test runners execute test files across worker processes. Make sure it's actually on and that your tests don't share mutable global state, or you'll trade speed for flakiness — and [flaky tests](https://blog.michaelsam94.com/testing-pyramid-vs-trophy/) erode trust in the whole pipeline faster than slowness does.

| Tactic | Typical effect | Cost |
|---|---|---|
| Dependency cache | -30-50% cold time | Low |
| Remote build cache | -50-80% on cache hits | Medium (setup) |
| Test sharding (4x) | ~4x on test stage | Low |
| Affected-only on PRs | -60-90% PR time | Medium (graph setup) |
| Docker layer cache | -50%+ image builds | Low |

## Only run what changed

The fastest task is the one you skip. On pull requests, run only the tests and builds affected by the diff. Monorepo tools compute this from the dependency graph: Nx, Turborepo, and Bazel all know that a change in `packages/ui` can't affect `services/billing`, so they skip billing's tests entirely.

Reserve the full matrix — every platform, every integration test, every browser — for merges to `main` and nightly runs. This is the single biggest lever for developer-facing feedback time, because most PRs touch a small slice of the codebase. It leans on [trunk-based development and feature flags](https://blog.michaelsam94.com/feature-flags-trunk-based-development/): small, frequent merges keep the affected set small and the pipeline fast.

Guard it, though. Affected-detection that's subtly wrong will skip a test that *should* have run and let a regression through. Keep the full suite on `main` as the safety net, and be conservative about what counts as "not affected."

## Fail fast, and keep runners warm

Put the cheap, high-signal checks first — lint, type-check, format — and let them fail the pipeline in seconds before you spend 20 minutes on tests that won't matter if the build is broken. Run independent stages concurrently rather than in a needless sequence; if lint and unit tests don't depend on each other, they shouldn't wait on each other.

Cold start is a hidden tax. Spinning up a fresh container, installing tools, and warming caches on every job adds up. Pre-baked runner images with your toolchain already installed, and larger/persistent runners for the heavy stages, remove minutes you never see in the pipeline definition.

## Watch it over time

Pipeline speed regresses silently. Someone adds a slow test, disables a cache to "debug something," or bumps a dependency that breaks a cache key, and three weeks later the pipeline is back to 25 minutes and nobody noticed the slide. Track pipeline duration as a first-class metric with an alert on regressions, the same way you'd watch a latency SLO. Treat a slow pipeline as a bug with an owner, not a fact of life.

## The short version

Measure the stages, cache dependencies and builds with correct keys, shard and parallelize the tests, run only what changed on PRs, and fail fast on the cheap checks. None of it is exotic. Done together it routinely turns a 40-minute pipeline into a sub-10-minute one, and the compounding effect on how the team works — smaller PRs, faster merges, less batching — is bigger than the raw minutes suggest.

## Resources

- [GitHub Actions — caching dependencies](https://docs.github.com/en/actions/using-workflows/caching-dependencies-to-speed-up-workflows)
- [Docker BuildKit — build cache](https://docs.docker.com/build/cache/)
- [Gradle — build cache](https://docs.gradle.org/current/userguide/build_cache.html)
- [Bazel — remote caching](https://bazel.build/remote/caching)
- [Turborepo — caching](https://turborepo.com/docs/crafting-your-repository/caching)
- [Martin Fowler — Continuous Integration](https://martinfowler.com/articles/continuousIntegration.html)
