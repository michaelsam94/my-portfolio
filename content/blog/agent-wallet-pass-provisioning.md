---
title: "Wallet Pass Provisioning from Agent Workflows"
slug: "agent-wallet-pass-provisioning"
description: "Issue Apple Wallet and Google Wallet passes via agent tools: boarding passes, event tickets, loyalty cards — signing certificates, pass updates, and PCI-adjacent data boundaries."
datePublished: "2025-05-17"
dateModified: "2026-07-17"
tags: ["AI Agents", "Mobile", "Wallet", "Integration"]
keywords: "wallet pass provisioning agent, Apple Wallet API agent tool, Google Wallet pass agent tool, PKPass generation"
faq:
  - q: "Should agents generate PKPass files directly or call a wallet service?"
    a: "Call a dedicated wallet microservice with narrow tools — never embed Apple signing certificates in the agent runtime. Agents pass structured intent (flight, seat, gate); the service signs, stores pass serial, and returns a add-to-wallet URL."
  - q: "How do pass updates work when an agent changes booking details?"
    a: "Apple Push Notification service (APNs) with passTypeIdentifier triggers device fetch from your webServiceURL. Google Wallet uses PATCH on pass object JWT. Agent tool `update_pass` must be idempotent on serial number."
  - q: "What data must stay out of LLM context for wallet flows?"
    a: "Signing keys, team identifiers, full barcode payloads with PII, payment tokens. Agent context gets: pass_type, serial, last4 confirmation, add_link_token — not PEM files or HMAC secrets."
  - q: "Are wallet passes in PCI scope?"
    a: "Passes displaying payment barcodes can be PCI-adjacent — treat barcode value as sensitive, log redaction, short TTL on links. Payment card provisioning to Apple Pay is full PCI; event tickets usually are not."
---

Travel agents that rebook flights need to push an updated boarding pass before the user reaches TSA — not email a PDF. **Wallet pass provisioning** from agent workflows means your orchestrator calls signing infrastructure, mints Apple `PKPass` bundles or Google Wallet objects, and returns an Add to Wallet link — while the LLM never touches private keys or raw barcode secrets.

## Architecture boundary

```
User: "Move me to the 6pm flight"
         │
         ▼
   Agent orchestrator ──tool──► WalletPassService
         │                           │
         │                           ├── Apple Pass Type ID cert (HSM)
         │                           ├── Google service account
         │                           └── Pass registry DB
         ▼
   User message: "Updated — tap to add boarding pass"
         │
         └── HTTPS link / wallet deep link (short-lived token)
```

Agent tools are CRUD on **pass intents**, not cryptographic operations.

## Agent tool definitions

```yaml
tools:
  - name: create_boarding_pass
    parameters:
      booking_id: string
      passenger_name: string  # validated against PNR server-side
      flight_number: string
      departure_iso: string
      seat: string
      gate: string
    returns:
      pass_serial: string
      add_to_wallet_url: string
      expires_at: string

  - name: update_wallet_pass
    parameters:
      pass_serial: string
      fields: object  # gate, seat, boarding_time
    returns:
      update_status: enum[ pushed, queued, not_found ]
```

Server validates `booking_id` against GDS/booking API — agent cannot forge passenger on arbitrary PNR.

## Apple Wallet — PKPass generation

Signing happens in wallet service:

```python
import json
import zipfile
from pathlib import Path

def build_pkpass(pass_json: dict, manifest_hashes: dict, signature: bytes) -> bytes:
    # pass.json + manifest.json + signature + assets → zip
    ...

def create_boarding_pass(booking: Booking) -> PassResult:
    pass_data = {
        "formatVersion": 1,
        "passTypeIdentifier": "pass.com.example.travel",
        "serialNumber": f"BRD-{booking.id}",
        "teamIdentifier": TEAM_ID,
        "organizationName": "Example Travel",
        "boardingPass": {
            "primaryFields": [{"key": "origin", "label": "SAN", "value": booking.origin}],
            "secondaryFields": [{"key": "gate", "label": "GATE", "value": booking.gate}],
            "auxiliaryFields": [{"key": "seat", "label": "SEAT", "value": booking.seat}],
        },
        "barcode": {
            "format": "PKBarcodeFormatAztec",
            "message": booking.barcode_payload,  # never log
            "messageEncoding": "iso-8859-1",
        },
        "webServiceURL": "https://wallet.example.com/v1/passes/",
        "authenticationToken": generate_auth_token(booking.id),
    }
    signed = sign_with_apple_cert(pass_data)
    store_pass_record(pass_data["serialNumber"], booking.id)
    url = issue_add_pass_url(signed, ttl_minutes=15)
    return PassResult(serial=pass_data["serialNumber"], url=url)
```

Certificates live in HSM or cloud KMS — rotation runbook separate from agent deploys.

## Google Wallet — JWT object pattern

```python
from google.oauth2 import service_account
import jwt
import time

def create_google_boarding_pass(booking: Booking) -> str:
    object_id = f"{ISSUER_ID}.boarding_{booking.id}"
    payload = {
        "iss": SERVICE_ACCOUNT_EMAIL,
        "aud": "google",
        "typ": "savetowallet",
        "iat": int(time.time()),
        "payload": {
            "flightObjects": [{
                "id": object_id,
                "classId": f"{ISSUER_ID}.boarding_class",
                "boardingAndSeatingInfo": {
                    "seatNumber": booking.seat,
                    "boardingGroup": booking.group,
                },
                "reservationInfo": {"confirmationCode": booking.pnr},
            }]
        },
    }
    token = jwt.encode(payload, credentials.signer, algorithm="RS256")
    return f"https://pay.google.com/gp/v/save/{token}"
```

