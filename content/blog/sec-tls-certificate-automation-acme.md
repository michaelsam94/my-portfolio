---
title: "Automating Certificates with ACME"
slug: "sec-tls-certificate-automation-acme"
description: "Automate TLS certificate issuance and renewal with ACME: Let's Encrypt, DNS-01 vs HTTP-01, cert-manager, and failure alerting."
datePublished: "2025-06-16"
dateModified: "2026-07-17"
tags: ["Security", "TLS", "DevOps", "Automation"]
keywords: "ACME protocol, Let's Encrypt automation, cert-manager Kubernetes, DNS-01 challenge, TLS certificate renewal, HTTPS automation"
faq:
  - q: "HTTP-01 or DNS-01 ACME challenge?"
    a: "HTTP-01 requires port 80 reachable on each hostname—simple for public web servers. DNS-01 creates TXT records proving domain control, essential for wildcards (*.example.com) and internal services without public HTTP. DNS-01 needs API credentials for your DNS provider stored securely in cert-manager or Caddy."
  - q: "How early should certificates renew?"
    a: "Let's Encrypt recommends renewing at one-third of lifetime remaining—about 30 days before expiry on 90-day certs. Automate daily renewal attempts; successful renewals are no-ops until within window. Alert if certificate expires in under 14 days—renewal has likely failed silently."
  - q: "What breaks automated renewal in production?"
    a: "Firewall blocking port 80, DNS API token expired, load balancer serving stale challenge path, rate limits from too many failed attempts, and mixed manual cert overrides on one hostname. Staging ACME endpoints (Let's Encrypt staging) help test without hitting production rate limits during setup."
---
Someone pasted a calendar reminder: "Renew SSL cert – March." In 2025 that process is a outage waiting to happen. ACME (Automatic Certificate Management Environment) lets agents prove domain control and download certificates without human ticket queues. Let's Encrypt issues free 90-day certs; automation renews at day 60. When renewal fails, monitoring should page—not the first customer seeing `NET::ERR_CERT_DATE_INVALID`.

## ACME flow overview

