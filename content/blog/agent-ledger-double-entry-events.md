---
title: "AI Agents: Ledger Double Entry Events"
slug: "agent-ledger-double-entry-events"
description: "Double-entry ledger events for agent billing and credits—immutable journals, idempotent posting, multi-currency balances, and reconciliation patterns when tool calls spend money."
datePublished: "2025-09-08"
dateModified: "2025-09-08"
tags: ["AI", "Agent", "Ledger"]
keywords: "double entry ledger, event sourcing, agent billing, idempotent posting, journal entries, credit balance, reconciliation"
faq:
  - q: "Why use double-entry for agent usage billing instead of a simple usage counter?"
    a: "Counters lose auditability— you cannot explain why balance changed or reproduce state after a bug. Double-entry journals record every debit and credit with accounts, amounts, and correlation ids. Finance reconciles to bank and vendor invoices; support traces a user's credit drop to specific agent tool calls. Imbalanced journals fail at insert time."
  - q: "How do agent tool calls map to ledger postings?"
    a: "Each billable tool invocation emits a posting command with idempotency key (tool_call_id), debit user credit liability, credit revenue or COGS expense account, optional tax lines. Never post directly from LLM output—only from orchestrator after tool success confirmed. Failed tools produce no posting; retries reuse the same idempotency key."
  - q: "What idempotency strategy prevents duplicate charges on agent retries?"
    a: "Unique constraint on (tenant_id, idempotency_key) in postings table. Orchestrator generates idempotency_key at tool schedule time, not after completion. HTTP 409 on duplicate returns original journal id. Message consumers dedupe with inbox pattern before posting."
  - q: "How should ledger events integrate with event sourcing?"
    a: "Treat each balanced journal as an immutable event appended to tenant stream. Materialized balance is projection updated in same transaction as journal insert—or rebuilt from stream on corruption. Snapshots every N events speed reads. Agent dashboards read projection; auditors replay stream."
---
A customer's credit balance dropped twice for one agent research session. The orchestrator retried a succeeded-but-slow tool call; the billing hook posted again because idempotency keyed on request id that changed between retries. Finance could not tie rows to tool logs—the table was a mutable `balance` column with no journal. Double-entry ledger events fix this: every agent spend is a balanced transaction with accounts, correlation ids, and insert-time idempotency—not a counter incremented from hope.

## Double-entry basics for agent platforms

Every posting touches at least two accounts with equal debits and credits:

| Account | Type | Agent use |
|---------|------|-----------|
| `user_credits_liability` | Liability | Prepaid credits owed to user |
| `revenue_agent_tools` | Revenue | Recognized tool usage |
| `cogs_llm_vendor` | Expense | OpenAI/Anthropic pass-through |
| `tax_payable` | Liability | VAT/GST collected |
| `accounts_receivable` | Asset | Postpaid invoices |

**Agent tool charge** (simplified):

```
Debit  user_credits_liability     $0.12
Credit revenue_agent_tools                 $0.10
Credit tax_payable                           $0.02
```

Sum debits = sum credits or the transaction rolls back.

## Schema: journals, lines, idempotency

```sql
CREATE TABLE ledger_journals (
  journal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  idempotency_key TEXT NOT NULL,
  correlation_id TEXT NOT NULL,  -- agent_run_id, tool_call_id
  posted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  metadata JSONB NOT NULL DEFAULT '{}',
  UNIQUE (tenant_id, idempotency_key)
);

CREATE TABLE ledger_lines (
  line_id BIGSERIAL PRIMARY KEY,
  journal_id UUID NOT NULL REFERENCES ledger_journals(journal_id),
  account_code TEXT NOT NULL,
  amount_minor BIGINT NOT NULL,  -- signed: debit positive, credit negative
  currency CHAR(3) NOT NULL,
  CHECK (amount_minor <> 0)
);

CREATE INDEX idx_ledger_lines_account ON ledger_lines(account_code, currency);
```

Balance check constraint via trigger or application transaction:

```python
def post_journal(db, tenant_id: str, idempotency_key: str, lines: list[Line]) -> str:
    assert sum(l.amount_minor for l in lines) == 0, "unbalanced journal"
    with db.transaction():
        journal_id = db.execute(
            """
            INSERT INTO ledger_journals (tenant_id, idempotency_key, correlation_id, metadata)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (tenant_id, idempotency_key) DO NOTHING
            RETURNING journal_id
            """,
            (tenant_id, idempotency_key, lines[0].correlation_id, lines[0].metadata),
        )
        if journal_id is None:
            return db.fetch_existing_journal(tenant_id, idempotency_key)
        for line in lines:
            db.insert_line(journal_id, line)
        db.update_balance_projection(tenant_id, lines)
        return journal_id
```

