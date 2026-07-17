---
title: "OCPP 2.0.1 vs 1.6: What Changed for EV Charging"
seoTitle: "OCPP 2.0.1 vs 1.6: What Changed for EV Charging"
slug: "ocpp-2-0-1-vs-1-6"
description: "A field comparison of OCPP 2.0.1 vs 1.6 from someone who built a charging platform: device model, security, smart charging, ISO 15118, and migration reality."
datePublished: "2026-07-14"
dateModified: "2026-07-17"
tags: ["OCPP", "EV Charging", "IoT", "Protocols"]
keywords: "OCPP 2.0.1, OCPP 1.6, EV charging protocol, OCPP comparison, charging station, smart charging, ISO 15118"
faq:
  - q: "What's the biggest difference between OCPP 1.6 and 2.0.1?"
    a: "OCPP 2.0.1 introduces a structured device model, built-in security profiles, richer smart charging, and support for ISO 15118 Plug & Charge. Where 1.6 was a flat set of messages, 2.0.1 gives each charger a self-describing set of components and variables the backend can query and configure."
  - q: "Should I build a new charging platform on 1.6 or 2.0.1?"
    a: "For new builds targeting the long term, 2.0.1 is the right foundation — especially if you need Plug & Charge, strong security, or advanced smart charging. But 1.6J is still the most widely deployed in the field, so most real platforms support both for years."
  - q: "Is OCPP 1.6 still relevant in 2026?"
    a: "Very. A huge installed base of chargers speaks 1.6J over WebSocket, and hardware lives in the field for a decade. Any production Charging Station Management System has to keep supporting 1.6 while adding 2.0.1 for newer hardware."
---

When I architected an EV charging platform, the OCPP version question wasn't academic — it decided how the backend talked to every charger in the field, how we did firmware updates, and whether we could offer Plug & Charge later. The short version: OCPP 1.6 is the workhorse that most deployed hardware still speaks, and 2.0.1 is the structured, secure, future-facing evolution you want for new builds. In practice a serious platform supports both, because chargers stay in the ground for ten years and you don't get to retire 1.6 on your schedule.

I've written up the broader platform decisions in [how I architected an EV charging platform](https://blog.michaelsam94.com/how-i-architected-an-ev-charging-platform/); this post zooms in on the protocol itself — what actually changed between 1.6 and 2.0.1, and where those changes bite you during implementation.

## Both still run over WebSocket

