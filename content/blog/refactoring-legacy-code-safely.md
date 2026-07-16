---
title: "Refactoring Legacy Code Safely"
slug: "refactoring-legacy-code-safely"
description: "Refactor legacy code safely with characterization tests, seam identification, incremental extraction, and strangler fig patterns that avoid big-bang rewrites."
datePublished: "2026-01-22"
dateModified: "2026-01-22"
tags: ["Career", "Refactoring", "Legacy Code", "Software Engineering"]
keywords: "refactoring legacy code, characterization tests, strangler fig pattern, seam identification, incremental refactoring, Michael Feathers"
faq:
  - q: "How do I start refactoring code with no tests?"
    a: "Write characterization tests before changing anything. These tests capture the code's current behavior — outputs for given inputs — not the behavior you wish it had. They act as a safety net documenting what the code actually does today. Once characterization tests pass, you can refactor with confidence that you have not broken existing behavior."
  - q: "What is the strangler fig pattern?"
    a: "Named after strangler fig vines that gradually replace a host tree, this pattern builds new functionality alongside legacy code, routing increasing traffic to the new implementation until the old code can be removed. It avoids big-bang rewrites by letting you ship incremental improvements while the legacy system continues running."
  - q: "When should I rewrite instead of refactor?"
    a: "Rewrite only when the legacy system's constraints make incremental change more expensive than replacement — fundamentally wrong architecture, unmaintainable technology stack, or security properties that cannot be patched. Even then, use the strangler fig approach to replace piece by piece. Full rewrites take years, lose institutional knowledge, and often recreate bugs the legacy system already solved."
---

The payment module was 4,000 lines in one class, had zero tests, and three engineers had tried to refactor it before — each leaving after two months of "just fixing the worst parts." The fourth engineer started by writing characterization tests around the existing behavior, identified seams where new code could replace old logic incrementally, and shipped the first extracted service in three weeks without a single production incident. Refactoring legacy code is not about courage or clean-code aesthetics. It is about risk management.

## Characterization tests first

You cannot refactor what you cannot verify. Characterization tests document current behavior:

```python
# Before touching PaymentProcessor at all
def test_process_payment_standard_flow():
    processor = PaymentProcessor(legacy_config)
    result = processor.process({
        "amount": 100.00,
        "currency": "USD",
        "card_token": "tok_test_123",
    })
    assert result["status"] == "completed"
    assert result["fee"] == 2.90  # current behavior, not ideal

def test_process_payment_declined_card():
    processor = PaymentProcessor(legacy_config)
    result = processor.process({
        "amount": 50.00,
        "currency": "USD",
        "card_token": "tok_declined",
    })
    assert result["status"] == "declined"
    assert "insufficient_funds" in result["reason"]
```

These tests may document bugs you will fix later. That is fine — they prevent you from introducing new bugs while restructuring.

**How to write them:**
1. Pick a public method.
2. Call it with representative inputs.
3. Assert whatever it currently returns.
4. Name tests descriptively: `test_current_behavior_when_X`.

## Identify seams

Michael Feathers defines a seam as "a place where you can alter behavior without editing in that place." Find them before cutting:

- **Function parameters** — pass dependencies instead of hardcoding them.
- **Interface boundaries** — legacy class implements an interface; new class implements the same interface.
- **Configuration** — feature flags routing to old or new implementation.
- **HTTP boundaries** — replace an internal module with an API call to a new service.
- **Message queues** — legacy code publishes events; new consumer handles them differently.

```python
# Seam: extract interface
class PaymentGateway(Protocol):
    def charge(self, amount: float, token: str) -> PaymentResult: ...

class LegacyPaymentGateway:
    def charge(self, amount, token):
        # existing 200-line method, unchanged for now
        ...

class StripePaymentGateway:
    def charge(self, amount, token):
        # new clean implementation
        ...
```

The seam is the `PaymentGateway` interface. Callers switch implementations without knowing which is behind it.

## The sprout technique

When you need new behavior, write it in a new module and call it from the legacy code:

```python
# Old code — add one line
def process_payment(self, data):
    if feature_flag("new-fee-calculation"):
        fee = new_fee_calculator.calculate(data)  # sprouted module
    else:
        fee = self._legacy_fee_calculation(data)  # untouched
    # rest of existing method continues...
```

The new fee calculator is clean, tested, and independent. The legacy method gains one branch. Over time, more logic sprouts into new modules.

## Wrap technique

Wrap the legacy module with a thin adapter that presents a clean API:

```python
class PaymentService:
    """Clean public API"""

    def __init__(self):
        self._legacy = PaymentProcessor(legacy_config)

    def charge(self, request: ChargeRequest) -> ChargeResult:
        raw = self._legacy.process({
            "amount": request.amount,
            "currency": request.currency,
            "card_token": request.payment_method.token,
        })
        return ChargeResult(
            status=raw["status"],
            transaction_id=raw.get("txn_id"),
            fee=Money(raw["fee"], request.currency),
        )
```

New code calls `PaymentService`. Legacy code stays untouched inside the wrapper. Gradually move implementation from `_legacy` to clean methods on `PaymentService`.

## Strangler fig for large systems

For modules too large to refactor in place:

```
Month 1:  [══════════ Legacy ══════════]
Month 3:  [══════ Legacy ══════][═ New ═]
Month 6:  [═══ Legacy ═══][════ New ════]
Month 9:  [═ Legacy ═][═══════ New ═══════]
Month 12: [═══════════ New ═══════════════]
```

1. **Route new features** to the new implementation.
2. **Migrate one endpoint/flow** at a time from legacy to new.
3. **Compare outputs** in shadow mode before switching traffic.
4. **Delete legacy code** only when zero traffic routes to it.

```python
def handle_payment(request):
    if feature_flag("new_payment_service") or request.type in MIGRATED_TYPES:
        return new_payment_service.charge(request)
    return legacy_processor.process(request)
```

## Safe extraction steps

For extracting a method or class from legacy code:

1. **Characterization test** the behavior you are extracting.
2. **Copy** (not move) the code to a new function/class.
3. **Run tests** — both old and new paths pass.
4. **Switch** the caller to the new code.
5. **Run tests** again.
6. **Delete** the old copy.
7. **Run tests** one more time.

Never move and modify in the same commit. Copy → verify → switch → delete.

## When to stop refactoring

Not all legacy code deserves refactoring:

- **Code that works and rarely changes** — leave it alone. Stability has value.
- **Code being replaced** — strangler fig it, do not polish the dying module.
- **Code nobody understands and nobody touches** — document it, add monitoring, move on.

Refactor when:
- You need to add features and the code fights every change.
- Bugs keep appearing in the same module.
- Onboarding engineers consistently stumble on it.
- Performance or security requires structural change.

## Team practices

- **Small PRs** — one extraction per PR, not a 3,000-line rewrite.
- **Pair on legacy** — two people understand what the code actually does.
- **Document decisions** — why you extracted X, what the characterization tests revealed.
- **Feature flags** — every migration step behind a flag for instant rollback.

## Common production mistakes

Teams get refactoring legacy code safely wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of refactoring legacy code safely fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [Michael Feathers — Working Effectively with Legacy Code](https://www.oreilly.com/library/view/working-effectively-with/0131177052/)
- [Martin Fowler — Strangler Fig Application](https://martinfowler.com/bliki/StranglerFigApplication.html)
- [Martin Fowler — Refactoring catalog](https://refactoring.com/catalog/)
- [Seam definition — Michael Feathers](https://wiki.c2.com/?SoftwareSeam)
- [Characterization test pattern](https://en.wikipedia.org/wiki/Characterization_test)
