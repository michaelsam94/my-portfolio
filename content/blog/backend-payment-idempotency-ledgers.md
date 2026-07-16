---
title: "Idempotency in Payment Ledgers"
slug: "backend-payment-idempotency-ledgers"
description: "Build payment and ledger APIs that survive retries: idempotency keys, ledger entries as facts, and reconciliation when the provider status is unknown."
datePublished: "2024-12-14"
dateModified: "2024-12-14"
tags: ["Backend", "Payments", "Architecture"]
keywords: "payment idempotency, ledger entries, idempotency key Stripe, double charge prevention, financial ledger design"
faq:
  - q: "Why are payments special for idempotency?"
    a: "Money movement is high-stakes and clients retry aggressively on timeouts. A double charge is worse than a slow success. Every charge, refund, and ledger post must be keyed so retries return the original result instead of creating a second movement."
  - q: "Should the ledger be mutable balances or append-only entries?"
    a: "Prefer append-only entries (debit/credit rows) with balances derived or maintained as a projection. Mutable balance-only systems make audit and dispute reconstruction painful. Entries are facts; balances are caches you can rebuild."
  - q: "What do I do when the payment provider times out?"
    a: "Do not retry a new charge blindly. Store the idempotency key and intent id, then retrieve the PaymentIntent/charge by id or key. Branch on known states (succeeded, requires_action, failed). Unknown means 'query again,' not 'create another payment.'"
---

Payment systems fail in the worst way: the HTTP client sees a timeout while the card network actually captured funds. If your API treats that as "try again with a new charge," you double-bill. Idempotency isn't a nice-to-have on ledgers — it's the product.

## Idempotency keys at the edge

Require clients to send `Idempotency-Key` on every money-moving POST. Persist the key with the request hash and response:

```sql
CREATE TABLE idempotency_keys (
  key TEXT PRIMARY KEY,
  tenant_id UUID NOT NULL,
  request_hash TEXT NOT NULL,
  response_code INT,
  response_body JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Same key + same body → return stored response. Same key + different body → `409 Conflict`. Keys should be scoped per tenant/merchant.

## Ledger entries as facts

```sql
CREATE TABLE ledger_entries (
  id UUID PRIMARY KEY,
  account_id UUID NOT NULL,
  amount_cents BIGINT NOT NULL, -- signed: +credit / -debit, or use separate columns
  currency CHAR(3) NOT NULL,
  transfer_id UUID NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (transfer_id, account_id)  -- one entry per account per transfer
);
```

A transfer posts two (or more) entries atomically. Retries of the same `transfer_id` no-op via the unique constraint. Never "update balance" without an entry.

## Provider integration

```typescript
async function charge(input: ChargeInput) {
  const existing = await store.getIdempotent(input.key);
  if (existing) return existing.response;

  const intent = await stripe.paymentIntents.create(
    { amount: input.amount, currency: input.currency, customer: input.customer },
    { idempotencyKey: input.key }
  );

  // Persist intent id BEFORE relying on webhook alone
  await store.saveIntent({ key: input.key, intentId: intent.id, status: intent.status });
  return mapResponse(intent);
}
```

Webhooks are backup confirmation, not the only write path — and webhooks also need [idempotent consumers](https://blog.michaelsam94.com/backend-idempotent-consumer-pattern/).

## Reconciliation

Nightly jobs compare provider exports to ledger entries. Gaps become tickets, not silent balance fudge. For in-flight unknowns, a state machine (`created → pending → succeeded|failed`) beats boolean `paid`.

Money paths demand boring discipline: keys, append-only facts, query-before-recreate. Everything else is how chargebacks start.

## Idempotency key lifecycle

Keys aren't fire-and-forget strings — they have a lifecycle tied to HTTP semantics:

1. **First request** — persist key with `status: processing` before calling the provider. This prevents concurrent duplicate requests from both passing the "no existing key" check.
2. **Provider responds** — update stored response atomically, set `status: completed`.
3. **Retry arrives** — return stored response with original status code (Stripe returns 200 with same body, not 409).
4. **Key expiry** — Stripe holds keys ~24 hours; your store should match. Expired keys allow intentional re-attempt with a new key for genuinely new operations.

```typescript
async function withIdempotency<T>(key: string, hash: string, fn: () => Promise<T>): Promise<T> {
  const existing = await db.idempotencyKeys.find(key);
  if (existing?.status === 'completed') return existing.response as T;
  if (existing?.requestHash !== hash) throw new ConflictError('Key reused with different body');

  const lock = await db.acquireIdempotencyLock(key); // SELECT FOR UPDATE or Redis SETNX
  try {
    const result = await fn();
    await db.completeIdempotency(key, result);
    return result;
  } catch (e) {
    await db.failIdempotency(key, e);
    throw e;
  } finally {
    await lock.release();
  }
}
```

Race two identical POSTs and only one should reach the provider.

## Double-entry invariants

Append-only ledgers follow accounting invariants that code must enforce:

- **Every transfer balances** — sum of entries for a transfer equals zero across accounts (or explicit fee accounts absorb the difference).
- **No negative balances** (unless credit lines are a product feature) — check constraint or application guard before commit.
- **Immutability** — never UPDATE or DELETE ledger rows; corrections are reversing entries with a reference to the original.
- **Monotonic sequence** — per-account entry sequence numbers make reconciliation and audit trails deterministic.

```sql
-- Correction pattern: never mutate, always reverse
INSERT INTO ledger_entries (account_id, amount_cents, transfer_id, reference_entry_id)
VALUES ($customer_account, 5000, $reversal_transfer, $original_entry_id),
       ($merchant_account, -5000, $reversal_transfer, $original_entry_id);
