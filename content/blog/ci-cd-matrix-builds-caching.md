---
title: "Matrix Builds and Caching in CI"
slug: "ci-cd-matrix-builds-caching"
description: "Combine CI matrix jobs with dependency and build caches to test multiple platforms without paying the full compile cost on every run."
datePublished: "2025-03-01"
dateModified: "2025-03-01"
tags: ["DevOps", "CI/CD"]
keywords: "CI matrix builds, GitHub Actions cache, Gradle cache, CI caching strategy, parallel jobs, build matrix"
faq:
  - q: "What is a matrix build in CI?"
    a: "A matrix build runs the same workflow against multiple configurations—OS versions, language runtimes, or target platforms—in parallel jobs generated from a single definition. Instead of copying a job five times for five JDK versions, you declare a matrix and the CI platform fans out automatically. Each cell is an independent job with its own logs and artifacts."
  - q: "Where should I put caches in a matrix pipeline?"
    a: "Cache at the dependency layer first: npm, Gradle, Maven, or pip caches keyed by lockfile hashes so every matrix cell reuses downloaded packages. Add build output caches only when your tool supports content-addressable keys—Gradle build cache, sccache for Rust, or Turbo for monorepos. Avoid caching final artifacts unless downstream jobs consume them directly."
  - q: "How do I prevent cache stampede on cold starts?"
    a: "Use a restore-keys fallback chain so a partial cache hit still beats a full cold download. Warm caches on a scheduled job or a dedicated main-branch workflow that runs before feature branches pile up. Keep cache keys stable across matrix dimensions that share dependencies—key by lockfile, not by OS, when packages are identical."
---

Matrix builds multiply your test surface area without multiplying your YAML copy-paste. The failure mode I see most often is teams that add a five-way matrix and wonder why CI minutes tripled overnight. The matrix itself is cheap; uncached dependency resolution on every cell is not. The fix is treating matrix jobs as parallel consumers of shared cache layers, not five independent cold builds.

## When a matrix actually helps

Use a matrix when the same steps apply to different axes: JDK 17 vs 21, Ubuntu vs macOS, or `debug` vs `release`. The value is coverage—you catch platform-specific breakage in one PR instead of after release. The cost is fan-out: five matrix cells means five concurrent runners, five log streams, and five chances to fail on flaky network.

Skip the matrix when configurations need different steps entirely. A job that runs integration tests on Linux and notarization on macOS is two jobs with different scripts, not a matrix with an empty `if` on half the cells.

## GitHub Actions matrix with Gradle cache

This pattern works for JVM projects where every cell shares the same dependency graph:

```yaml
jobs:
  test:
    strategy:
      fail-fast: false
      matrix:
        java: [17, 21]
        os: [ubuntu-latest, macos-latest]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: ${{ matrix.java }}

      - name: Cache Gradle
        uses: actions/cache@v4
        with:
          path: |
            ~/.gradle/caches
            ~/.gradle/wrapper
          key: gradle-${{ runner.os }}-${{ hashFiles('**/*.gradle*', '**/gradle-wrapper.properties') }}
          restore-keys: |
            gradle-${{ runner.os }}-

      - run: ./gradlew test --build-cache
```

Key the cache by lockfile and wrapper hash, not by matrix values, when dependencies do not change across cells. All four jobs hit the same Gradle cache entry after the first warm run.

## Cache key design

Bad keys cause silent misses or worse—poisoned hits from stale dependencies.

| Layer | Key input | Restore fallback |
|-------|-----------|------------------|
| Package manager | Lockfile hash | Prefix by OS if binaries differ |
| Compiler cache | Source hash + toolchain | Previous commit hash |
| Test fixtures | Fixture file hashes | `main` branch key |

Include the runner OS in the key only when native binaries differ—many npm packages ship prebuilt binaries per platform. For pure JVM or Python projects, a single cross-platform key often works on Linux runners even in a macOS matrix cell if you accept re-downloading platform-specific wheels on macOS.

## Remote build cache vs action cache

GitHub Actions cache and Gradle remote build cache solve different problems. Actions cache persists directories between workflow runs on the same repo. Gradle build cache stores compiled class outputs keyed by task inputs—ideal when matrix cells compile the same modules with different test filters.

```kotlin
// settings.gradle.kts
buildCache {
    local { isEnabled = true }
    remote<HttpBuildCache> {
        url = uri("https://cache.example.com/cache/")
        isPush = isCi
        credentials { /* ... */ }
    }
}
```

Push from main-branch CI, read from PR matrix jobs. PR jobs should not push by default—concurrent writers create race conditions and cache pollution.

## Matrix-specific pitfalls

**fail-fast: true** hides failures. On a PR touching shared infrastructure code, you want all matrix cells to finish so you see whether the bug is JDK-specific or universal. Set `fail-fast: false` for release branches and shared library repos.

**Duplicate work across cells.** If integration tests need identical Docker images, build the image once in a setup job, push to a registry or pass as an artifact, then matrix-test against it. Building the image four times because four matrix cells each run `docker build` wastes minutes.

**Cache size limits.** GitHub Actions evicts caches LRU-style at 10 GB per repo. Large matrix repos with per-OS keys can evict each other. Consolidate keys and prune aggressively—cache only what saves more time than the upload/download overhead.

## Measuring impact

Track three numbers per matrix cell: cache restore time, dependency install time, and compile time. A healthy setup shows restore under 30 seconds and dependency install near zero on cache hit. If compile time dominates even on hit, your build cache is not wired up or task inputs are too volatile (timestamps in generated files break cache keys).

I add a CI summary step that prints cache hit/miss from the cache action output. Visible metrics stop the "CI got slow again" debates from being guesswork.

## Common production mistakes

Teams get matrix builds caching wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

CI/CD for matrix builds caching breaks merges when pipeline secrets rotate without updating OIDC trust, cache keys ignore lockfile changes, and deployment gates check build success but not smoke tests.

## Debugging and triage workflow

When matrix builds caching misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [GitHub Actions cache documentation](https://docs.github.com/en/actions/using-workflows/caching-dependencies-to-speed-up-workflows)
- [Gradle build cache guide](https://docs.gradle.org/current/userguide/build_cache.html)
- [GitHub Actions strategy matrix reference](https://docs.github.com/en/actions/using-jobs/using-a-matrix-for-your-jobs)
- [actions/cache usage patterns](https://github.com/actions/cache/blob/main/tips-and-workarounds.md)
