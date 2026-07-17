---
title: "RAG: Certificate Transparency Monitoring"
slug: "rag-certificate-transparency-monitoring"
description: "Monitor Certificate Transparency logs for unauthorized TLS certificates on RAG API domains—detect misissued certs, subdomain takeover, and shadow infrastructure before clients trust them."
datePublished: "2025-10-14"
dateModified: "2026-07-17"
tags: ["AI", "Rag", "Certificate"]
keywords: "certificate transparency, CT logs, cert monitoring, TLS security, RAG API security, misissued certificates, crt.sh, Certstream"
faq:
  - q: "What is Certificate Transparency and why does it matter for RAG APIs?"
    a: "Certificate Transparency (CT) is a public, append-only log of all TLS certificates issued by participating CAs. Monitoring CT logs for your RAG API domains detects unauthorized certificates—whether from compromised CAs, social engineering at a registrar, or shadow deployments using legitimate-looking subdomains."
  - q: "How quickly can CT monitoring detect a rogue certificate?"
    a: "Certstream and similar services push new CT log entries within minutes of issuance. Alert latency depends on your monitoring pipeline—typically 5–15 minutes from issuance to Slack notification. Compare against known-good cert inventory to filter expected renewals."
  - q: "Which domains should RAG teams monitor in CT logs?"
    a: "Monitor exact domains and wildcard patterns: rag.example.com, *.rag.example.com, api.example.com if shared, and any tenant subdomain pattern like *.rag.internal.example.com. Include domains from staging and dev environments—compromised staging certs can enable MITM during testing."
---
A security researcher emailed: "I found a valid Let's Encrypt certificate for `rag-api-staging.example.com` issued yesterday. Is this yours?" It was not. Someone had completed DNS-01 validation against a dangling CNAME pointing to a decommissioned Heroku app. The certificate was legitimate—issued by a trusted CA—but the infrastructure was attacker-controlled. Certificate Transparency logs had recorded the issuance within minutes; nobody was watching.

RAG APIs handle sensitive query text, document uploads, and admin operations over TLS. Compromised or misissued certificates enable man-in-the-middle attacks that bypass application-layer security entirely. CT monitoring provides early warning when certificates appear for your domains outside your cert-manager workflow.

## How Certificate Transparency works

When a public CA issues a certificate, it submits the certificate to one or more CT logs. Logs are public and cryptographically verifiable:

```
CA issues cert → submits to CT log → log returns signed timestamp (SCT)
                                  → cert appears in public log within minutes
```

Monitors watch logs for domain matches and alert on unexpected issuances. You do not need to control the CA—transparency is mandatory for browser-trusted certs.

## Threat model for RAG infrastructure

CT monitoring catches:

**Shadow RAG deployments.** Engineer spins up unauthorized RAG instance on `rag-test.company.com` with legitimate cert—data exfiltration risk.

**Subdomain takeover.** Dangling DNS record allows attacker to pass ACME challenge, get cert for `old-service.rag.example.com`.

**Compromised CA or RA.** Rare but catastrophic—CT log shows cert you did not request.

