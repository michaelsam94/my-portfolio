---
title: "AI Agents: External Dns Automation"
slug: "agent-external-dns-automation"
description: "ExternalDNS for Kubernetes — automated Route53, Cloudflare, and GCP DNS from Ingress and Service annotations, ownership TXT records, split-horizon patterns, and safe cutovers for agent endpoints."
datePublished: "2026-02-16"
dateModified: "2026-02-16"
tags: ["AI", "Agent", "External"]
keywords: "ExternalDNS, Kubernetes DNS automation, Route53, Cloudflare, Ingress DNS, agent endpoints, DNS ownership"
faq:
  - q: "What does ExternalDNS do in a Kubernetes cluster?"
    a: "ExternalDNS watches Ingress, Service, Gateway API, and custom resources for hostnames and target records, then creates/updates/deletes DNS records in your provider (Route53, Cloudflare, Google Cloud DNS, Azure DNS). It keeps public DNS in sync with cluster state so agent API endpoints survive redeploys without manual ticket-driven DNS changes."
  - q: "How does ExternalDNS prevent two clusters from fighting over the same record?"
    a: "It writes ownership metadata — typically TXT records at `heritage=<domain>` or provider-specific labels — encoding which cluster/namespace owns a name. A second ExternalDNS instance refuses to adopt records it does not own unless you explicitly configure domain filters and txt-owner-id per cluster."
  - q: "Should agent inference endpoints use ExternalDNS or a static CNAME?"
    a: "Use ExternalDNS when hostnames bind to cluster Ingress/Gateway that change with deploys. Use static CNAMEs at a global load balancer (Cloudflare, AWS Global Accelerator) when multiple clusters or serverless backends sit behind one stable name. Many teams CNAME `api.agents.example.com` → Ingress LB hostname managed by ExternalDNS on a stable `ingress-lb` Service."
  - q: "What are the biggest operational risks with ExternalDNS?"
    a: "Over-broad domain filters deleting production records, stale ownership after cluster decommission, rate limits on Cloudflare/Route53 APIs during mass Ingress churn, and TTL too low during certificate issuance storms. Always scope `--domain-filter`, use `--txt-owner-id`, and test in a sandbox zone before pointing at production apex domains."
---
Every agent platform eventually exposes HTTPS endpoints: chat APIs, webhook receivers, MCP servers, eval dashboards. Someone creates an Ingress, grabs the load balancer hostname, opens a DNS ticket, waits two days, and ships. The next cluster migration repeats the ritual. ExternalDNS automates that loop — and introduces new failure modes when ownership, filters, and TTL are misconfigured.

This deep dive covers ExternalDNS architecture, provider-specific patterns, and production guardrails for teams running agent workloads on Kubernetes.

## Control loop: desired state in DNS

ExternalDNS implements the same reconcile pattern as controllers:

1. **List** DNS records from the provider API (or cache).
2. **Watch** Kubernetes resources annotated with target hostnames.
3. **Plan** create/update/delete to match desired records.
4. **Apply** changes with provider-specific adapters.

```
┌─────────────┐     watch      ┌──────────────┐     API      ┌─────────────┐
│  Ingress /  │ ─────────────► │ ExternalDNS  │ ───────────► │ Route53 /   │
│  Service    │   hostnames    │  controller  │   upsert     │ Cloudflare  │
└─────────────┘                └──────────────┘              └─────────────┘
                                      │
                                      ▼
                               TXT ownership record
                               (heritage=external-dns)
```

For agent stacks, the watched sources usually include:

- **Ingress** with `spec.rules[].host` for `agent-api.example.com`
- **Gateway API HTTPRoute** hostnames (ExternalDNS 0.14+)
- **LoadBalancer Services** when exposing TCP MCP or gRPC without Ingress

## Baseline Helm deployment

```yaml
# values-external-dns.yaml
provider:
  name: aws

domainFilters:
  - agents.example.com

txtOwnerId: prod-us-east-1-agents

policy: sync  # upsert-only is safer for shared zones; sync deletes orphans

sources:
  - ingress
  - service

serviceAccount:
  create: true
  annotations:
    eks.amazonaws.com/role-assume: arn:aws:iam::123456789012:role/external-dns-route53

extraArgs:
  - --aws-zone-type=public
  - --annotation-filter=external-dns.alpha.kubernetes.io/exclude notin (true)
  - --ingress-class=nginx
```

Install:

```bash
helm repo add external-dns https://kubernetes-sigs.github.io/external-dns/
helm upgrade --install external-dns external-dns/external-dns \
  -n kube-system \
  -f values-external-dns.yaml
```

IAM for Route53 should be minimal — `ChangeResourceRecordSets`, `ListResourceRecordSets`, `ListHostedZones` on the specific hosted zone ARN, not `route53:*` on `*`.

## Annotating agent Ingress resources

Explicit annotations beat magic defaults when multiple teams share a cluster:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: agent-chat-api
  namespace: agents-prod
  annotations:
    external-dns.alpha.kubernetes.io/hostname: chat.agents.example.com
    external-dns.alpha.kubernetes.io/ttl: "300"
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - chat.agents.example.com
      secretName: chat-agents-tls
  rules:
    - host: chat.agents.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: agent-gateway
                port:
                  number: 8080
```

ExternalDNS creates an A/AAAA alias (or CNAME) to the Ingress controller load balancer. cert-manager completes HTTP-01 or DNS-01 challenges on the same hostname — coordinate TTL: very low TTL during cert renewal reduces stuck propagation; 300s is a reasonable default for agent APIs.

## Cloudflare-specific patterns

Cloudflare proxy (orange cloud) sits in front of the origin. ExternalDNS can manage proxied records:

```yaml
extraArgs:
  - --cloudflare-proxied
  - --cloudflare-dns-records-per-page=5000

env:
  - name: CF_API_TOKEN
    valueFrom:
      secretKeyRef:
        name: cloudflare-api-token
        key: token
```

Token scopes: `Zone:DNS:Edit` for the target zone only. For agent endpoints needing WebSocket or long-lived SSE streams, verify Cloudflare timeout settings — DNS automation does not fix HTTP protocol limits.

Use **`upsert-only` policy** when the zone contains manual records (MX, verification TXT) ExternalDNS should never delete:

```yaml
extraArgs:
  - --policy=upsert-only
```

## Multi-cluster and blue-green cutovers

Running agent inference in `cluster-blue` and `cluster-green` requires distinct ownership:

| Cluster | txt-owner-id | hostnames during cutover |
|---------|--------------|--------------------------|
| blue | agents-blue | `chat.agents.example.com` (production) |
| green | agents-green | `chat-green.agents.example.com` (staging) |

Cutover sequence:

1. Deploy green; ExternalDNS creates `chat-green` records under green owner.
2. Validate agent evals against green hostname.
3. Update Ingress on green to claim `chat.agents.example.com` — or swap weighted Route53 records if using DNS-level traffic split.
4. Blue ExternalDNS releases ownership TXT; green adopts production name.

```typescript
// Internal runbook checker — not ExternalDNS itself
interface DnsCutoverChecklist {
  greenHostnameReachable: boolean;
  tlsValid: boolean;
  txtOwnerMatchesGreen: boolean;
  agentEvalPassRate: number;
  rollbackIngressManifest: string;
}

export function readyForProductionCutover(c: DnsCutoverChecklist): boolean {
  return (
    c.greenHostnameReachable &&
    c.tlsValid &&
    c.txtOwnerMatchesGreen &&
    c.agentEvalPassRate >= 0.98
  );
}
```

Never run two ExternalDNS instances with the same `txt-owner-id` in different clusters — they will corrupt ownership metadata.

## Split-horizon and private agent endpoints

Internal agent orchestrators (tool executors, PII-heavy workers) often use private DNS:

```yaml
extraArgs:
  - --aws-zone-type=private
  - --domain-filter=internal.agents.example.com
```

Pair with private hosted zones associated to the VPC. ExternalDNS on the cluster creates `executor.internal.agents.example.com` pointing to internal NLB. Public ExternalDNS instance uses `--domain-filter=agents.example.com` only — separate deployments, separate IAM roles.

## Gateway API, MCP endpoints, and non-HTTP services

Agent platforms increasingly expose Model Context Protocol (MCP) servers and gRPC tool backends alongside REST chat APIs. ExternalDNS sources differ by exposure pattern:

- **HTTPRoute (Gateway API):** add `gateway-httproute` to `--sources`; hostnames come from `spec.hostnames`.
- **TCP LoadBalancer Services:** annotate the Service directly when Ingress is not in path:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: mcp-tool-server
  namespace: agents-prod
  annotations:
    external-dns.alpha.kubernetes.io/hostname: mcp.agents.example.com
    external-dns.alpha.kubernetes.io/access: public
spec:
  type: LoadBalancer
  ports:
    - name: mcp
      port: 443
      targetPort: 8443
  selector:
    app: mcp-tool-server
```

