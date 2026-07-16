---
title: "Testing Pyramid vs Testing Trophy"
slug: "testing-pyramid-vs-trophy"
description: "Testing pyramid vs testing trophy: what each model gets right, why integration tests earn their keep, and how to build a test strategy that catches real bugs fast."
datePublished: "2026-06-09"
dateModified: "2026-06-09"
tags: ["Testing", "Engineering", "Quality", "Backend"]
keywords: "testing pyramid, testing trophy, test strategy, integration tests, unit tests, test coverage, end-to-end tests"
faq:
  - q: "What is the difference between the testing pyramid and the testing trophy?"
    a: "The pyramid says write many fast unit tests, fewer integration tests, and very few end-to-end tests. The trophy shifts weight toward integration tests as the biggest layer, arguing they give the most confidence per unit of effort. Both agree on lots of static checks at the base and few E2E tests at the top."
  - q: "Are integration tests better than unit tests?"
    a: "Neither is universally better — they answer different questions. Unit tests verify a piece of logic in isolation and run in milliseconds; integration tests verify that pieces work together, which is where most real bugs actually live. A good suite uses both, weighted toward whichever catches more bugs for your system."
  - q: "How much test coverage do I actually need?"
    a: "Coverage percentage is a weak proxy. High coverage of trivial getters proves nothing; moderate coverage of critical paths and edge cases proves a lot. Aim to cover the behavior that would cause real incidents, and treat any single coverage number with suspicion."
---

Ask ten engineers how to structure a test suite and you'll get the testing pyramid, the testing trophy, and a fight. The pyramid — lots of unit tests, some integration, a sliver of end-to-end — has been the default for two decades. The trophy pushes back: it says integration tests deserve the most weight because they catch the bugs that actually ship. Both are useful models, and treating either as scripture is how you end up with a suite that's either slow and flaky or fast and blind.

My take, after a decade of maintaining mobile and backend suites: the shapes matter less than the principle underneath them. Write tests at the level where a bug is cheapest to catch and most likely to occur, and stop optimizing for a diagram.

## What the two models actually say

The **testing pyramid** (Mike Cohn) is a triangle. A wide base of unit tests — fast, isolated, cheap — then a narrower band of integration tests, then a thin cap of slow, brittle end-to-end tests. The logic: push tests down to the fastest, most stable layer, because the higher you go the slower and flakier they get.

The **testing trophy** (Kent C. Dodds) keeps a base of static analysis (types, linting), then makes *integration tests* the fat middle, with unit tests slimmer and E2E thin at the top. Its argument, captured in the line "write tests. not too many. mostly integration," is that a test's value is proportional to how much confidence it gives, and integration tests — verifying that units work *together* — give the most confidence per test because that's where real systems break.

```
   Pyramid                 Trophy
    /\                       /\        E2E
   /  \  E2E              /------\
  /----\ Integration     /        \   Integration  (biggest)
 /------\                /----------\
/--------\ Unit         /____________\ Unit
                        [============] Static
```

Notice what they agree on: static checks are cheap and belong at the bottom, and E2E tests are expensive and belong at the top in small numbers. The disagreement is only about the middle — unit-heavy or integration-heavy.

## Why integration tests earn their keep

The trophy's insight is one I've felt viscerally. Most bugs I've shipped were not "this function returns the wrong value" — they were "these two correct components disagree about the contract between them." A repository that returns an empty list where the caller expected null. A serializer that drops a field the API consumer needs. A timezone handled correctly in two places and inconsistently at the seam. Unit tests, by mocking everything around the unit under test, are structurally incapable of catching those. They test your assumptions about the collaborators, not the collaborators.

Integration tests hit that seam. They exercise real components together — a real database, a real HTTP layer — so they catch contract mismatches, wiring mistakes, and the config errors that unit tests mock away. That's why they buy more confidence per test. The cost is speed and setup: a test that spins up Postgres is slower than one that doesn't, and slower suites get run less.

## The mocking trap

