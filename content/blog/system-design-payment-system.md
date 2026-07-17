---
title: "System Design: Payment System"
slug: "system-design-payment-system"
description: "Design a payment processing system with authorization, capture, refunds, idempotency, and PCI compliance for handling financial transactions at scale."
datePublished: "2025-11-05"
dateModified: "2026-07-17"
tags: ["System Design", "Payments", "Architecture", "Fintech"]
keywords: "payment system design, payment processing architecture, idempotency payments, PCI compliance, authorization capture, ledger system design"
faq:
  - q: "What is the difference between authorization and capture in payments?"
    a: "Authorization reserves funds on the customer's payment method without transferring them — like holding a hotel deposit. Capture actually moves the money to the merchant. For physical goods, authorize at checkout and capture at shipment. For digital goods, authorize and capture in one step. Authorization holds typically expire after 7 days (varies by card network). Uncaptured authorizations must be voided or they hold customer funds unnecessarily."
  - q: "How do payment systems ensure exactly-once charging?"
    a: "Idempotency keys on every payment request. The client generates a unique key per payment attempt (UUID or order ID). The payment service stores the key with the result. Retries with the same key return the stored result without re-processing. This handles network timeouts where the client doesn't know if the payment succeeded. Keys expire after 24 hours; new attempts need new keys."
  - q: "Should I store credit card numbers in my database?"
    a: "Never store raw card numbers, CVV, or magnetic stripe data — this requires full PCI DSS Level 1 compliance (expensive audits, strict infrastructure). Use a payment processor (Stripe, Adyen) with tokenization: the processor stores the card, you store a token (pm_abc123) that references it. Your servers never touch raw card data. For custom flows, use hosted payment fields or SAQ A-EP compliant iframe solutions."
faqAnswers:
  - question: "When is system design payment system the wrong approach?"
    answer: "When a simpler control already covers the risk, or when the operational cost exceeds the benefit for your threat and traffic model."
  - question: "What should we measure for system design payment system?"
    answer: "Pair a leading operational signal with a lagging user or risk outcome, reviewed on a fixed cadence with a named owner."
  - question: "How do we roll back system design payment system safely?"
    answer: "Keep the prior artifact or config warm, rehearse the revert once in staging, and document the one-command rollback for on-call."
---
Payment systems have zero tolerance for "mostly correct." A double charge generates angry customers and chargebacks. A lost payment means free products. A security breach with card data means regulatory fines and destroyed trust. The architecture must guarantee that every dollar is accounted for, every operation is idempotent, and raw card data never touches your servers.

## Architecture overview

```
Client → Payment API → Payment Service → Payment Processor (Stripe/Adyen)
              ↓              ↓                    ↓
         Idempotency     Ledger Service      Card Networks (Visa/MC)
           Store              ↓
                        Reconciliation Jobs
```

Your payment service is a state machine wrapper around a payment processor. The ledger records every financial movement. Reconciliation jobs detect discrepancies between your records and the processor's settlement reports.

## Payment state machine

Every payment follows a strict lifecycle:

```
created → authorized → captured → settled
                ↓           ↓
             voided     refunded (partial/full)
                ↓
             failed
```

```python
class PaymentState(Enum):
    CREATED = "created"
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    VOIDED = "voided"
    FAILED = "failed"
    REFUNDED = "refunded"

async def authorize(payment_id: str, amount: int, payment_method: str, idempotency_key: str):
    existing = await idempotency_store.get(idempotency_key)
    if existing:
        return existing

    payment = await payment_store.get(payment_id)
    if payment.state != PaymentState.CREATED:
        raise InvalidStateTransition()

    result = await processor.authorize(
        amount=amount,
        payment_method=payment_method,
        idempotency_key=idempotency_key
    )

    if result.success:
        payment.state = PaymentState.AUTHORIZED
        payment.processor_auth_id = result.auth_id
    else:
        payment.state = PaymentState.FAILED
        payment.failure_reason = result.error

    await payment_store.save(payment)
    await idempotency_store.set(idempotency_key, payment)
    await ledger.record_authorization(payment)
    return payment
```

Valid state transitions are enforced in code — never allow captured → authorized or refunded → captured.

## Idempotency implementation

```python
async def process_payment(request: PaymentRequest) -> PaymentResult:
    cached = await redis.get(f"idempotency:{request.idempotency_key}")
    if cached:
        return PaymentResult.parse(cached)

    lock = await redis.set(
        f"idempotency:lock:{request.idempotency_key}",
        "1", nx=True, ex=86400
    )
    if not lock:
        # Another request is processing — wait and retry
        await asyncio.sleep(0.5)
        return await process_payment(request)

    try:
        result = await execute_payment(request)
        await redis.setex(
            f"idempotency:{request.idempotency_key}",
            86400, result.serialize()
        )
        return result
    finally:
        await redis.delete(f"idempotency:lock:{request.idempotency_key}")
```

The lock prevents concurrent duplicate processing. The cached result handles retries after completion.

## Double-entry ledger

Every financial movement is recorded in a double-entry ledger:

```sql
CREATE TABLE ledger_entries (
    id UUID PRIMARY KEY,
    transaction_id UUID,
    account TEXT,        -- 'merchant:123', 'platform:fees', 'processor:settlement'
    debit_amount BIGINT, -- in cents
    credit_amount BIGINT,
    currency TEXT,
    created_at TIMESTAMP,
    metadata JSONB
);

-- Constraint: sum of debits = sum of credits per transaction
```

```python
async def record_capture(payment: Payment):
    fee = calculate_fee(payment.amount)
    merchant_amount = payment.amount - fee

    entries = [
        LedgerEntry(account=f"processor:settlement", debit=payment.amount),
        LedgerEntry(account=f"merchant:{payment.merchant_id}", credit=merchant_amount),
        LedgerEntry(account="platform:fees", credit=fee),
    ]
    await ledger.append(entries, transaction_id=payment.id)
```

