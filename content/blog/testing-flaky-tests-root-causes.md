---
title: "Root Causes of Flaky Tests"
slug: "testing-flaky-tests-root-causes"
description: "Flaky tests pass and fail without code changes. Identify root causes — timing, shared state, external dependencies, and test order — and fix them systematically."
datePublished: "2025-12-26"
dateModified: "2025-12-26"
tags: ["Testing", "CI/CD", "Quality", "Engineering"]
keywords: "flaky tests, test flakiness root causes, intermittent test failures, fix flaky tests, test isolation, async test timing"
faq:
  - q: "What percentage of test flakiness is acceptable?"
    a: "Zero is the target. In practice, teams tolerate flaky tests until trust erodes — typically when more than 2-3% of CI runs fail on tests that pass on retry. At that point, engineers ignore red builds ('just re-run') and real failures slip through. Track flakiness rate per test. Quarantine any test that fails without code changes more than once in 100 runs."
  - q: "Should I retry flaky tests in CI?"
    a: "Retries mask flakiness without fixing it — use them as a temporary bandage, not a strategy. If a test fails once and passes on retry, quarantine it and fix the root cause within a sprint. Automated retry with reporting is acceptable while fixing. Never retry more than twice — three attempts turning green means the test is broken."
  - q: "How do I find which tests are flaky?"
    a: "Run the test suite 100+ times without code changes. Any test that fails at least once is flaky. Tools like Buildkite Test Analytics and pytest-rerunfailures with --count=100 identify flaky tests automatically. Track failure rate per test over 30 days — tests with 1-99% pass rate are flaky."
---

Our CI had a 12% failure rate on main branch. No code changes between the failing run and the passing re-run. Engineers developed a reflex: see red, click "Re-run jobs," go get coffee. A real regression — a null pointer in the payment flow — sat in a failing build for six hours because three other failures were known flakes.

Flaky tests are tests that produce non-deterministic results — pass sometimes, fail others, with identical code and environment. They erode trust in CI faster than having no tests at all.

## Root cause 1: Async timing and race conditions

The most common cause. Tests assume async operations complete before assertions run:

```javascript
// FLAKY
test("loads user data", () => {
  fetchUser("123");
  expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();
});

// FIXED
test("loads user data", async () => {
  render(<UserProfile userId="123" />);
  expect(await screen.findByText("Ada Lovelace")).toBeInTheDocument();
});
```

Fix: use framework-provided async utilities (`findBy*`, `waitFor`, `await`). Never use bare `sleep()`.

## Root cause 2: Shared mutable state

Tests that mutate global state leak into subsequent tests. Fix with setup/teardown fixtures and run tests in random order (`pytest-randomly`, Jest `--randomize`) to detect order dependencies early.

## Root cause 3: External dependencies

Tests that hit real networks, databases, or clocks fail when those dependencies are slow or unavailable. Fix: mock external dependencies, control time with `@freeze_time` or Jest fake timers, use test containers for database tests.

## Root cause 4: Insufficient isolation in parallel execution

Tests sharing files, ports, or database rows collide in parallel CI. Fix: use `tmp_path` fixtures, random ports, unique database schemas per test worker.

## Root cause 5: Floating-point and comparison issues

Use `pytest.approx()` for floats. Sort collections before comparing when order is irrelevant.

## Systematic flakiness reduction

1. **Measure:** Track per-test pass rate over 30 days. Flag anything below 99%.
2. **Quarantine:** Move flaky tests to a separate CI job that doesn't block merges.
3. **Prevent:** Code review checklist — no bare sleeps, no shared mutable state, no external calls without mocks.
4. **Detect early:** Run tests in random order locally and in CI.
5. **Culture:** A flaky test is a bug, same priority as a production bug.

```bash
for i in $(seq 1 100); do
  pytest tests/test_suspect.py || echo "FAILED on run $i"
done
```

## Operational checklist for teams

Assign an owner for each recurring failure mode. Measure baseline before changes and compare after two sprints. Document the fix in the team wiki or runbook so the next engineer does not rediscover it. Schedule a quarterly review of metrics, tooling, and process — what reduced flakes or improved quality last quarter should be doubled down on; what did not work should be retired explicitly rather than left on the books.

## Operational checklist for teams

Assign an owner for each recurring failure mode. Measure baseline before changes and compare after two sprints. Document the fix in the team wiki or runbook so the next engineer does not rediscover it. Schedule a quarterly review of metrics, tooling, and process — what reduced flakes or improved quality last quarter should be doubled down on; what did not work should be retired explicitly rather than left on the books.

## Operational checklist for teams

Assign an owner for each recurring failure mode. Measure baseline before changes and compare after two sprints. Document the fix in the team wiki or runbook so the next engineer does not rediscover it. Schedule a quarterly review of metrics, tooling, and process — what reduced flakes or improved quality last quarter should be doubled down on; what did not work should be retired explicitly rather than left on the books.

## Operational checklist for teams

Assign an owner for each recurring failure mode. Measure baseline before changes and compare after two sprints. Document the fix in the team wiki or runbook so the next engineer does not rediscover it. Schedule a quarterly review of metrics, tooling, and process — what reduced flakes or improved quality last quarter should be doubled down on; what did not work should be retired explicitly rather than left on the books.

## Common production mistakes

Teams get flaky tests root causes wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Testing strategy for flaky tests root causes gives false confidence when mocks return happy paths only, flakey tests are retried until green, and contract tests are never run against staging before deploy.

## Debugging and triage workflow

When flaky tests root causes misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Google Testing Blog — Flaky Tests at Google](https://testing.googleblog.com/2016/05/flaky-tests-at-google-and-how-we.html)
- [pytest-randomly plugin](https://github.com/pytest-dev/pytest-randomly)
- [Jest fake timers documentation](https://jestjs.io/docs/timer-mocks)
- [freezegun — Python time mocking](https://github.com/spulec/freezegun)
- [Buildkite Test Analytics for flakiness detection](https://buildkite.com/docs/test-analytics)
