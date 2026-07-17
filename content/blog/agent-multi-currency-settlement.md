---
title: "AI Agents: Multi Currency Settlement"
slug: "agent-multi-currency-settlement"
description: "Ledger design, FX handling, and reconciliation patterns for agent platforms that bill usage in one currency and settle payouts in another."
datePublished: "2025-09-04"
dateModified: "2025-09-04"
tags: ["AI", "Agent", "Multi"]
keywords: "multi-currency billing, agent usage metering, FX settlement, minor units, ledger reconciliation, Stripe multi-currency"
faq:
  - q: "Should agent usage be metered in the customer's currency or a platform base currency?"
    a: "Meter in a single platform base currency internally—usually USD or EUR—then convert for display and invoicing at defined rate snapshots. Metering directly in dozens of currencies creates reconciliation nightmares when rates move intraday and usage events arrive out of order."
  - q: "How do you avoid rounding errors that accumulate across millions of micro-transactions?"
    a: "Store all amounts as integers in minor units (cents, yen without decimals) and never use floating point in the ledger. Apply banker's rounding only at presentation boundaries. Keep a separate rounding adjustment account that finance can zero out monthly."
  - q: "When should FX rates be locked for a settlement batch?"
    a: "Lock at batch close time, not at individual event ingestion. Agent usage events stream continuously; settlement batches close on a schedule—daily at 23:59 UTC for SMB, monthly for enterprise. The rate table version ID becomes part of the batch metadata for audit."
  - q: "What breaks if partner payouts lag invoice collection by a week?"
    a: "You carry FX exposure. If you invoice a German customer in EUR on Monday but pay a US GPU vendor in USD on Friday, a 2% EUR move hits margin. Either shorten the payout window, hedge programmatically, or quote prices in the payout currency with explicit FX buffers."
---
Finance opened a ticket labeled "pennies wrong" and attached a spreadsheet showing €847.13 billed versus €847.19 accrued over six weeks of agent usage. The root cause was not fraud—it was three engineers storing `amount * rate` as JavaScript floats, rounding per event instead of per batch, and pulling FX from two different providers without versioning. Multi-currency settlement for agent platforms is arithmetic dressed up as infrastructure; get the invariants wrong and every dashboard lies a little.

## The money path for agent usage

An agent platform typically moves value through four hops:

1. **Metering** — token counts, tool invocations, storage bytes, attributed to `tenant_id` with timestamps.
2. **Rating** — apply price list (per-model, per-region surcharges) in base currency minor units.
3. **Invoicing** — convert rated totals to customer currency for Stripe or NetSuite.
4. **Settlement** — aggregate payable lines to vendors and partners in their preferred currency.

Each hop is idempotent and append-only. Corrections are new ledger entries, never updates.

```
usage events → rating engine → rated_lines (USD cents)
                                    ↓
                         FX snapshot @ batch_close
                                    ↓
                    invoice_lines (EUR cents) → Stripe
                                    ↓
                    payout_lines (USD cents) → vendor ACH
```

If any arrow lacks a versioned snapshot ID, auditors will ask questions you cannot answer.

## Minor units everywhere

Define a single internal type and ban floats in code review:

```typescript
/** Amount stored as integer minor units in a specific currency. */
type Money = {
  currency: CurrencyCode; // ISO 4217
  minorUnits: bigint;     // JPY: 1 yen = 1 unit; USD: 1 cent = 1 unit
};

function add(a: Money, b: Money): Money {
  if (a.currency !== b.currency) {
    throw new Error("cannot add unlike currencies without FX conversion");
  }
  return { currency: a.currency, minorUnits: a.minorUnits + b.minorUnits };
}
```

PostgreSQL users should store `minor_units BIGINT` and `currency CHAR(3)`—never `NUMERIC` without explicit scale rules. For currencies with three decimal places (KWD, BHD), document the exponent in a `currency_metadata` table rather than hardcoding `100`.

## FX rate sourcing and snapshots

Pull rates from a provider with a commercial SLA—Open Exchange Rates, ECB daily feed, or your bank's treasury API. Cache raw responses in object storage with SHA-256 hashes.

```sql
CREATE TABLE fx_rate_snapshots (
  snapshot_id     UUID PRIMARY KEY,
  provider        TEXT NOT NULL,
  base_currency   CHAR(3) NOT NULL,
  fetched_at      TIMESTAMPTZ NOT NULL,
  raw_payload_uri TEXT NOT NULL,
  UNIQUE (provider, base_currency, fetched_at)
);

CREATE TABLE fx_rates (
  snapshot_id UUID REFERENCES fx_rate_snapshots(snapshot_id),
  from_ccy    CHAR(3) NOT NULL,
  to_ccy      CHAR(3) NOT NULL,
  rate        NUMERIC(20, 10) NOT NULL, -- stored rational, applied with integer math
  PRIMARY KEY (snapshot_id, from_ccy, to_ccy)
);
```

At batch close, bind `snapshot_id` to every `settlement_batch` row. Replaying a batch six months later uses the same snapshot—required for SOX-style audits.

Conversion at scale uses integer math:

```typescript
function convert(m: Money, to: CurrencyCode, rate: { numerator: bigint; denominator: bigint }): Money {
  const converted = (m.minorUnits * rate.numerator) / rate.denominator;
  return { currency: to, minorUnits: converted };
}
```

Choose rounding mode explicitly—`ROUND_HALF_EVEN` at batch totals, not per line item, unless local tax law demands otherwise.

## Rating agent usage without double billing

Agent workloads produce high-cardinality events. Aggregate before rating when possible:

