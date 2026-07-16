---
title: "ISO 15118-20 and Bidirectional Charging"
slug: "ev-charging-iso-15118-20"
description: "Implement ISO 15118-20 for plug-and-charge and V2G: AC/DC bidirectional power transfer, certificate handling, and differences from ISO 15118-2."
datePublished: "2026-01-15"
dateModified: "2026-01-15"
tags: ["IoT", "EV Charging", "ISO 15118", "V2G"]
keywords: "ISO 15118-20, bidirectional charging, V2G ISO 15118, plug and charge, AC BPT DC BPT, EV charging protocol, ISO 15118-2 vs 15118-20, SECC EVSE"
faq:
  - q: "What does ISO 15118-20 add over ISO 15118-2?"
    a: "ISO 15118-20 extends the vehicle-to-grid communication standard with modular documents for AC and DC charging, bidirectional power transfer (BPT), wireless power transfer references, and improved certificate provisioning flows. It supports dynamic modes needed for V2G and fleet depot scheduling while maintaining backward compatibility paths with 15118-2 deployments."
  - q: "Is ISO 15118-20 required for vehicle-to-grid?"
    a: "V2G requires standardized communication of power limits, grid codes, and discharge authorization between EV, EVSE, and energy management. ISO 15118-20 BPT modules define message sets for bidirectional sessions; regional grid integrations (IEEE 1547, EN 50549) still apply at the energy layer."
  - q: "Who implements the SECC versus the EVCC?"
    a: "EVCC (EV Communication Controller) runs in the vehicle; SECC (Supply Equipment Communication Controller) runs in the charger. Both must implement matching ISO 15118 editions, TLS with plug-and-charge certificates, and SAP (Supported App Protocol) negotiation to agree on protocol version and energy transfer mode."
---

Fleet operators want chargers that pull power from vehicles during peak tariff windows — but only if the car, charger, and grid operator agree on discharge limits in milliseconds, not via a phone app. ISO 15118-20 is the updated vehicle-to-charger communication stack that adds bidirectional power transfer (BPT) messaging, refined certificate flows for plug-and-charge, and modular documents separating AC from DC semantics. If you are building SECC firmware on a charge point or integrating EVCC on a TCU, 15118-20 is the path from "dumb Level 2 socket" to grid-aware energy asset.

## Protocol stack overview

```
Application (15118-20 EXI messages: SessionSetup, ChargeLoop, BPT...)
        │
   TLS 1.2/1.3 + mutual cert auth (Plug & Charge)
        │
      TCP/IP (typically IPv6 on PLC per ISO 15118-8)
        │
   ISO 15118-3 / DIN 70121 (PLC physical layer)
```

Session flow (simplified):

1. **SDP** — SECC IP discovery
2. **SupportedAppProtocol** — negotiate 15118-2 vs -20
3. **SessionSetup / ServiceDiscovery**
4. **Authorization** — EIM (external) or PnC (certificate)
5. **PowerDelivery / ChargeLoop** — dynamic limits, BPT schedules
6. **SessionStop**

## Bidirectional power transfer (BPT)

15118-20 defines **BPT** variants for AC and DC:

- **AC_BPT** — discharge from onboard inverter back to grid
- **DC_BPT** — discharge via DC link (vehicle-dependent architecture)

Key message concepts:

```xml
<!-- conceptual EXI element names, not literal schema -->
<BPT_ScheduledMode>
  <DepartureTime>2026-01-15T17:00:00Z</DepartureTime>
  <EVTargetEnergyRequest>-5.0 kWh</EVTargetEnergyRequest> <!-- negative = export -->
  <EVMaximumDischargePower>7.4 kW</EVMaximumDischargePower>
</BPT_ScheduledMode>
```

EV sends discharge capabilities; SECC merges grid operator limits from EMS; both sides enforce ramp rates.

Implement state machines carefully — mode transitions mid-session require renegotiation without unsafe power steps.

## Plug and Charge certificates

PnC uses V2G PKI:

- **OEM provisioning certificate (PCID)** installed at manufacture
- **Contract certificate** from mobility operator
- **SECC leaf certificate** on charger

15118-20 refines **CertificateInstallation** and **CertificateUpdate** flows for contract cert rotation without dealer visit. Misconfigured trust stores cause the silent fallback to RFID — test cross-OEM chains in interoperability plugs.

## SECC implementation notes

Embedded Linux SECC stack typical components:

```c
// pseudocode session state
typedef enum {
    SECC_IDLE,
    SECC_TLS_HANDSHAKE,
    SECC_SESSION_ACTIVE,
    SECC_BPT_DISCHARGE,
    SECC_ERROR_STOP
} secc_state_t;

void on_charge_loop(BPT_ChargeLoopReq *req) {
    grid_limit_w_t grid_cap = ems_get_export_limit();
    res->EVSEMaxDischargePower = min(req->EVMaxDischargePower, grid_cap);
    res->EVSEProcessing = Ongoing;
}
```

