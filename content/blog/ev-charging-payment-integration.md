---
title: "Payment Integration for EV Charging"
slug: "ev-charging-payment-integration"
description: "Integrate payments for EV charging: CPO billing models, PCI scope, pre-auth holds, roaming settlement, and UX for session-based pricing."
datePublished: "2026-01-18"
dateModified: "2026-01-18"
tags: ["IoT", "EV Charging", "Payments", "Integration"]
keywords: "EV charging payment integration, CPO billing, charging session payment, PCI EV charging, pre-authorization EVSE, roaming payment settlement, Stripe Terminal EV"
faq:
  - q: "How are EV charging sessions typically billed?"
    a: "Most public charging bills by energy (kWh), time (per minute), session flat fee, or hybrid — idle fees after charge completes. The CPO payment system captures a payment method at session start, meters energy from the charger, calculates cost at stop, and captures or adjusts the pre-authorization hold."
  - q: "Does PCI DSS apply to charge point operators?"
    a: "Yes if you accept card data. Reduce scope with hosted payment pages, tokenization via PSP (Stripe, Adyen), or RFID/app wallets where card never touches your SECC firmware. Never store track data on charger or CSMS; tokens only."
  - q: "How do roaming sessions get paid between CPO and eMSP?"
    a: "Roaming protocols (OCPI) exchange session CDRs (charge detail records); eMSP bills the driver on their contract; clearing houses or bilateral agreements settle between CPO and eMSP periodically — separate from the driver's single tap payment experience."
---

A driver plugs in, charges 42 kWh, idles twenty minutes, and disputes a $68 charge because the app showed one price per kWh but the station added session fees and occupancy penalties buried in terms of service. Payment integration for EV charging is not e-commerce checkout — it is session-metered billing with pre-authorization, regulatory price display rules in some markets, and roaming settlement happening days later between operators the driver never heard of. CPOs that treat payments as "Stripe button on website" learn expensive lessons at charge stop when holds fail or PCI scope includes firmware.

## Billing models and metering trust

Revenue components:

| Component | Source |
|-----------|--------|
| Energy (kWh) | SECC meter / MID-certified energy meter |
| Time | Session clock |
| Idle fee | Grace period after SoC threshold |
| Parking | Local policy overlay |

Metering must align with **OCPP MeterValues** or ISO 15118 meter info — payment disputes hinge on certified kWh totals.

```json
{
  "session_id": "sess_8f3a",
  "meter_start_wh": 124500,
  "meter_stop_wh": 166700,
  "energy_kwh": 42.2,
  "tariff_id": "public_dc_peak",
  "total_cents": 6840,
  "currency": "USD"
}
```

Tamper-evident meter logs and CSMS reconciliation prevent underbilling from firmware bugs.

## Payment flow at session lifecycle

```
Start session ──► Pre-auth hold ($25–$100 typical DC)
       │
   Charging ──► Optional mid-session auth increase
       │
 Stop session ──► Calculate CDR ──► Capture ≤ hold
       │
       └──► Release unused hold / partial capture
```

```python
# conceptual capture after OCPP StopTransaction
def finalize_session(session, cdr):
    amount = calculate_price(cdr.energy_kwh, cdr.duration, session.tariff)
    if amount > session.preauth_amount:
        extra = payment_provider.increment_auth(session.payment_intent, amount)
    payment_provider.capture(session.payment_intent, amount)
    emit_ocpi_cdr(session, cdr)  # if roaming
```

Pre-auth amounts must cover peak tariff × expected energy; failed capture triggers dunning, not silent loss.

## PCI scope minimization

**Good:** App or QR opens PSP hosted checkout; charger displays QR only; token stored in CSMS vault.

**Bad:** Card reader on charger sending PAN to your custom API without certified P2PE.

RFID fleet cards map to backend tokens — same capture flow, different presentation.

For **Plug & Charge**, payment is contract-based (eMSP); CPO trusts OCPI auth, not card at charger.

## Tariff engine and display

Regulations (e.g., EU AFIR transparency) require visible kWh price before start:

```yaml
tariffs:
  - id: ac_standard
    elements:
      - type: ENERGY
        price_per_kwh: 0.35
        currency: EUR
      - type: TIME
        price_per_min: 0.10
        restrictions:
          min_duration_min: 60  # idle after full
```