First, what didn't change: transport. OCPP 1.6J and 2.0.1 both run JSON over a WebSocket connection initiated by the charger to the Charging Station Management System (CSMS). The charger is the WebSocket client, the CSMS is the server, and messages are the same call/result/error RPC pattern. If you've built the 1.6 WebSocket layer — connection handling, heartbeats, reconnection, message correlation by unique ID — that plumbing carries over. The [WebSocket architecture](https://blog.michaelsam94.com/websocket-architecture-at-scale/) concerns (connection scaling, backpressure, dropped-connection recovery) are identical; what changes is the vocabulary spoken over the socket.

## The device model: the headline change

OCPP 1.6 is essentially a flat list of messages and a loose set of configuration keys accessed via `GetConfiguration` / `ChangeConfiguration` — string keys, string values, and a lot of vendor-specific interpretation. It works, but the backend never really *knows* what a charger is; it just sends messages and hopes.

2.0.1 introduces a proper **device model**: a charger is described as a tree of Components (like `Connector`, `EVSE`, `SmartChargingCtrlr`) each with Variables that have types, mutability, and characteristics. The backend queries structure with `GetVariables` and configures with `SetVariables`:

```json
// OCPP 2.0.1 — read a typed variable from a component
{
  "getVariableData": [{
    "component": { "name": "SmartChargingCtrlr" },
    "variable": { "name": "LimitChangeSignificance" }
  }]
}
```

This is a genuine step up operationally. You can discover a charger's capabilities instead of maintaining a spreadsheet of vendor quirks, and configuration becomes typed rather than a stringly-typed guessing game.

## Security: from bolt-on to built-in

Security is where 1.6 shows its age. The original 1.6 spec had essentially no security story; the later 1.6 security whitepaper added TLS and authentication as an extension, but it's optional and inconsistently implemented. In the field I saw plenty of 1.6 deployments running plain `ws://` on a private APN and calling it good enough — which it mostly was, until it wasn't.

2.0.1 bakes in three **security profiles**:

| Profile | Auth | Transport |
| --- | --- | --- |
| 1 | HTTP Basic auth | TLS |
| 2 | HTTP Basic auth + charger cert | TLS |
| 3 | Mutual TLS (client certificates) | TLS |

Profile 3 with mutual TLS is what you want for public infrastructure — the charger and CSMS authenticate each other with certificates, and 2.0.1 includes the certificate management messages (`InstallCertificate`, `CertificateSigned`) to rotate them over the air. That certificate lifecycle is a real chunk of implementation work, but it's the difference between "trusts the network" and "trusts the peer," which matters the moment your chargers sit on the public internet.

## Smart charging and ISO 15118

1.6 has smart charging via charging profiles, and it's usable — you can set power limits and schedules. 2.0.1 extends it substantially with more granular profiles, better support for load balancing across an EVSE, and the hooks for **ISO 15118 Plug & Charge**, where the car and charger authenticate and authorize the session over the charging cable itself, no app or RFID card needed. If Plug & Charge is on your roadmap, that's a strong reason to build on 2.0.1 — retrofitting it onto a 1.6 core is painful.

## Transactions and messaging cleanup

2.0.1 also tidied up the transaction model. 1.6 used `StartTransaction` / `StopTransaction` with a transaction ID assigned by the backend; 2.0.1 uses a unified `TransactionEvent` message (Started / Updated / Ended) with the charger owning the transaction ID. The 2.0.1 model is cleaner for handling offline transactions and metering, but it means your backend's transaction state machine is genuinely different code, not a tweak. When you support both protocols, you effectively maintain two transaction handlers behind a common internal event model.

## The migration reality

Here's the honest operational picture. You can't flip a fleet from 1.6 to 2.0.1 — chargers are hardware, firmware updates are risky, and a lot of deployed units will never get a 2.0.1 firmware. So a production CSMS does this:

1. Terminates both 1.6J and 2.0.1 WebSocket connections, negotiating the subprotocol during the handshake (`Sec-WebSocket-Protocol: ocpp1.6` vs `ocpp2.0.1`).
2. Normalizes both into a **common internal domain model** so the rest of the platform — billing, smart charging, monitoring — doesn't care which protocol a given charger speaks.
3. Adds 2.0.1-only features (Plug & Charge, richer diagnostics) behind capability checks so 1.6 chargers degrade gracefully.

That internal abstraction is the single most important design decision. Get it right and adding 2.0.1 is additive; get it wrong and every new feature forks into two codepaths forever. This is the same idempotency-and-state discipline that shows up across [distributed systems](https://blog.michaelsam94.com/idempotency-distributed-systems/) — chargers reconnect, replay messages, and go offline mid-transaction, so both protocol handlers need to treat duplicate and out-of-order messages as normal.

For a new platform in 2026, I'd build the core on 2.0.1's model and adapt 1.6 into it. For an existing 1.6 platform, I'd add 2.0.1 alongside rather than migrate — because the field decides your timeline, not the spec.

## Message mapping cheat sheet

Dual-protocol CSMS code rots when message mapping lives in developers' heads. Maintain an explicit table:

| Concern | OCPP 1.6 | OCPP 2.0.1 |
|---------|----------|------------|
| Start session | `StartTransaction` | `TransactionEvent` (Started) |
| Meter data | `MeterValues` | `TransactionEvent` (Updated) + Metering component |
| Stop session | `StopTransaction` | `TransactionEvent` (Ended) |
| Remote start | `RemoteStartTransaction` | `RequestStartTransaction` |
| Config change | `ChangeConfiguration` | `SetVariables` |
| Connector status | `StatusNotification` | Device Model `AvailabilityState` + `NotifyEvent` |
| Auth | `Authorize` + `StartTransaction` | `Authorize` + `TransactionEvent` with `idToken` |
| Firmware | `UpdateFirmware` | `FirmwareStatusNotification` + signed `UpdateFirmware` |

Your normalization layer should emit internal events (`session.started`, `session.metered`, `session.ended`) regardless of protocol. Billing, OCPI session export, and demand-response modules consume those events — never OCPP JSON directly.

## DisplayMessage, diagnostics, and operator UX

OCPP 2.0.1 adds `SetDisplayMessage` and richer `GetLog` / `CustomerInformation` use cases that 1.6 handled with vendor-specific extensions. Fleet operators notice this immediately: unified fault messages on charger screens, standardized log upload requests, and tariff display without proprietary middleware.

1.6 deployments often relied on manufacturer cloud portals for diagnostics — acceptable for 50 chargers, painful at 5,000. If your migration pitch to operations includes "one pane of glass," these 2.0.1-only features matter as much as TLS.

## Certification and procurement language

RFPs increasingly specify "OCPP 2.0.1 with Security Profile 3." Hardware procured as "1.6J compatible" may never receive 2.0.1 firmware. Lock firmware upgrade path and 2.0.1 certification status in purchase contracts. Budget engineering time for **two** OCPP test harnesses through at least one full release cycle — message schemas, state machines, and error codes all differ enough that shared test cases give false confidence.

## Resources

- [Open Charge Alliance — OCPP downloads](https://openchargealliance.org/protocols/open-charge-point-protocol/)
- [OCPP 2.0.1 specification (Open Charge Alliance)](https://openchargealliance.org/protocols/open-charge-point-protocol/#OCPP2.0.1)
- [OCPP 1.6 specification](https://openchargealliance.org/protocols/open-charge-point-protocol/#OCPP1.6)
- [ISO 15118 — Vehicle to grid communication interface](https://www.iso.org/standard/77845.html)
- [Open Charge Alliance certification](https://openchargealliance.org/certification/)
- [RFC 6455 — The WebSocket Protocol](https://datatracker.ietf.org/doc/html/rfc6455)