Integrate with **ISO 15118-3** PLC modem driver; latency jitter on HomePlug affects TLS timeout tuning.

Log EXI messages hashed for audit — full payload logs may contain contract identifiers (GDPR).

## Differences from 15118-2 deployments

| Topic | 15118-2 | 15118-20 |
|-------|---------|----------|
| Structure | Monolithic | Modular (-2, -4 DC, -5 AC, -8 PLC...) |
| BPT | Limited / external | Native BPT modes |
| WPT | Not focus | Reference modules |
| SAP negotiation | Required | Extended protocol set |

Field chargers often support dual stack — detect vehicle capability and branch.

## Testing and certification

- **CharIN** test cases for interoperability events
- Hardware-in-loop simulators (e.g., EVerest, RISE V2G) for SECC regression
- Grid code coupling tests with simulated IEEE 1547 ride-through

Certification paths vary by market — UL 9741, CE grid codes — protocol compliance is necessary not sufficient.

## EMS integration for V2G

ISO 15118-20 handles vehicle-to-charger communication. Grid integration requires an Energy Management System (EMS) layer:

```
Grid operator ←→ EMS ←→ SECC ←→ EVCC ←→ Vehicle BMS
                  ↑
            IEEE 1547 / EN 50549 limits
            Tariff signals (OpenADR, EEBUS)
            Fleet scheduler API
```

The SECC must merge three constraint sets in real-time:
1. **Vehicle limits** — max discharge power from BMS via EVCC
2. **Charger limits** — hardware capability of the power module
3. **Grid limits** — export cap from EMS based on grid code and tariff

```c
void compute_discharge_limit(BPT_ChargeLoopReq *ev_req) {
    float ev_max = ev_req->EVMaximumDischargePower;
    float evse_max = hardware_get_max_discharge();
    float grid_max = ems_get_export_limit();  // from IEEE 1547 ride-through

    res->EVSEMaxDischargePower = min(ev_max, evse_max, grid_max);
    res->EVSEMaxDischargeCurrent = res->EVSEMaxDischargePower / voltage;
}
```

If EMS communication fails, default to zero export — never discharge without grid authorization.

## Open source SECC stacks

Building SECC from scratch is years of work. Open source stacks accelerate development:

- **EVerest** — modular C++ charging station framework with ISO 15118-20 support, OCPP integration, and simulated EVCC for testing
- **RISE V2G** — Java-based reference implementation for EVCC and SECC development/testing
- **Solidstudio EV** — commercial stack with CharIN certification support

Use simulators for regression testing before hardware-in-loop:

```bash
# EVerest: start SECC with simulated EVCC
everest start --config configs/15118-20-ac-bpt.yaml
everest trigger --module evse_manager --action start_charging
```

## Interoperability testing

Cross-OEM interoperability is the hard part — Tesla, VW, Hyundai, and Ford each implement 15118-20 with vendor variations:

- **CharIN testival** — industry interoperability events; bring SECC + multiple EVs
- **Certificate chain testing** — PnC fails silently to RFID if trust store doesn't include OEM root CA
- **SAP negotiation** — vehicle offers 15118-2 only; SECC must fall back gracefully
- **BPT mode transitions** — switching charge→discharge mid-session without power spike

Maintain a compatibility matrix: vehicle model × firmware version × test result. Update after every firmware release on either side.

## Failure modes

- **PnC certificate chain mismatch** — silent fallback to RFID; user thinks plug-and-charge is broken
- **BPT without EMS grid limit** — uncontrolled export trips grid protection relay
- **15118-2 vs -20 SAP failure** — session doesn't start; need dual-stack support
- **PLC link drop mid-BPT session** — power must ramp down safely within ISO 15118-3 timing
- **GDPR in EXI logs** — contract certificates contain personal identifiers; hash, don't log raw

## Production checklist

- Dual-stack 15118-2 and -20 SAP negotiation supported
- EMS integration with grid export limits enforced
- PnC certificate trust store includes target OEM root CAs
- BPT mode transitions tested without power spikes
- Open-source simulator regression tests in CI
- CharIN interoperability event attended before market launch
- EXI message logging GDPR-compliant (hashed identifiers)

## Resources

- [ISO 15118-20 standard (ISO store)](https://www.iso.org/standard/77833.html)
- [CharIN e.V. — ISO 15118 industry group](https://charin.global/)
- [EVerest open-source charging stack](https://github.com/EVerest/everest-core)
- [V2G Clarity / Hubject PnC ecosystem](https://www.hubject.com/)
- [IEEE 1547 — interconnection standard for DER](https://standards.ieee.org/standard/1547-2018.html)
