---
title: "ISO 15118 Plug and Charge Explained"
slug: "iso-15118-plug-and-charge"
description: "ISO 15118 Plug and Charge explained for engineers: the PKI, certificate chains, TLS handshake, contract certificates, and why V2G high-level communication is hard."
datePublished: "2026-03-19"
dateModified: "2026-03-19"
tags: ["EV", "IoT", "Security", "Protocols"]
keywords: "ISO 15118, plug and charge, PnC, V2G, EV certificates, PKI EV charging, high level communication"
faq:
  - q: "What is ISO 15118 Plug and Charge?"
    a: "ISO 15118 Plug and Charge (PnC) is a standard that lets an electric vehicle authenticate and authorize a charging session automatically by exchanging digital certificates with the charger, with no app, RFID card, or payment terminal. When you plug in, the car and charger negotiate identity and billing over a secure channel, and charging simply starts."
  - q: "How does the ISO 15118 PKI work?"
    a: "ISO 15118 relies on a public key infrastructure with several certificate chains: a V2G root that anchors trust, an OEM provisioning chain that identifies the vehicle, a contract chain (the eMAID) tied to a mobility contract, and charge point operator certificates. The vehicle presents a contract certificate, the charger validates it back to a trusted root, and a mutual TLS channel protects the exchange."
  - q: "Is Plug and Charge the same as autocharge?"
    a: "No. Autocharge is a simpler, non-standard trick that identifies a vehicle by its MAC address or EVCCID and maps it to an account, with no cryptographic proof. Plug and Charge is the ISO 15118 standard using signed certificates and mutual TLS, so it is far harder to spoof and supports proper contract-based billing across networks."
---

Plug in, walk away, get billed correctly — that's the entire user-facing promise of ISO 15118 Plug and Charge. Behind that one-sentence experience sits a full public key infrastructure, a TLS handshake between a car and a wall, and four different certificate chains that all have to validate in the couple of seconds before a driver starts wondering why nothing is happening. PnC is genuinely good UX built on genuinely serious cryptography, and the gap between those two facts is where most implementation pain lives.

I came to ISO 15118 from the charger operator side, and the thing nobody tells you upfront is that "Plug and Charge" is a small feature riding on top of a large trust system. If you get the PKI wrong, nothing about the pleasant tap-free experience matters.

## What actually happens when you plug in

The physical connection triggers **high-level communication (HLC)** over the control pilot line using power-line communication. From there the sequence is roughly:

1. The vehicle (EVCC) and charger (SECC) establish an IP link and discover each other.
2. They perform a TLS handshake — in ISO 15118-2 the charger authenticates to the car; in -20 it's mutual.
3. The car presents its **contract certificate** (identified by an eMAID, essentially an account identifier).
4. The charger validates that certificate up its chain to a trusted V2G root.
5. If valid, authorization succeeds and energy transfer negotiation begins.

All of that is meant to complete in a few seconds. The reason it sometimes doesn't is that certificate validation is a chain-walking, revocation-checking, clock-sensitive operation happening on embedded hardware, and any weak link stalls the whole flow.

## The certificate chains, and why there are so many

The single biggest conceptual hurdle is that ISO 15118 doesn't have "a certificate" — it has several distinct hierarchies that each answer a different question:

| Chain | Answers | Held by |
|---|---|---|
| V2G Root | "Whom do we all trust?" | Everyone, as an anchor |
| OEM Provisioning | "Is this a genuine vehicle?" | Vehicle from factory |
| Contract (eMAID) | "Who pays for this session?" | Vehicle, from mobility operator |
| CPO / SECC | "Is this a legitimate charger?" | Charge point operator |

The contract certificate is the star of the show for billing — it binds the car to a mobility contract so any charger on any compatible network can identify and bill the right party. But it has to be *provisioned* into the vehicle first, which is its own dance involving the provisioning certificate and a certificate installation flow, often brokered through the charging network back to a contract certificate pool. This is the part that took me longest to internalize: the car doesn't ship knowing how to pay; it gets that identity installed, and the installation itself is a secured transaction.

