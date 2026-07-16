---
title: "Depot Charging for EV Fleets"
slug: "ev-fleet-depot-charging"
description: "Design depot charging for electric fleets: load management, overnight scheduling, telematics integration, charger-to-depot ratios, and TCO modeling."
datePublished: "2026-01-27"
dateModified: "2026-01-27"
tags: ["IoT", "EV Charging", "Fleet", "Energy"]
keywords: "fleet depot charging, EV fleet charging management, load management depot, smart charging fleet, depot charger sizing, overnight fleet charging, VRP EV fleet"
faq:
  - q: "How many chargers does a fleet depot need?"
    a: "Not one per vehicle unless all return simultaneously with tight turnaround. Model routes and dwell times: overnight depots often size for 30–50% simultaneous charging with power sharing; transit depots with mid-day returns need higher peak counts or opportunity charging en route. Simulation with actual telematics beats rules of thumb."
  - q: "What is smart charging for fleets?"
    a: "Central system assigns power caps per vehicle based on departure time, state of charge, route energy need, and site grid limit. OCPP ChargingProfiles or ISO 15118 schedules implement limits. Goal: every vehicle reaches target SoC before shift without exceeding transformer capacity or demand charges."
  - q: "How do fleet chargers integrate with route planning?"
    a: "Telematics feeds expected arrival SoC and next-day mileage into depot EMS. Route optimization (VRP) outputs kWh requirement per vehicle; scheduler prioritizes low-SoC and early departure buses. Integration APIs connect fleet management software to CSMS smart charging modules."
---

Fifty electric delivery vans return between 6 PM and 9 PM to a depot fed by a 400 kW transformer — and someone ordered fifty 19 kW Level 2 chargers because "one per van is simple." Peak demand blows the connection fee, blows the budget, and still leaves van #37 at 62% SoC when drivers leave at 5 AM. Depot charging for fleets is an operations research problem dressed as electrical installation: right-size power, schedule intelligently, and tie charging to when vehicles actually need to leave, not when they physically plug in.

## Site power and charger mix

Steps:

1. **Utility capacity** — firm kW, demand charge structure, upgrade timeline
2. **Dwell window** — hours available × vehicle count
3. **Energy per vehicle** — kWh/day from telematics or route model
4. **Peak simultaneous** — histogram of return times

Example calculation sketch:

```
Fleet: 40 vans, avg 45 kWh/day replenishment
Dwell: 10 hours (19:00–05:00)
Minimum average power: 40 × 45 / 10 = 180 kW
With 20% scheduling inefficiency → 216 kW plan
```

Mix **DCFC** for quick-turn vehicles and **Level 2** for overnight dwell — not uniform hardware.

Dynamic load management (DLM) shares unused capacity:

```
Site limit 300 kW
  ├── Bus A: 80 kW (departs 05:00, SoC 40%)
  ├── Bus B: 60 kW (departs 06:00, SoC 55%)
  └── Vans C–N: 7 kW each capped dynamically
```

## CSMS scheduling architecture

```python
def schedule_depot(vehicles, site_limit_kw, horizon_hours):
    # sort by departure urgency / energy deficit
    ranked = sorted(vehicles, key=lambda v: v.energy_deficit_kwh / v.hours_until_departure, reverse=True)
    allocations = {}
    for v in ranked:
        need_kw = min(v.max_charge_kw, v.energy_deficit_kwh / max(v.hours_until_departure, 0.5))
        allocations[v.id] = allocate_with_cap(need_kw, site_limit_kw, allocations)
    return allocations  # push via OCPP SetChargingProfile
```

Inputs from telematics webhook:

```json
{
  "vehicle_id": "van-104",
  "eta_depot": "2026-01-27T19:22:00Z",
  "soc": 0.31,
  "next_shift_miles": 112,
  "departure": "2026-01-28T05:00:00Z"
}
```

Recompute every 15 minutes as arrivals shift.

## OCPP smart charging integration

OCPP 2.0.1 **ChargingProfile** with `TxProfile` stack:

```json
{
  "chargingProfile": {
    "chargingProfilePurpose": "TxProfile",
    "stackLevel": 0,
    "chargingSchedule": {
      "duration": 36000,
      "chargingRateUnit": "W",
      "chargingSchedulePeriod": [
        { "startPeriod": 0, "limit": 11000 },
        { "startPeriod": 7200, "limit": 0 }
      ]
    }
  }
}
```

