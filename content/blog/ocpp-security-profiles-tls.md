---
title: "OCPP Security Profiles and TLS"
slug: "ocpp-security-profiles-tls"
description: "Configure OCPP security profiles and TLS: certificate-based authentication, Security Profiles 1-3, WebSocket over WSS, and production hardening."
datePublished: "2025-11-08"
dateModified: "2025-11-08"
tags: ["IoT", "EV Charging", "OCPP", "Security"]
keywords: "OCPP security profiles, OCPP TLS, WSS OCPP, charging station security, OCPP certificate authentication, Security Profile 3 OCPP"
faq:
  - q: "What are the three OCPP security profiles?"
    a: "Profile 1: unencrypted HTTP with basic auth (deprecated, never use in production). Profile 2: TLS with server-side certificate (WSS) and basic auth or client certificates. Profile 3: TLS with mutual authentication—both CSMS and charger present certificates. Profile 3 is the production standard."
  - q: "Why do chargers ship with Security Profile 1?"
    a: "Manufacturing convenience—no certificate provisioning during factory setup. Before deploying to production, upgrade to Profile 2 or 3, install certificates, and disable plaintext connections. Many regulators now require encrypted OCPP."
  - q: "How do I provision certificates to 500 chargers?"
    a: "Use the OCPP Certificate Management functions: CSMS sends InstallCertificate, charger generates a key pair and sends SignCertificate request, CSMS signs and returns the certificate chain. Automate via your device provisioning pipeline."
---

A penetration test finds 40 chargers communicating over unencrypted WebSocket with basic auth credentials transmitted in plaintext. Security Profile 1—HTTP with username/password—is the factory default for many chargers because it simplifies manufacturing setup. In production, it exposes charging infrastructure to credential theft, session hijacking, and remote command injection. OCPP defines three security profiles; Profile 3 with mutual TLS is the target for every deployment.

## Security profiles compared

| Profile | Transport | Server auth | Client auth | Status |
|---------|-----------|-------------|-------------|--------|
| 1 | WS (plaintext) | None | HTTP Basic | Deprecated |
| 2 | WSS (TLS) | Server certificate | HTTP Basic or cert | Acceptable |
| 3 | WSS (TLS) | Server certificate | Client certificate | Recommended |

## Profile 3 setup

**CSMS server configuration:**

```nginx
server {
    listen 443 ssl;
    server_name ocpp.example.com;

    ssl_certificate     /etc/ssl/csms-server.crt;
    ssl_certificate_key /etc/ssl/csms-server.key;
    ssl_client_certificate /etc/ssl/charging-ca.crt;
    ssl_verify_client on;

    location /ocpp/ {
        proxy_pass http://ocpp-backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header X-Client-CN $ssl_client_s_dn;
    }
}
```

**Charger configuration:**

```
SecurityProfile = 3
CpoName = ocpp.example.com
Identity = CS-001-ABC123
```

The charger connects via `wss://ocpp.example.com/ocpp/CS-001-ABC123` presenting its client certificate.

## Certificate provisioning flow

OCPP defines certificate management messages:

```
1. CSMS → InstallCertificate (root CA cert to charger trust store)
2. Charger generates key pair
3. Charger → SignCertificate (CSR to CSMS)
4. CSMS signs CSR with charging CA
5. CSMS → CertificateSigned (signed cert chain to charger)
6. Charger installs certificate, reconnects with Profile 3
```

```json
// SignCertificate request (charger → CSMS)
{
  "csr": "-----BEGIN CERTIFICATE REQUEST-----\nMIIC...==\n-----END CERTIFICATE REQUEST-----"
}

// CertificateSigned (CSMS → charger)
{
  "certificateChain": "-----BEGIN CERTIFICATE-----\nMIID...==\n-----END CERTIFICATE-----\n-----BEGIN CERTIFICATE-----\nMIIC...==\n-----END CERTIFICATE-----"
}
```

Automate this in your charger onboarding pipeline. Manual certificate installation does not scale past 20 devices.

## Certificate rotation

```python
async def rotate_charger_cert(charger_id: str, days_before_expiry: int = 30):
    cert = await db.get_certificate(charger_id)
    if cert.days_until_expiry > days_before_expiry:
        return

    # Trigger re-enrollment
    await csms.send_trigger_message(charger_id, "SignCertificate")
    # Charger generates new CSR, CSMS signs, old cert remains valid during overlap
```

Alert at 30 days and 7 days before expiry. Chargers that cannot connect due to expired certificates require physical intervention.

## WebSocket over TLS (WSS)

OCPP uses WebSocket as its transport. Profile 2+ requires WSS:

```
Profile 1: ws://csms.example.com/ocpp/CS-001    ← plaintext
Profile 2: wss://csms.example.com/ocpp/CS-001   ← TLS encrypted
Profile 3: wss://csms.example.com/ocpp/CS-001   ← TLS + client cert
```

