---
title: "AI Agents: Cert Manager Dns01"
slug: "agent-cert-manager-dns01"
description: "cert-manager DNS-01 challenges for agent platforms — wildcard TLS, multi-tenant ingress, Route53 and Cloudflare solvers, propagation delays, and renewal failure modes."
datePublished: "2026-02-19"
dateModified: "2026-02-19"
tags: ["AI", "Agent", "Cert"]
keywords: "cert-manager DNS-01, Let's Encrypt wildcard, ACME challenge, Kubernetes TLS, agent ingress, Route53 solver, Cloudflare DNS-01, certificate renewal"
faq:
  - q: "When should agent platforms use DNS-01 instead of HTTP-01?"
    a: "Use DNS-01 when you need wildcard certificates (*.agents.example.com), when agent APIs sit behind internal-only ingress without public HTTP reachability, when terminating TLS at a layer that cannot serve ACME HTTP paths, or when issuing certs for services without public A records yet. HTTP-01 is simpler for single-hostname public ingress but cannot issue wildcards."
  - q: "What IAM permissions does the Route53 DNS-01 solver need?"
    a: "Minimum: route53:GetChange, route53:ChangeResourceRecordSets, route53:ListResourceRecordSets on the hosted zone; route53:ListHostedZonesByName for zone discovery. Scope IAM policies to the specific zone ARN. IRSA on EKS or workload identity on GKE avoids long-lived access keys in cluster secrets."
  - q: "Why do DNS-01 challenges fail with 'propagation' or 'NXDOMAIN' errors?"
    a: "Let's Encrypt queries authoritative DNS from multiple vantage points. Failure modes include TTL caching, CNAME to external DNS with delayed updates, split-horizon DNS where internal views differ from public, typos in zone names, and API rate limits on DNS providers. cert-manager's recursiveNameserversOnly and increased challenge timeout settings help; fixing DNS architecture helps more."
  - q: "How do you prevent certificate expiry for agent microservices?"
    a: "Monitor cert-manager Certificate Ready=False conditions, Prometheus metrics certmanager_certificate_expiration_timestamp_seconds, and alert at 14 days before NotAfter. Run cert-manager v1.13+ with automatic renewal at 2/3 lifetime. Test renewal monthly by forcing re-issue in staging. Document runbook for stuck challenges — expired agent gateway certs take down all tenant traffic."
---
Wildcard TLS for `*.agents.example.com` broke our HTTP-01 automation on the first try — Let's Encrypt couldn't reach the ACME challenge path on tenant subdomains that didn't exist yet. Switching to **cert-manager with DNS-01** fixed issuance but introduced a new failure class: Route53 API throttling during parallel tenant onboarding, TXT records orphaned in `_acme-challenge` subdomains, and a silent renewal failure that expired the agent gateway cert on a Friday night because nobody wired alerts to the `Certificate` resource status.

Agent platforms often expose per-tenant subdomains (`acme.agents.example.com`), internal gRPC mesh endpoints, webhook receivers, and admin APIs behind the same ingress controller. DNS-01 proves domain control by publishing `_acme-challenge` TXT records — no public HTTP required — and it is the **only** ACME method Let's Encrypt accepts for wildcard certs. cert-manager automates the loop: create Certificate → Order → Challenge → solver creates TXT → CA validates → Secret populated → ingress references Secret.

## ACME DNS-01 flow in Kubernetes

```
┌─────────────┐    Certificate     ┌──────────────┐    TXT record    ┌─────────────┐
│ cert-manager│ ────────────────► │  ACME CA     │ ◄─────────────── │  Route53 /  │
│  controller │ ◄── signed cert ── │ (Let's Encrypt)│   queries DNS   │  Cloudflare │
└─────────────┘                    └──────────────┘                  └─────────────┘
       │ creates
       ▼
  Secret tls-agent-wildcard ──► Ingress / Gateway API
```

