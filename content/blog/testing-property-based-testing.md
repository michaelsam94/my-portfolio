---
title: "Property-Based Testing"
slug: "testing-property-based-testing"
description: "Property-based testing generates hundreds of random inputs to verify universal properties hold. Find edge cases unit tests miss with QuickCheck, Hypothesis, and jqwik."
datePublished: "2026-01-06"
dateModified: "2026-01-06"
tags: ["Testing", "Property-Based Testing", "Quality", "Engineering"]
keywords: "property-based testing, Hypothesis Python, QuickCheck Haskell, jqwik Java, generative testing, test properties not examples"
faq:
  - q: "When should I use property-based testing instead of example-based tests?"
    a: "Use property-based tests for pure functions with clear invariants — sorting (output is sorted, same length, same elements), serialization (decode(encode(x)) == x), math operations (commutativity, associativity), and parsers. Use example-based tests for specific known cases, error messages, and integration points. Combine both: examples for documentation and regression, properties for comprehensive edge case coverage."
  - q: "How is property-based testing different from fuzz testing?"
    a: "Fuzz testing feeds random inputs to find crashes — no assertions beyond 'didn't crash.' Property-based testing defines properties (invariants) that must hold for all inputs and shrinks failing cases to minimal examples. Fuzzing finds crashes; property testing finds logic bugs."
  - q: "What if property tests are too slow?"
    a: "Reduce example count in CI (Hypothesis: @settings(max_examples=50)) and run full counts nightly. Focus properties on core logic, not I/O-bound code. Use targeted generators that produce meaningful inputs instead of completely random data."
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

## Common production mistakes

Teams get property based testing wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Testing strategy for property based testing gives false confidence when mocks return happy paths only, flakey tests are retried until green, and contract tests are never run against staging before deploy.

## Resources

- [Hypothesis documentation](https://hypothesis.readthedocs.io/)
- [Hypothesis strategy guide](https://hypothesis.readthedocs.io/en/latest/data.html)
- [jqwik user guide](https://jqwik.net/docs/current/user-guide.html)
- [QuickCheck paper — John Hughes](https://www.cs.tufts.edu/~nr/cs257/archive/john-hughes/quick.pdf)
- [Property-Based Testing with PropEr (Erlang)](https://propertesting.com/)
