---
title: "Vehicle-to-Grid Integration"
slug: "ev-vehicle-to-grid-v2g"
description: "Integrate V2G for fleet and residential: ISO 15118 BPT, grid interconnection standards, aggregator models, battery warranty, and revenue stacking."
datePublished: "2026-01-30"
dateModified: "2026-01-30"
tags: ["IoT", "EV Charging", "V2G", "Grid"]
keywords: "vehicle to grid V2G, bidirectional EV charging, V2G integration, ISO 15118 BPT, grid services EV, V2G aggregator, IEEE 1547 EV, battery warranty V2G"
faq:
  - q: "What is the difference between V2G and V2H?"
    a: "V2G (vehicle-to-grid) exports power to the utility grid, subject to interconnection agreements and grid codes. V2H (vehicle-to-home) powers a residence behind the meter, often during outages, without necessarily exporting to the grid. Hardware may be similar (bidirectional inverter), but regulatory and control paths differ."
  - q: "Does V2G degrade EV batteries?"
    a: "Additional cycling and time at high SoC during grid services increase degradation versus drive-only use. OEM warranty terms vary — some exclude V2G unless fleet program approved. Model revenue vs accelerated degradation; use SoC buffers (e.g., operate between 20–80% for grid events) and thermal management."
  - q: "Who controls V2G dispatch — the driver, CPO, or utility?"
    a: "Typically a grid aggregator or DERMS sends dispatch signals to a V2G platform, which translates to per-vehicle power setpoints via ISO 15118 or OCPP smart charging extensions, respecting driver departure SoC constraints. Driver opt-in and override remains essential for consumer trust."
---

The utility offered $400/month if your fleet lets them pull power from parked buses during peak — sounds simple until the first driver leaves with 40% SoC because dispatch overrode departure schedules, or the interconnection reviewer asks for IEEE 1547-2018 ride-through tests on a charger certified only for one-way DC. Vehicle-to-grid integration connects bidirectional chargers, vehicle battery management systems, and grid operator signals into a stack where physics, regulation, and contract law all apply at once. V2G is deployable today in pilot form; production scale requires aligning ISO 15118 BPT messaging, aggregator platforms, and warranty economics.

## System architecture

```
Grid operator / ISO
       │
   Aggregator (DERMS, VPP platform)
       │
   CSMS / V2G orchestrator
       │
  SECC (bidirectional EVSE) ◄──ISO 15118 BPT──► EV (EVCC + BMS)
       │
   Utility meter (revenue grade)
```

Power flow export requires **utility permission** — relay closing to grid, not just inverter capability.

## Protocol layer: ISO 15118-20 BPT

Session negotiates discharge limits:

- EV: max discharge power, min SoC reserve
- EVSE: grid export cap from EMS
- Dynamic updates each ChargeLoop

OCPP 2.1 extensions emerging for CSMS↔charger V2G coordination where ISO 15118 not end-to-end.

Fleet API example orchestrator → CSMS:

```json
{
  "event_id": "dr-2026-01-30-17",
  "site_id": "depot-west",
  "target_export_kw": 150,
  "duration_min": 60,
  "min_departure_soc": 0.75,
  "vehicle_ids": ["bus-12", "bus-19", "bus-22"]
}
```

Orchestrator solves who discharges how much without violating next-route energy needs.

## Grid interconnection and compliance

Exporting makes the EVSE+vehicle a **Distributed Energy Resource (DER)**:

- **IEEE 1547** — voltage/frequency ride-through, cease export on fault
- **UL 9741** — North American EVSE grid support evaluation
- **Local utility interconnection agreement** — export limits, metering

Anti-islanding mandatory — detect grid loss and stop export within milliseconds.

Revenue metering often requires **ANSI C12** or IEC certified meters separate from charger internal display.

## Revenue streams (stacking)

| Service | Mechanism | Duration |
|---------|-----------|----------|
| Peak shaving | Reduce site import | Minutes–hours |
| Demand response | Utility dispatch event | 1–4 hours |
| Frequency regulation | Fast up/down regulation | Seconds |
| Wholesale energy arbitrage | Buy low charge, sell high discharge | Hours |

Not all stack simultaneously — contract exclusivity and battery wear constrain participation. Aggregators bundle small DERs into market bids.

## Battery and warranty management

Degradation drivers in V2G:

- Depth of discharge cycles
- Time at high SoC while idle-exporting
- Fast discharge heat

Mitigations:

```python
def allow_discharge(vehicle, event):
    if vehicle.projected_departure_soc(event.end) < vehicle.min_required_soc:
        return False
    if vehicle.battery_cycle_cost_usd(event.kwh) > event.revenue_usd * 0.4:
        return False  # economics don't justify wear
    return True
```

OEM fleet programs may provide **state-of-health telemetry** API — integrate before promising grid operator capacity.

## Consumer vs fleet V2G

**Fleet** — predictable schedules, centralized opt-in, uniform hardware, easier aggregation.

**Residential** — fragmented chargers, driver override essential, regulatory retail net metering rules vary wildly by state/country.

Start fleet depot pilots with single OEM+charger pairing certified together — avoid combinatorial interoperability matrix early.

## Safety and UX

- Visible **export indicator** on charger
- App shows: "Grid event active — guaranteed 70% at 7 AM"
- Hard stop on driver "leave now" override
- Fail-safe: grid anomaly → stop export, resume charge if needed

V2G succeeds when drivers trust departure SoC more than they fear grid experimentation.

## Grid services and revenue models

V2G enables multiple grid services, each with different requirements:

| Service | Direction | Duration | Revenue model |
|---|---|---|---|
| Peak shaving | Discharge | 1–4 hours | Capacity payment |
| Frequency regulation | Bidirectional | Continuous | Per-MW payment |
| Demand response | Discharge | Event-based | Per-event incentive |
| Solar self-consumption | Store excess | Daily cycle | Avoided retail rate |

Frequency regulation requires sub-second response — only viable with direct inverter control (ISO 15118-20 BPT), not OCPP-only chargers. Peak shaving works with OCPP 2.1 scheduled charging profiles.

```python
def calculate_v2g_revenue(session, grid_signal):
    export_kwh = min(session.available_export_kwh, grid_signal.requested_kwh)
    capacity_payment = export_kwh * grid_signal.capacity_rate
    energy_payment = export_kwh * grid_signal.energy_rate
    return capacity_payment + energy_payment
```

Revenue must exceed battery degradation cost per cycle — typically $0.05–0.15/kWh degradation vs $0.10–0.50/kWh grid payment depending on market.

## Battery degradation accounting

Every V2G cycle adds degradation — model it explicitly:

```python
def degradation_cost(cycle_depth_pct, battery_capacity_kwh, replacement_cost):
    # Simplified: linear degradation model
    cycle_life_at_depth = {20: 8000, 50: 3000, 80: 1500, 100: 1000}
    cycles_remaining = cycle_life_at_depth.get(cycle_depth_pct, 1000)
    cost_per_cycle = replacement_cost / cycles_remaining
    return cost_per_cycle * (cycle_depth_pct / 100) * battery_capacity_kwh
```

Only dispatch V2G when grid payment exceeds degradation cost. OEM warranty may void on V2G cycles beyond rated count — check warranty terms before fleet deployment.

## ISO 15118-20 bidirectional power transfer

BPT extends ISO 15118 with grid-side communication:

```
EV ←→ EVSE ←→ CSMS ←→ Grid operator (via OCPP 2.1 or direct API)
     ↑ ISO 15118-20 BPT
     ↑ PowerDelivery, ChargeLoop, BPT parameters
```

BPT parameters include max export power, export voltage limits, and grid frequency response capability. Without ISO 15118-20 BPT support on both EV and charger, V2G is limited to OCPP-scheduled discharge profiles with coarse granularity.

## Failure modes

- **Departure SoC guarantee violated** — driver stranded; V2G program abandoned
- **Degradation cost not modeled** — V2G unprofitable after battery replacement
- **Grid signal latency too high** — frequency regulation impossible via OCPP polling
- **OEM warranty voided** — undisclosed V2G cycle count to manufacturer
- **Driver override ignored** — grid event continues after "leave now" tap

## Production checklist

- Departure SoC guarantee enforced with hard stop
- Battery degradation cost calculated per dispatch decision
- Revenue vs degradation breakeven documented per grid market
- Driver override ("leave now") stops export immediately
- Visible export indicator on charger and app
- OEM warranty terms reviewed for V2G cycle limits

Grid code compliance varies by utility territory — V2G software certified in California may be illegal to operate in Texas without re-certification.

## Resources

- [ISO 15118-20 BPT modules](https://www.iso.org/standard/77833.html)
- [IEEE 1547-2018 standard](https://standards.ieee.org/standard/1547-2018.html)
- [NREL V2G research and projects](https://www.nrel.gov/transportation/v2g.html)
- [CharIN Grid Integration and V2G task force](https://charin.global/)
- [OCPP 2.1 draft V2G-related work (Open Charge Alliance)](https://www.openchargealliance.org/)
