---
title: "RAG: Egress Filtering Dns"
slug: "rag-egress-filtering-dns"
description: "Egress filtering and DNS controls for RAG pipelines — allowlisted embedding APIs, blocking data exfiltration, and network policy for ingestion workers."
datePublished: "2026-02-04"
dateModified: "2026-07-17"
tags: ["AI", "Rag", "Egress"]
keywords: "rag, egress, filtering, dns, ai, production, engineering, architecture"
faq:
  - q: "Why do RAG ingestion pods need egress filtering?"
    a: "Ingestion workers read untrusted documents and run parsers that historically suffer RCE vulnerabilities. Unrestricted egress lets compromised pods exfiltrate corpus content, scrape credentials from metadata services, or join botnets. Allowlists limiting destinations to S3, embedding APIs, and internal services shrink blast radius."
  - q: "Should egress control happen at DNS, network policy, or both?"
    a: "Use both for defense in depth. DNS filtering (Policy DNS, CoreDNS plugins) blocks resolution of unknown domains early with clear logs. Kubernetes NetworkPolicy or Cilium policies enforce IP/port allowlists even when malware uses hard-coded IPs. DNS alone fails against IP literals; network policy alone misses domain-level audit trails."
  - q: "How do you allowlist SaaS embedding providers that use CDNs?"
    a: "Prefer provider-documented domain lists and stable API hostnames over wildcard CDNs where possible. For dynamic IPs, use provider-published IP range JSON (AWS, Cloudflare) synced to policy weekly, or route outbound through a proxy that terminates TLS and validates SNI against allowlist."
---
After a parser CVE shipped unpatched for eleven days, a security researcher demonstrated outbound DNS queries from ingestion pods to `paste.ee` and `185.220.x.x`—neither on any architecture diagram. The pods needed S3 read, an internal chunk queue, and HTTPS to the embedding vendor. They had unrestricted egress because "debugging was easier." Compromised workers could have exfiltrated pre-redaction legal documents; luck and a researcher email prevented it.

RAG pipelines combine **untrusted input** with **high-value outbound access**—cloud storage, paid LLM APIs, internal databases. **Egress filtering** restricts where workloads can connect. **DNS filtering** is the first choke point: if a pod cannot resolve attacker domains, many exfil paths never start; combined with L4/L7 network policy, you get enforceable allowlists instead of hope.

## Threat model for RAG worker egress

Expected legitimate destinations:

| Destination | Port | Purpose |
|-------------|------|---------|
| `s3.{region}.amazonaws.com` | 443 | Source documents |
| `api.openai.com` (example) | 443 | Embeddings |
| Internal `chunk-queue.rag.svc` | 443/9092 | Pipeline messaging |
| `sts.amazonaws.com` | 443 | IAM credentials |

Everything else is suspicious by default—including `metadata.google.internal`, public DNS resolvers misused for tunneling, and crypto pool domains.

Attack paths egress filtering blocks:

- DNS exfiltration encoding data in subdomain queries
- HTTPS POST to attacker-controlled servers
- SSRF via parser fetching arbitrary URLs from document hyperlinks (handle separately with URL fetch proxy)

## DNS filtering architecture

```
[Pod] → CoreDNS / NodeLocal DNSCache
           ↓
    [Policy plugin / external DNS firewall]
           ↓ allow / deny / log
    [Upstream resolver 1.1.1.1 or VPC resolver]
```

**CoreDNS** `policy` or `firewall` plugins, **Cloudflare Gateway**, **Infoblox**, or cloud **Route53 Resolver DNS Firewall** evaluate queries against rules:

```yaml
# Example rule intent
allow:
  - suffix: amazonaws.com
  - suffix: api.openai.com
  - suffix: rag.internal.example.com
deny:
  - suffix: .
    log: true
    message: "RAG ingest namespace blocked DNS"
```

Log denied queries with pod identity (via k8s metadata) for SOC review.

### Bypass risks

Malware using **hard-coded IPs** bypasses DNS—complement with NetworkPolicy:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: rag-ingest-egress
  namespace: rag-ingest
spec:
  podSelector:
    matchLabels:
      app: document-parser
  policyTypes: [Egress]
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: kube-system
      ports:
        - protocol: UDP
          port: 53
    - to:
        - ipBlock:
            cidr: 10.0.0.0/8   # internal services
    - ports:
        - protocol: TCP
          port: 443
      to:
        - ipBlock:
            cidr: 0.0.0.0/0
            except:
              - 10.0.0.0/8
              - 172.16.0.0/12
              - 192.168.0.0/16
```

Broad 443 to public internet still allows IP-literal exfil—**Cilium FQDN policy** or **egress gateway** with TLS SNI inspection is tighter.

## Egress gateway pattern for SaaS APIs

Centralize outbound HTTPS through **squid/envoy egress proxy**:

1. Pods only reach proxy on 3128/443
2. Proxy validates `:authority` / SNI against allowlist
3. TLS intercept optional for corporate compliance (careful with embedding API cert pinning)

```yaml
# Envoy ext_authz or route match
domains:
  - "api.openai.com"
  - "*.amazonaws.com"
