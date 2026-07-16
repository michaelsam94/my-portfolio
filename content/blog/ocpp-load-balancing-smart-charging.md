---
title: "Smart Charging and Load Balancing"
slug: "ocpp-load-balancing-smart-charging"
description: "Implement OCPP smart charging and load balancing: charging profiles, SetChargingProfile, load management across sites, and grid-friendly dispatch."
datePublished: "2025-10-27"
dateModified: "2025-10-27"
tags: ["IoT", "EV Charging", "OCPP", "Energy"]
keywords: "OCPP smart charging, load balancing EV chargers, SetChargingProfile, charging profiles OCPP, EV fleet load management, demand response charging"
faq:
  - q: "What is the difference between smart charging and load balancing?"
    a: "Smart charging adjusts individual charger power based on grid signals, tariffs, or vehicle needs. Load balancing distributes a fixed site power budget across multiple chargers so the total draw never exceeds the circuit breaker rating. They work together: load balancing is the constraint, smart charging is the optimization."
  - q: "Which OCPP message controls charging power?"
    a: "SetChargingProfile sends a ChargingProfile with power or current limits over time periods. ClearChargingProfile removes it. In OCPP 2.0.1, NotifyEVChargingNeeds reports vehicle-side requirements, and the CSMS responds with a charging profile matching both vehicle needs and grid constraints."
  - q: "How do I handle a site with 200A service and six 48A chargers?"
    a: "Set a site-level cap of 200A (48 kW at 240V). Dynamically allocate current per charger based on active sessions, vehicle SOC, and departure time. A charger with a nearly-full battery gets 16A while a newly-arrived vehicle gets 40A."
---

Six 48A chargers on a 200A panel. All six start charging simultaneously. The main breaker trips. The electrician's fix—hard-cap each charger at 32A—means no vehicle ever charges at full speed, even when only one is in use. OCPP smart charging solves this dynamically: the CSMS sends charging profiles that adjust power limits per connector based on how many sessions are active, time-of-use tariffs, and grid demand signals.

## Charging profile structure

```json
{
  "connectorId": 1,
  "chargingProfile": {
    "chargingProfileId": 101,
    "stackLevel": 0,
    "chargingProfilePurpose": "TxDefaultProfile",
    "chargingProfileKind": "Absolute",
    "chargingSchedule": {
      "chargingRateUnit": "A",
      "chargingSchedulePeriod": [
        { "startPeriod": 0, "limit": 32.0 },
        { "startPeriod": 3600, "limit": 16.0 },
        { "startPeriod": 7200, "limit": 48.0 }
      ]
    }
  }
}
```

| Field | Meaning |
|-------|---------|
| `stackLevel` | Priority (0 = highest). Higher levels override lower. |
| `chargingProfilePurpose` | ChargePointMaxProfile (hardware cap), TxDefaultProfile (per session), TxProfile (specific transaction) |
| `chargingSchedulePeriod` | Time-based limits. `startPeriod` in seconds from schedule start. |
| `limit` | Max current (A) or power (W) depending on `chargingRateUnit`. |

## Profile purposes

```
ChargePointMaxProfile  → Hardware maximum (never exceed breaker)
    ↓ overridden by
TxDefaultProfile       → Default for new transactions
    ↓ overridden by
TxProfile              → Specific to one active transaction
```

Set `ChargePointMaxProfile` at installation to the site breaker rating. Layer `TxDefaultProfile` for normal operation. Override with `TxProfile` for priority vehicles or demand response events.

## Load balancing algorithm

```python
def allocate_current(
    active_sessions: list[Session],
    site_max_amps: float,
    min_amps_per_session: float = 6.0,
) -> dict[int, float]:
    if not active_sessions:
        return {}

    fair_share = site_max_amps / len(active_sessions)

    allocations = {}
    remaining_amps = site_max_amps

    # Priority: vehicles departing soon get more current
    sorted_sessions = sorted(active_sessions, key=lambda s: s.departure_time)

    for session in sorted_sessions:
        requested = session.max_amps
        allocated = min(requested, fair_share, remaining_amps)
        allocated = max(allocated, min_amps_per_session)
        allocations[session.connector_id] = allocated
        remaining_amps -= allocated

    return allocations
```

Send updated profiles when sessions start, stop, or every 60 seconds.

## OCPP 2.0.1 smart charging

OCPP 2.0.1 adds vehicle-side input:

```
Vehicle → Charger: ISO 15118 charging needs (target SOC, departure time)
Charger → CSMS: NotifyEVChargingNeeds
CSMS → Charger: SetChargingProfile (optimized for needs + grid)
```

This enables the charger to balance user needs ("I need 80% by 8 AM") against grid constraints ("site max 100 kW until 6 PM").

## Time-of-use integration