Push tariff to charger via OCPP `SetChargingProfile` / ISO 15118 `ChargeParameterDiscovery`. App, signage, and receipt must match — regulatory fines and chargebacks otherwise.

## Roaming and settlement

Driver with eMSP App A at CPO Network B:

1. OCPI `POST /tokens/authorize` — eMSP guarantees payment
2. Session runs; CDR sent via OCPI `POST /cdrs`
3. Clearing: invoice B→A monthly; driver sees one line on App A

Your payment integration must idempotently handle duplicate CDR retries and currency conversion if cross-border.

## Failure modes

- **Hold insufficient** — block start or lower max power with clear UX
- **Offline charger** — store signed CDR locally; capture when CSMS reconnects (liability policy)
- **Partial session abort** — bill delivered energy only; release hold promptly
- **Refund disputes** — tie support tools to meter timeline graph

Payments complete the charging loop — design them with metering and roaming from day one, not as a Phase 2 afterthought.

## PCI scope reduction

Minimize PCI DSS scope by never touching raw card data:

```
Driver app → Stripe SDK (tokenizes card) → your backend receives token only
Charger → no card data ever
CSMS → no card data ever
```

SAQ-A (simplest PCI questionnaire) applies when all card data handled by PCI-compliant third party. Never log, store, or transmit raw PAN/CVV through your CSMS or charger firmware.

For fleet accounts with invoicing (no card at charge time), PCI scope is minimal — billing happens offline via invoice.

## Pre-authorization amount calculation

Hold amount must cover worst-case session cost:

```python
def calculate_pre_auth_amount(tariff, connector_max_kw, vehicle_battery_kwh):
    max_duration_hours = vehicle_battery_kwh / connector_max_kw
    max_energy_cost = max_duration_hours * connector_max_kw * tariff.energy_rate
    idle_fee_buffer = tariff.idle_rate * 2  # 2 hours idle after full
    return max_energy_cost + idle_fee_buffer + tariff.min_fee

# Example: 75kWh battery, 150kW charger, €0.35/kWh
# max_energy = 75 * 0.35 = €26.25
# idle buffer = €5/h * 2h = €10
# pre-auth = €36.25 → round up to €40 hold
```

Display hold amount to driver before session start — unexpected holds cause chargebacks.

## Settlement reconciliation

Daily reconciliation between payment processor, CSMS sessions, and OCPI CDRs:

```sql
-- Find sessions without captured payment
SELECT s.session_id, s.total_cost, p.status
FROM sessions s
LEFT JOIN payments p ON s.session_id = p.session_id
WHERE s.status = 'completed'
  AND (p.status IS NULL OR p.status != 'captured')
  AND s.end_time < NOW() - INTERVAL '1 hour';
```

Alert on uncaptured payments >1 hour after session end. OCPI CDR retries can arrive hours later — idempotency keys prevent double capture.

## Failure modes

- **Pre-auth hold too low** — session ends with uncaptured amount; revenue loss
- **Duplicate CDR capture** — missing idempotency key; double charge
- **Offline session without signed CDR** — no payment proof; liability dispute
- **Currency mismatch in roaming** — CDR in EUR, eMSP bills in USD without exchange rate
- **PCI scope creep** — card data logged in CSMS debug logs

## Production checklist

- PCI SAQ-A scope maintained (no raw card data in CSMS/charger)
- Pre-auth amount calculated from worst-case session cost
- Hold amount displayed to driver before session start
- Idempotency keys on all payment capture requests
- Daily reconciliation job for uncaptured sessions
- OCPI CDR idempotency prevents double billing on retry

Implement idempotent payment capture keyed on OCPP transaction ID — network retries during charging sessions double-charge without it.

## Resources

- [OCPI 2.2.1 specification (EV Roaming Foundation)](https://evroaming.org/ocpi-downloads/)
- [OCPP 2.0.1 — Open Charge Alliance](https://www.openchargealliance.org/protocols/ocpp-201/)
- [PCI DSS v4.0 documentation](https://www.pcisecuritystandards.org/)
- [Stripe payment intents lifecycle](https://docs.stripe.com/payments/payment-intents/lifecycle)
- [EU Alternative Fuels Infrastructure Regulation (AFIR)](https://energy.ec.europa.eu/topics/eus-energy-system/eu-alternative-fuels-infrastructure-regulation_en)
