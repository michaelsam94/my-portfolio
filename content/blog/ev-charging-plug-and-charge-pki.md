---
title: "Plug and Charge PKI"
slug: "ev-charging-plug-and-charge-pki"
description: "Deploy Plug and Charge PKI for ISO 15118: V2G root CAs, contract certificates, provisioning, SECC certificate chains, and common trust failures."
datePublished: "2026-01-21"
dateModified: "2026-01-21"
tags: ["IoT", "EV Charging", "PKI", "Security"]
keywords: "Plug and Charge PKI, V2G PKI, ISO 15118 certificates, contract certificate EV, provisioning certificate, SECC leaf certificate, Hubject PKI, CharIN V2G CA"
faq:
  - q: "What certificates are required for Plug and Charge?"
    a: "The vehicle holds a provisioning certificate (from OEM) and contract certificate (from eMSP/mobility provider). The charger (SECC) presents its SECC leaf certificate chained to a V2G charging network CA. TLS mutual authentication during ISO 15118 session establishment validates both sides against trusted root CAs."
  - q: "Who operates the V2G root certificate authorities?"
    a: "Regional V2G CAs exist under frameworks like Hubject, CharIN/V2G Root, and market-specific programs (e.g., US NCAT). OEMs, CPOs, and eMSPs obtain sub-CA or leaf issuance contracts; trust stores on vehicles and chargers must include the same root set or PnC falls back to RFID."
  - q: "How often must contract certificates be renewed?"
    a: "Typical contract certificate validity is one to two years. ISO 15118 CertificateUpdate messages allow over-the-air renewal before expiry. Expired contract certs block PnC authorization — monitor fleet cert expiry centrally like TLS cert management."
---

RFID cards get lost, stolen, and skimmed; drivers hate apps that fail in parking garages with no signal. Plug and Charge promises authentication by plugging the cable — payment and authorization ride on TLS mutual authentication between car and charger using a V2G PKI nobody outside e-mobility has heard of until certificates expire fleet-wide on a holiday weekend. Understanding provisioning certificates, contract certificates, and SECC chain trust is mandatory for CPO platform engineers and OEM EVCC teams, not just security specialists.

## Certificate roles in V2G PKI

| Certificate | Holder | Purpose |
|-------------|--------|---------|
| V2G Root CA | Trust anchor | Signs MO/ CPO sub-CAs |
| OEM Provisioning cert | Vehicle (factory) | Proves vehicle identity to eMSP for contract cert issuance |
| Contract certificate | Vehicle | Authorization credential for charging billed to eMSP contract |
| SECC leaf | Charger | Authenticates EVSE to vehicle; signed by CPO sub-CA |
| Sub-CAs | OEM, MO, CPO | Intermediate issuers under root |

Chain example:

```
V2G Root
  └── CPO Sub-CA
        └── SECC Leaf (charger serial 12345)
V2G Root
  └── MO Sub-CA
        └── Contract Cert (EMAID / PCID linked)
```

## Provisioning flow (OEM → eMSP)

1. OEM installs **vehicle provisioning certificate** at manufacture (links to PCID)
2. Driver subscribes with eMSP; eMSP verifies provisioning cert
3. eMSP issues **contract certificate** installed via OEM backend or ISO 15118 **CertificateInstallation**
4. Vehicle presents contract cert at SECC during **AuthorizationReq**

```xml
<!-- AuthorizationReq conceptual -->
<AuthorizationReq>
  <Id>ContractCertificateChain</Id>
  <GenChallenge>...</GenChallenge>
  <ContractSignatureCertChain>...</ContractSignatureCertChain>
</AuthorizationReq>
```

SECC validates chain against trust store, checks revocation (OCSP where deployed), forwards to CSMS/eMSP for online authorization if policy requires.

## SECC certificate management

Chargers ship with factory SECC cert or enroll at commissioning:

```bash
# commissioning checklist (operational)
# 1. Generate key in HSM or secure element
# 2. CSR with charger ID, EVSE ID
# 3. CPO CA signs leaf
# 4. Install chain + trust store update OCPP Firmware update
# 5. Verify with interoperability test vehicle
```

Rotate SECC certs before expiry via OCPP **InstallCertificate** / **DeleteCertificate** (OCPP 2.0.1) without truck roll when possible.

Trust store updates must reach vehicles too — OEM OTA updates root bundles when new CPO CAs join roaming networks.