```python
def get_tariff_limit(timestamp: datetime, tariff: TariffSchedule) -> float:
    hour = timestamp.hour
    if tariff.is_peak(hour):
        return tariff.peak_max_amps  # e.g., 16A during peak
    return tariff.off_peak_max_amps  # e.g., 48A overnight

def build_profile(connector_id: int, limit: float) -> dict:
    return {
        "connectorId": connector_id,
        "chargingProfile": {
            "chargingProfileId": int(time.time()),
            "stackLevel": 1,
            "chargingProfilePurpose": "TxDefaultProfile",
            "chargingProfileKind": "Relative",
            "chargingSchedule": {
                "chargingRateUnit": "A",
                "chargingSchedulePeriod": [
                    {"startPeriod": 0, "limit": limit}
                ],
            },
        },
    }
```

Update profiles when tariff periods change—typically at midnight and peak-hour boundaries.

## Demand response

When the utility sends a demand response signal:

1. CSMS receives DR event (reduce load by 30% for 2 hours).
2. Calculate new limits: `site_max * 0.7`.
3. Push updated `TxDefaultProfile` to all active chargers.
4. Log compliance: actual draw vs target.
5. Restore full limits when DR event ends.

```python
async def handle_demand_response(event: DREvent):
    chargers = await get_active_chargers(event.region)
    reduced_max = event.site_capacity * (1 - event.reduction_pct)

    for charger in chargers:
        profiles = compute_profiles(charger.sessions, reduced_max)
        for profile in profiles:
            await csms.set_charging_profile(charger.id, profile)
```

## Monitoring

Track per site:
- Total power draw vs site capacity (utilization %)
- Per-connector allocated vs actual current
- Profile override events (vehicle requesting more than allocated)
- DR compliance during events

Alert when site utilization exceeds 95% for > 10 minutes—time to add capacity or tighten allocation.

## OCPP charging profile stack

Profiles stack with priority — lower stack level wins:

```
Stack Level 0: TxDefaultProfile    (site-wide limit, always active)
Stack Level 1: TxProfile           (per-transaction limit from CSMS)
Stack Level 2: ChargingStationMaxProfile  (hardware max)
Stack Level 3: ExternalConstraints (ISO 15118 from vehicle)
```

```json
{
  "connectorId": 1,
  "csChargingProfiles": {
    "chargingProfileId": 42,
    "stackLevel": 0,
    "chargingProfilePurpose": "TxDefaultProfile",
    "chargingProfileKind": "Recurring",
    "recurrencyKind": "Daily",
    "chargingSchedule": {
      "duration": 86400,
      "chargingRateUnit": "W",
      "chargingSchedulePeriod": [
        {"startPeriod": 0,    "limit": 11000},
        {"startPeriod": 28800,"limit": 22000},
        {"startPeriod": 64800,"limit": 11000}
      ]
    }
  }
}
```

Off-peak (0–8h): 11kW. Peak (8–18h): 22kW. Evening (18–24h): 11kW. Update at tariff period boundaries.

## Vehicle-aware load balancing

ISO 15118 enables vehicle to communicate charging needs:

```
Vehicle → EVSE: "I need 80% SoC by 7 AM, max 11kW acceptable"
CSMS → Charger: SetChargingProfile with vehicle constraints
Charger → Vehicle: Charge at allocated power within vehicle limits
```

Without ISO 15118, CSMS allocates blindly — vehicle may request more than allocated, causing profile override events. Log override events — frequent overrides indicate allocation algorithm needs tuning.

## Capacity planning from utilization data

```python
def capacity_recommendation(site_id: str, months: int = 6) -> dict:
    history = get_utilization_history(site_id, months)
    peak_util = max(h["utilization_pct"] for h in history)
    p95_util = percentile([h["utilization_pct"] for h in history], 95)

    if p95_util > 85:
        return {"action": "add_capacity", "urgency": "high",
                "recommended_kw": site_capacity * 0.3}
    if peak_util > 95:
        return {"action": "tighten_allocation", "urgency": "medium"}
    return {"action": "monitor", "urgency": "low"}
```

Six months of utilization data informs infrastructure investment decisions — not guesswork.

## Failure modes

- **Profile not updated at tariff boundary** — peak rates applied during off-peak hours
- **No DR event handler** — utility demand response signal ignored; penalty charges
- **Site capacity hardcoded** — actual available capacity changes with other loads
- **Override events not logged** — allocation algorithm bugs undetected
- **Single profile for all connectors** — one high-priority session starves others

## Production checklist

- Charging profile stack configured with correct priority levels
- Profiles updated at tariff period boundaries (automated)
- DR event handler reduces site max and restores after event
- Per-connector allocated vs actual current monitored
- Profile override events logged and alerted
- Capacity planning based on 6-month utilization history

## Resources

- [OCPP 1.6 Smart Charging](https://www.openchargealliance.org/protocols/ocpp-protocols/ocpp-1-6/) — SetChargingProfile specification
- [OCPP 2.0.1 Smart Charging use case](https://www.openchargealliance.org/protocols/ocpp-protocols/ocpp-2-0-1/) — NotifyEVChargingNeeds
- [ISO 15118 vehicle-to-grid communication](https://www.iso.org/standard/55366.html) — vehicle charging needs protocol
- [IEA Global EV Outlook](https://www.iea.org/reports/global-ev-outlook-2024) — grid impact projections
- [OpenADR demand response standard](https://www.openadr.org/) — utility signal integration
