---
title: "Defending Against SSRF"
slug: "ssrf-prevention-defense"
description: "Server-side request forgery lets attackers pivot through your backend to internal services. Learn URL validation, network segmentation, and allowlists that block SSRF in production."
datePublished: "2025-09-16"
dateModified: "2026-07-17"
tags: ["Security", "SSRF", "Backend", "Cloud"]
keywords: "SSRF prevention, server-side request forgery, URL validation, metadata endpoint protection, AWS IMDS, SSRF allowlist, cloud security"
faq:
  - q: "What is the most common SSRF target in cloud environments?"
    a: "The cloud metadata service at 169.254.169.254 (AWS, GCP, Azure). An SSRF vulnerability that lets an attacker control the URL your server fetches can reach this endpoint and retrieve IAM credentials, instance tokens, and service account keys. This is how SSRF escalates from 'fetch a URL' to full cloud account compromise within seconds."
  - q: "Does blocking private IP ranges stop all SSRF?"
    a: "It stops the most common cases — accessing internal services on RFC 1918 addresses and the metadata endpoint. It doesn't stop SSRF to external services you didn't intend (attacker-controlled servers for data exfiltration), DNS rebinding attacks that resolve to internal IPs after validation, or attacks via redirect chains. Defense requires allowlists, network policies, and disabling unnecessary outbound access."
  - q: "How do I test for SSRF in my application?"
    a: "Identify every endpoint where your server makes HTTP requests based on user-supplied URLs — webhooks, URL previews, PDF generators, import-from-URL features, OAuth callbacks. Submit internal addresses (127.0.0.1, 169.254.169.254, 10.0.0.1) and observe whether your server connects. Use Burp Collaborator or an external canary server to detect blind SSRF where responses aren't returned to the attacker."
faqAnswers:
  - question: "When is ssrf prevention defense the wrong approach?"
    answer: "When a simpler control already covers the risk, or when the operational cost exceeds the benefit for your threat and traffic model."
  - question: "What should we measure for ssrf prevention defense?"
    answer: "Pair a leading operational signal with a lagging user or risk outcome, reviewed on a fixed cadence with a named owner."
  - question: "How do we roll back ssrf prevention defense safely?"
    answer: "Keep the prior artifact or config warm, rehearse the revert once in staging, and document the one-command rollback for on-call."
---
A URL preview feature in our staging app fetched whatever link a user pasted and returned the page title. A security researcher submitted `http://169.254.169.254/latest/meta-data/iam/security-credentials/` and got back live AWS credentials in the JSON response. The feature was meant to show "Example Domain" as a title tag. Instead it became a pivot point to our entire AWS account.

Server-side request forgery (SSRF) happens when your application makes HTTP requests to URLs controlled or influenced by an attacker. The attacker doesn't attack your server directly — they trick your server into attacking internal resources on their behalf. Metadata endpoints, internal admin panels, Redis instances on localhost, and services behind firewalls that trust internal traffic all become reachable.

## How SSRF attacks work

The pattern is consistent across vulnerabilities:

1. Your app has a feature that fetches a remote URL (webhook delivery, image proxy, RSS import, PDF rendering).
2. The attacker supplies a URL pointing to an internal resource.
3. Your server — sitting inside the network with access to internal services — makes the request.
4. The attacker reads the response (direct SSRF) or infers success from side effects (blind SSRF).

```python
# Vulnerable webhook tester
@app.post("/webhooks/test")
async def test_webhook(url: str):
    response = httpx.get(url)  # Attacker controls url
    return {"status": response.status_code, "body": response.text[:500]}
```

An attacker submits `http://127.0.0.1:6379/` and your server sends Redis commands. Or `http://internal-admin.corp:8080/delete-all` and your server triggers admin actions that external attackers can't reach directly.

## The metadata endpoint threat

In cloud environments, the link-local metadata service is the highest-value SSRF target:

- **AWS:** `http://169.254.169.254/latest/meta-data/iam/security-credentials/ROLE_NAME`
- **GCP:** `http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token`
- **Azure:** `http://169.254.169.254/metadata/identity/oauth2/token`

These endpoints return credentials your instance uses to access cloud APIs. SSRF that reaches them gives attackers the same permissions as your application — often far more than they need.

Mitigate at the infrastructure level: require IMDSv2 on AWS (token-based, not trivially reachable via simple GET), restrict metadata access with network policies, and use minimal IAM roles so compromised credentials have limited blast radius.

## URL validation that actually works

Blocklisting private IPs is necessary but insufficient. Implement layered validation:

**Parse and validate the URL structure:**