## Trust store synchronization hell

PnC fails silently to ISO 15118 EIM (external identification, RFID) when:

- Vehicle lacks CPO sub-CA intermediate
- Charger lacks MO contract CA
- Clock skew invalidates cert validity window
- Revoked cert not in CRL/OCSP responder reachability at roadside

Run **CharIN interoperability** events before production rollout. Log TLS handshake failure reason codes — `unknown_ca` vs `certificate_expired` drives different fixes.

## Security considerations

- **Private keys** in vehicle HSM and charger secure element — never export plaintext OEM provisioning keys
- **Certificate binding** — contract cert tied to PCID; clone detection via nonce challenges
- **Privacy** — EMAID may pseudonymize; GDPR retention on auth logs
- **Fallback** — RFID/app must remain when PnC fails — do not strand drivers

Pen-test PnC stack against malformed cert chains and downgrade to weak TLS versions — disable TLS 1.1.

## Operational monitoring

Dashboard alerts:

- Contract certs expiring < 30 days (fleet telematics)
- SECC leaf expiry per charger inventory
- PnC success rate vs EIM ratio drop
- OCSP failures by region

Automate **CertificateUpdate** triggers when vehicle connects to home charger with connectivity.

## Certificate lifecycle management

Plug & Charge certificates have distinct lifetimes:

| Certificate | Issuer | Typical validity | Renewal trigger |
|---|---|---|---|
| V2G root CA | CharIN/HUB | 10–20 years | Manual rotation |
| MO contract cert | eMSP/OEM | 1–3 years | Vehicle telematics |
| SECC leaf cert | CPO | 1 year | CSMS inventory scan |
| OEM provisioning cert | OEM | 5 years | Factory provisioning |

```python
def check_cert_expiry(inventory):
    alerts = []
    for charger in inventory:
        secc_cert = charger.get_cert("SECC")
        days_left = (secc_cert.not_after - datetime.now()).days
        if days_left < 30:
            alerts.append(CertExpiryAlert(charger.id, "SECC", days_left))
    return alerts
```

Automate renewal 60 days before expiry — manual renewal at scale (10k+ chargers) is operationally impossible.

## PKI hierarchy for ISO 15118

```
V2G Root CA (CharIN)
  └── MO Sub-CA (eMSP/OEM)
        └── Contract Certificate (bound to PCID/EMAID)
  └── CPO Sub-CA
        └── SECC Leaf Certificate (per charger)
```

Contract certificate proves the vehicle's billing account. SECC leaf proves the charger's identity. Both required for mutual TLS during ISO 15118 handshake.

## Fallback when PnC fails

Never block charging when Plug & Charge fails:

```
ISO 15118 handshake:
  1. Attempt mutual TLS with contract cert
  2. If cert invalid/expired → fall back to EIM (External Identification Means)
  3. EIM = RFID tap or app authorization
  4. Log PnC failure reason for ops dashboard
```

PnC success rate target: >95% for fleet vehicles with valid certs. Below 90% indicates PKI infrastructure problem, not user error.

## Failure modes

- **SECC cert expired** — all PnC sessions fail at that charger; RFID fallback required
- **Contract cert not renewed** — fleet vehicles can't auto-authenticate
- **Wrong root CA in trust store** — TLS handshake fails with `unknown_ca`
- **Private key exported from HSM** — security breach; revoke and re-provision
- **No fallback auth method** — drivers stranded when PnC fails

## Production checklist

- Certificate expiry monitoring with 30/60/90-day alerts
- Automated SECC cert renewal via CSMS
- Contract cert renewal via OEM telematics integration
- PnC failure rate dashboard with reason code breakdown
- RFID/app fallback always available
- CharIN interoperability tested before production rollout

## Common production mistakes

Teams get ev charging plug and charge pki wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of ev charging plug and charge pki fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [ISO 15118-2 / -20 certificate requirements](https://www.iso.org/standard/77833.html)
- [Hubject Plug&Charge documentation](https://www.hubject.com/plug-and-charge)
- [CharIN V2G PKI whitepapers](https://charin.global/knowledge-base/)
- [OCPP 2.0.1 ISO15118 certificate management use cases](https://www.openchargealliance.org/)
- [IEEE 1609.2 / PKI parallels for vehicular networks (reference)](https://standards.ieee.org/standard/1609.2-2016.html)