```

Embedding providers rotating CDN edges complicate IP allowlists—domain-based proxy rules age better. Automate sync of vendor IP ranges where domain pinning insufficient.

## Hyperlink fetching is not pod egress

Documents contain URLs. **Never** let parsers fetch arbitrary links directly from ingestion pods with full egress.

Dedicated **URL fetch service**:

- Resolves DNS through same filtering
- Blocks RFC1918, link-local, cloud metadata IPs
- Rate limited, size capped, content-type allowlist
- Returns sanitized bytes to parser over internal RPC

Parser pod egress then excludes general internet entirely—only fetch service reaches external URLs.

## Operational workflow for allowlist changes

New embedding vendor or S3 bucket region requires ticket:

1. Security review destination necessity
2. PR to DNS policy + NetworkPolicy + proxy config
3. Staging validation with `dig`/`curl` from test pod
4. Deploy with 24h enhanced logging before enforce mode

Emergency break-glass: time-limited policy exception with manager approval—auto-expire.

## Observability

Dashboards:

- Top denied DNS queries by pod deployment
- Egress bytes by destination category
- New unique domains attempted (weekly report)

Alert on any `rag-ingest` pod resolving non-allowlisted domain—page severity lower than shell spawn (eBPF) but investigate same day.

Correlate DNS deny logs with document IDs being processed—identifies malicious file vs policy gap.

## Compliance mapping

SOC2 CC6.6, ISO 27001 A.13.1.1 expect network segregation. Document RAG egress architecture in security packet: diagrams showing default-deny, allowlist maintenance owner, break-glass procedure.

GDPR: egress to US SaaS from EU ingest requires transfer mechanism—geo routing separate concern but DNS logs prove traffic stayed in approved endpoints.

## Testing

CI **network policy tests** (https://github.com/appvia/kompose examples, Cilium policy verifier):

```bash
kubectl exec -n rag-ingest test-pod -- curl -m 5 https://evil.example.com
# expect timeout or connection refused
kubectl exec -n rag-ingest test-pod -- curl -m 5 https://s3.eu-west-1.amazonaws.com
# expect success
```

Quarterly red team: drop test binary in staging parser attempting DNS tunnel—verify deny + alert.

Egress filtering and DNS controls turn "compromised parser" from full corpus leak into failed connection attempts logged to SOC. Default-deny outbound from ingestion namespaces, allowlist embedding and storage domains explicitly, and never conflate document hyperlink fetching with unrestricted pod internet access.

## IPv6 and dual-stack considerations

Egress policies written for IPv4-only miss **IPv6 exfil** paths. Enable IPv6 on nodes only with symmetric network policies, or disable IPv6 in pod network if unsupported—document choice. DNS filtering must handle AAAA records; malware resolving dual-stack domains bypasses IPv4-only blocks.

## Incident response for egress violations

Runbook: on denied DNS alert for production ingest pod, **isolate pod** (NetworkPolicy deny all egress except SIEM), snapshot memory if forensics requires, rotate secrets mounted to pod, preserve DNS query log with timestamp correlation to document being processed. Do not delete pod immediately—lose evidence.

Post-incident: add denied domain pattern to threat intel feed; scan other pods for same query history via centralized DNS logs.

## Break-glass egress procedures

Document **time-limited egress exception** process: security approves 4-hour widen to specific domain for vendor support session; auto-revert via Terraform TTL or scheduled policy rollback. Post-exception review mandatory—did we patch parser instead of permanent hole?

Break-glass usage metrics dashboard—frequent exceptions indicate allowlist maintenance neglected or tooling friction driving unsafe workarounds.

## Shared services and platform egress

Central **egress gateway** shared by RAG and non-RAG workloads simplifies allowlist maintenance—platform team owns proxy, application teams request FQDN additions via ticket. RAG-specific sensitive namespaces still default-deny direct egress even to gateway unless authenticated mTLS identity presented.

Log retention for DNS denials balances SOC needs vs storage cost—90 days hot, 1 year cold archive for regulated customers requesting proof of egress controls during audits.

## Wrapping up egress posture

Default-deny egress from RAG ingest namespaces is baseline hygiene in 2026, not paranoia. The paste.ee incident class—compromised parser, unrestricted outbound—ends when DNS and network policy block resolution and connection before data leaves the cluster. Pair technical controls with procurement: parser vendors must disclose outbound network requirements during security review so allowlists are complete on day one, not discovered during incident response.

Include egress allowlist diffs in pull request templates for any parser or OCR dependency upgrade—new libraries often introduce unexpected CDN or telemetry domains that default-deny policies catch only if reviewers know to look.

Egress posture reviews belong in every parser upgrade security checklist—new dependencies are the most common reason allowlists need expansion before production deploy, not zero-day exploits.

## Common regressions around egress filtering dns

Teams often pass a demo and then regress under load: retries without jitter, missing idempotency keys, or caches that never invalidate. Write a short regression list specific to egress filtering dns and turn each item into an automated check or a game-day step. Prefer failing CI on the regression over discovering it from customer tickets. When you change defaults, update alerts in the same pull request so observability stays coupled to behavior.
