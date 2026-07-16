---
title: "CoAP for Constrained IoT Devices"
slug: "coap-constrained-devices"
description: "CoAP for constrained IoT devices explained: the RFC 7252 request-response model, DTLS security, Observe for push, and how it compares to MQTT and HTTP on tiny hardware."
datePublished: "2026-05-13"
dateModified: "2026-05-13"
tags: ["IoT", "Protocols", "Embedded"]
keywords: "CoAP, constrained devices, RFC 7252, DTLS, observe CoAP, low power IoT, UDP IoT protocol"
faq:
  - q: "What is CoAP?"
    a: "CoAP (Constrained Application Protocol, RFC 7252) is a lightweight request-response protocol designed for constrained devices and low-power networks. It offers a RESTful model like HTTP — GET, POST, PUT, DELETE on resources identified by URIs — but runs over UDP with tiny binary headers, optional reliability, and security via DTLS, making it suitable for microcontrollers with kilobytes of RAM."
  - q: "How is CoAP different from MQTT?"
    a: "CoAP is a request-response protocol over UDP with a RESTful resource model, ideal for occasional reads and writes directly to a device. MQTT is a publish-subscribe protocol over TCP that routes messages through a central broker, ideal for streaming telemetry to many consumers. CoAP suits device-centric interactions and firmware-constrained nodes; MQTT suits event distribution and fan-out at scale."
  - q: "Is CoAP secure?"
    a: "CoAP itself has no built-in security, but the standard pairs it with DTLS (Datagram TLS) to provide encryption, integrity, and authentication over UDP — this combination is often called CoAPs and uses port 5684. DTLS supports pre-shared keys, raw public keys, and certificates, though the handshake cost and packet overhead are real considerations on very constrained hardware."
---

When your device has 32 KB of RAM, a coin-cell battery expected to last years, and a radio that sleeps most of the time, HTTP over TCP is a non-starter — the handshakes, header bloat, and connection state cost too much energy and memory. CoAP, the Constrained Application Protocol defined in RFC 7252, exists for exactly this class of hardware. It gives you a familiar RESTful model — resources at URIs, GET/POST/PUT/DELETE, response codes — but squeezes it into compact binary messages over UDP, so a microcontroller can speak it without a heavyweight networking stack.

I like CoAP for the honest reason that it respects the constraints instead of pretending they don't exist. It's not trying to be a general-purpose web protocol; it's trying to let a sensor talk without draining its battery. Here's how it does that and when it's the right pick.

## REST, but shrunk to fit

If you know HTTP, you already understand CoAP's shape. A client sends a method to a URI, the server returns a response code and payload. The difference is entirely in the packaging. A CoAP header is 4 bytes. Methods and codes are single bytes. Options (CoAP's equivalent of headers) are delta-encoded so common cases cost almost nothing. The result is a request that can fit — headers and all — in a single small UDP datagram, often under 20 bytes.

That compactness isn't cosmetic. On a low-power wireless link, every byte transmitted is energy spent and airtime consumed. A protocol that turns a sensor read into one tiny packet instead of a multi-segment TCP exchange directly extends battery life. The design goal of RFC 7252 was to make the common case — read a value, write a setpoint — as cheap as physically possible.

## Reliability without TCP

CoAP runs over UDP, which has no delivery guarantees, so it adds its own lightweight reliability where you want it. Every message is one of four types:

| Type | Meaning | Use |
|---|---|---|
| CON (Confirmable) | Must be acknowledged | Important reads/writes |
| NON (Non-confirmable) | Fire and forget | Frequent, loss-tolerant telemetry |
| ACK | Acknowledges a CON | Automatic |
| RST | Rejects a message | Error / unknown |

A confirmable message is retransmitted with exponential backoff until acknowledged, giving you TCP-like reliability for the requests that need it, per-message, without holding open a connection. For a stream of temperature readings where losing one doesn't matter, you send NON and skip the overhead entirely. This per-message choice is one of CoAP's quietly clever decisions — you pay for reliability only where it earns its keep.

## Observe: push without a broker

