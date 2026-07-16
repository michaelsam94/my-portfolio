---
title: "Reconciling Charging Sessions"
slug: "iot-charging-session-reconciliation"
description: "Reconcile EV charging sessions across OCPP, meter data, and billing: handling disconnects, duplicate events, idempotency, and audit trails."
datePublished: "2025-07-16"
dateModified: "2025-07-16"
tags: ["IoT", "Embedded", "Architecture", "Backend"]
keywords: "EV charging session reconciliation, OCPP billing, charging session idempotency, meter value reconciliation, EV charging platform"
faq:
  - q: "Why do charging sessions need reconciliation?"
    a: "A charging session generates data from multiple sources — OCPP StartTransaction/StopTransaction events, periodic MeterValues, the charger's internal meter, and the billing system. These can disagree due to network drops, duplicate messages, clock drift, or firmware bugs. Reconciliation ensures the billed amount matches the energy actually delivered."
  - q: "What happens when a StopTransaction is lost?"
    a: "The session stays open in the backend indefinitely. Reconciliation detects orphaned sessions (no StopTransaction after N hours, or charger reports Available with an open transaction) and closes them using the last known MeterValue or a charger query. The session must be marked as 'reconciled' not 'completed' for audit purposes."
  - q: "How do I prevent double-billing on OCPP retries?"
    a: "Use the OCPP transaction ID and idTag as idempotency keys. StartTransaction with the same connector and an active transaction should return the existing transaction ID, not create a new one. MeterValues are append-only — deduplicate by (transactionId, timestamp, measurand). StopTransaction is idempotent — processing it twice should not change the final amount."
---

A driver plugs in, charges for 45 minutes, unplugs, and gets billed for 90 minutes. Or gets billed twice. Or gets a $0 invoice because the StopTransaction never arrived and the session timed out with no meter data. These aren't edge cases — they're the normal failure modes of a system where the network drops, the charger reboots mid-session, and OCPP retries messages it already sent. Reconciliation is how you turn messy real-world events into correct invoices.

## Session lifecycle and data sources

A complete session produces events from three sources:

```
OCPP events:          MeterValues:           Billing:
StartTransaction      sampled every 60s       tariff calculation
MeterValues (periodic) connector meter        payment capture
StopTransaction       signed meter (OCMF)     invoice generation
StatusNotification    local display           refund/adjustment
```

Each source can fail independently. Reconciliation compares them.

## The session state machine

```
                    StartTransaction
    ┌─────────┐ ──────────────────────► ┌──────────┐
    │ PENDING │                         │  ACTIVE  │
    └─────────┘                         └────┬─────┘
                                             │
                              StopTransaction │ (or timeout/reconcile)
                                             ▼
                    ┌──────────────┐  ┌──────────────┐
                    │  RECONCILED  │◄─┤   CLOSING    │
                    └──────────────┘  └──────────────┘
```

States:
- **PENDING** — StartTransaction received, waiting for first MeterValue
- **ACTIVE** — charging in progress, meter values accumulating
- **CLOSING** — StopTransaction received, computing final amount
- **RECONCILED** — manually or automatically closed without a clean stop
- **COMPLETED** — billed and archived

Only `COMPLETED` sessions with a matching StopTransaction are "clean." Everything else went through reconciliation.

## Idempotency keys

OCPP messages can be retried. Every handler must be idempotent:

```python
def handle_start_transaction(charger_id: str, connector_id: int, id_tag: str, meter_start: int, timestamp: datetime):
    existing = db.sessions.find_active(charger_id, connector_id)
    if existing:
        return existing.transaction_id  # return existing, don't create duplicate

    return db.sessions.create(
        charger_id=charger_id,
        connector_id=connector_id,
        id_tag=id_tag,
        meter_start=meter_start,
        started_at=timestamp,
        status="ACTIVE",
    )
```

For MeterValues:

```python
def handle_meter_value(transaction_id: int, timestamp: datetime, value: float, measurand: str):
    key = (transaction_id, timestamp.isoformat(), measurand)
    if db.meter_readings.exists(key):
        return  # duplicate, skip silently

    db.meter_readings.insert(transaction_id, timestamp, value, measurand)
```

## Detecting orphaned sessions

A background job runs every 15 minutes:

```python
def reconcile_orphaned_sessions():
    orphans = db.sessions.find(
        status="ACTIVE",
        started_at__lt=now() - timedelta(hours=4),
    )

    for session in orphans:
        charger_status = ocpp_server.get_status(session.charger_id, session.connector_id)

        if charger_status == "Available":
            last_meter = db.meter_readings.latest(session.transaction_id)
            session.close(
                meter_stop=last_meter.value if last_meter else session.meter_start,
                stopped_at=last_meter.timestamp if last_meter else now(),
                status="RECONCILED",
                reason="orphan_no_stop_transaction",
            )
            billing.queue(session)
```

Rules for orphan detection:
- No StopTransaction after 4 hours → reconcile
- Charger reports Available with open transaction → reconcile immediately
- No MeterValues for 30 minutes during active session → alert, then reconcile

## Energy calculation

Billable energy = `meter_stop - meter_start` (in Wh, converted to kWh):

```python
def calculate_energy(session) -> Decimal:
    if session.meter_stop is not None and session.meter_start is not None:
        raw_wh = session.meter_stop - session.meter_start
    elif session.meter_readings:
        raw_wh = session.meter_readings[-1].value - session.meter_start
    else:
        raise InsufficientDataError(f"Session {session.id} has no meter data")

    if raw_wh < 0:
        log.warning("negative energy", session_id=session.id, raw_wh=raw_wh)
        raw_wh = 0  # meter rollover or data error

    return Decimal(raw_wh) / Decimal(1000)  # kWh
```

Apply tariff:

```python
def calculate_cost(energy_kwh: Decimal, tariff: Tariff, session_duration: timedelta) -> Decimal:
    if tariff.type == "per_kwh":
        return energy_kwh * tariff.rate
    elif tariff.type == "per_minute":
        return Decimal(session_duration.total_seconds() / 60) * tariff.rate
    elif tariff.type == "flat":
        return tariff.rate
```

## Audit trail

Every reconciliation action must be logged:

```json
{
  "session_id": "txn-48291",
  "action": "reconciled",
  "reason": "orphan_no_stop_transaction",
  "meter_start": 125000,
  "meter_stop": 147832,
  "energy_kwh": 22.832,
  "original_status": "ACTIVE",
  "charger_status_at_reconcile": "Available",
  "reconciled_at": "2025-07-16T14:30:00Z",
  "reconciled_by": "system:orphan-job"
}
```

Billing disputes will reference these records months later. Store them immutably.

## Multi-site reconciliation

Fleet operators running chargers across regions face timezone and tariff complexity:

```python
def reconcile_session(session, site_config):
    tz = ZoneInfo(site_config.timezone)
    local_start = session.started_at.astimezone(tz)
    tariff = get_tariff(site_config.tariff_id, local_start)

    energy = calculate_energy(session)
    cost = calculate_cost(energy, tariff, session.duration)

    session.finalize(energy_kwh=energy, cost=cost, currency=site_config.currency)
    return session
```

Always store UTC timestamps internally. Convert to local time only for tariff lookup and customer-facing invoices.

Always store UTC timestamps internally. Convert to local time only for tariff lookup and customer-facing invoices.

## Dispute handling

When a driver challenges an invoice:

1. Pull the full session timeline (all OCPP messages with timestamps)
2. Compare meter_start/meter_stop against periodic MeterValues — they should be consistent
3. Check if the session was RECONCILED (flag for manual review)
4. If charger supports OCMF/signed meter data, verify the cryptographic signature
5. Adjust or refund with a new audit entry explaining the correction

## Common production mistakes

Teams get charging session reconciliation wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

IoT deployments of charging session reconciliation fail in the field when firmware assumes stable Wi-Fi, OTA rollback is untested, and device certificates expire without automated renewal.

## Debugging and triage workflow

When charging session reconciliation misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [OCPP 1.6 Specification — Transaction handling](https://www.openchargealliance.org/protocols/ocpp-16/) — StartTransaction, StopTransaction, MeterValues
- [OCMF — Open Charge Metering Format](https://www.ocmf.de/) — signed meter data for billing disputes
- [How I Architected an EV Charging Platform](/blog/how-i-architected-an-ev-charging-platform) — full platform architecture walkthrough
- [OCPP 2.0.1 — Device model and transactions](https://www.openchargealliance.org/protocols/ocpp-201/) — next-gen transaction handling
