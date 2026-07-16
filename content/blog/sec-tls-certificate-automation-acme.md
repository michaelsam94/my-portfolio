---
title: "Automating Certificates with ACME"
slug: "sec-tls-certificate-automation-acme"
description: "Automate TLS certificate issuance and renewal with ACME: Let's Encrypt, DNS-01 vs HTTP-01, cert-manager, and failure alerting."
datePublished: "2025-06-16"
dateModified: "2025-06-16"
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

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

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

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## HTTP-01 behind load balancers

Ensure `/.well-known/acme-challenge/` routes to the solver pod, not cached CDN. Temporarily bypass cache for challenge path or use DNS-01 if CDN cannot origin-pull challenges.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Wildcards require DNS-01

```
*.example.com + example.com
```

Create `_acme-challenge.example.com` TXT via provider API. Scope IAM to TXT record on challenge subdomain only.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Monitoring expiry

Prometheus `ssl_exporter` or cloud load balancer metrics. Alert:

```
days_until_expiry < 14
```

Include cert name and SAN list in alert body. Run weekly synthetic TLS handshake from external vantage.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Revocation and key compromise

ACME supports revocation if private key leaks. Document runbook: revoke cert, reissue with new key, invalidate old secret in Kubernetes. CAA DNS records restrict which CAs may issue for your domain—add before automation.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.


Use `https://acme-staging-v02.api.letsencrypt.org/directory` until challenges succeed reliably, then switch issuer to production to avoid rate limit bans during typos.

Staging ACME endpoint first—production rate limits punish typos during setup. Monitor days_until_expiry with alert under 14 days.

CAA DNS records restrict which CAs may issue for your domain before automation goes live. Revocation runbook for key compromise: revoke, reissue, invalidate old secret in all load balancers.

HTTP-01 requires port 80 reachable; CDN must forward acme-challenge path or use DNS-01 for wildcard certs.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

Document the decision, owner, and rollback path in your team wiki the same week you ship. Future you will not remember which environment variable toggled the behavior unless it is written next to the runbook entry and linked from the alert. That habit costs ten minutes per change and saves hours when pagination or auth misbehaves under a single large tenant.



Run the change through your standard PR checklist: tests, observability, and a two-minute rollback drill in staging. Small operational habits accumulate into systems that survive on-call nights without heroics.


Share a short write-up in your engineering channel after rollout: what shipped, what metric you watch, and who owns follow-up. That closes the loop for teammates who were not in the PR and surfaces gaps in docs before the next person repeats the same investigation.

## Resources

- [RFC 8555: ACME Protocol](https://www.rfc-editor.org/rfc/rfc8555.html)
- [Let's Encrypt documentation](https://letsencrypt.org/docs/)
- [cert-manager documentation](https://cert-manager.io/docs/)
- [Caddy automatic HTTPS](https://caddyserver.com/docs/automatic-https)
- [Mozilla SSL Configuration Generator](https://ssl-config.mozilla.org/)
