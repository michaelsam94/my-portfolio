---
title: "The OCPP Transaction Lifecycle"
slug: "ocpp-transaction-lifecycle"
description: "Follow the complete OCPP transaction lifecycle: authorization, StartTransaction, MeterValues, StopTransaction, and handling edge cases."
datePublished: "2025-11-11"
dateModified: "2026-07-17"
tags: ["IoT", "EV Charging", "OCPP", "Protocols"]
keywords: "OCPP transaction lifecycle, StartTransaction, StopTransaction, OCPP charging session, transaction handling OCPP, EV charging session flow"
faq:
  - q: "What triggers a StopTransaction in OCPP?"
    a: "A StopTransaction is sent when the user stops charging (RFID swipe, app command), the vehicle disconnects (cable unplugged), the charger detects a fault, a remote stop command arrives from the CSMS, or the charging profile limits are reached. Each cause has a different reason code."
  - q: "What happens if StartTransaction fails after authorization?"
    a: "The charger should not deliver power if StartTransaction is rejected or times out. If the CSMS is unreachable, the charger may start a local transaction (offline mode) and sync later. The transaction ID is assigned by the CSMS in the response—or locally in offline mode."
  - q: "Can one connector have multiple active transactions?"
    a: "No. One connector supports exactly one active transaction at a time. A new StartTransaction on an occupied connector is rejected. Transaction IDs are unique per charger, not globally."
---

A driver plugs in, the session starts, energy flows for 45 minutes, and the driver unplugs. Behind that simple interaction, the charger and CSMS exchange six or more OCPP messages tracking authorization, meter readings, and session state. A bug in any step—starting without authorization, missing the stop event, duplicate transaction IDs—creates billing errors or orphaned sessions that never close. The transaction lifecycle is the core state machine of OCPP.

## Complete lifecycle

```
1. Authorize(idTag)           → Accepted
2. StartTransaction           → transactionId assigned
3. MeterValues (periodic)     → energy, power samples
4. [charging occurs]
5. StopTransaction            → reason, final meter reading
6. CSMS processes billing
```

## Step 1: Authorization

```json
// Charger → CSMS
{ "idTag": "RFID-0042" }

// CSMS → Charger
{
  "idTagInfo": {
    "status": "Accepted",
    "parentIdTag": "FLEET-ACME"
  }
}
```

Authorization is optional in OCPP 1.6 (charger can start without it) but mandatory in practice for billing. OCPP 2.0.1 integrates authorization into the transaction request.

## Step 2: StartTransaction

```json
// Charger → CSMS
{
  "connectorId": 1,
  "idTag": "RFID-0042",
  "meterStart": 45230,
  "timestamp": "2025-11-11T08:15:00Z"
}

// CSMS → Charger
{
  "transactionId": 1042,
  "idTagInfo": { "status": "Accepted" }
}
```

The CSMS assigns `transactionId`—a monotonically increasing integer per charger. Store this ID for all subsequent MeterValues and the StopTransaction.

**Charger-side state:**

```python
class ConnectorState:
    IDLE = "idle"
    AUTHORIZED = "authorized"
    CHARGING = "charging"
    FINISHING = "finishing"

class Connector:
    def __init__(self, connector_id: int):
        self.id = connector_id
        self.state = ConnectorState.IDLE
        self.transaction_id: int | None = None
        self.meter_start: float = 0
```

## Step 3: MeterValues during charging

Sent every `MeterValueSampleInterval` seconds:

```json
{
  "connectorId": 1,
  "transactionId": 1042,
  "meterValue": [{
    "timestamp": "2025-11-11T08:16:00Z",
    "sampledValue": [
      { "value": "45238.5", "measurand": "Energy.Active.Import.Register", "unit": "Wh" },
      { "value": "7400", "measurand": "Power.Active.Import", "unit": "W" }
    ]
  }]
}
```

## Step 4: StopTransaction

```json
// Charger → CSMS
{
  "transactionId": 1042,
  "idTag": "RFID-0042",
  "meterStop": 45305,
  "timestamp": "2025-11-11T09:00:00Z",
  "reason": "Local"
}
```

