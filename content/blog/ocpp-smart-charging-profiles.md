---
title: "OCPP Smart Charging and Load Profiles"
slug: "ocpp-smart-charging-profiles"
description: "How OCPP smart charging works in practice: ChargingProfile hierarchy, TxProfile, load balancing across a site, and the edge cases that trip up real deployments."
datePublished: "2026-02-22"
dateModified: "2026-02-22"
tags: ["OCPP", "EV", "IoT", "Architecture"]
keywords: "OCPP smart charging, charging profiles, load management, TxProfile, ChargingProfile, demand response, EV load balancing"
faq:
  - q: "What is OCPP smart charging?"
    a: "OCPP smart charging is the mechanism by which a central system limits or shapes the power a charging station delivers, using ChargingProfile messages that describe power or current limits over time. It lets an operator keep a whole site under its grid connection limit, respond to demand-response signals, and prioritize sessions without physically capping each charger."
  - q: "What is the difference between TxProfile, TxDefaultProfile, and ChargePointMaxProfile?"
    a: "ChargePointMaxProfile sets the absolute ceiling for a whole charge point regardless of session. TxDefaultProfile applies to any transaction that starts without its own profile. TxProfile targets one specific transaction and overrides the default for that session. The effective limit at any instant is the minimum across the applicable profiles in that stacking order."
  - q: "Does smart charging need the EV to support anything special?"
    a: "No. Basic OCPP smart charging works over the standard control-pilot signaling defined in IEC 61851, so the charger simply advertises a lower current limit and any compliant EV follows it. Richer negotiation with the vehicle needs ISO 15118 high-level communication, but load management across a site works without it."
---

If you run more than a handful of chargers behind one grid connection, you will hit your supply limit long before you hit your parking-space limit. OCPP smart charging is how you avoid tripping the main breaker: instead of every charger pulling its rated current whenever a car plugs in, a central system hands each station a `ChargingProfile` — a schedule of power or current limits over time — and the station clamps its output to match. Done well, it lets you put twice as many chargers on the same feeder. Done badly, it strands drivers with 6 A trickle charges and no explanation.

I've built and debugged the smart-charging layer for an EV platform, and the protocol is deceptively simple on paper and full of ordering subtleties in production. Here's how the pieces actually fit together.

## The ChargingProfile, concretely

A `ChargingProfile` is not a single number — it's a small object with a purpose, a stacking level, and a schedule. The schedule is a list of periods, each with a start offset and a limit, expressed either in amperes or watts. A minimal TxProfile that limits a session to 16 A looks like this over the wire:

```json
{
  "chargingProfileId": 4021,
  "stackLevel": 2,
  "chargingProfilePurpose": "TxProfile",
  "chargingProfileKind": "Absolute",
  "transactionId": 90114,
  "chargingSchedule": {
    "chargingRateUnit": "A",
    "chargingSchedulePeriod": [
      { "startPeriod": 0, "limit": 16.0, "numberPhases": 3 },
      { "startPeriod": 3600, "limit": 32.0, "numberPhases": 3 }
    ]
  }
}
```

That says: for the first hour cap at 16 A per phase, then allow up to 32 A. The station is responsible for enforcing this against the pilot signal. Get the `chargingRateUnit` wrong — sending watts where the station expects amps — and you'll either throttle to nothing or fail to throttle at all, which is one of the first bugs everyone ships.

## Profile purposes and the stacking rule

The part that trips people up is that multiple profiles apply at once, and the effective limit is the **minimum** of all of them at that moment. There are three purposes, and they compose:

| Purpose | Scope | Typical use |
|---|---|---|
| `ChargePointMaxProfile` | Whole charge point, all sessions | Hardware or connection ceiling |
| `TxDefaultProfile` | Any transaction without its own profile | Site-wide default policy |
| `TxProfile` | One specific transaction | Per-session override, priority charging |

Within a purpose, `stackLevel` breaks ties — higher wins. Across purposes, they all constrain simultaneously, so if `ChargePointMaxProfile` says 32 A and an active `TxProfile` says 16 A, the car gets 16 A. The mental model I give new engineers: every profile is a ceiling, and physics obeys the lowest ceiling in the room. If you remember only that, you'll debug 80% of "why is this car charging slow" tickets correctly.

## Load balancing across a site

The reason all this machinery exists is dynamic load management. Say you have a 100 kW grid connection and eight 22 kW chargers — that's 176 kW of nameplate demand into a 100 kW pipe. Static allocation (give each charger 12.5 kW forever) wastes capacity because most stalls sit idle. The better approach is a control loop:

- Poll each active transaction for its actual draw via `MeterValues`.
- Compute headroom: connection limit minus current total draw, minus a safety margin.
- Redistribute headroom across active sessions, respecting per-session minimums (a car below ~6 A may stop charging entirely).
- Push updated `TxProfile` or `TxDefaultProfile` messages via `SetChargingProfile`.

The trap I keep seeing is running this loop too fast. EVs don't respond to a new limit instantly — there's a control-pilot ramp measured in seconds, and some vehicles pause and renegotiate. Recompute every 30–60 seconds, damp your changes, and never oscillate a car between 6 A and 32 A because your loop is chasing meter noise. This is the same discipline that separates OCPP 1.6 and 2.0.1 deployments in practice, and it's worth understanding [how OCPP 2.0.1 differs from 1.6](https://blog.michaelsam94.com/ocpp-2-0-1-vs-1-6/) before you commit to a smart-charging design, because the profile model got richer in 2.0.1.

## Composite schedule: what will actually happen

Before you trust your stacking logic, ask the station. OCPP defines `GetCompositeSchedule`, which asks a charge point to flatten all applicable profiles into the single schedule it intends to enforce over a requested window. This is the single most useful debugging tool in the smart-charging toolbox — it turns "I think the car should get 16 A" into "the station reports it will deliver 16 A for the next 1800 seconds." I lean on it heavily during commissioning:

```kotlin
val request = GetCompositeScheduleRequest(
    connectorId = 1,
    duration = 1800,          // seconds
    chargingRateUnit = ChargingRateUnit.A,
)
val composite = station.send(request).await()
// composite.chargingSchedule now shows the *resolved* limits,
// after stacking every applicable profile — trust this over your model
```

If the composite schedule disagrees with what you expected, your bug is in profile construction, not in the station. That distinction saves hours.

## Demand response and time-of-use

Smart charging isn't only about staying under a breaker. The same profiles express demand-response and time-of-use policy. A utility signal that says "shed 40% of EV load for the next hour" becomes a `ChargePointMaxProfile` with a `Recurring` or `Absolute` schedule dropping the ceiling. Off-peak overnight rates become a `TxDefaultProfile` that ramps limits up after midnight. Because everything reduces to time-indexed limits, one mechanism covers grid protection, cost optimization, and utility programs.

The senior-engineer opinion here: keep policy out of the station. The charge point should be a dumb enforcer of whatever schedule it's handed; all the intelligence — grid limits, tariffs, fairness, priority — lives in your central system where you can test it, version it, and roll it back. Chargers in the field are the hardest thing to update, so push logic to where it's cheap to change. If you're designing the broader system, this fits into the same layering I described in [how I architected an EV charging platform](https://blog.michaelsam94.com/how-i-architected-an-ev-charging-platform/), where the load-management service is deliberately separate from the OCPP gateway.

## Edge cases that cost you real money

A few failures that only show up in the field:

- **Profile persistence across reboots.** A station that forgets its `ChargePointMaxProfile` on power-cycle will happily pull full current on reconnect. Re-assert critical profiles when a station comes back online.
- **Clock skew.** `Absolute` and `Recurring` schedules depend on the station's clock. If it's hours off, your overnight tariff fires at the wrong time. Sync time aggressively.
- **Minimum charge current.** Below roughly 6 A, many EVs stop rather than trickle. If your load balancer drives a session that low to free headroom, you've effectively cancelled a charge. Reserve minimums.
- **Phase awareness.** A 16 A limit on single-phase and three-phase are very different power levels. Respect `numberPhases` or your kilowatt math is wrong.

Smart charging is one of those features that looks like a config toggle and turns out to be a distributed control system with real hardware, real clocks, and real cars that don't do what the spec implies. Model it as ceilings, verify with composite schedules, keep the policy central, and it becomes reliable — which, for something standing between a parking lot and a substation, is the only acceptable outcome.

## Resources

- [OCPP specifications — Open Charge Alliance](https://openchargealliance.org/protocols/open-charge-point-protocol/)
- [IEC 61851 — EV conductive charging system (overview)](https://www.iec.ch/homepage)
- [ISO 15118 — Vehicle to grid communication interface](https://www.iso.org/standard/77845.html)
- [OpenADR — demand response standard](https://www.openadr.org/)
- [SteVe — open-source OCPP central system](https://github.com/steve-community/steve)