1. You define a `Certificate` referencing an `Issuer` or `ClusterIssuer`.
2. cert-manager creates an `Order` and `Challenge` resource.
3. DNS-01 solver patches TXT at `_acme-challenge.<hostname>`.
4. CA polls DNS globally; on success, cert lands in `spec.secretName`.
5. Renewal repeats automatically ~30 days before expiry (Let's Encrypt certs valid 90 days).

## ClusterIssuer with Route53 solver

Production pattern on EKS with IRSA:

```yaml
# clusterissuer-letsencrypt-prod.yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod-dns01
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: platform-security@example.com
    privateKeySecretRef:
      name: letsencrypt-prod-account-key
    solvers:
      - dns01:
          route53:
            region: us-east-1
            hostedZoneID: Z1234567890ABC
            # IRSA: cert-manager SA annotated with role ARN
        selector:
          dnsZones:
            - "agents.example.com"
```

cert-manager ServiceAccount annotation:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: cert-manager
  namespace: cert-manager
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::123456789012:role/cert-manager-route53
```

IAM policy (scoped):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["route53:GetChange", "route53:ChangeResourceRecordSets", "route53:ListResourceRecordSets"],
      "Resource": "arn:aws:route53:::hostedzone/Z1234567890ABC"
    },
    {
      "Effect": "Allow",
      "Action": "route53:ListHostedZonesByName",
      "Resource": "*"
    }
  ]
}
```

## Wildcard certificate for agent ingress

```yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: agent-wildcard-tls
  namespace: agent-platform
spec:
  secretName: agent-wildcard-tls
  issuerRef:
    name: letsencrypt-prod-dns01
    kind: ClusterIssuer
  commonName: "*.agents.example.com"
  dnsNames:
    - "*.agents.example.com"
    - "agents.example.com"   # apex if needed for marketing landing
  renewBefore: 720h           # 30 days
```

Ingress reference (nginx):

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: agent-tenant-ingress
  namespace: agent-platform
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod-dns01
spec:
  tls:
    - hosts:
        - "*.agents.example.com"
      secretName: agent-wildcard-tls
  rules:
    - host: "*.agents.example.com"
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: agent-gateway
                port:
                  number: 443
```

For Gateway API, attach cert to `Gateway` listener TLS configuration referencing the same Secret.

## Cloudflare and multi-solver setups

Agent platforms split DNS: public marketing on Cloudflare, internal service discovery on Route53. cert-manager supports **multiple solvers** with selectors:

```yaml
spec:
  acme:
    solvers:
      - selector:
          dnsNames:
            - "internal.agents.example.com"
        dns01:
          route53:
            region: us-east-1
            hostedZoneID: ZINTERNAL
      - selector:
          dnsZones:
            - "agents.example.com"
        dns01:
          cloudflare:
            apiTokenSecretRef:
              name: cloudflare-api-token
              key: api-token
```

Cloudflare API token needs `Zone:DNS:Edit` on the specific zone. Prefer tokens over global API keys. Watch Cloudflare's propagation — cert-manager can set `propagationPolicy: None` on Cloudflare solver in recent versions to skip full-zone polling when appropriate.

## Propagation, timing, and debugging stuck challenges

DNS-01 failures dominate cert-manager support threads. Checklist:

```bash
# Inspect challenge state
kubectl describe challenge -n agent-platform

# Expected TXT name and value appear in challenge status
dig +short TXT _acme-challenge.tenant.agents.example.com @8.8.8.8
dig +short TXT _acme-challenge.tenant.agents.example.com @1.1.1.1

# cert-manager logs
kubectl logs -n cert-manager deploy/cert-manager -f --since=10m
```

Common root causes:

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| NXDOMAIN | Wrong zone / delegated subdomain | Verify NS chain, hosted zone ID |
| TXT exists internally only | Split-horizon DNS | Publish TXT to public authoritative |
| Intermittent failure | Slow TTL, CNAME to external DNS | Lower TTL on `_acme-challenge`, avoid CNAME indirection |
| 403 on Route53 | IAM too narrow or wrong zone | Audit IRSA role trust + policy |
| Rate limited | Too many orders during load test | Stagger Certificate resources, use staging CA |

Use Let's Encrypt **staging** issuer for CI and tenant-provisioning integration tests:

```yaml
spec:
  acme:
    server: https://acme-staging-v02.api.letsencrypt.org/directory
```

Staging certs are not trusted by browsers but exercise the full DNS loop without rate limit burns.

## Per-tenant certificates vs wildcard

Wildcard `*.agents.example.com` covers all tenant subdomains with one cert — operationally simple. Some enterprise tenants demand **dedicated certs** with their own domain (`agents.acme.com`) via DNS-01 on their delegated zone:

```yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: tenant-acme-custom-domain
  namespace: tenant-acme
spec:
  secretName: tenant-acme-tls
  issuerRef:
    name: letsencrypt-prod-dns01
    kind: ClusterIssuer
  dnsNames:
    - "agents.acme.com"
  # Tenant provides DNS credentials via sealed secret or external-dns delegation
```

Automate carefully — each custom domain is a renewal dependency and support ticket vector. Centralize monitoring.

## Security considerations

- **ACME account key** stored in cluster Secret — restrict RBAC; backup for account recovery.
- **DNS provider credentials** in cert-manager namespace — network policy isolate cert-manager; rotate tokens quarterly.
- **CT logging** — all Let's Encrypt certs appear in Certificate Transparency logs; expect subdomain discovery. Plan internal host naming accordingly.
- **Private CAs** — air-gapped agent deployments may use cert-manager with Vault or step-ca instead of public ACME; DNS-01 still applies for internal zones.

Never grant cert-manager broad `route53:ChangeResourceRecordSets` on `*` — compromised cert-manager becomes DNS takeover for the entire domain.

## Observability and renewal SLOs

Prometheus alerts (kube-prometheus-stack includes cert-manager metrics):

```yaml
# prometheus-rules/cert-manager.yaml
groups:
  - name: cert-manager
    rules:
      - alert: AgentCertExpiringSoon
        expr: |
          certmanager_certificate_expiration_timestamp_seconds{namespace="agent-platform"} - time() < 14 * 86400
        for: 1h
        labels:
          severity: warning
        annotations:
          summary: "Agent TLS cert expiring within 14 days"
      - alert: AgentCertNotReady
        expr: certmanager_certificate_ready_status{condition="False"} == 1
        for: 15m
        labels:
          severity: critical
        annotations:
          summary: "cert-manager Certificate not Ready — agent ingress at risk"
```

Runbook steps for `CertificateNotReady`:

1. `kubectl describe certificate,certificateRequest,order,challenge`
2. Verify TXT with public resolvers
3. Check DNS provider status page and API quotas
4. If challenge corrupted, delete Challenge resource for retry (cert-manager recreates)
5. Temporary mitigation: import manually issued cert to Secret (document debt)

Test renewal by annotating Certificate to force reissue in staging monthly.

## Interaction with agent deploy velocity

High churn tenant namespaces tempt engineers to embed `Certificate` per microservice. **Prefer shared wildcard** at gateway plus mTLS inside mesh for service-to-service. Fewer ACME orders = fewer DNS API calls = fewer Friday incidents.

External-dns can coexist — ensure it does not delete `_acme-challenge` TXT records mid-validation. Use ownership annotations or exclude `_acme-challenge` via txtOwnerId patterns.

## Gateway API and cert-manager Certificate discovery

Modern agent gateways using Gateway API attach TLS at the `Gateway` listener:

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: agent-gateway
  namespace: agent-platform
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod-dns01
spec:
  gatewayClassName: istio
  listeners:
    - name: https-wildcard
      hostname: "*.agents.example.com"
      port: 443
      protocol: HTTPS
      tls:
        mode: Terminate
        certificateRefs:
          - name: agent-wildcard-tls
            kind: Secret
```

cert-manager's `ingress-shim` equivalent for Gateway is the **`cert-manager.io/issuer` annotation on Gateway** or explicit `Certificate` resources — verify your cert-manager version supports Gateway API GA resources. Misconfiguration leaves listeners serving default fake certs while `Certificate` status shows Ready on an unreferenced Secret.

## cert-manager upgrade and CRD migration notes

Agent platforms lagging cert-manager versions hit breaking changes: ACME API version bumps, solver config renames, and webhook failures blocking all pod creation during partial upgrades.

Safe upgrade path:

1. Read release notes for target version (v1.13 → v1.16 common jump)
2. Apply CRD updates **before** controller Deployment
3. Staging cluster: full DNS-01 cycle on wildcard test cert
4. Production: upgrade during low-traffic window; watch `certmanager_webhook_request_duration_seconds` for webhook timeouts

Helm values to pin:

```yaml
# values-cert-manager.yaml
installCRDs: true
prometheus:
  enabled: true
  servicemonitor:
    enabled: true
extraArgs:
  - --dns01-recursive-nameservers-only=true
  - --dns01-recursive-nameservers=8.8.8.8:53,1.1.1.1:53
```

`dns01-recursive-nameservers-only` forces validation against public resolvers — catches split-horizon mistakes in CI before production orders fail.

## Disaster recovery for ACME account and certificates

Back up these cluster Secrets to encrypted object storage (not git):

- `letsencrypt-prod-account-key` — losing it means new ACME account, fresh rate limits, re-validating all domain authorizations
- `agent-wildcard-tls` — emergency import if cert-manager down during incident
- DNS provider API tokens referenced by solvers

Recovery runbook when cert-manager namespace deleted:

1. Restore CRDs and Helm release from IaC
2. Restore ACME account key Secret first
3. Reapply ClusterIssuer and Certificate manifests
4. DNS-01 challenges re-run automatically — expect 2–5 minute issuance if DNS healthy
5. Verify ingress/Gateway picks up new Secret (may require rolling restart)

Let's Encrypt rate limits: 50 certificates per registered domain per week, 5 duplicate certificates per week. Botched automation loops can exhaust limits — use staging, add `Certificate` creation guards in tenant provisioning webhooks.

## mTLS and DNS-01 boundary

DNS-01 proves control of DNS, not that traffic reaches your cluster. Agent **internal** services (model router, tool executor) should use mesh mTLS (Istio, Linkerd) with cert-manager-issued internal CA — separate `ClusterIssuer` using cert-manager's **CA issuer** or HashiCorp Vault — not public Let's Encrypt. Public DNS-01 certs belong at the north-south gateway only.

Confusion between the two issuers causes internal services to request public certs for `.svc.cluster.local` names — CAs reject, challenges hang, on-call pages at 2 AM.

## Closing

cert-manager DNS-01 is the standard path for wildcard and internal agent ingress TLS. Success requires correct DNS authority, least-privilege cloud IAM, propagation-aware debugging, and renewal monitoring treated as production SLOs — not certificate install-and-forget. HTTP-01 remains fine for a single public hostname; everything else in multi-tenant agent land tends toward DNS-01 sooner or later.

## Resources

- [cert-manager DNS-01 documentation](https://cert-manager.io/docs/configuration/acme/dns01/)
- [Let's Encrypt DNS-01 challenge](https://letsencrypt.org/docs/challenge-types/#dns-01-challenge)
- [cert-manager Route53 solver](https://cert-manager.io/docs/configuration/acme/dns01/route53/)
- [AWS IRSA for cert-manager on EKS](https://cert-manager.io/docs/configuration/acme/dns01/route53/#set-up-an-iam-role)
- [Prometheus cert-manager metrics](https://cert-manager.io/docs/devops-tools/prometheus/)