| Reason | Trigger |
|--------|---------|
| `Local` | User stopped (RFID, button) |
| `Remote` | CSMS sent RemoteStopTransaction |
| `EVDisconnected` | Cable unplugged from vehicle |
| `EmergencyStop` | Emergency button pressed |
| `HardReset` / `SoftReset` | Charger reboot |
| `PowerLoss` | Grid power lost |
| `DeAuthorized` | ID tag blocked mid-session |

## Edge cases

**Power loss during session:**

```json
{
  "transactionId": 1042,
  "meterStop": 45280,
  "timestamp": "2025-11-11T08:45:00Z",
  "reason": "PowerLoss"
}
```

Charger sends StopTransaction on reboot if it can determine the final meter reading. If not, send with best available `meterStop` and flag as estimated.

**Remote stop:**

```json
// CSMS → Charger
{ "transactionId": 1042 }

// Charger stops power delivery, then sends:
{
  "transactionId": 1042,
  "meterStop": 45295,
  "reason": "Remote"
}
```

**Connector unavailable mid-session:**

If a fault occurs during charging (ground fault, over-temperature), the charger stops power and sends StopTransaction with `reason: "Other"` or a vendor-specific reason. Update connector status to `Faulted`.

**Offline start, online stop:**

```python
async def handle_stop_transaction(charger, stop_msg):
    if stop_msg.transaction_id in charger.local_transactions:
        # Started offline — CSMS may not know about this transaction
        local_tx = charger.local_transactions[stop_msg.transaction_id]
        await csms.send_start_transaction(local_tx)  # backfill
    await csms.send_stop_transaction(stop_msg)
```

## OCPP 2.0.1 changes

OCPP 2.0.1 uses `TransactionEvent` instead of separate Start/Stop messages:

```json
{
  "eventType": "Started",
  "timestamp": "2025-11-11T08:15:00Z",
  "triggerReason": "Authorized",
  "seqNo": 0,
  "transactionInfo": {
    "transactionId": "TX-1042",
    "chargingState": "EVConnected"
  },
  "idToken": { "idToken": "RFID-0042", "type": "ISO14443" },
  "meterValue": [{ "sampledValue": [{ "value": "45230", "measurand": "Energy.Active.Import.Register" }] }]
}
```

`eventType` progresses: `Started` → `Updated` (MeterValues) → `Ended`. One message type replaces three.

## CSMS transaction state machine

```python
class TransactionStatus(Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    ABORTED = "aborted"

def handle_start(csms, msg):
    tx = Transaction(
        id=msg.transaction_id,
        station_id=msg.station_id,
        connector_id=msg.connector_id,
        id_tag=msg.id_tag,
        meter_start=msg.meter_start,
        start_time=msg.timestamp,
        status=TransactionStatus.ACTIVE,
    )
    csms.db.insert(tx)

def handle_stop(csms, msg):
    tx = csms.db.get(msg.transaction_id)
    tx.meter_stop = msg.meter_stop
    tx.stop_time = msg.timestamp
    tx.stop_reason = msg.reason
    tx.energy_wh = msg.meter_stop - tx.meter_start
    tx.status = TransactionStatus.COMPLETED
    csms.db.update(tx)
    csms.billing.process(tx)
```

Alert on transactions in `ACTIVE` status for > 24 hours—likely a missing StopTransaction.

## Billing reconciliation

Energy delivered must match meter readings:

```python
def reconcile_transaction(tx: Transaction) -> ReconciliationResult:
    meter_delta = tx.meter_stop - tx.meter_start
    sampled_total = sum(mv.energy_wh for mv in tx.meter_values)
    if abs(meter_delta - sampled_total) > tolerance_wh:
        return ReconciliationResult.FLAGGED, "meter mismatch"
    return ReconciliationResult.OK, meter_delta
```

OCPP 1.6 sends MeterValues during session; OCPP 2.0.1 uses TransactionEvent with embedded meter data. Reconciliation rules differ — don't assume 1.6 StopTransaction meter_stop equals sum of intervals without validation.

## Offline and orphaned transactions

When charger loses CSMS connection mid-session:

1. Charger continues charging (local limit enforcement)
2. Stores StartTransaction locally
3. Sends StopTransaction on reconnect with backdated timestamp
4. CSMS must accept out-of-order events

