---
title: "TLS 1.3 in Practice"
slug: "encryption-in-transit-tls13"
description: "Deploy TLS 1.3 correctly: cipher suites, 0-RTT risks, certificate management, mTLS patterns, and debugging handshake failures in production."
datePublished: "2025-12-22"
dateModified: "2025-12-22"
tags: ["Security", "Encryption", "TLS", "Networking"]
keywords: "TLS 1.3 deployment, TLS cipher suites, 0-RTT security, mTLS mutual TLS, certificate rotation, ALPN HTTP2, openssl s_client debug TLS"
faq:
  - q: "Should I disable TLS 1.2 now that TLS 1.3 is widely supported?"
    a: "TLS 1.3-only is reasonable for greenfield internal services and modern client bases. Public-facing APIs often keep TLS 1.2 enabled temporarily for legacy clients but restrict to AEAD cipher suites (ECDHE + AES-GCM or ChaCha20). Monitor ClientHello stats before disabling 1.2."
  - q: "Is TLS 1.3 0-RTT safe to enable?"
    a: "0-RTT replays early data against idempotent endpoints — dangerous for state-changing requests. Disable 0-RTT for public APIs or restrict to GET with anti-replay tokens. Most conservative production configs disable 0-RTT entirely until threat model explicitly allows it."
  - q: "How do I debug TLS handshake failures in production?"
    a: "Use openssl s_client -connect host:443 -servername host -tls1_3 for manual handshake inspection. Enable structured logs on reverse proxy (nginx ssl_handshake, Envoy TLS inspector). Common failures: SNI mismatch, expired intermediate chain, incompatible cipher policy, clock skew on client."
---

TLS 1.3 removes a decade of foot-guns: no RSA key transport, no CBC mode suites, no custom DH groups negotiated by amateurs. The handshake is one round trip for full mode, optional 0-RTT for resumption, and forward secrecy is mandatory. That simplicity helps until your load balancer terminates TLS with a cipher policy copied from a 2018 blog post, or your mobile app pins a cert that expired Tuesday. TLS 1.3 in practice is less about enabling the version flag and more about certificate lifecycle, cipher policy, and knowing what 0-RTT can replay.

## Handshake at a glance

```
ClientHello (key shares, cipher suites, SNI)
        │
        ▼
ServerHello + EncryptedExtensions + Certificate + CERT verify + Finished
        │
        ▼
Client Finished ──► Application data (1-RTT)
```

Session tickets enable resumption; 0-RTT sends early data before full handshake completes — fast but replayable.

## Server configuration (nginx)

```nginx
ssl_protocols TLSv1.2 TLSv1.3;
ssl_prefer_server_ciphers off;  # TLS 1.3 ignores this; 1.2 uses server order

ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:
             ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';

ssl_session_timeout 1d;
ssl_session_cache shared:SSL:50m;
ssl_session_tickets off;  # or rotate ticket keys if enabled

# OCSP stapling
ssl_stapling on;
ssl_stapling_verify on;
```

TLS 1.3 cipher suites in OpenSSL 1.1.1+:

- `TLS_AES_256_GCM_SHA384`
- `TLS_CHACHA20_POLY1305_SHA256`
- `TLS_AES_128_GCM_SHA256`

Clients negotiate automatically — do not force obsolete CBC suites for "compatibility."

## Certificate and chain hygiene

Use Let's Encrypt or ACME automation with short-lived certs (90 days). Store full chain — leaf + intermediate — not leaf alone:

```bash
openssl s_client -connect api.example.com:443 -servername api.example.com </dev/null 2>/dev/null \
  | openssl x509 -noout -dates -issuer -subject
```

Monitor expiry 30 days ahead. Multi-cloud deployments benefit from cert-manager (Kubernetes) or cloud-native cert services with auto-renewal.

**SNI is mandatory** for virtual hosting — clients without SNI hit wrong vhost or default cert mismatch.

## mTLS for service-to-service

Internal zero-trust often requires client certificates:

```yaml
# Envoy downstream TLS example snippet
transport_socket:
  name: envoy.transport_sockets.tls
  typed_config:
    common_tls_context:
      tls_certificates:
        - certificate_chain: { filename: "/certs/server.pem" }
          private_key: { filename: "/certs/server-key.pem" }
      validation_context:
        trusted_ca: { filename: "/certs/ca.pem" }
        match_subject_alt_names:
          - exact: "orders.internal.svc"
```

Rotate client certs with overlapping validity windows. SPIFFE/SPIRE issues SVIDs with short TTL — better than year-long shared client certs baked into images.

## 0-RTT decision matrix