Verify the charger's WebSocket library supports WSS with client certificate presentation. Some embedded WebSocket stacks only support server-side TLS.

## Network segmentation

```
Internet
  │
  ├── Firewall (allow 443/WSS inbound only)
  │
  ├── CSMS (DMZ)
  │     └── WSS termination
  │
  ├── Application network
  │     └── CSMS backend, billing, auth
  │
  └── Charger network (VPN or private APN)
        └── Chargers connect outbound to CSMS
```

Chargers initiate outbound connections—no inbound ports on charger networks. Use VPN or private cellular APN for charger-to-CSMS connectivity.

## Security audit checklist

- [ ] All chargers on Profile 2 or 3 (zero on Profile 1)
- [ ] TLS 1.2+ only (disable TLS 1.0/1.1)
- [ ] Certificate expiry monitoring with 30-day alerts
- [ ] Client certificate revocation process documented
- [ ] Basic auth credentials rotated (if Profile 2)
- [ ] WebSocket connections use `wss://` (verify with packet capture)
- [ ] CSMS rejects connections without valid client cert (Profile 3)
- [ ] Firmware signed and verified (see firmware update post)

## Compliance context

The German calibration law (Eichrecht) and the EU AFIR regulation increasingly require encrypted communication for public charging infrastructure. Security Profile 3 positions your network for regulatory compliance.

## OCPP Security Profile comparison

| Profile | Transport | Authentication | Use case |
|---|---|---|---|
| Profile 1 | HTTP/WS (unencrypted) | None | Lab/dev only — never production |
| Profile 2 | HTTPS/WSS (TLS) | HTTP Basic Auth | Legacy deployments |
| Profile 3 | HTTPS/WSS (TLS) | Mutual TLS (client cert) | Production standard |

Profile 3 mutual TLS: charger presents client certificate, CSMS verifies against trusted CA. Charger identity cryptographically proven — not just password-based.

```bash
# Verify charger connects with client cert (Profile 3)
openssl s_client -connect csms.example.com:443 \
  -cert charger_client.pem -key charger_key.pem \
  -CAfile csms_ca.pem
# Should complete handshake; CSMS logs charger identity from cert CN
```

## Certificate provisioning at scale

Manufacturing and field deployment workflow:

```
Factory:
  1. Generate unique key pair per charger (HSM or secure element)
  2. Submit CSR to CSMS CA
  3. Install signed certificate before shipping
  4. Record serial number → certificate mapping in inventory

Field replacement:
  1. New charger arrives with factory cert OR
  2. CSMS issues cert via OCPP CertificateSigned message (OCPP 2.0.1)
  3. Old cert revoked in CSMS inventory
```

Never reuse certificates across chargers — each charger needs unique identity for audit and revocation.

## TLS configuration for OCPP WebSocket

```nginx
# nginx WSS termination for OCPP
server {
    listen 443 ssl;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_client_certificate /etc/nginx/ca/charger_ca.pem;
    ssl_verify_client optional;  # Profile 2: optional; Profile 3: on

    location /ocpp/ {
        proxy_pass http://csms_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header X-Charger-CN $ssl_client_s_dn;
    }
}
```

Verify with packet capture that no OCPP traffic flows over unencrypted WS in production.

## Failure modes

- **Profile 1 in production** — credentials and session data transmitted in cleartext
- **Certificate expiry without monitoring** — chargers disconnect en masse at expiry
- **Shared client certificate across chargers** — can't revoke individual compromised charger
- **TLS 1.0/1.1 enabled** — deprecated protocols; disable explicitly
- **Basic auth credentials not rotated** — Profile 2 long-lived credentials compromised

## Production checklist

- All production chargers on Profile 2 minimum, Profile 3 preferred
- Unique client certificate per charger with inventory tracking
- Certificate expiry monitoring with 30/60/90-day alerts
- TLS 1.2+ only; TLS 1.0/1.1 disabled
- WSS verified with packet capture (no cleartext WS)
- Certificate revocation process documented and tested

## Resources

- [OCPP 1.6 Security Whitepaper](https://www.openchargealliance.org/protocols/ocpp-protocols/) — security profiles definition
- [OCPP 2.0.1 Part 2 Security](https://www.openchargealliance.org/protocols/ocpp-protocols/ocpp-2-0-1/) — certificate management functions
- [RFC 6455 — WebSocket Protocol](https://www.rfc-editor.org/rfc/rfc6455) — OCPP transport layer
- [Mozilla SSL Configuration Generator](https://ssl-config.mozilla.org/) — TLS cipher configuration
- [OWASP IoT Security Project](https://owasp.org/www-project-internet-of-things/) — embedded device security guidance