```python
def handle_late_stop(msg):
    tx = db.get_or_create(msg.transaction_id)
    if tx.status == TransactionStatus.COMPLETED:
        return  # idempotent
    complete_transaction(tx, msg)
```

Pair with [OCPP local controller offline](https://blog.michaelsam94.com/ocpp-local-controller-offline/) for site-level transaction queueing during outages.

## IdTag authorization failures

| Reason | OCPP 1.6 | Action |
|--------|----------|--------|
| Invalid tag | StartTransaction rejected | Log attempt, notify fleet admin |
| Blocked tag | AuthorizationStatus=Blocked | Display message on charger |
| Expired contract | Invalid after date check | OCPI token validation first |

Pre-authorize via OCPI before OCPP StartTransaction when roaming — local auth list may be stale for roaming RFID tokens.

## Lifecycle bugs that survive code review

- **RemoteStart without matching Stop** — CSMS-initiated sessions need watchdog timers.
- **Duplicate StartTransaction on reconnect** — charger replays start; CSMS must idempotent-accept same `transactionId`.
- **MeterValues after Stop** — some firmware sends late samples; ignore for billing after `Ended` unless regulation requires full trace.

## TransactionEvent sequencing in OCPP 2.0.1

`TransactionEvent` carries `seqNo` — monotonic per transaction. CSMS must reject or buffer out-of-order events:

```python
def handle_transaction_event(tx, msg):
    if msg.seq_no != tx.expected_seq:
        buffer_out_of_order(tx, msg)
        return
    apply_event(tx, msg)
    tx.expected_seq += 1
    flush_buffered(tx)
```

Missing `Ended` events leave ghost sessions. Run a sweeper: if no `Updated` event for 24h and connector reports `Available`, auto-close with `reason: Timeout` and estimated `meterStop`.

## CDR export and OCPI session alignment

Internal transaction state must map cleanly to OCPI CDRs for roaming settlement:

| Internal field | OCPI CDR field |
|----------------|----------------|
| `meter_start/stop` (Wh) | `total_energy` (kWh) |
| `start/stop_time` | `start_date_time` / `end_date_time` |
| `id_tag` | `cdr_token` |
| `stop_reason` | `remark` / custom |

Normalize timezones to UTC at ingestion — roaming partners reject CDRs with ambiguous offsets.

## Reason code analytics

Aggregate `StopTransaction.reason` monthly — `EVDisconnected` spike may mean cable wear; `Remote` spike may mean demand-response bugs. OCPP 2.0.1 `triggerReason` on TransactionEvent offers finer grain than 1.6 reason enum.

## Idempotent stop handling

```python
def handle_stop(msg):
    tx = db.get(msg.transaction_id)
    if tx and tx.status == "completed":
        return Ack()  # duplicate stop after reconnect
    complete(tx, msg)
```

Duplicate stops are normal after WebSocket reconnect — billing must not double-close sessions.

## Remote start timeout handling

`RequestStartTransaction` without cable plugged within 60s should cancel — orphaned Preparing states block connector. UI on charger shows countdown; CSMS clears reservation automatically.

## SuspendedEV and power limit events

OCPP 2.0.1 `TransactionEvent` with `chargingState: SuspendedEV` during lifecycle — CSMS should not bill idle energy at full rate if tariff is time-based. Align billing engine with charging state transitions.
## MeterStart zero on new hardware

Factory reset chargers report `meterStart: 0` — billing must handle first session after install without negative energy edge case on botched migration import.
## Transaction id namespace per station

Document that transaction IDs are unique per charger, not global — CSMS databases need composite key `(station_id, transaction_id)` to avoid collision across fleet imports.

## Resources

- [OCPP 1.6 Transaction handling](https://www.openchargealliance.org/protocols/ocpp-protocols/ocpp-1-6/) — Start/Stop specification
- [OCPP 2.0.1 TransactionEvent](https://www.openchargealliance.org/protocols/ocpp-protocols/ocpp-2-0-1/) — unified event model
- [OCPP 1.6 status codes](https://www.openchargealliance.org/protocols/ocpp-protocols/ocpp-1-6/) — connector and transaction statuses
- [ISO 15118 plug and charge](https://www.iso.org/standard/55366.html) — automated authorization
- [OCPI sessions module](https://evroaming.org/ocpi-downloads/) — cross-operator session data