WebSocket and server-sent event streams for streaming agent responses require stable DNS just like REST — but health checks at the load balancer must tolerate long-lived connections. Lowering TTL during agent model cutovers lets clients pick up new LB targets faster; raise TTL to 3600+ once the endpoint stabilizes to reduce provider API churn.

When MCP servers sit behind the same hostname as the chat API, use path-based routing on one Ingress rather than competing ExternalDNS hostnames on separate Services. Duplicate hostname declarations remain the most common source of flapping A records in multi-team clusters.

## Rate limits and reconciliation backoff

Route53 and Cloudflare throttle bulk changes. Agent deploy pipelines that recreate dozens of preview Ingresses (`pr-1842-chat.agents.example.com`) can hit rate limits during business hours.

Configure exponential backoff on ExternalDNS and cap preview namespace Ingress count via policy. For preview environments, use wildcard DNS (`*.preview.agents.example.com` → shared preview LB) managed once, with in-cluster routing by hostname — ExternalDNS maintains one record instead of hundreds.

```yaml
extraArgs:
  - --interval=5m
  - --events-trigger-loop=false
```

Longer sync intervals trade freshness for API quota headroom. For production agent APIs, 1–3 minute intervals are typical; preview zones can run 10–15 minutes.

## Observability and alerting

Metrics to export (Prometheus):

- `external_dns_registry_errors_total`
- `external_dns_source_errors_total`
- `external_dns_controller_last_sync_timestamp_seconds`

Alert when last successful sync > 15 minutes or registry errors spike after mass Ingress deletion (namespace teardown during agent experiment cleanup).

Log every planned change at INFO in staging; aggregate `kind=DELETE` in production — unexpected deletes often mean wrong `--domain-filter` or orphaned `--txt-owner-id` after cluster rebuild.

## Security

- **IRSA / workload identity** for cloud API access — no long-lived keys in ConfigMaps.
- **Domain filter** is your blast-radius limiter. Omitting it on a Route53 role with broad permissions has deleted apex domains in real incidents.
- **Annotation filter** excludes system namespaces: `external-dns.alpha.kubernetes.io/exclude=true` on kube-system Ingresses.
- Audit DNS API calls via CloudTrail — unexpected `ChangeResourceRecordSets` at 3am from a compromised node identity is a kill-switch event.

## Testing before production

1. **Dry-run / mock provider** in CI with a fake zone.
2. **Sandbox subdomain** `dns-test.agents.example.com` with full sync policy.
3. **Chaos:** delete Ingress, confirm record removal within TTL + sync interval.
4. **Ownership transfer:** simulate cluster rebuild with new owner ID — manual TXT cleanup procedure documented.

## Common mistakes

- **`sync` policy on shared corporate zones** — deletes MX records ExternalDNS did not create but matched its filter logic. Use `upsert-only` or narrow filters.
- **Same hostname on two Ingresses** — last writer wins; intermittent flapping to different load balancers.
- **Ignoring IPv6** — AAAA records missing when Ingress publishes IPv6; agent clients on IPv6-only networks fail.
- **TTL=60 everywhere** — amplifies provider API rate limits during rolling agent deploys.

## The takeaway

ExternalDNS removes manual DNS tickets from the agent release path when ownership, filters, and policies are explicit. Scope each controller instance to one zone class (public vs private), one owner ID per cluster, and annotate Ingresses deliberately. Pair with cert-manager, monitor sync health, and treat DNS automation with the same reverence as the agent API it points to — because when DNS is wrong, every tool call fails before the model runs.

## Resources

- [ExternalDNS official documentation](https://kubernetes-sigs.github.io/external-dns/)

- [ExternalDNS GitHub repository](https://github.com/kubernetes-sigs/external-dns)

- [AWS Route53 IAM policy examples for ExternalDNS](https://kubernetes-sigs.github.io/external-dns/latest/docs//tutorials/aws/)

- [Cloudflare provider tutorial](https://kubernetes-sigs.github.io/external-dns/latest/docs/tutorials/cloudflare/)

- [cert-manager DNS01 + ExternalDNS integration](https://cert-manager.io/docs/configuration/acme/dns01/)
