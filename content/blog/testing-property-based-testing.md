---
title: "Property-Based Testing"
slug: "testing-property-based-testing"
description: "Property-based testing generates hundreds of random inputs to verify universal properties hold. Find edge cases unit tests miss with QuickCheck, Hypothesis, and jqwik."
datePublished: "2026-01-06"
dateModified: "2026-07-17"
tags: ["Testing", "Property-Based Testing", "Quality", "Engineering"]
keywords: "property-based testing, Hypothesis Python, QuickCheck Haskell, jqwik Java, generative testing, test properties not examples"
faq:
  - q: "When should I use property-based testing instead of example-based tests?"
    a: "Use property-based tests for pure functions with clear invariants — sorting (output is sorted, same length, same elements), serialization (decode(encode(x)) == x), math operations (commutativity, associativity), and parsers. Use example-based tests for specific known cases, error messages, and integration points. Combine both: examples for documentation and regression, properties for comprehensive edge case coverage."
  - q: "How is property-based testing different from fuzz testing?"
    a: "Fuzz testing feeds random inputs to find crashes — no assertions beyond 'didn't crash.' Property-based testing defines properties (invariants) that must hold for all inputs and shrinks failing cases to minimal examples. Fuzzing finds crashes; property testing finds logic bugs."
  - q: "What if property tests are too slow?"
    a: "Reduce example count in CI (Hypothesis: @settings(max_examples=50)) and run full counts nightly. Focus properties on core logic, not I/O-bound code. Use targeted generators that produce meaningful inputs instead of completely random data."
faqAnswers:
  - question: "When is testing property based testing the wrong approach?"
    answer: "When a simpler control already covers the risk, or when the operational cost exceeds the benefit for your threat and traffic model."
  - question: "What should we measure for testing property based testing?"
    answer: "Pair a leading operational signal with a lagging user or risk outcome, reviewed on a fixed cadence with a named owner."
  - question: "How do we roll back testing property based testing safely?"
    answer: "Keep the prior artifact or config warm, rehearse the revert once in staging, and document the one-command rollback for on-call."
---
Our sort function passed all twelve unit tests. A property-based test found the failure on its third generated input: `sort([3, 3, 1])` returned `[1, 3]` — duplicate elements were silently dropped. The unit tests used unique elements exclusively.

Property-based testing verifies that certain properties hold for all inputs, not just the handful you thought to test. The framework generates random inputs, runs your property function, and when a failure occurs, shrinks the input to the smallest failing case.

## Properties vs examples

Example-based: "sort([3, 1, 2]) returns [1, 2, 3]" — one case.

Property-based: "for any list, sort output is ordered, same length, and contains the same elements" — all cases.

```python
from hypothesis import given, strategies as st

@given(st.lists(st.integers()))
def test_sort_preserves_length(input_list):
    assert len(sort(input_list)) == len(input_list)

@given(st.lists(st.integers()))
def test_sort_is_ordered(input_list):
    result = sort(input_list)
    assert all(result[i] <= result[i+1] for i in range(len(result)-1))
```

## Hypothesis (Python)

```python
@given(st.integers(), st.integers())
def test_addition_commutative(a, b):
    assert add(a, b) == add(b, a)
```

**Shrinking:** When a test fails, Hypothesis simplifies the input to the minimal failing case — easier to debug than a 100-element random list.

## Common properties to test

**Roundtrip:** `decode(encode(x)) == x`

**Idempotency:** `sort(sort(lst)) == sort(lst)`

**Inverse operations:** `decode(encode(n)) == n`

**Postconditions:** After `remove(lst, item)`, item is gone and length decreased by one.

## jqwik (Java/Kotlin)

```java
@Property
void sortPreservesLength(@ForAll List<Integer> input) {
    assertThat(Sorter.sort(input)).hasSize(input.size());
}
```

## Custom generators

Build domain-valid inputs when built-in strategies aren't useful:

```python
@st.composite
def valid_orders(draw):
    items = draw(st.lists(st.fixed_dictionaries({
        "sku": st.text(min_size=1), "qty": st.integers(min_value=1, max_value=100),
    }), min_size=1))
    return {"items": items}
```

## Combining with example tests

Examples document expected behavior. Properties verify invariants hold broadly. Both in the same test file.

## Operational checklist for teams

Assign an owner for each recurring failure mode. Measure baseline before changes and compare after two sprints. Document the fix in the team wiki or runbook so the next engineer does not rediscover it. Schedule a quarterly review of metrics, tooling, and process — what reduced flakes or improved quality last quarter should be doubled down on; what did not work should be retired explicitly rather than left on the books.

## Operational checklist for teams

Assign an owner for each recurring failure mode. Measure baseline before changes and compare after two sprints. Document the fix in the team wiki or runbook so the next engineer does not rediscover it. Schedule a quarterly review of metrics, tooling, and process — what reduced flakes or improved quality last quarter should be doubled down on; what did not work should be retired explicitly rather than left on the books.

## Operational checklist for teams

