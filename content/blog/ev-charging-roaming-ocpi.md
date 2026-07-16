---
title: "EV Roaming with OCPI"
slug: "ev-charging-roaming-ocpi"
description: "Implement OCPI for EV roaming: roles, modules, token authorization, session sync, CDR settlement, and production pitfalls for CPOs and eMSPs."
datePublished: "2026-01-24"
dateModified: "2026-01-24"
tags: ["IoT", "EV Charging", "OCPI", "Integration"]
keywords: "OCPI EV roaming, Open Charge Point Interface, CPO eMSP integration, OCPI CDR, token authorization OCPI, EV roaming hub, OCPI 2.2.1 modules"
faq:
  - q: "What roles exist in OCPI?"
    a: "Common roles: CPO (Charge Point Operator runs chargers), eMSP (e-Mobility Service Provider sells to drivers), Hub (routes between networks), NAP (national access point in some regions), and SCSP (smart charging). A company can hold multiple roles. Roaming connects CPO locations to eMSP tokens via bilateral or hub agreements."
  - q: "How does OCPI authorize a charging session?"
    a: "CPO calls eMSP POST /tokens/{uid}/authorize (or realtime auth) with token UID from RFID/app. eMSP responds allowed/denied with authorization reference. Session starts via OCPP on charger; CPO pushes session updates; on stop, CPO sends CDR to eMSP for billing."
  - q: "What is the difference between OCPI and OCPP?"
    a: "OCPP connects charge point hardware to CPO backend (charger management). OCPI connects CPO backend to eMSP backend (roaming/commerce). You need both in public networks: OCPP for physical control, OCPI for cross-network driver authorization and settlement."
---

Your charging network works flawlessly for subscribers — but a visiting driver with a competing app sees "unknown RFID" because nobody implemented OCPI token routing between your CPO and their eMSP. Roaming is the B2B layer that makes public charging feel universal while money and liability flow correctly behind the scenes. OCPI (Open Charge Point Interface) standardizes how locations, tariffs, live sessions, and charge detail records sync between operators. Getting it wrong means authorized sessions that never settle, duplicate CDRs, or drivers blocked at peak travel weekends.

## OCPI module map

| Module | Purpose |
|--------|---------|
| credentials | Registration, endpoint discovery, version handshake |
| locations | EVSE metadata, connectors, opening hours, geo |
| tariffs | Price components for transparency |
| tokens | RFID/app token whitelist sync |
| sessions | Active session state mirroring |
| cdrs | Final billable charge detail records |
| commands | Remote start/stop (optional) |
| chargingprofiles | Smart charging (advanced) |

Version negotiation starts at `/versions` → pick `2.2.1` → exchange `credentials` tokens for authenticated calls.

## Roaming topology

```
Driver (eMSP App) ──► eMSP platform
                           │
                      OCPI (Hub or direct)
                           │
                      CPO platform ── OCPP ──► Charger
```

**Hub** (Gireve, Hubject, e-clearing) reduces N×M bilateral integrations — one OCPI connection to hub, many roaming partners.

Direct bilateral common for strategic partners with custom SLAs.

## Authorization flow

```http
POST /ocpi/2.2.1/tokens/DE-ABC-12345678-9/authorize
Authorization: Token CPO-credentials-token
{
  "location_id": "LOC-001",
  "evse_uids": ["EVSE-3"],
  "connector_id": "1"
}
```

Response:

```json
{
  "data": {
    "allowed": "ALLOWED",
    "authorization_reference": "auth-ref-9921",
    "info": { "language": "en", "text": "OK" }
  },
  "status_code": 1000
}
```

CPO stores `authorization_reference` on OCPP StartTransaction. Real-time auth for Plug & Charge maps PCID/EMAID to token record.

Deny reasons must propagate to charger display where OCPP supports it.

## Sessions and CDRs

During charging, CPO pushes session PATCH:

```json
{
  "id": "sess-441",
  "kwh": 18.4,
  "status": "ACTIVE",
  "start_date_time": "2026-01-24T14:02:00Z",
  "cdr_token": { "uid": "DE-ABC-12345678-9", "type": "RFID" },
  "auth_method": "AUTH_REQUEST"
}
```

On completion, **CDR** is immutable financial record:

```json
{
  "id": "cdr-441",
  "total_cost": { "excl_vat": 12.50, "incl_vat": 14.88, "currency": "EUR" },
  "total_energy": 18.4,
  "tariffs": [{ "id": "T1", "currency": "EUR", "elements": [...] }],
  "signed_data": { "encoding_method": "OCMF", "public_key": "..." }
}
```

