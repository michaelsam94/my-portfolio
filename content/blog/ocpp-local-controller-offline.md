---
title: "Offline Operation with a Local Controller"
slug: "ocpp-local-controller-offline"
description: "Design EV charging sites for offline operation with local controllers: authorization caching, transaction queuing, and CSMS reconnection sync."
datePublished: "2025-10-30"
dateModified: "2025-10-30"
tags: ["IoT", "EV Charging", "OCPP", "Architecture"]
keywords: "OCPP offline operation, local controller EV charging, charging station offline mode, OCPP transaction queue, edge controller EV, CSMS reconnection"
faq:
  - q: "What happens when an EV charger loses connection to the CSMS?"
    a: "Behavior depends on configuration. Without a local controller, most chargers reject new authorizations when offline. With a local controller caching authorized ID tags and queuing transactions, charging continues and data syncs when connectivity returns."
  - q: "How long can a charger operate offline?"
    a: "Indefinitely for basic authorize-and-charge if the local controller has cached authorization lists and stores transactions locally. Practical limits depend on storage capacity—plan for 30 days of queued transactions and periodic authorization list updates when online."
  - q: "What is the difference between a local controller and a CSMS?"
    a: "The CSMS is the cloud central system managing the entire fleet. A local controller is an edge device at the charging site that handles authorization, load balancing, and transaction logging when the WAN link to the CSMS is down."
---

The charging site is in a parking garage three levels underground. Cellular signal drops for hours at a time. Without offline capability, every ID tag scan returns "authorization failed" and drivers leave angry. A local controller at the site maintains an authorization cache, runs load balancing across chargers, and queues transactions for upload when the CSMS connection returns. The cloud is the source of truth; the edge is the operational fallback.

## Architecture

```
                    ┌─────────────┐
                    │    CSMS     │ (cloud)
                    └──────┬──────┘
                           │ WAN (may fail)
                    ┌──────▼──────┐
                    │   Local     │
                    │ Controller  │ (edge, on-site)
                    └──┬───┬───┬──┘
                       │   │   │
                    ┌──▼┐┌▼┐ ┌▼──┐
                    │CP1││CP2││CP3│  (charge points)
                    └───┘└──┘ └───┘
```

The local controller speaks OCPP to the CSMS (upstream) and OCPP or a proprietary protocol to chargers (downstream).

## Offline authorization

Cache authorized ID tags locally:

```json
{
  "localAuthList": {
    "version": 42,
    "entries": [
      { "idTag": "RFID-001", "status": "Accepted", "expiry": "2026-01-01" },
      { "idTag": "RFID-002", "status": "Accepted", "expiry": "2026-01-01" }
    ]
  }
}
```

**Online:** CSMS sends `SendLocalList` to update the cache.
**Offline:** Controller checks local cache. Accept if tag exists and not expired.

```python
def authorize(id_tag: str, local_list: LocalAuthList) -> str:
    entry = local_list.find(id_tag)
    if entry and entry.status == "Accepted":
        if entry.expiry and entry.expiry < datetime.now():
            return "Expired"
        return "Accepted"
    if local_list.offline_unknown_policy == "allow":
        return "Accepted"  # whitelist mode: allow unknown, flag for review
    return "Invalid"
```

Configure `offline_unknown_policy` per site. Fleet operators typically use `deny`; workplace chargers with known users may use `allow`.

## Transaction queuing

When offline, store transactions locally:

```python
@dataclass
class QueuedTransaction:
    transaction_id: int
    connector_id: int
    id_tag: str
    start_time: datetime
    meter_start: float
    stop_time: datetime | None = None
    meter_stop: float | None = None
    status: str = "active"

class TransactionStore:
    def __init__(self, db_path: str):
        self.db = sqlite3.connect(db_path)

    def start_transaction(self, tx: QueuedTransaction):
        self.db.execute(
            "INSERT INTO transactions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (tx.transaction_id, tx.connector_id, tx.id_tag,
             tx.start_time.isoformat(), tx.meter_start,
             None, None, "active"),
        )

    def get_pending_sync(self) -> list[QueuedTransaction]:
        return self.db.execute(
            "SELECT * FROM transactions WHERE synced = 0"
        ).fetchall()
```

## Reconnection sync

When the CSMS connection restores:

```
1. Send queued StartTransaction messages (oldest first)
2. Send queued StopTransaction messages
3. Send queued MeterValues
4. Request updated LocalAuthList (SendLocalList)
5. Resume normal real-time operation
```