## The TLS layer is doing real work

People sometimes treat the TLS handshake here as boilerplate. It isn't. This channel carries authorization and, in vehicle-to-grid scenarios, control signals that can move real power. A downgraded or spoofed session is a safety and fraud problem, not just a privacy one. A few things I'd insist on in any implementation:

```text
- Validate the FULL chain to a trusted V2G root, not just the leaf.
- Enforce certificate validity windows — which means the clock MUST be right.
- Handle revocation (OCSP stapling or CRLs) rather than trusting forever.
- Reject weak cipher suites; ISO 15118-20 tightens the crypto for a reason.
```

That third point is the recurring field failure. Embedded chargers with drifting clocks reject perfectly valid certificates because "now" is wrong, or accept expired ones because they can't check revocation. Time synchronization is a security control in this system, exactly the way it is in [OCPP smart charging schedules](https://blog.michaelsam94.com/ocpp-smart-charging-profiles/) — the same clock discipline shows up in both places, and for related reasons.

## Where OCPP fits in

ISO 15118 is the car-to-charger conversation; OCPP is the charger-to-backend conversation. They're complementary, and PnC needs both. When a vehicle presents a contract certificate the charger often can't fully validate it locally, so it forwards the authorization request to the central system over OCPP, which either validates against a cached certificate hierarchy or reaches out to the mobility operator. OCPP 2.0.1 added explicit support for this — `Get15118EVCertificate`, `AuthorizeRequest` with certificate data, and related messages. If you're choosing a protocol version for a new deployment, this is one of the strongest arguments in the [OCPP 2.0.1 vs 1.6 comparison](https://blog.michaelsam94.com/ocpp-2-0-1-vs-1-6/): 1.6 has no native ISO 15118 certificate handling, so bolting PnC onto it means non-standard extensions.

## The honest downsides

I'm a fan of where PnC is going, but it is not free:

- **Operational PKI is a burden.** You now run or integrate with a certificate authority ecosystem, manage trust anchors on field hardware, and handle rotation. Most operators underestimate this by an order of magnitude.
- **Interoperability is still maturing.** In theory any PnC car works at any PnC charger. In practice, mismatched trust roots, missing intermediate certificates, and vendor quirks mean you test combinations empirically. I keep a matrix of "car model × charger firmware" that actually works.
- **Debuggability is poor.** A failed handshake gives a driver "charging failed" and gives you a cryptic embedded log. Build good telemetry early or you'll be blind.
- **-2 vs -20 fragmentation.** ISO 15118-20 improves security and adds bidirectional power transfer, but the fleet is mixed, so you support both for years.

## Is it worth it?

For a public network, yes — increasingly it's table stakes, and the frictionless experience genuinely moves people off apps and cards. For a small private depot, honestly, RFID or a simple backend auth is fine and dramatically cheaper to operate. The rule I use: adopt Plug and Charge when the cost of running the PKI is smaller than the value of removing payment friction at scale, and not a moment before. When you do adopt it, treat the certificate infrastructure as a first-class production system with monitoring, rotation runbooks, and clock discipline — because from the driver's side it looks like magic, and magic that fails silently is the worst kind of product.

## Resources

- [ISO 15118-2 — network and application protocol requirements](https://www.iso.org/standard/55366.html)
- [ISO 15118-20 — 2nd generation V2G communication](https://www.iso.org/standard/77845.html)
- [Open Charge Alliance — OCPP and ISO 15118 whitepapers](https://openchargealliance.org/)
- [Hubject — Plug and Charge ecosystem documentation](https://www.hubject.com/plug-charge)
- [RFC 8446 — TLS 1.3](https://datatracker.ietf.org/doc/html/rfc8446)
- [RFC 5280 — X.509 PKI certificate and CRL profile](https://datatracker.ietf.org/doc/html/rfc5280)