eMSP bills driver; clearing settles CPO↔eMSP per contract. Idempotency keys on CDR POST prevent double payment on retries.

## Locations and tariffs sync

eMSP apps display CPO locations from OCPI `GET /locations` delta sync (`date_from`, `date_to`). Stale maps cause "station not found" rage.

Tariff complexity (idle fees, time-of-use) must match payment engine — OCPI tariff IDs linked to internal tariff engine version.

Geo indexing for "nearest available" pulls from synced location objects — include `STATUS` updates via push or frequent poll.

## Production pitfalls

- **Clock skew** — ISO8601 UTC everywhere; session ordering breaks across zones
- **Partial sessions** — define CDR rules for failed stops under 1 kWh
- **Token whitelist lag** — new app subscribers need realtime auth if batch sync hourly
- **VAT and currency** — roaming cross-border needs explicit exchange in clearing, not guessed
- **Rate limits** — hub partners throttle; backoff with exponential retry

Monitor: auth deny rate, CDR reject rate, session stuck without CDR > 24h.

## Testing

- OCPI compliance tools from EV Roaming Foundation
- Simulators pairing mock eMSP + CPO
- Contract tests on golden JSON fixtures in CI

Roaming is revenue infrastructure — treat OCPI adapters as critical path, not partner integration side project.

## OCPI module architecture

Separate OCPI concerns into modules matching the spec:

```
ocpi/
├── credentials/     # Token exchange, version negotiation
├── locations/       # Station sync, status updates
├── sessions/        # Real-time session tracking
├── cdr/             # Charge detail records (billing)
├── tariffs/         # Pricing sync
└── tokens/          # Authorization whitelist
```

Each module has its own sync schedule and error handling:

| Module | Sync frequency | Failure impact |
|---|---|---|
| Locations | Every 15 min | Stale map, user frustration |
| Tokens | Real-time push | Auth denied at station |
| Sessions | Real-time push | Billing delay |
| CDR | On session end | Revenue loss if lost |
| Tariffs | Daily | Wrong price displayed |

CDR module is highest priority — lost CDRs mean lost revenue with no recovery path.

## Hub vs peer-to-peer roaming

**Peer-to-peer:** eMSP connects directly to each CPO's OCPI endpoint. Simple for few partners; N×M connection matrix at scale.

**Hub (Gireve, e-clearing.net):** Single connection to hub; hub routes to all connected CPOs/eMSPs. Simplifies integration but adds hub fees and single point of dependency.

```
eMSP ──→ Hub ←── CPO_A
              ←── CPO_B
              ←── CPO_C
```

Start peer-to-peer for first 2–3 partners to learn OCPI. Move to hub when partner count exceeds 10.

## Reconciliation and clearing

CDRs flow: CPO → eMSP (via OCPI) → clearing house → settlement:

```sql
-- Reconciliation: match CDRs to sessions
SELECT c.cdr_id, s.session_id, c.total_cost, s.authorized_amount
FROM cdrs c
JOIN sessions s ON c.session_id = s.session_id
WHERE c.total_cost != s.authorized_amount  -- discrepancies
   OR c.status = 'pending' AND c.created_at < NOW() - INTERVAL '24 hours';
```

Alert on CDRs pending >24 hours. Discrepancies between authorized amount and CDR total need manual review before clearing.

## Failure modes

- **Token whitelist lag** — new subscriber can't charge for hours
- **CDR lost on network retry** — idempotency key missing; double or zero billing
- **Clock skew across partners** — session ordering breaks; use UTC everywhere
- **Stale location data** — driver arrives at offline station shown as available
- **VAT miscalculation on cross-border** — clearing disputes; explicit exchange rates required

## Production checklist

- CDR idempotency keys on all POST requests
- UTC timestamps everywhere (ISO8601)
- Location sync every 15 minutes minimum
- Token whitelist push on subscription change (not batch hourly)
- CDR reconciliation job alerting on pending >24h
- OCPI contract tests in CI with golden JSON fixtures

Version OCPI modules explicitly in partner contracts — roaming failures at 2 AM trace to unsupported endpoint versions, not network issues.

## Resources

- [EV Roaming Foundation — OCPI downloads](https://evroaming.org/ocpi-downloads/)
- [OCPI 2.2.1 specification PDF](https://github.com/ocpi/ocpi)
- [Gireve roaming hub](https://www.gireve.com/)
- [Open Charge Alliance — OCPP complement](https://www.openchargealliance.org/)
- [e-clearing.net settlement services](https://www.e-clearing.net/)