```python
async def sync_on_reconnect(controller, csms):
    pending = controller.transaction_store.get_pending_sync()
    for tx in pending:
        if tx.status == "active" and tx.stop_time:
            await csms.send_start_transaction(tx)
            await csms.send_stop_transaction(tx)
            controller.transaction_store.mark_synced(tx.transaction_id)
        elif tx.status == "active":
            await csms.send_start_transaction(tx)
            # leave open — still charging

    await csms.request_local_list_update()
    controller.set_mode("online")
```

Send transactions in chronological order. The CSMS must accept backdated transactions.

## Local load balancing

The local controller runs load balancing without CSMS input:

```python
def offline_load_balance(chargers: list[Charger], site_max_amps: float):
    active = [c for c in chargers if c.has_active_session]
    if not active:
        return

    share = site_max_amps / len(active)
    for charger in active:
        charger.set_current_limit(min(share, charger.max_amps))
```

Store the site power budget in controller configuration. Update when CSMS is reachable.

## Hardware requirements

| Component | Specification |
|-----------|--------------|
| Local controller | Industrial PC or ARM SBC (Raspberry Pi 4+ class) |
| Storage | 32 GB flash for transaction queue and auth cache |
| Network | Ethernet to chargers; LTE/DSL WAN to CSMS |
| UPS | Controller and network gear on battery backup |
| Clock | NTP with RTC fallback for accurate timestamps |

## Conflict resolution

When synced transactions conflict with CSMS state:

- **Duplicate transaction ID:** CSMS rejects; controller increments local ID range on next online sync.
- **Overlapping sessions on same connector:** CSMS wins; controller logs discrepancy for ops review.
- **Meter value gaps:** Interpolate or flag as estimated.

Define a `sync_status` field on each transaction: `pending`, `synced`, `conflict`.

## Testing offline scenarios

Don't ship offline mode without systematic tests:

1. **CSMS disconnect mid-session** — transaction completes locally, syncs on reconnect
2. **Extended outage (72h)** — queue doesn't exhaust disk, IDs don't collide
3. **Partial sync failure** — HTTP 500 on batch 3 of 5; retry without duplicating batches 1–2
4. **Clock rollback** — NTP correction doesn't create negative-duration sessions
5. **Auth list expiry** — cached RFID still valid per local list TTL policy

Use chaos testing: iptables DROP to CSMS IP during automated test suite.

## Security in offline mode

Local auth list is a cache of CSMS decisions — protect it:

- Encrypt SQLite database at rest on controller storage
- Sign local list updates when received online; reject tampered lists
- Rate-limit StartTransaction from same idTag to prevent brute force
- Log all offline authorizations for audit when CSMS returns

Compromised local controller could authorize unlimited charging — physical tamper detection and secure boot matter as much as network security.

## Capacity planning

Size offline queue for worst-case outage:

```
Transactions per day: 200
Avg transaction record size: 2 KB
Max offline days: 7
Queue storage: 200 × 2 KB × 7 = 2.8 MB (+ meter values ≈ 50 MB)
```

MeterValue sampling every 60s during 8-hour charge adds significant storage — tune sampling interval for offline mode vs online mode separately.

Pair with [OCPP security profiles and TLS](https://blog.michaelsam94.com/ocpp-security-profiles-tls/) for securing the sync channel when connectivity returns.

## Production checklist

- [ ] Offline queue sized for 7-day worst-case outage
- [ ] Chaos test: CSMS disconnect mid-transaction
- [ ] Local auth list encrypted at rest
- [ ] Sync batches idempotent with retry on partial failure
- [ ] `sync_status` tracked per transaction for ops visibility

Site power budgets should be configured locally with conservative defaults — when CSMS is unreachable, offline load balancing must assume the full site amperage envelope, not last-known CSMS limits.

## Resources

- [OCPP 1.6 Local Auth List Management](https://www.openchargealliance.org/protocols/ocpp-protocols/ocpp-1-6/) — SendLocalList specification
- [OCPP 2.0.1 Offline behavior](https://www.openchargealliance.org/protocols/ocpp-protocols/ocpp-2-0-1/) — offline transaction handling
- [Edge computing for IoT (LF Edge)](https://lfedge.org/) — edge architecture patterns
- [SQLite for embedded storage](https://www.sqlite.org/docs.html) — local transaction database
- [IEC 61851-1 EV charging safety](https://webstore.iec.ch/en/publication/6029) — hardware safety requirements