## Push updates on agent-driven changes

When agent tool `update_wallet_pass` fires after gate change:

**Apple:**

```python
def push_pass_update(serial: str):
    record = pass_registry.get(serial)
    apns_send(
        topic=f"pass.{PASS_TYPE_ID}",
        device_tokens=record.registered_devices,
        payload={},  # empty → device pulls update
    )
```

Device GETs `webServiceURL/v1/devices/.../registrations/...` → returns fresh pass.json.

**Google:** PATCH object via REST API; no APNs equivalent.

Agent receives `update_status: pushed` — not raw APNs diagnostics.

## Idempotency and concurrency

Same booking change retried twice:

```python
def update_pass(serial: str, fields: dict, idempotency_key: str):
    if dedupe.exists(idempotency_key):
        return dedupe.result(idempotency_key)
    merged = pass_registry.merge_fields(serial, fields)
    push_pass_update(serial)
    dedupe.store(idempotency_key, {"update_status": "pushed"})
    return {"update_status": "pushed"}
```

## Security and redaction

| Field | In LLM context? | Storage |
|-------|-----------------|---------|
| Apple signing cert | Never | HSM |
| barcode_payload | Never | Encrypted at rest |
| add_to_wallet_url | Token only, short TTL | Audit log |
| passenger_name | Yes if user-owned session | Pass registry |

Rotate `authenticationToken` on suspicious agent session revoke.

## Testing without production certs

- Apple PassKit test environment with sandbox certs
- Google Wallet demo issuer mode
- Stub tools in agent evals returning fixture URLs

## Resources

- [Apple — Wallet Passes documentation](https://developer.apple.com/documentation/walletpasses)
- [Apple — PassKit Web Service Reference](https://developer.apple.com/library/archive/documentation/PassKit/Reference/PassKit_WebService/WebService.html)
- [Google Wallet — REST API](https://developers.google.com/wallet)
- [Passkit.io — open PKPass tooling reference](https://github.com/passkit/passkit-generator)

## Operational checklist for production rollouts

Before widening traffic, confirm dashboards exist for the leading indicators discussed above — not only lagging incident counts. Run a game day that exercises rollback: feature flag off, alias revert, or kill switch without a new deploy. Document who owns each control in the service catalog so on-call is not guessing during a Sev2.

Slice metrics by tenant tier during canary. Global averages hide bad enterprise cohorts. Pair technical metrics with a sample of user-visible outcomes weekly — support ticket themes often lead dashboards by 48 hours.

When third-party providers change defaults (models, TLS roots, streaming semantics), error-class metrics should catch drift within hours even if no deploy shipped on your side. Keep a changelog subscription for every dependency on the critical path.

## Field notes from incident reviews

Repeat incidents without automation tickets are a planning failure, not an engineering surprise. Capture toil hours in retro; fund paydown in the next sprint. Prefer idempotent handlers and explicit state machines over ad-hoc scripts that only the author understands.

Audit trails matter for billing, auth, and safety paths. Log structured enums — not prose — so aggregation survives high volume. Redact secrets and tokens at the logging boundary; debugging can use correlation ids instead.

## Operational checklist for production rollouts

Before widening traffic, confirm dashboards exist for the leading indicators discussed above — not only lagging incident counts. Run a game day that exercises rollback: feature flag off, alias revert, or kill switch without a new deploy. Document who owns each control in the service catalog so on-call is not guessing during a Sev2.

Slice metrics by tenant tier during canary. Global averages hide bad enterprise cohorts. Pair technical metrics with a sample of user-visible outcomes weekly — support ticket themes often lead dashboards by 48 hours.

When third-party providers change defaults (models, TLS roots, streaming semantics), error-class metrics should catch drift within hours even if no deploy shipped on your side. Keep a changelog subscription for every dependency on the critical path.

## Field notes from incident reviews

Repeat incidents without automation tickets are a planning failure, not an engineering surprise. Capture toil hours in retro; fund paydown in the next sprint. Prefer idempotent handlers and explicit state machines over ad-hoc scripts that only the author understands.

Audit trails matter for billing, auth, and safety paths. Log structured enums — not prose — so aggregation survives high volume. Redact secrets and tokens at the logging boundary; debugging can use correlation ids instead.

## Operational checklist for production rollouts

Before widening traffic, confirm dashboards exist for the leading indicators discussed above — not only lagging incident counts. Run a game day that exercises rollback: feature flag off, alias revert, or kill switch without a new deploy. Document who owns each control in the service catalog so on-call is not guessing during a Sev2.

Slice metrics by tenant tier during canary. Global averages hide bad enterprise cohorts. Pair technical metrics with a sample of user-visible outcomes weekly — support ticket themes often lead dashboards by 48 hours.

When third-party providers change defaults (models, TLS roots, streaming semantics), error-class metrics should catch drift within hours even if no deploy shipped on your side. Keep a changelog subscription for every dependency on the critical path.

## Field notes from incident reviews

Repeat incidents without automation tickets are a planning failure, not an engineering surprise. Capture toil hours in retro; fund paydown in the next sprint. Prefer idempotent handlers and explicit state machines over ad-hoc scripts that only the author understands.

Audit trails matter for billing, auth, and safety paths. Log structured enums — not prose — so aggregation survives high volume. Redact secrets and tokens at the logging boundary; debugging can use correlation ids instead.