```

Disputes and chargebacks become searchable chains of linked entries, not forensic archaeology through balance column history.

## Webhook and async confirmation

Provider webhooks arrive out of order, duplicate, and late. Treat them as idempotent state transitions, not primary write paths:

```typescript
async function handlePaymentIntentSucceeded(event: StripeEvent) {
  const intent = event.data.object as PaymentIntent;
  await db.transaction(async (tx) => {
    const record = await tx.payments.findByIntentId(intent.id);
    if (record?.status === 'succeeded') return; // already processed

    await tx.payments.updateStatus(intent.id, 'succeeded');
    await tx.ledger.postTransfer(buildTransferFromIntent(intent));
  });
}
```

The synchronous API path and webhook path must converge on the same state machine. If API returned `pending` and webhook says `succeeded`, the webhook promotes state and posts ledger entries — the API response on retry should reflect final state.

## Reconciliation deep dive

Nightly reconciliation compares three sources: your ledger, your payment records, and provider exports (Stripe Sigma, settlement reports). Mismatches fall into categories:

| Gap type | Likely cause | Action |
|---|---|---|
| Provider has charge, you don't | Webhook missed, crash before persist | Backfill from provider API |
| You have entry, provider doesn't | Test mode leak, wrong API key | Halt, investigate |
| Amount mismatch | Currency conversion, partial capture | Manual review |
| Timing difference | Settlement delay | Expected, track in transit account |

Run reconciliation before month-end close. Finance teams care about settlement date, not authorization date — model both if you operate internationally.

## Failure modes

- **Optimistic "paid" flag** — UI shows success before webhook confirms; user refreshes and sees unpaid. Gate UX on `succeeded` state only.
- **Key scoped globally** — two merchants reuse the same key format and collide. Scope keys per tenant.
- **Hash excludes fields that matter** — same key, client sends different amount. Hash the full canonical request body.
- **Ledger posted, provider failed** — ordering bug. Post ledger only after confirmed provider success, or use a pending/hold account pattern.

## Production checklist

- Idempotency keys required on all money-moving endpoints
- Keys scoped per tenant with request body hashing
- Processing lock prevents concurrent duplicate execution
- Ledger is append-only with reversing entries for corrections
- Provider intent ID persisted before async confirmation
- Webhooks deduplicated by event ID
- Nightly reconciliation with categorized gap handling
- State machine documented: valid transitions, terminal states, recovery paths

## Resources

- [Stripe Idempotent Requests](https://docs.stripe.com/api/idempotent_requests)
- [Stripe — Designing robust payment systems](https://stripe.com/docs/payments)
- [Martin Kleppmann — Accounting for Computer Scientists](https://martin.kleppmann.com/2011/03/07/accounting-for-computer-scientists.html)
---