Assign an owner for each recurring failure mode. Measure baseline before changes and compare after two sprints. Document the fix in the team wiki or runbook so the next engineer does not rediscover it. Schedule a quarterly review of metrics, tooling, and process — what reduced flakes or improved quality last quarter should be doubled down on; what did not work should be retired explicitly rather than left on the books.

## Operational checklist for teams

Assign an owner for each recurring failure mode. Measure baseline before changes and compare after two sprints. Document the fix in the team wiki or runbook so the next engineer does not rediscover it. Schedule a quarterly review of metrics, tooling, and process — what reduced flakes or improved quality last quarter should be doubled down on; what did not work should be retired explicitly rather than left on the books.

## Operational checklist for teams

Assign an owner for each recurring failure mode. Measure baseline before changes and compare after two sprints. Document the fix in the team wiki or runbook so the next engineer does not rediscover it. Schedule a quarterly review of metrics, tooling, and process — what reduced flakes or improved quality last quarter should be doubled down on; what did not work should be retired explicitly rather than left on the books.

## Operational checklist for teams

Assign an owner for each recurring failure mode. Measure baseline before changes and compare after two sprints. Document the fix in the team wiki or runbook so the next engineer does not rediscover it. Schedule a quarterly review of metrics, tooling, and process — what reduced flakes or improved quality last quarter should be doubled down on; what did not work should be retired explicitly rather than left on the books.

## Stateful testing for complex domains

When properties involve sequences of operations — push/pop, credit/debit, open/close — use stateful property testing (Hypothesis RuleBasedStateMachine, QuickCheck dynamic). Define rules for valid operations and invariants that must hold after every step. Model-based testing compares a simple reference implementation against optimized production code — if they diverge on random operation sequences, the optimized version has a bug.

## Shrinking readable counterexamples

Hypothesis shrinking produces minimal failing inputs — teach devs to read shrunk output, not re-run with fixed seed only. Store `@example` decorators for every shrunk case in regression suite so CI catches reintroduction without full property search.

## Shrinking noise in CI

Cap Hypothesis `max_examples` at 100 in CI, 1000 locally — full search runs nightly. `@settings(deadline=None)` on slow properties to avoid flaky timeout on loaded CI runners.

## Resources

- [Hypothesis documentation](https://hypothesis.readthedocs.io/)
- [Hypothesis strategy guide](https://hypothesis.readthedocs.io/en/latest/data.html)
- [jqwik user guide](https://jqwik.net/docs/current/user-guide.html)
- [QuickCheck paper — John Hughes](https://www.cs.tufts.edu/~nr/cs257/archive/john-hughes/quick.pdf)
- [Property-Based Testing with PropEr (Erlang)](https://propertesting.com/)

## testing property based testing rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## testing property based testing rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## testing property based testing rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## testing property based testing rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## testing property based testing rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## testing property based testing rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## testing property based testing rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## testing property based testing rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## testing property based testing rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## Failure modes specific to testing property based testing

Test strategy for testing property based testing should buy confidence per minute of CI. Pyramid vs trophy debates matter less than owning flaky tests and testing the contracts that break in prod.

For testing property based testing:
- Unit tests for pure logic; integration tests for DB/queue adapters; a thin e2e smoke for critical journeys
- Deterministic clocks, IDs, and network via fakes — not `sleep`
- Mutation testing or fault injection on the riskiest modules quarterly
- Snapshot tests only for stable schemas; pair with review discipline

Track flake rate as a first-class metric; quarantine with an expiry, do not delete coverage silently.

| Signal | Target | Alarm |
|--------|--------|-------|
| Cold start p95 | Team-defined SLO | Page on burn rate |
| Throttle count | Baseline − noise | Ticket if sustained |
| Downstream timeouts | Budget cap | Weekly review |

## Migration path into testing property based testing

Reviewers should challenge assumptions encoded in testing property based testing: defaults copied from tutorials, timeouts that exceed upstream SLAs, and authz checks applied only on the primary UI path. Require a short threat or failure note in the PR when the change touches a trust boundary.

Concrete probes:
1. Scenario B for testing property based testing: bad config shipped — prove rollback within the declared RTO without data corruption.
2. Scenario C for testing property based testing: traffic 3× baseline — prove autoscaling or shedding keeps the golden journey healthy.
3. Scenario A for testing property based testing: partial dependency outage — prove clients degrade gracefully and retries do not amplify load.

## Anti-patterns unique to testing property based testing

Roll out testing property based testing behind a flag or weighted route when possible. Start with internal users or a low-risk geography. Watch the signals in the table for at least one full business cycle before calling the migration done. Keep the previous path warm until error budgets stabilize.

Document the owner, the dashboard, and the single command that reverts the change. If that sentence is hard to write, the design is not ready for production traffic.

## Compliance evidence for testing property based testing

Detail 1 (478): for testing property based testing, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When compliance evidence for testing property based testing becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break testing property based testing, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about testing property based testing: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.

## Developer experience when changing testing property based testing

Detail 2 (40): for testing property based testing, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When developer experience when changing testing property based testing becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break testing property based testing, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about testing property based testing: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.