| Enable 0-RTT | When |
|--------------|------|
| No | Default for APIs with POST/PUT side effects |
| Maybe | CDN edge serving cacheable GET only |
| Yes with care | Custom anti-replay (single-use tokens) |

nginx: `ssl_early_data off;` unless explicitly needed.

## Debugging checklist

1. **Protocol version** — `TestSSL.sh` or `sslscan` reports offered versions
2. **Chain trust** — Android older devices miss ISRG Root X1 cross-sign issues
3. **ALPN** — HTTP/2 requires `h2` advertisement; HTTP/1.1-only clients fail mysteriously if misconfigured
4. **Clock skew** — cert validation fails on embedded devices with wrong RTC
5. **Middleboxes** — corporate proxies break TLS 1.3; collect PCAP (with consent) for stuck handshakes

```bash
openssl s_client -connect host:443 -tls1_3 -alpn h2,http/1.1
```

## Application-layer additions

TLS encrypts and authenticates the channel — not your JWT, cookies, or SQL. Still use:

- HSTS with preload for browser clients
- Certificate Transparency monitoring for mis-issued certs
- Per-request auth regardless of mTLS at edge (defense in depth)

TLS 1.3 is the baseline for encryption in transit; operational excellence is cert automation, cipher hygiene, and conscious 0-RTT policy.

## Certificate lifecycle automation

Manual cert renewal causes outages — automate with ACME:

```yaml
# cert-manager Kubernetes issuer
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: ops@example.com
    privateKeySecretRef:
      name: letsencrypt-prod-key
    solvers:
      - http01:
          ingress:
            class: nginx
```

```yaml
# Certificate resource — auto-renewed 30 days before expiry
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: api-tls
spec:
  secretName: api-tls-secret
  issuerRef:
    name: letsencrypt-prod
  dnsNames:
    - api.example.com
```

Alert 14 days before expiry as backup — cert-manager should handle renewal, but alerts catch misconfiguration.

## mTLS for service-to-service

TLS 1.3 between services with mutual authentication:

```go
// Server: require client certificate
tlsConfig := &tls.Config{
    MinVersion: tls.VersionTLS13,
    ClientAuth: tls.RequireAndVerifyClientCert,
    ClientCAs:  clientCAPool,
    CipherSuites: []uint16{tls.TLS_AES_256_GCM_SHA384},
}

// Client: present service identity certificate
clientTLS := &tls.Config{
    MinVersion:   tls.VersionTLS13,
    Certificates: []tls.Certificate{serviceCert},
    RootCAs:      serverCAPool,
}
```

SPIFFE/SPIRE issues short-lived service identity certificates — rotation every hour, no long-lived shared secrets.

## TLS termination architecture

```
Client → TLS → Load Balancer → TLS/mTLS → Service → plain HTTP → Sidecar (Envoy)
```

Decisions:
- **Terminate at LB:** simpler cert management; internal traffic unencrypted
- **Terminate at sidecar:** mTLS end-to-end; more cert management overhead
- **Pass-through:** LB sees encrypted traffic; service terminates TLS

For zero-trust, terminate at sidecar with mTLS between all hops. For simpler setups, terminate at LB with encrypted internal network.

## Failure modes

- **Manual cert renewal** — forgotten expiry causes outage
- **TLS 1.0/1.1 enabled** — deprecated protocols; disable explicitly
- **0-RTT enabled on stateful APIs** — replay attacks on POST requests
- **Weak cipher suites** — CBC mode vulnerable; use AEAD only (GCM, ChaCha20)
- **No cert expiry monitoring** — misconfigured auto-renewal undetected until failure

## Production checklist

- TLS 1.3 minimum; TLS 1.0/1.1 disabled
- Certificate auto-renewal via ACME (cert-manager or equivalent)
- Expiry alert 14 days before certificate expiration
- 0-RTT disabled for APIs with state-changing operations
- AEAD cipher suites only (TLS_AES_256_GCM_SHA384, TLS_CHACHA20_POLY1305_SHA256)
- HSTS header with preload for browser clients

## Common production mistakes

Teams get encryption in transit tls13 wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of encryption in transit tls13 fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [RFC 8446 — TLS 1.3 specification](https://www.rfc-editor.org/rfc/rfc8446)
- [Mozilla SSL Configuration Generator](https://ssl-config.mozilla.org/)
- [Let's Encrypt documentation](https://letsencrypt.org/docs/)
- [OWASP Transport Layer Protection Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Transport_Layer_Protection_Cheat_Sheet.html)
- [SPIFFE — secure production identity](https://spiffe.io/)