```python
from urllib.parse import urlparse
import ipaddress
import socket

BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]

def is_safe_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    if not parsed.hostname:
        return False
    if parsed.username or parsed.password:
        return False  # block userinfo bypass tricks

    try:
        resolved = socket.getaddrinfo(parsed.hostname, parsed.port or 80)
    except socket.gaierror:
        return False

    for _, _, _, _, sockaddr in resolved:
        ip = ipaddress.ip_address(sockaddr[0])
        if any(ip in net for net in BLOCKED_NETWORKS):
            return False
    return True
```

**Resolve DNS before connecting** — validate the resolved IP, not just the hostname. DNS rebinding attacks change the IP between validation and connection, so resolve once and connect to that specific IP.

**Block redirects to internal addresses.** Configure your HTTP client to not follow redirects, or re-validate every redirect target:

```python
client = httpx.Client(follow_redirects=False)
# Or if redirects are needed:
client = httpx.Client(event_hooks={"response": [validate_redirect_target]})
```

**Prefer allowlists over blocklists.** If your feature only needs to fetch from known partner domains, allowlist those domains instead of trying to block every internal address:

```python
ALLOWED_HOSTS = {"api.stripe.com", "hooks.slack.com", "api.github.com"}

def is_allowed(url: str) -> bool:
    host = urlparse(url).hostname
    return host in ALLOWED_HOSTS
```

## Network-level defenses

Application validation can have bugs. Network policies provide a second line:

- **Egress firewalls:** Block outbound traffic from application servers to RFC 1918 ranges and 169.254.169.254 at the firewall or security group level.
- **Service mesh policies:** Istio or Linkerd egress rules restrict which external hosts each service can reach.
- **Separate network segments:** Webhook delivery services run in a DMZ without routes to internal admin networks.
- **Disable unnecessary outbound:** If a service doesn't need to fetch external URLs, block all egress except required API endpoints.

## Architecture patterns that reduce SSRF risk

**Proxy through a dedicated fetch service.** One hardened service handles all outbound URL fetching with strict validation, logging, and rate limiting. Other services call it via internal RPC instead of making HTTP requests directly.

**Use pre-signed URLs for user content.** Instead of fetching user-supplied URLs, have users upload content directly to object storage and process it from there.

**Webhook signatures instead of URL testing.** When users configure webhooks, deliver a test payload and verify they receive it — don't fetch their URL and return the response body.

## URL parser differential attacks

Blocklist `169.254.169.254` is not enough — DNS rebinding, decimal IP encoding, and redirect chains bypass naive filters. Use allowlist of hostnames, resolve DNS and verify IP against private ranges after redirect final URL, disable redirects or cap hops.

## Metadata credential exfiltration

Cloud metadata endpoints return IAM credentials — egress proxy with default-deny for link-local ranges. Server-side fetchers run with no cloud credentials when possible (scoped task role with empty policy for fetcher service).

## Practical follow-through (1)

Ship the smallest vertical slice first — one route, one widget, one index configuration — with rollback documented before expanding scope. Baseline the user-visible metric this work protects (latency, recall, conversion, task success rate) for seven days before change and seven days after in your largest market.

## Practical follow-through (2)

Ship the smallest vertical slice first — one route, one widget, one index configuration — with rollback documented before expanding scope. Baseline the user-visible metric this work protects (latency, recall, conversion, task success rate) for seven days before change and seven days after in your largest market.

## Practical follow-through (3)

Ship the smallest vertical slice first — one route, one widget, one index configuration — with rollback documented before expanding scope. Baseline the user-visible metric this work protects (latency, recall, conversion, task success rate) for seven days before change and seven days after in your largest market.

## Resources

- [OWASP SSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)
- [PortSwigger SSRF labs](https://portswigger.net/web-security/ssrf)
- [AWS IMDSv2 documentation](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/configuring-instance-metadata-service.html)
- [CWE-918: Server-Side Request Forgery](https://cwe.mitre.org/data/definitions/918.html)
- [Google Cloud metadata server security](https://cloud.google.com/compute/docs/metadata/overview)

## Field validation 1

A webhook tester fetched 169. Document owner, rollback path, and leading metric before promoting `ssrf-prevention-defense` to 100% traffic.

## Field validation 2

A webhook tester fetched 169. Document owner, rollback path, and leading metric before promoting `ssrf-prevention-defense` to 100% traffic.

## Field validation 3

A webhook tester fetched 169. Document owner, rollback path, and leading metric before promoting `ssrf-prevention-defense` to 100% traffic.

## Logging blocked SSRF attempts

Log blocked URL, source service, and timestamp — aggregate alerts on spike from one pod indicate compromise or misconfiguration worth paging.

## Egress proxy allowlists

Default-deny egress from fetcher services — allow only required external hostnames at network policy layer.