---
title: "How I Architected an EV Charging Platform (OCPP, WebSocket, Flutter)"
seoTitle: "Architecting an EV Charging Platform with OCPP & Flutter"
slug: "how-i-architected-an-ev-charging-platform"
description: "A walkthrough of an EV charging platform: OCPP 1.6 over WebSocket, a Node.js middleware layer, sub-100ms local control, and a Flutter app — with key decisions."
datePublished: "2026-06-04"
dateModified: "2026-06-04"
tags: ["Flutter", "OCPP", "WebSocket", "Architecture", "IoT"]
keywords: "EV charging platform architecture, OCPP 1.6, OCPP WebSocket, OCPP developer, OCPP expert, Open Charge Point Protocol, charging station protocol, Flutter IoT app, charging management system, real-time mobile architecture"
faq:
  - q: "What is OCPP and why does it matter for EV charging?"
    a: "OCPP (Open Charge Point Protocol) is the open standard that lets charging stations and management systems communicate. Running OCPP 1.6 over WebSocket kept the platform vendor-neutral."
  - q: "How did the platform achieve sub-100ms local control?"
    a: "A peer-to-peer local control path let the app talk directly to the charger on the same network, avoiding a cloud round-trip so start and stop actions felt instant."
  - q: "Why add a Node.js middleware layer?"
    a: "The Node.js middleware brokered OCPP WebSocket sessions, normalized messages, and isolated charger quirks from the app, which simplified the client and improved reliability."
---

Charging an electric vehicle looks simple from the driver's seat: tap, plug in, watch the kilowatts climb. Underneath is a real-time distributed system speaking a 15-year-old industrial protocol to hardware you don't control, over networks that drop. I led the architecture for one such platform end-to-end — the charging management backend, the protocol middleware, and the Flutter apps. It shipped with **zero critical post-launch defects**. Here's how it was put together and why each layer exists.

## The shape of the problem

Three constraints drove every decision:

1. **The protocol is fixed.** Chargers speak [OCPP](https://www.openchargealliance.org/) (Open Charge Point Protocol) 1.6 over WebSocket. You adapt to it; it does not adapt to you.
2. **It's bidirectional and stateful.** A charger reports status changes (`StatusNotification`), meter values, and transaction events on its own schedule; the backend issues commands (`RemoteStartTransaction`, `Reset`) back down the same socket. There is no clean request/response — it's a long-lived conversation.
3. **The network is hostile.** Chargers sit on cellular or shaky site Wi-Fi. Sockets drop mid-session, and a dropped socket must never mean a lost or double-charged transaction.

## Layered architecture

I split the system into four layers, each with one job, so failures stay contained:

```
┌──────────────┐   OCPP 1.6 / WS   ┌──────────────────┐
│   Charger    │ ───────────────▶  │  OCPP Server      │  Python
│  (hardware)  │ ◀───────────────  │  (protocol core)  │  state machine
└──────────────┘                   └─────────┬─────────┘
                                             │ internal events
                                   ┌─────────▼─────────┐
                                   │  Node.js          │  WebSocket
                                   │  middleware/gateway│  fan-out + auth
                                   └─────────┬─────────┘
                                             │ app-facing WS / REST
                                   ┌─────────▼─────────┐
                                   │  Flutter app       │  drivers + ops
                                   └────────────────────┘
```

**The OCPP server (Python).** This is the protocol's home and the single source of truth for charger state. It implements OCPP 1.6 as an explicit state machine — `Available → Preparing → Charging → Finishing → Available` — and refuses to leave a state on an unexpected message instead of guessing. Keeping every protocol quirk *here* meant the rest of the stack never had to know OCPP existed.

**The Node.js middleware.** Apps must not talk OCPP, and they must not hold a socket open to every charger. The middleware is the gateway: it authenticates app clients, translates charger-state events into a clean app-facing schema, and fans a single charger update out to every subscribed app. It also enforces authorization — *this* user may start *that* charger — so the protocol layer stays purely about the protocol.

**The Flutter app.** One codebase served both drivers and site operators, with [Riverpod state and real-time WebSocket sync](https://blog.michaelsam94.com/flutter-riverpod-state-management/). The app treats the backend as the source of truth and itself as a renderer of pushed state — which is what kept the UI honest when networks misbehaved.

## Idempotency: the rule that prevented disasters

The most important architectural rule in the whole platform: **every state-changing operation is idempotent and carries a transaction id.** When a socket drops mid-`StartTransaction`, the charger may retry; the network may deliver a message twice. If "start charging" weren't idempotent, a retry could open a second billable session.

So transactions are keyed by an id the server assigns and both sides echo. Replaying the same `StartTransaction` for an id that's already active is a no-op that returns the existing session, not a new one. Meter values are upserts keyed by `(transactionId, timestamp)`. This single discipline is the reason a flaky link produced reconnections instead of phantom charges or double-billing.

## Sub-100ms P2P local control

One feature needed latency the cloud round-trip couldn't deliver: when the phone and charger are on the same local network, the app controls the charger **directly**, peer-to-peer, with sub-100ms sync — no trip to the backend. The architecture supports this because the command schema is identical whether it arrives via the cloud middleware or the local link; only the transport changes. The app discovers the charger on the LAN, opens a direct channel, and falls back to the cloud path transparently when they're apart. Designing the command layer to be transport-agnostic from day one is what made this possible without a parallel code path.

## Designing for the network that fails

Resilience was built in, not bolted on:

- **Heartbeats and timeouts.** OCPP `Heartbeat` plus app-level pings detect a dead socket in seconds rather than waiting for TCP to give up.
- **Reconnect with state reconciliation.** On reconnect, a charger resyncs its current status and any transaction in flight, so the server's state machine reconciles rather than assumes.
- **Honest UI.** The app never shows stale data as live — a degraded connection surfaces as "Reconnecting…", and the displayed charger state is re-fetched before resuming live updates.

## Why it shipped clean

Zero critical post-launch defects wasn't luck; it came from the boundaries:

- Protocol complexity was **quarantined** in the Python state machine, so a malformed charger message could never corrupt app state.
- Idempotency made retries safe by construction, eliminating the entire class of double-charge bugs.
- A transport-agnostic command schema meant local and cloud paths shared the same tested logic.
- The app trusted the backend as the source of truth, so there was no client-side state to drift.

## Takeaways for any real-time IoT platform

- Quarantine the messy protocol behind one explicit state machine; let nothing else speak it.
- Make every state-changing operation idempotent and id-keyed before you write the happy path.
- Separate the gateway/auth/fan-out concern from the protocol concern.
- Design commands to be transport-agnostic so local and remote paths reuse one code path.
- Treat connectivity as first-class state and make the UI honest about it.

Real-time hardware platforms reward boring, strict boundaries. The interesting behavior — instant local control, clean reconnection, accurate billing — falls out of getting the unglamorous parts right.

## Resources

- [OCPP 1.6 specification](https://www.openchargealliance.org/protocols/ocpp-16/)
- [OCPP 2.0.1 specification](https://www.openchargealliance.org/protocols/ocpp-201/)
- [ISO 15118 — Vehicle-to-grid communication](https://www.iso.org/standard/69146.html)
- [WebSocket RFC 6455](https://datatracker.ietf.org/doc/html/rfc6455)

*Working on OCPP, EV charging, IoT, or real-time mobile infrastructure? [I'd love to help](/#contact) as an OCPP developer or OCPP consultant.*