```python
def aggregate_usage(events: list[UsageEvent]) -> dict[tuple, int]:
    buckets: dict[tuple, int] = {}
    for e in events:
        key = (e.tenant_id, e.model, e.region, e.hour_bucket())
        buckets[key] = buckets.get(key, 0) + e.token_count
    return buckets
```

Idempotency keys on ingestion prevent duplicate charges when clients retry:

```python
def ingest(event: UsageEvent, store: LedgerStore) -> None:
    if store.seen_idempotency_key(event.idempotency_key):
        return
    store.append_raw(event)
    store.mark_idempotency_key(event.idempotency_key, ttl_days=90)
```

Retention policy: raw events 13 months, rated aggregates 7 years, PII stripped after 30 days unless contract requires otherwise.

## Settlement batches and cutoff windows

Align batch boundaries with [settlement cutoff windows](https://blog.michaelsam94.com/agent-settlement-cutoff-windows/) so finance knows when numbers freeze. A daily batch might close at `23:59:59 UTC`; events with `occurred_at` after cutoff roll forward.

```sql
INSERT INTO settlement_batches (batch_id, period_start, period_end, fx_snapshot_id, status)
VALUES ('2025-09-04-daily', '2025-09-03 00:00:00+00', '2025-09-03 23:59:59+00', 'snap-abc', 'open');

-- Close batch: no more lines accepted for this period
UPDATE settlement_batches SET status = 'closed', closed_at = now() WHERE batch_id = '2025-09-04-daily';
```

Partial closes for enterprise tenants—custom contracts with Net 45 terms—get separate batch types. Never mix SMB daily close with enterprise monthly close in one reconciliation report.

## Invoicing vs payout currency mismatch

Customers in Brazil may insist on BRL invoices while your GPU vendor invoices you in USD. Track **economic exposure** explicitly:

| Line type | Currency | When locked |
|-----------|----------|-------------|
| Rated usage | USD (internal) | Event hour |
| Customer invoice | BRL | Batch close FX |
| Vendor payable | USD | Vendor invoice date |
| FX gain/loss | USD | Month-end reval |

Stripe multi-currency charges settle to your platform balance in charge currency; payouts to your bank may still convert. Read Stripe's settlement reports—not the Dashboard summary—to tie agent revenue to bank deposits.

## Reconciliation that catches drift early

Nightly job:

1. Sum rated lines for closed batches.
2. Sum invoice line items exported to Stripe.
3. Sum payout records in treasury system.
4. Assert triangle equality within one minor unit per ten thousand lines.

```python
def reconcile(batch_id: str) -> ReconciliationReport:
    rated = ledger.sum_rated(batch_id)
    invoiced = stripe.sum_invoices(batch_id)
    diff = rated - invoiced
    if abs(diff.minor_units) > tolerance(rated):
        pager.trigger("settlement_drift", batch_id=batch_id, diff=str(diff))
    return ReconciliationReport(rated=rated, invoiced=invoiced, diff=diff)
```

Drift sources ranked by frequency: timezone cutoff bugs, duplicate idempotency key expiry, manual credit notes without ledger mirror, FX snapshot mismatch between rating and invoicing services.

## Tax and regulatory overlays

VAT/GST depends on customer location, not server location. Store `tax_jurisdiction` on the tenant at invoice time. Agent platforms selling into the EU need valid VAT IDs and reverse-charge handling on B2B lines.

Sanctions screening applies before first payout in a new currency corridor. Block settlement to flagged entities at batch generation, not at ACH submission—returns are expensive.

## Testing money paths

Property-based tests on `Money` arithmetic. Golden-file tests on FX conversion with known ECB rates. Integration tests that replay a week of synthetic usage through ingest → rate → batch → mock Stripe.

Chaos: inject duplicate events, delayed events crossing cutoff, and provider returning stale rates. The ledger should never go negative on a tenant prepay balance without an explicit credit line.

## Operational dashboards finance actually opens

- **Unbilled rated usage** — accrual not yet invoiced; should trend smoothly, not stair-step.
- **FX snapshot age** — alert if latest snapshot older than 26 hours on weekdays.
- **Batch close duration** — p95 under five minutes for daily SMB batch.
- **Reconciliation exceptions** — count open items; target zero older than 48 hours.

## Partner revenue share in foreign corridors

When agents resell through partners—systems integrators, marketplace listings, white-label deployments—settlement adds a **revenue share** line denominated in the partner's currency while usage remains rated in base currency. Model this as a separate payable line type rather than adjusting the rated total:

```sql
INSERT INTO payout_lines (batch_id, partner_id, currency, minor_units, line_type)
VALUES ('2025-09-04-daily', 'partner-42', 'GBP', 125000, 'revenue_share');
```

Compute share as a rational fraction applied after FX conversion so partners see consistent percentages on their statements even when daily FX moves. Document whether share applies pre- or post-tax in the partner agreement; mixing conventions across partners guarantees quarterly disputes.

## Closing the loop on the €0.06

The penny ticket closed when the team migrated rated totals to `bigint` minor units, pinned FX snapshots at batch close, and added a reconciliation job that pages on more than three mismatched lines per million. Multi-currency settlement is not exotic—it is disciplined bookkeeping at streaming scale.

## Resources

- [ISO 4217 currency codes](https://www.iso.org/iso-4217-currency-codes.html)
- [Stripe — multi-currency payments](https://docs.stripe.com/payments/currencies)
- [European Central Bank — daily FX reference rates](https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html)
- [Martin Fowler — patterns for money](https://martinfowler.com/eaaCatalog/money.html)
- [PostgreSQL arbitrary precision numeric types](https://www.postgresql.org/docs/current/datatype-numeric.html)