1. Agent generates key pair and CSR
2. Order created with ACME CA (Let's Encrypt)
3. Complete challenge (HTTP-01 or DNS-01)
4. Download certificate chain
5. Install on load balancer or ingress
6. Repeat before expiry

```bash
# Caddy obtains and renews automatically
example.com {
    reverse_proxy app:8080
}
```

Caddy embeds ACME client—zero config for simple cases.

## cert-manager on Kubernetes

```yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: api-tls
spec:
  secretName: api-tls-secret
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  dnsNames:
    - api.example.com
```

ClusterIssuer with DNS-01 via Route53 or Cloudflare API. Ingress annotation `cert-manager.io/cluster-issuer: letsencrypt-prod` triggers issuance.

## HTTP-01 behind load balancers

Ensure `/.well-known/acme-challenge/` routes to the solver pod, not cached CDN. Temporarily bypass cache for challenge path or use DNS-01 if CDN cannot origin-pull challenges.

## Wildcards require DNS-01

```
*.example.com + example.com
```

Create `_acme-challenge.example.com` TXT via provider API. Scope IAM to TXT record on challenge subdomain only.

## Monitoring expiry

Prometheus `ssl_exporter` or cloud load balancer metrics. Alert:

```
days_until_expiry < 14
```

Include cert name and SAN list in alert body. Run weekly synthetic TLS handshake from external vantage.

## Revocation and key compromise

ACME supports revocation if private key leaks. Document runbook: revoke cert, reissue with new key, invalidate old secret in Kubernetes. CAA DNS records restrict which CAs may issue for your domain—add before automation.

Use `https://acme-staging-v02.api.letsencrypt.org/directory` until challenges succeed reliably, then switch issuer to production to avoid rate limit bans during typos.

Staging ACME endpoint first—production rate limits punish typos during setup. Monitor days_until_expiry with alert under 14 days.

CAA DNS records restrict which CAs may issue for your domain before automation goes live. Revocation runbook for key compromise: revoke, reissue, invalidate old secret in all load balancers.

HTTP-01 requires port 80 reachable; CDN must forward acme-challenge path or use DNS-01 for wildcard certs.

Run the change through your standard PR checklist: tests, observability, and a two-minute rollback drill in staging. Small operational habits accumulate into systems that survive on-call nights without heroics.

Share a short write-up in your engineering channel after rollout: what shipped, what metric you watch, and who owns follow-up. That closes the loop for teammates who were not in the PR and surfaces gaps in docs before the next person repeats the same investigation.

## Rollout and ownership

Teams shipping this capability should wire observability before calling the work done: metrics on the user-visible outcome the control protects, alerts linked to runbook steps, and at least one automated test covering the last incident class you care about. Slice dashboards by region and device during rollout because global averages hide bad canaries. When vendors, routes, or org structure change, revisit assumptions from launch week—they age faster than code. Document rollback commands in the runbook header so on-call does not rediscover steps during pagination. Cross-functional review after major traffic shifts keeps product, platform, and security aligned on the leading metric.

## Rollout and ownership

Teams shipping this capability should wire observability before calling the work done: metrics on the user-visible outcome the control protects, alerts linked to runbook steps, and at least one automated test covering the last incident class you care about. Slice dashboards by region and device during rollout because global averages hide bad canaries. When vendors, routes, or org structure change, revisit assumptions from launch week—they age faster than code. Document rollback commands in the runbook header so on-call does not rediscover steps during pagination. Cross-functional review after major traffic shifts keeps product, platform, and security aligned on the leading metric.

## Rollout and ownership

Teams shipping this capability should wire observability before calling the work done: metrics on the user-visible outcome the control protects, alerts linked to runbook steps, and at least one automated test covering the last incident class you care about. Slice dashboards by region and device during rollout because global averages hide bad canaries. When vendors, routes, or org structure change, revisit assumptions from launch week—they age faster than code. Document rollback commands in the runbook header so on-call does not rediscover steps during pagination. Cross-functional review after major traffic shifts keeps product, platform, and security aligned on the leading metric.

## Rollout and ownership

Teams shipping this capability should wire observability before calling the work done: metrics on the user-visible outcome the control protects, alerts linked to runbook steps, and at least one automated test covering the last incident class you care about. Slice dashboards by region and device during rollout because global averages hide bad canaries. When vendors, routes, or org structure change, revisit assumptions from launch week—they age faster than code. Document rollback commands in the runbook header so on-call does not rediscover steps during pagination. Cross-functional review after major traffic shifts keeps product, platform, and security aligned on the leading metric.

## Rollout and ownership

Teams shipping this capability should wire observability before calling the work done: metrics on the user-visible outcome the control protects, alerts linked to runbook steps, and at least one automated test covering the last incident class you care about. Slice dashboards by region and device during rollout because global averages hide bad canaries. When vendors, routes, or org structure change, revisit assumptions from launch week—they age faster than code. Document rollback commands in the runbook header so on-call does not rediscover steps during pagination. Cross-functional review after major traffic shifts keeps product, platform, and security aligned on the leading metric.

## Edge cases in sec tls certificate automation acme

Security work around sec tls certificate automation acme fails when it is treated as a checklist instead of a feedback loop. Start from a threat model: who is the adversary, what is the asset, and which control fails closed if misconfigured. For sec tls certificate automation acme, I write the abuse cases first — credential stuffing, dependency CVE, log exfiltration, CSRF on cookie sessions — then map each to a detection signal and an owner.

### Controls that actually change outcomes

| Control | Where enforced | Failure mode |
|---------|----------------|--------------|
| Input validation | API edge | Injection / mass assignment |
| Authn | IdP + resource server | Stolen session / token |
| Authz | Policy engine | Broken object level auth |
| Secrets | Vault / KMS | Long-lived plaintext keys |

Wire these into CI where possible. A control that only lives in a wiki page will not survive the next on-call rotation.

### Incident-shaped verification

Run a tabletop: assume the primary control for sec tls certificate automation acme failed at 02:00. Who gets paged? What is the first command? How do you revoke access or roll credentials without cascading outages? If you cannot answer in under five minutes, the design is incomplete.

### Measurement

Track mean time to remediate findings related to sec tls certificate automation acme, false-positive rate of scanners, and number of production changes that bypass the gate. Celebrate burn-down of legacy exceptions with expiry dates — permanent exceptions are just vulnerabilities with paperwork.

### Pitfalls specific to this domain

Avoid denylist-only validation, logging secrets "temporarily," and blocking every advisory at severity informational. Prefer allowlists, structured redaction, and severity+reachability for gates. Document the dual-credential or dual-key window whenever rotation is involved so operators do not revoke early.

## Resources

- [RFC 8555: ACME Protocol](https://www.rfc-editor.org/rfc/rfc8555.html)
- [Let's Encrypt documentation](https://letsencrypt.org/docs/)
- [cert-manager documentation](https://cert-manager.io/docs/)
- [Caddy automatic HTTPS](https://caddyserver.com/docs/automatic-https)
- [Mozilla SSL Configuration Generator](https://ssl-config.mozilla.org/)