## Agent tool billing flow

Orchestrator lifecycle:

```
Plan tool → Reserve idempotency_key → Execute tool → On success emit PostUsage command
    → Ledger posts journal → Projection updates available credits → Agent continues
```

```typescript
interface ToolBillingEvent {
  tenantId: string;
  toolCallId: string;
  agentRunId: string;
  idempotencyKey: string;  // == toolCallId for billing
  amountMinor: number;
  currency: string;
  toolName: string;
}

async function onToolSuccess(event: ToolBillingEvent): Promise<void> {
  const lines = buildToolChargeLines(event);
  await ledger.postJournal({
    tenantId: event.tenantId,
    idempotencyKey: event.idempotencyKey,
    correlationId: event.toolCallId,
    lines,
    metadata: { tool: event.toolName, run: event.agentRunId },
  });
}
```

Never bill on tool **start**—only on confirmed success unless you implement separate hold/capture journals (authorize + capture pattern).

## Holds and capture for long-running tools

Long LLM batches may need **credit holds**:

```python
def authorize_hold(db, tenant_id: str, hold_key: str, amount_minor: int):
    # Debit user_available, credit user_holds (both liability sub-accounts)
    lines = [
        Line("user_credits_available", amount_minor, "USD"),
        Line("user_credits_held", -amount_minor, "USD"),
    ]
    post_journal(db, tenant_id, f"hold:{hold_key}", lines)

def capture_hold(db, tenant_id: str, hold_key: str, actual_minor: int, revenue_minor: int):
    # Release hold, post revenue for actual
    ...
```

Agent orchestrator releases unused hold on cancellation—prevents overspend mid-run.

## Event sourcing integration

Append journal to tenant event stream:

```python
@dataclass
class JournalPosted:
  journal_id: str
  tenant_id: str
  lines: list[Line]
  posted_at: datetime

def append_and_project(store, event: JournalPosted):
    with store.transaction():
        store.append_stream(f"ledger:{event.tenant_id}", event)
        store.upsert_balance_snapshot(event.tenant_id, event.lines)
```

Rebuild projection from stream after logic bugs:

```python
def rebuild_balance(tenant_id: str) -> int:
    balance = 0
    for event in store.read_stream(f"ledger:{tenant_id}"):
        if isinstance(event, JournalPosted):
            balance += sum(
                l.amount_minor for l in event.lines
                if l.account_code == "user_credits_available"
            )
    return balance
```

Compare to snapshot nightly—drift triggers pager.

## Multi-currency and FX

Agent tools may bill USD while user wallet is EUR:

```sql
CREATE TABLE ledger_lines (
  ...
  amount_minor BIGINT NOT NULL,
  currency CHAR(3) NOT NULL,
  fx_rate NUMERIC(18, 8),  -- to tenant reporting currency at post time
  reporting_amount_minor BIGINT
);
```

Store FX rate on post from internal cache with source timestamp—never re-fetch historical rate on replay.

## Reconciliation jobs

Batch reconcilers compare ledger to external systems:

| Reconciler | Frequency | Match key |
|------------|-----------|-----------|
| Stripe payouts | Daily | journal metadata.stripe_invoice |
| OpenAI usage export | Daily | vendor_request_id in metadata |
| Internal agent logs | Hourly | tool_call_id |

```python
def reconcile_vendor_usage(vendor_rows, ledger_rows):
    vendor_by_id = {r["request_id"]: r for r in vendor_rows}
    ledger_by_id = {r["metadata"]["vendor_request_id"]: r for r in ledger_rows}
    missing_in_ledger = vendor_by_id.keys() - ledger_by_id.keys()
    missing_in_vendor = ledger_by_id.keys() - vendor_by_id.keys()
    return ReconciliationReport(missing_in_ledger, missing_in_vendor)
```

Unresolved mismatches open finance tickets—agents do not auto-adjust balances.

## Read models for agents

Agents querying "how much credit left?" hit **projection**, not stream scan:

```sql
CREATE TABLE credit_balances (
  tenant_id UUID PRIMARY KEY,
  available_minor BIGINT NOT NULL,
  held_minor BIGINT NOT NULL,
  currency CHAR(3) NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);
```

Expose read API with versioning:

```python
def get_balance(tenant_id: str) -> dict:
    row = db.fetchone("SELECT * FROM credit_balances WHERE tenant_id = %s", tenant_id)
    return {
        "available": row.available_minor / 100,
        "held": row.held_minor / 100,
        "currency": row.currency,
        "as_of": row.updated_at.isoformat(),
    }
```

Agent prompts include `as_of` so users know staleness during active runs.

## Compliance and audit

- Journals are **append-only**—corrections via reversing entries, never UPDATE on lines.
- Analyst role can query full trail by `correlation_id` linking to agent run logs.
- PCI scope: do not store PAN in journal metadata; token references only.

```python
def reverse_journal(db, tenant_id: str, original_journal_id: str, reason: str):
    orig = db.fetch_lines(original_journal_id)
    reversal_lines = [Line(l.account_code, -l.amount_minor, l.currency) for l in orig]
    post_journal(
        db, tenant_id,
        idempotency_key=f"reversal:{original_journal_id}",
        lines=reversal_lines,
        metadata={"reverses": original_journal_id, "reason": reason},
    )
```

## Observability

Metrics:

- `ledger_postings_total{result}` — success, idempotent_duplicate, unbalanced_reject
- `ledger_posting_latency_seconds`
- `ledger_reconciliation_drift_minor{currency}`
- `ledger_balance_projection_lag_seconds`

Alert on unbalanced reject > 0 (should never happen) and reconciliation drift above materiality threshold.

## Anti-patterns

- **Mutable balance column** without journals—cannot audit agent charges.
- **Idempotency key from HTTP layer only**—retries change keys.
- **Billing on tool invocation start**—failed tools should not charge.
- **Single account "usage"**—no double-entry, no finance export.
- **Recomputing FX on replay**—historical reports drift.

## The takeaway

Agent platforms that spend user credits or bill postpaid need double-entry ledger events: balanced journals, idempotent posting keyed to tool_call_id, projections for fast reads, and reconciliation to vendor exports. Orchestrators emit posting commands after tool success; storage enforces balance at insert. When retries happen—and they will—duplicate idempotency keys return the original journal instead of charging twice.

## FAQ

### Why use double-entry for agent usage billing instead of a simple usage counter?

Counters lose auditability—you cannot explain why balance changed or reproduce state after a bug. Double-entry journals record every debit and credit with accounts, amounts, and correlation ids. Finance reconciles to bank and vendor invoices; support traces a user's credit drop to specific agent tool calls. Imbalanced journals fail at insert time.

### How do agent tool calls map to ledger postings?

Each billable tool invocation emits a posting command with idempotency key (tool_call_id), debit user credit liability, credit revenue or COGS expense account, optional tax lines. Never post directly from LLM output—only from orchestrator after tool success confirmed. Failed tools produce no posting; retries reuse the same idempotency key.

### What idempotency strategy prevents duplicate charges on agent retries?

Unique constraint on (tenant_id, idempotency_key) in postings table. Orchestrator generates idempotency_key at tool schedule time, not after completion. HTTP 409 on duplicate returns original journal id. Message consumers dedupe with inbox pattern before posting.

### How should ledger events integrate with event sourcing?

Treat each balanced journal as an immutable event appended to tenant stream. Materialized balance is projection updated in same transaction as journal insert—or rebuilt from stream on corruption. Snapshots every N events speed reads. Agent dashboards read projection; auditors replay stream.

## Resources

- [martinfowler.com/eaaDev/EventSourcing.html](https://martinfowler.com/eaaDev/EventSourcing.html) — Event sourcing (Martin Fowler)
- [www.accountingcoach.com/debits-and-credits/explanation](https://www.accountingcoach.com/debits-and-credits/explanation) — Debits and credits primer
- [stripe.com/docs/billing/subscriptions/usage-based](https://stripe.com/docs/billing/subscriptions/usage-based) — Stripe usage-based billing
- [docs.aws.amazon.com/eventbridge/latest/userguide/eb-idempotency.html](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-idempotency.html) — Idempotent event consumption patterns
- [github.com/eventstore/eventstore](https://github.com/eventstore/eventstore) — EventStoreDB