The failure mode of a unit-heavy suite isn't the unit tests themselves — it's over-mocking. When every dependency is a mock, your tests assert that the code calls the mocks the way you *expect*, which is circular: you're testing that the code does what you wrote it to do, not that it's correct. I've seen suites with 95% coverage and a green board ship a catastrophic bug because every test mocked the one integration that was actually broken.

```kotlin
// This "passes" whether or not the real repository works
@Test fun `saves user`() {
    val repo = mockk<UserRepository>(relaxed = true)
    val service = UserService(repo)
    service.register("a@b.com")
    verify { repo.save(any()) }   // proves we called a mock. that's all.
}
```

That test tells you nothing about whether `save` actually persists anything. Mocks are a tool for isolating genuinely expensive or nondeterministic dependencies (network, clock, third-party APIs), not a default for everything. When you mock the thing you should be testing, coverage becomes theater.

## Where the pyramid still wins

None of this retires the pyramid. Unit tests remain the right tool for logic-dense code: a pricing calculator, a date-range parser, a state machine with many transitions, a retry policy. These have a combinatorial explosion of cases that would be absurd to test through the full stack — you want hundreds of millisecond-fast cases hammering the logic directly.

On the [EV charging platform](https://blog.michaelsam94.com/how-i-architected-an-ev-charging-platform/) I worked on, the OCPP protocol state machine was pure pyramid territory: dozens of unit tests driving it through every valid and invalid transition, because that's where correctness lived and each case was cheap to express. Meanwhile the seam between the protocol server and the app-facing gateway was integration-test territory, because that's where the contracts could drift. Same system, both shapes, chosen per component.

## Build the suite around bug economics

Here's the framing I actually use, independent of any diagram. For each kind of test, weigh three things:

| Layer | Speed | Confidence | Flakiness |
|---|---|---|---|
| Static (types/lint) | instant | low-but-broad | none |
| Unit | ms | narrow, deep | very low |
| Integration | 100ms–s | high | low-moderate |
| End-to-end | s–min | highest, fragile | high |

Put tests where they catch the most bugs for the least ongoing pain. Logic-heavy code → unit. Component seams, database access, API contracts → integration. Critical user journeys (login, checkout) → a handful of E2E, and no more, because their flakiness tax compounds. This bug-economics view is also how I keep [technical debt](https://blog.michaelsam94.com/managing-technical-debt/) in check: a flaky E2E test that fails randomly is itself a liability, eroding trust in the whole suite until people start ignoring red builds.

## Coverage is a compass, not a destination

Chasing a coverage number produces bad tests. Ninety percent coverage of trivial getters and mock verifications is worse than sixty percent that covers every branch of your payment logic and its edge cases. Coverage tells you what's *un*tested — a useful signal for finding blind spots — but it says nothing about whether the tested paths are tested *well*. I use it to hunt for untouched critical code, never as a target to hit.

The suite that serves you is the one developers trust enough to gate deploys on. That means fast enough to run constantly (so people do), reliable enough that red means broken (not flaky), and focused on behavior that would cause real incidents. Fast, trustworthy tests are also what make [trunk-based development and continuous delivery](https://blog.michaelsam94.com/feature-flags-trunk-based-development/) possible — every commit leans on them. Pyramid or trophy, build for that, and let the diagram be an afterthought.

## Resources

- [Martin Fowler — The Practical Test Pyramid](https://martinfowler.com/articles/practical-test-pyramid.html)
- [Kent C. Dodds — The Testing Trophy and Testing Classifications](https://kentcdodds.com/blog/the-testing-trophy-and-testing-classifications)
- [Martin Fowler — TestPyramid](https://martinfowler.com/bliki/TestPyramid.html)
- [Google Testing Blog — Test Sizes](https://testing.googleblog.com/2010/12/test-sizes.html)
- [Martin Fowler — Mocks Aren't Stubs](https://martinfowler.com/articles/mocksArentStubs.html)
- [Testcontainers — Integration testing with real dependencies](https://testcontainers.com/)