The ledger is append-only — never update or delete entries. Corrections are new entries (refunds, adjustments).

## Refund handling

```python
async def refund(payment_id: str, amount: int, reason: str, idempotency_key: str):
    payment = await payment_store.get(payment_id)

    if payment.state != PaymentState.CAPTURED:
        raise CannotRefund()

    total_refunded = await ledger.sum_refunds(payment_id)
    if total_refunded + amount > payment.amount:
        raise RefundExceedsCapture()

    result = await processor.refund(
        charge_id=payment.processor_charge_id,
        amount=amount,
        idempotency_key=idempotency_key
    )

    if result.success:
        if total_refunded + amount == payment.amount:
            payment.state = PaymentState.REFUNDED
        await ledger.record_refund(payment, amount)
        await payment_store.save(payment)
```

Partial refunds are common (one item returned from a multi-item order). Track cumulative refunded amount against the captured amount.

## PCI compliance architecture

Never let card data touch your servers:

```
Client → Stripe.js (hosted fields) → Stripe API → Card Networks
                ↓
         Your server receives token (tok_abc123)
                ↓
         Payment Service uses token for charge
```

Your server handles tokens, not card numbers. This qualifies for SAQ A (simplest PCI self-assessment). If you must handle card data (custom checkout), use a PCI-compliant vault service and tokenize immediately — card data exists in your system for milliseconds.

## Reconciliation

Daily jobs compare your ledger against processor settlement reports:

```python
async def reconcile(date: date):
    our_records = await ledger.get_settled_transactions(date)
    processor_report = await processor.get_settlement_report(date)

    for txn in our_records:
        processor_txn = processor_report.find(txn.processor_id)
        if not processor_txn:
            await alert("Missing in processor report", txn)
        elif processor_txn.amount != txn.amount:
            await alert("Amount mismatch", txn, processor_txn)

    for processor_txn in processor_report.unmatched:
        await alert("Missing in our ledger", processor_txn)
```

Discrepancies trigger alerts for manual investigation. Common causes: timing differences (authorized today, settled tomorrow), processor fees calculated differently, or failed webhook delivery.

Treat production rollout as a measured change: ship with observability, validate rollback, and review metrics 24 hours after deploy — patterns that look obvious in docs fail when skipped under release pressure.

## Webhook reliability and idempotent handlers

Payment processors confirm state via webhooks — `charge.succeeded`, `charge.refunded`. Webhooks arrive at-least-once, sometimes out of order. Handlers must be idempotent on event ID:

```python
async def handle_webhook(event: WebhookEvent):
    if await processed_events.exists(event.id):
        return 200
    await apply_event(event)
    await processed_events.mark(event.id)
    return 200
```

Verify webhook signatures before processing. Respond 200 quickly and process async if handler work is slow — providers retry on timeout and duplicate delivery is guaranteed.

## PCI scope and tokenization boundaries

Card data never touches application servers — hosted fields or tokenization SDK returns a single-use token to your backend. PCI scope shrinks to SAQ A when checkout iframe is served from the processor domain. Log payment intent IDs, never PAN fragments. Quarterly ASV scans and key rotation for API credentials remain mandatory even with outsourced card entry.

## Reconciliation and ledger invariants

Daily reconciliation jobs compare processor settlement files against internal ledger entries — mismatches trigger finance alerts before month-end close. Double-entry ledger with immutable append-only transaction log makes audit tractable. Never update balance columns in place without corresponding ledger row; investigators need history.

## Resources

- [Stripe payment lifecycle documentation](https://stripe.com/docs/payments/payment-intents)
- [PCI DSS requirements overview](https://www.pcisecuritystandards.org/document_library/)
- [Double-entry bookkeeping for engineers](https://www.moderntreasury.com/journal/accounting-for-engineers)
- [Adyen payment flow architecture](https://docs.adyen.com/online-payments/payment-flow/)
- [Payment card industry data security standard (PCI DSS v4.0)](https://docs-prv.pcisecuritystandards.org/PCI%20DSS/Standard/PCI-DSS-v4_0.pdf)

## Ledger first, API second

Model intents, captures, refunds, and chargebacks as append-only ledger entries with client and provider idempotency keys. At-least-once webhooks plus deterministic transitions beat mythical exactly-once delivery.

Keep PAN data out of your VPC via hosted fields/tokens. Reconcile daily to processor settlements. Load-test idempotency and webhook handlers under retry storms — double charges and stuck pendings are ledger bugs until proven otherwise.

## Verification layer 1 for system design payment system

Define an acceptance check for layer 1: failure injection, timeout behavior, and rollback. Keep it next to the code that implements system design payment system. Reviewers confirm the check fails when the control is disabled.

## Verification layer 2 for system design payment system

Define an acceptance check for layer 2: failure injection, timeout behavior, and rollback. Keep it next to the code that implements system design payment system. Reviewers confirm the check fails when the control is disabled.

## Verification layer 3 for system design payment system

Define an acceptance check for layer 3: failure injection, timeout behavior, and rollback. Keep it next to the code that implements system design payment system. Reviewers confirm the check fails when the control is disabled.

## Verification layer 4 for system design payment system

Define an acceptance check for layer 4: failure injection, timeout behavior, and rollback. Keep it next to the code that implements system design payment system. Reviewers confirm the check fails when the control is disabled.

## Verification layer 5 for system design payment system

Define an acceptance check for layer 5: failure injection, timeout behavior, and rollback. Keep it next to the code that implements system design payment system. Reviewers confirm the check fails when the control is disabled.