**Certificate misissuance.** CA bug issues cert for your domain to wrong party—[Google's 2015 incident](https://googleonlinesecurity.blogspot.com/2015/03/maintaining-digital-certificate-security.html) is the canonical example.

**Expired domain re-registration.** Expired domain re-registered, historical subdomain certs still in CT logs—monitor for re-issuance.

CT monitoring does not prevent issuance—it enables rapid detection and revocation response.

## Monitoring with crt.sh and Certstream

**crt.sh** — searchable CT log database:

```bash
# Query recent certs for domain
curl -s "https://crt.sh/?q=%.rag.example.com&output=json" | \
  jq '[.[] | {id, name_value, not_before, issuer_name}] | unique_by(.name_value)'
```

Good for ad-hoc investigation; not real-time alerting.

**Certstream** — real-time CT log firehose:

```python
# monitoring/certstream_watcher.py
import certstream
import re
from datetime import datetime

WATCH_PATTERNS = [
    re.compile(r"(\.|^)rag\.example\.com$", re.I),
    re.compile(r"(\.|^)rag-api\.example\.com$", re.I),
    re.compile(r"\.rag\.internal\.example\.com$", re.I),
]

KNOWN_ISSUERS = {"Let's Encrypt", "Amazon", "DigiCert"}
AUTHORIZED_ISSUANCE = load_authorized_cert_inventory()  # from cert-manager

def callback(message, context):
    if message["message_type"] != "certificate_update":
        return

    cert = message["data"]["leaf_cert"]
    domains = cert.get("all_domains", [])

    for domain in domains:
        if not any(p.search(domain) for p in WATCH_PATTERNS):
            continue

        fingerprint = cert["fingerprint"]
        if fingerprint in AUTHORIZED_ISSUANCE:
            continue  # expected renewal

        alert = {
            "domain": domain,
            "issuer": cert["issuer"]["O"],
            "fingerprint": fingerprint,
            "not_before": cert["not_before"],
            "source": cert.get("source", "unknown"),
            "detected_at": datetime.utcnow().isoformat(),
        }
        send_slack_alert("#security-alerts", alert)
        log_to_siem(alert)

certstream.listen_for_events(callback, url="wss://certstream.calidog.io/")
```

Run as Deployment with restart policy. Filter against authorized inventory to reduce noise from expected cert-manager renewals.

## Building authorized cert inventory

Expected certificates come from your infrastructure:

```python
# monitoring/cert_inventory.py
import subprocess
import json

def load_k8s_cert_inventory(namespace: str = "rag-production") -> set[str]:
    """Pull fingerprints from cert-manager Secrets."""
    result = subprocess.run(
        ["kubectl", "get", "secrets", "-n", namespace,
         "-l", "cert-manager.io/certificate-name", "-o", "json"],
        capture_output=True, text=True,
    )
    fingerprints = set()
    for item in json.loads(result.stdout)["items"]:
        cert_pem = item["data"].get("tls.crt")
        if cert_pem:
            fingerprints.add(compute_fingerprint(base64_decode(cert_pem)))
    return fingerprints
```

Refresh inventory hourly. New cert-manager issuance automatically enters authorized set on next sync.

## Alert triage runbook

When unexpected cert alert fires:

1. **Verify legitimacy.** Check cert-manager Certificate resources—is this our renewal with new fingerprint?
2. **Identify issuance path.** crt.sh shows CA, date, SANs. Who could have passed domain validation?
3. **Check DNS.** Dangling records? Unauthorized TXT records for ACME?
4. **Assess exposure.** Is domain reachable? Active MITM risk?
5. **Revoke if malicious.** Submit revocation to issuing CA. Remove dangling DNS.
6. **Document.** Post-incident review; update CT watch patterns if new subdomain discovered.

Severity:
- **Critical:** Production RAG API domain, active DNS, unknown issuer
- **High:** Staging domain with production-adjacent data
- **Medium:** Dev domain, no active infrastructure
- **Info:** Expected renewal not yet in inventory (sync lag)

## Integration with enterprise PKI monitoring

Commercial tools provide managed CT monitoring:

- **Facebook Certifier** (open source)
- **SSLMate Cert Spotter**
- **Google Certificate Transparency monitoring**

These reduce operational burden vs self-hosted Certstream. Evaluate if your security team already operates CT monitoring—add RAG domains to existing watchlist.

## CT monitoring for internal/private CAs

Private CA certificates are not logged to public CT. Monitor separately:

- Audit cert-manager CertificateRequest creation via Kubernetes audit logs
- Alert on Certificate resources in unauthorized namespaces
- Vault PKI audit log monitoring for internal CA

Do not assume CT covers internal certs—it does not.

## Compliance relevance

CT monitoring supports:

- **SOC 2 CC6.6** — logical and physical access controls for network security
- **PCI DSS 4.0** — requirement to detect unauthorized network connections
- **NIST CSF PR.DS-2** — data in transit protected

Document CT monitoring in security control matrix. Auditors ask "how do you detect unauthorized TLS endpoints?"

## Limitations

- CT logs public certs only—not internal CA, not self-signed
- Detection lag of minutes—active MITM may occur before alert
- High-volume domains generate noise—inventory filtering essential
- Wildcard certs log the wildcard SAN, not every subdomain using it

Pair CT monitoring with:
- DNS monitoring for unauthorized record changes
- External attack surface scanning
- mTLS for RAG admin APIs regardless of public cert status

## Getting started

1. List all domains RAG infrastructure uses (including staging/dev)
2. Query crt.sh for historical baseline
3. Deploy Certstream watcher or add domains to commercial monitor
4. Build authorized inventory from cert-manager
5. Wire alerts to security Slack with runbook
6. Test with staging cert issuance—confirm alert fires then clears on inventory sync

Certificate Transparency makes TLS issuance observable. For RAG teams who treat TLS as cert-manager's problem, CT monitoring is the feedback loop that catches what cert-manager did not issue.

## Building CT monitoring into vendor onboarding

When onboarding a new SaaS vendor that receives RAG API credentials, add their domains to CT watch list if they terminate TLS for your data. Shadow IT RAG deployments—engineers spinning up unauthorized retrieval endpoints—appear in CT logs before they appear in asset inventory. Quarterly CT log review for company domain variants catches typosquatting and forgotten staging environments.

## Automating CT alert response

Wire CT alerts to automated containment for high-severity patterns: unauthorized Bedrock InvokeModel from unknown principal triggers IAM policy deny via Lambda; unauthorized S3 GetObject on corpus bucket from new role triggers security team page with pre-built CloudTrail Lake investigation query. Automation reduces mean-time-to-contain from hours to minutes for credential compromise scenarios discovered via CT anomaly detection.


## Production rollout notes

Include subdomain enumeration in quarterly CT review: attackers register rag-api-staging.example.com, rag-api-dev.example.com, rag-api-backup.example.com variants. Automated CT monitoring with regex watch patterns catches variants faster than manual asset inventory. Feed discoveries into DNS cleanup and dangling record remediation workflows.

## Acceptance criteria for certificate transparency monitoring

Ship only when staging demonstrates the failure modes you claim to handle. Record the evidence — load test output, chaos result, or screenshot of the alert firing — in the PR. Revisit the settings after the first real incident; production will teach you which timeout or retention value was optimistic. Prefer boring, documented tradeoffs over clever defaults that only exist in one engineer's head.

## Resources

- Certificate Transparency project specification
- Certstream API documentation
- crt.sh query interface
- cert-manager certificate inventory patterns
