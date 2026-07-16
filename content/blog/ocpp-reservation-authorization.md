---
title: "Reservations and Authorization in OCPP"
slug: "ocpp-reservation-authorization"
description: "Implement OCPP reservations and authorization: ReserveNow, ID tag validation, local auth lists, parent ID tags, and handling concurrent access."
datePublished: "2025-11-05"
dateModified: "2025-11-05"
tags: ["IoT", "EV Charging", "OCPP", "Security"]
keywords: "OCPP reservation, ReserveNow OCPP, ID tag authorization, OCPP authorization, local auth list, EV charging access control, parent ID tag OCPP"
faq:
  - q: "How does an OCPP reservation work?"
    a: "The CSMS sends ReserveNow with an ID tag, connector ID, and expiry time. The charger holds that connector for the tagged user until the reservation expires or the user starts charging. Other users cannot start a session on the reserved connector."
  - q: "What happens when an unauthorized ID tag is presented?"
    a: "The charger sends Authorize to the CSMS (if online) or checks the local auth list (if offline). The response is Accepted, Blocked, Expired, or Invalid. Only Accepted tags can start a transaction. Blocked tags are explicitly denied; Invalid means the tag is unknown."
  - q: "What is a parent ID tag?"
    a: "A parent ID tag groups multiple child tags under one billing account. When a child tag authorizes, the CSMS returns the parent ID tag in the Authorize response. The transaction is billed to the parent account. Useful for fleet cards where each driver has an individual RFID but one company pays."
---

A driver reserves a charger for 6 PM, arrives at 6:05, and finds another vehicle charging on "their" connector. The reservation expired at 6:00 because the CSMS set a 30-minute window and the driver's meeting ran long. Reservations and authorization are the access control layer of OCPP—who can charge, on which connector, and for how long. Get authorization wrong and you bill the wrong account. Get reservations wrong and drivers stop trusting your network.

## Authorization flow

```
User presents ID tag (RFID, app, credit card)
  → Charger sends Authorize(idTag) to CSMS
  → CSMS responds: Accepted / Blocked / Expired / Invalid
  → If Accepted: StartTransaction
  → If not: reject, display reason
```

**Authorize request/response:**

```json
// Request
{ "idTag": "RFID-0042-A" }

// Response
{
  "idTagInfo": {
    "status": "Accepted",
    "expiryDate": "2026-06-01T00:00:00Z",
    "parentIdTag": "FLEET-ACME-CORP"
  }
}
```

| Status | Meaning | User message |
|--------|---------|-------------|
| `Accepted` | Authorized to charge | "Starting session" |
| `Blocked` | Explicitly denied | "Card blocked—contact support" |
| `Expired` | Tag validity ended | "Card expired" |
| `Invalid` | Unknown tag | "Card not recognized" |
| `ConcurrentTx` | Already charging elsewhere | "Active session on another charger" |

## Local authorization list

For offline operation and reduced latency, cache authorized tags:

```json
{
  "listVersion": 15,
  "localAuthorizationList": [
    {
      "idTagInfo": {
        "status": "Accepted",
        "expiryDate": "2026-01-01T00:00:00Z",
        "parentIdTag": "FLEET-ACME"
      },
      "idTag": "RFID-0042-A"
    }
  ]
}
```

**CSMS updates via SendLocalList:**

```json
{
  "listVersion": 16,
  "updateType": "Differential",
  "localAuthorizationList": [
    { "idTag": "RFID-0099-B", "idTagInfo": { "status": "Accepted" } }
  ]
}
```

`Differential` adds/updates entries. `Full` replaces the entire list. Increment `listVersion` on every update.

## Reservations

**CSMS reserves a connector:**

```json
{
  "connectorId": 2,
  "expiryDate": "2025-11-05T18:30:00Z",
  "idTag": "RFID-0042-A",
  "reservationId": 101
}
```

**Charger response:**

```json
{ "status": "Accepted" }
// or: "Faulted", "Occupied", "Rejected", "Unavailable"
```

While reserved:
- Connector status shows `Reserved`.
- Only the matching ID tag can start a transaction.
- Other tags are rejected even if otherwise authorized.
- Reservation auto-cancels at `expiryDate`.

**Cancel reservation:**

```json
{ "reservationId": 101 }
```

## Parent ID tag billing

```python
def process_authorization(id_tag: str, auth_response: dict) -> BillingAccount:
    parent = auth_response.get("parentIdTag")
    billing_tag = parent if parent else id_tag

    account = db.get_account(billing_tag)
    if not account:
        raise BillingError(f"No account for {billing_tag}")

    if account.balance <= 0 and account.payment_method == "prepaid":
        return reject("Insufficient balance")

    return account
```