Plain request-response means the client polls, which is wasteful if it wants updates. CoAP's Observe extension (RFC 7641) fixes this: a client registers interest in a resource, and the server pushes notifications when the value changes, reusing the same request. It's a subscription model without a separate broker in the middle.

```text
Client                          Server (sensor)
  |  GET /temperature           |
  |  Observe: 0 (register)      |
  |---------------------------->|
  |  2.05 Content, Observe: 12  |   <- current value
  |<----------------------------|
  |                             |   (value changes)
  |  2.05 Content, Observe: 13  |   <- pushed update
  |<----------------------------|
  |  2.05 Content, Observe: 14  |
  |<----------------------------|
```

The increasing Observe number lets the client detect reordered or stale notifications over UDP. For a device that wakes, publishes, and sleeps, Observe gives you event-driven behavior without the always-on TCP connection that a broker-based protocol would need. That said, if your architecture is fundamentally about fanning one event out to many consumers, a broker is the better tool — the tradeoff is the same one I laid out in [MQTT for IoT at scale](https://blog.michaelsam94.com/mqtt-iot-at-scale/), where pub/sub decoupling beats point-to-point.

## Security: DTLS and its costs

CoAP has no security on its own; you layer DTLS underneath it — Datagram TLS, TLS adapted for the unreliable, connectionless world of UDP. The combination (sometimes called CoAPs, on port 5684) gives you encryption, integrity, and authentication with several credential modes:

- **Pre-shared keys (PSK)** — cheapest, good for closed fleets where you can provision keys.
- **Raw public keys** — asymmetric without full certificate machinery.
- **Certificates** — full PKI, most expensive on tiny hardware.

The honest caveat: DTLS handshakes cost RAM, flash, CPU, and packets, all of which are scarce on the devices CoAP targets. On a genuinely tiny node the handshake can dominate your energy budget. Techniques like connection ID and session resumption help, and OSCORE (RFC 8613) offers an alternative that protects the CoAP message layer directly and survives proxies. Choose PSK when you can; reach for certificates only when the fleet's trust model demands it.

## When CoAP is the right call — and when it isn't

I reach for CoAP when the device is severely constrained, the network is lossy and low-power (6LoWPAN, Thread, NB-IoT), and the interaction is genuinely device-centric — read this sensor, set this actuator. Its RESTful model also maps cleanly onto HTTP through a proxy, so a constrained device can be addressed almost like a web resource from the outside.

I don't reach for it when the job is high-fanout event distribution to many backend consumers, or when I need the operational maturity and broker ecosystem that MQTT brings. And on the plant floor, where the real challenge is talking to legacy equipment, neither CoAP nor MQTT is the starting point — that's a protocol-translation problem I covered in [Modbus and industrial IoT gateways](https://blog.michaelsam94.com/modbus-industrial-gateways/), where a gateway bridges old fieldbuses into whatever modern transport you prefer.

A rough decision line I use: if the constraint is the *device*, look hard at CoAP; if the constraint is the *distribution pattern*, look at MQTT; if the constraint is *legacy hardware*, you need a gateway before you need either. They're not competitors so much as tools for different bottlenecks.

CoAP is a small, focused protocol that does one thing well — RESTful interaction on hardware too small for the normal web stack. Used within its niche, it's an elegant fit; pushed outside it, you'll fight it. Respect the constraints it was built for and it repays you in battery life and simplicity.

## Resources

- [RFC 7252 — The Constrained Application Protocol (CoAP)](https://datatracker.ietf.org/doc/html/rfc7252)
- [RFC 7641 — Observing Resources in CoAP](https://datatracker.ietf.org/doc/html/rfc7641)
- [RFC 8613 — Object Security for Constrained RESTful Environments (OSCORE)](https://datatracker.ietf.org/doc/html/rfc8613)
- [RFC 6347 — Datagram Transport Layer Security 1.2](https://datatracker.ietf.org/doc/html/rfc6347)
- [Eclipse Californium — CoAP framework for Java](https://github.com/eclipse-californium/californium)
- [libcoap — C implementation of CoAP](https://libcoap.net/)
