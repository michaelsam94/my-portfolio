---
title: "Digital Twins: From Buzzword to Architecture"
slug: "digital-twins-architecture"
description: "A pragmatic look at digital twin architecture: what a digital twin actually is, the telemetry-to-model pipeline, state management, simulation, and where they pay off."
datePublished: "2026-07-11"
dateModified: "2026-07-11"
tags: ["Digital Twins", "IoT", "Architecture", "Real-Time Systems"]
keywords: "digital twin, digital twins, IoT digital twin, simulation, real-time model, telemetry, state management"
faq:
  - q: "What is a digital twin, really?"
    a: "A digital twin is a live software model of a physical asset, kept in sync with reality by a stream of telemetry. It's more than a dashboard: it holds current state, history, and often a simulation model, so you can query the asset's condition and predict its behavior without touching the physical thing."
  - q: "What's the difference between a digital twin and a database record?"
    a: "A database record stores the last known values. A digital twin adds a behavioral model and continuous synchronization — it doesn't just remember the temperature, it can model how the temperature will evolve, detect anomalies, and simulate what-if scenarios against the real asset's current state."
  - q: "Do I need a special platform to build a digital twin?"
    a: "Not necessarily. Platforms like Azure Digital Twins provide a modeling language and graph, which help at large scale, but many effective twins are built from ordinary components: a telemetry pipeline, a state store, a model, and an API. Start with the pipeline and model before reaching for a platform."
---

Strip away the marketing and a digital twin is a living software model of a physical thing, kept honest by a continuous feed of telemetry. Not a 3D render, not a dashboard — a model that holds the current state of an asset, remembers its history, and can often simulate its future. The physical device sends data; the twin reflects it, reasons about it, and answers questions you'd otherwise have to inspect the hardware to answer. That's the whole idea, and once you see it as an architecture rather than a product category, it becomes buildable with components you already know.

I've built systems that were digital twins in everything but name — a backend maintaining the authoritative live state of physical devices from a telemetry stream. The EV chargers in my [charging platform](https://blog.michaelsam94.com/how-i-architected-an-ev-charging-platform/) each had a server-side representation tracking connector status, active sessions, and health, updated in real time. Call it a twin or call it a stateful device model; the architecture is the same.

## The three parts every twin has

Regardless of domain, a digital twin decomposes into three layers:

1. **Ingestion** — telemetry flows in from the physical asset, usually over MQTT or a similar protocol, at whatever rate and reliability the device manages.
2. **State** — the twin maintains the current authoritative state plus enough history to reason over trends.
3. **Model + interface** — a behavioral model (rules, physics, or ML) plus an API that lets applications query and simulate against the twin.

Most "digital twin" projects that stall do so because they treat it as step 3 — the fancy simulation — before nailing steps 1 and 2. Without reliable ingestion and trustworthy state, the model is fiction rendered convincingly.

## Ingestion: garbage in, garbage twin

The twin is only as accurate as the telemetry keeping it in sync. That means the ingestion layer inherits every hard problem of real-time IoT: unreliable networks, out-of-order messages, duplicate deliveries, and clock skew between devices. MQTT is the common transport here — I covered scaling it in [MQTT for IoT at scale](https://blog.michaelsam94.com/mqtt-iot-at-scale/) — and the twin's ingestion has to be idempotent because at-least-once delivery *will* send duplicates.

Timestamping discipline matters enormously. If the twin fuses readings from multiple sensors, it has to align them by when they were actually measured, not when they arrived — the exact [clock-sync and event-time problem](https://blog.michaelsam94.com/sensor-fusion-clock-sync-real-time/) that quietly corrupts real-time systems. A twin that orders events by arrival time will occasionally show the physical asset doing impossible things.

## State: the hard part nobody demos

The demo shows a spinning 3D model. The engineering is in the state layer. A good twin separates:

- **Reported state** — what the device last told us (from telemetry).
- **Desired state** — what we want the device to be (commands not yet acknowledged).
- **Derived state** — computed properties: health scores, anomaly flags, aggregates.

This reported/desired split is exactly the "device shadow" pattern from AWS IoT and Azure, and it exists because devices go offline. When a charger drops its connection, the twin still holds its last reported state and any pending desired changes, reconciling when it reconnects. Modeling this explicitly is what separates a twin from a `devices` table that's stale the moment a device disconnects.

```json
// A device shadow / twin state document
{
  "deviceId": "charger-7",
  "reported": { "status": "charging", "powerKw": 48.2, "ts": 1710000000 },
  "desired":  { "maxPowerKw": 50 },
  "derived":  { "healthy": true, "utilization24h": 0.63 },
  "lastSeen": 1710000000,
  "connected": true
}
```

## The model: rules first, ML later

The "twin" part — the ability to reason and predict — ranges from simple to sophisticated:

| Model type | Example | When |
| --- | --- | --- |
| Rule-based | "Alert if temp > 80°C for 5 min" | Start here; most value, least effort |
| Physics/analytical | Thermal or wear model from equations | When domain physics is well understood |
| ML/statistical | Anomaly detection, remaining-useful-life | When you have history and patterns aren't obvious |

Almost every twin should start with rule-based logic. It's transparent, debuggable, and delivers most of the operational value — presence detection, threshold alerts, utilization tracking. Reach for physics or ML models once the basics are solid and you have a specific prediction that rules can't express. Building the ML twin first is a classic way to spend six months and ship nothing that operators trust.

## Where twins actually pay off

Digital twins aren't worth the complexity for everything. They pay off when the physical asset is expensive to inspect, operates continuously, and benefits from prediction:

- **Predictive maintenance** — model wear from telemetry, service before failure.
- **Remote monitoring at scale** — one operator watching thousands of assets through their twins instead of physical checks.
- **What-if simulation** — test a control change against the twin's current state before applying it to hardware, which is invaluable when the hardware is a robot, a turbine, or a live charging site.
- **Fleet optimization** — aggregate twins to balance load, as with smart charging across a network of stations.

For a single cheap sensor, a twin is overkill; a state table does fine. The value scales with asset cost, fleet size, and the cost of being wrong about the physical world.

## How I'd build one today

Concretely, for a new twin: stand up reliable MQTT ingestion with idempotent, event-time-ordered processing; model reported/desired/derived state explicitly with a shadow-style document per asset; expose a clean query-and-command API; add rule-based derived state for the alerts operators need on day one; and only then layer in simulation or ML where a specific prediction justifies it. Reach for a dedicated platform like [Azure Digital Twins](https://learn.microsoft.com/en-us/azure/digital-twins/) when the relationships between assets — a graph of sites, chargers, and connectors — become the thing you're modeling, not just individual devices.

A digital twin is less a product you buy than an architecture you assemble: telemetry in, honest state, a model that earns operators' trust, and an API that lets the rest of the system treat the physical world as a queryable object. Build it in that order and it stops being a buzzword.

## Resources

- [Azure Digital Twins documentation](https://learn.microsoft.com/en-us/azure/digital-twins/)
- [AWS IoT Device Shadow service](https://docs.aws.amazon.com/iot/latest/developerguide/iot-device-shadows.html)
- [Digital Twin Consortium](https://www.digitaltwinconsortium.org/)
- [Eclipse Ditto — open-source digital twin framework](https://eclipse.dev/ditto/)
- [NIST — Digital Twin research](https://www.nist.gov/programs-projects/digital-twins)
- [MQTT.org — telemetry transport](https://mqtt.org/)