Fleet scenario: 50 drivers, each with `RFID-XXXX` child tags under `FLEET-ACME` parent. All sessions bill to the fleet account.

## Concurrent transaction handling

Prevent one user from occupying multiple connectors:

```python
def check_concurrent(id_tag: str, csms) -> bool:
    active = csms.get_active_transactions(id_tag)
    if active:
        return False  # ConcurrentTx
    return True
```

Configure per account: fleet accounts may allow 2 concurrent sessions; individual users get 1.

## Authorization cache on charger

OCPP 1.6 supports `LocalAuthListEnabled` and `AuthorizationCacheEnabled`:

```
Authorize(idTag) → check cache (TTL: LocalAuthorizeOfflineParam)
                 → check local list
                 → send to CSMS (if online)
                 → cache response
```

Cache TTL of 300 seconds reduces CSMS load. Clear cache entry when CSMS sends `ClearCache`.

## Reservation UX considerations

- **Expiry buffer:** Set reservation 15 minutes past the user's requested time.
- **Grace period:** Allow 5 minutes after expiry before releasing to others.
- **Notification:** Push notification 10 minutes before expiry via the mobile app (outside OCPP).
- **No-show tracking:** After 3 no-shows, require immediate arrival or shorten reservation windows.

## OCPP 2.0.1 authorization improvements

OCPP 2.0.1 replaces flat authorization with structured IdToken types:

```json
{
  "idToken": {
    "idToken": "RFID-ABC123",
    "type": "ISO14443"
  },
  "certificate": "base64-ocsp-response"
}
```

Supported IdToken types: `Central`, `eMAID` (ISO 15118 Plug & Charge), `ISO14443`, `ISO15693`, `KeyCode`, `Local`, `NoAuthorization`. Each type has different validation rules — eMAID requires certificate chain validation against V2G root CA.

Plug & Charge (ISO 15118) authorization flow:

```
EV presents eMAID → charger validates certificate → CSMS Authorize(eMAID)
→ contract certificate verified → charging starts without RFID tap
```

## Offline authorization fallback

When CSMS is unreachable, chargers must decide locally:

```
Authorize(idTag):
  1. Check local auth list (pre-synced whitelist)
  2. Check authorization cache (recent successful auths)
  3. If AllowOfflineTxForUnknownIdEnabled → accept unknown tags
  4. Else → reject with Blocked status
```

Configure `LocalAuthListMaxLength` and sync frequency based on expected offline duration. Fleet depots with reliable connectivity can use shorter cache TTL; highway stations need longer offline tolerance.

## Reservation conflict resolution

Multiple reservation scenarios need explicit handling:

| Scenario | Resolution |
|---|---|
| User arrives early | Allow charging if connector free; reservation still valid |
| User arrives late (within grace) | Honor reservation; shorten session if needed |
| Connector occupied at arrival | Queue or redirect to alternate connector |
| CSMS offline during reservation window | Local list must include reservation idTags |
| Double reservation same connector | CSMS rejects second ReserveNow |

Log all reservation state transitions — disputes about no-shows require audit trail.

## Failure modes

- **Cache stale after account suspension** — revoked user charges offline
- **Concurrent session not checked** — double billing on same idTag
- **Reservation expiry not enforced locally** — connector blocked after user no-show
- **Plug & Charge cert expired** — authorization fails silently; need OCSP check
- **Local auth list not synced** — new subscribers can't charge offline

## Production checklist

- Authorization cache TTL configured per deployment type
- Local auth list synced on subscription change
- Concurrent session check before Authorize response
- Reservation grace period and no-show policy documented
- Plug & Charge certificate validation with OCSP
- Offline authorization policy explicit (allow vs deny unknown tags)

## Common production mistakes

Teams get ocpp reservation authorization wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of ocpp reservation authorization fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [OCPP 1.6 Authorization](https://www.openchargealliance.org/protocols/ocpp-protocols/ocpp-1-6/) — Authorize and Local Auth List
- [OCPP 1.6 Reservations](https://www.openchargealliance.org/protocols/ocpp-protocols/ocpp-1-6/) — ReserveNow and CancelReservation
- [OCPP 2.0.1 Authorization](https://www.openchargealliance.org/protocols/ocpp-protocols/ocpp-2-0-1/) — updated auth flows
- [ISO 14443 RFID standard](https://www.iso.org/standard/73585.html) — contactless card protocol
- [OCPI tokens module](https://evroaming.org/ocpi-downloads/) — cross-network authorization