Validate charger supports profile units (W vs A). Fallback: contactor-level DLM hardware if legacy AC chargers ignore software limits.

## Depot layout and operations

- **Pull-through vs back-in** affects cable reach and session start latency
- **Pre-conditioning** — cabin/battery heat while plugged reduces route energy; schedule before departure spike
- **Maintenance bays** — isolated circuits so repair lifts do not steal schedule capacity
- **RFID/driver login** — assign session cost center; prevent personal vehicle plug-in abuse

## TCO and reliability

Model:

- Energy cost vs diesel equivalent
- Demand charge avoidance value of smart scheduling
- Charger downtime SLA — redundant dispensers for critical morning wave
- Labor — automated start on plug (no manual app) saves shift change minutes

Track **ready-at-departure SoC** KPI — missed departures cost more than kWh savings.

## Transit vs last-mile differences

| | Transit bus depot | Last-mile van depot |
|---|-------------------|---------------------|
| Energy/day | 200–400 kWh | 30–80 kWh |
| Turnaround | Opportunity + overnight | Overnight dominant |
| Charger type | DC 150–450 kW | AC 11–19 kW often sufficient |
| Grid impact | Very high peaks | Moderate with DLM |

Transit may need **in-route** opportunity charging — depot becomes partial node in larger network.

## Load management and demand charges

Depot electricity bills have two cost components — energy (kWh) and demand (peak kW):

```
Monthly bill = (kWh × energy_rate) + (peak_kW × demand_charge)

Example:
  50,000 kWh × $0.12/kWh = $6,000 energy
  800 kW peak × $15/kW    = $12,000 demand charge
  Total: $18,000/month
```

Smart charging reduces peak kW without reducing total kWh:

```python
def optimize_depot_schedule(vehicles, chargers, departure_times, max_site_kw):
    # Sort by departure time (most urgent first)
    sorted_vehicles = sorted(vehicles, key=lambda v: departure_times[v.id])
    schedule = []
    for vehicle in sorted_vehicles:
        # Assign charger slot that doesn't exceed site limit
        slot = find_slot(chargers, vehicle, schedule, max_site_kw)
        schedule.append(slot)
    return schedule
```

Target: reduce peak kW by 30–40% vs uncontrolled charging. Demand charge savings often exceed energy cost optimization.

## Vehicle-to-depot (V2D) and grid services

Fleet batteries can provide grid services when not charging:

```
Overnight: vehicles charge (low grid demand, cheap rates)
Morning peak: fleet departs
Midday: parked vehicles export to grid (demand response revenue)
Evening: vehicles return and charge
```

Requires ISO 15118-20 BPT-capable chargers and fleet OEM agreement on battery degradation compensation. Start with unmanaged charging; add V2D after baseline operations stable.

## Charger redundancy and uptime

Morning departure failure costs more than overnight energy savings:

| Redundancy level | Uptime target | Cost multiplier |
|---|---|---|
| N chargers for N vehicles | 95% | 1× |
| N+1 redundancy | 99% | 1.1× |
| N+2 redundancy | 99.9% | 1.2× |

For 20-vehicle depot with 6 AM departure deadline: N+2 redundancy on DC fast chargers. AC overnight chargers tolerate N+1 — vehicles have 8+ hours to charge.

## Failure modes

- **Uncontrolled charging** — demand charge exceeds energy cost; bill shock
- **No departure SoC monitoring** — vehicle leaves undercharged; route failure
- **Single charger failure with no redundancy** — morning departure missed
- **Schedule ignores driver overtime** — vehicle returns late; not in charge queue
- **RFID not assigned** — personal vehicle charges on fleet account

## Production checklist

- Load management algorithm caps site peak kW
- Departure SoC guarantee enforced per vehicle schedule
- N+1 redundancy on DC fast chargers for morning departure
- RFID/driver login assigns session to cost center
- Ready-at-departure SoC tracked as primary KPI
- Demand charge vs energy cost modeled in TCO analysis

## Resources

- [OCPP 2.0.1 smart charging use cases](https://www.openchargealliance.org/protocols/ocpp-201/)
- [NREL fleet electrification analysis tools](https://www.nrel.gov/transportation/fleet-energy-and-emissions-footprint.html)
- [CharIN fleet and depot charging guides](https://charin.global/)
- [ISO 15118 scheduled charging modes](https://www.iso.org/standard/77833.html)
- [California HTF depot charging case studies (CARB)](https://ww2.arb.ca.gov/our-work/programs/truck-bus-regulation)
