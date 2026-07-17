---
title: "RAG: Cert Manager Dns01"
slug: "rag-cert-manager-dns01"
description: "cert-manager DNS-01 challenges issue TLS certificates for internal RAG API endpoints—wildcard certs for multi-tenant retrieval services without HTTP-01 ingress exposure."
datePublished: "2026-02-18"
dateModified: "2026-07-17"
tags: ["AI", "Rag", "Cert"]
keywords: "cert-manager, DNS-01, ACME, Let's Encrypt, TLS certificates, Kubernetes, RAG API, wildcard certificate, Route53, Cloudflare DNS"
faq:
  - q: "Why use DNS-01 instead of HTTP-01 for RAG API certificates?"
    a: "DNS-01 proves domain ownership via TXT records, enabling wildcard certificates (*.rag.internal.example.com) and certs for services without public HTTP endpoints. RAG retrieval APIs often run on internal ingress or service mesh—HTTP-01 requires exposing /.well-known/acme-challenge/ publicly."
  - q: "What DNS provider integrations does cert-manager support?"
    a: "cert-manager supports Route53, Cloudflare, Google Cloud DNS, Azure DNS, and 30+ providers via webhook solvers. Choose based on where your RAG API DNS records live. Cloudflare and Route53 are the most common in production Kubernetes."
  - q: "How do you automate cert renewal for RAG services?"
    a: "cert-manager Certificate resources auto-renew before expiry (default 30 days before). Monitor Certificate Ready condition and cert-manager metrics. Failed DNS-01 challenges during renewal usually indicate IAM permission drift or API token expiry—not something users notice until TLS handshake fails."
---
The internal RAG retrieval API served ten tenant-specific subdomains—`acme.rag.internal.example.com`, `beta.rag.internal.example.com`, and eight more. Each needed TLS because service mesh mTLS terminated at the gateway and client SDKs validated certificates. HTTP-01 ACME was impossible: no public ingress, no port 80 exposure for challenge paths. DNS-01 via cert-manager with Route53 solved it—one wildcard Certificate resource, automatic renewal, TXT record challenges invisible to RAG clients.

TLS for RAG infrastructure is non-negotiable: retrieval APIs carry query text that may include sensitive context, embedding endpoints accept document payloads, and admin APIs expose corpus management. cert-manager with DNS-01 is the standard Kubernetes pattern for internal and wildcard certificates.

## ACME challenge types for RAG deployments

| Challenge | Proves | Wildcard | Internal services |
|-----------|--------|----------|-------------------|
| HTTP-01 | Control of web server | No | Requires public HTTP |
| DNS-01 | Control of DNS zone | Yes | Works for internal |
| TLS-ALPN-01 | Control of TLS port | No | Requires public 443 |

RAG APIs on internal ingress, private GKE clusters, or VPN-only access need DNS-01.

## cert-manager installation and issuers

Install cert-manager in the cluster:

```bash
helm repo add jetstack https://charts.jetstack.io
helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  --set crds.enabled=true
```

Create a ClusterIssuer for Let's Encrypt production:

```yaml
# cert-manager/cluster-issuer-letsencrypt-prod.yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: platform@example.com
    privateKeySecretRef:
      name: letsencrypt-prod-account-key
    solvers:
      - dns01:
          route53:
            region: us-east-1
            hostedZoneID: Z1234567890ABC
        selector:
          dnsZones:
            - "rag.internal.example.com"
```

For Cloudflare:

```yaml
    solvers:
      - dns01:
          cloudflare:
            apiTokenSecretRef:
              name: cloudflare-api-token
              key: api-token
        selector:
          dnsZones:
            - "rag.example.com"
```

Use staging issuer first to avoid rate limits during testing:

```yaml
    server: https://acme-staging-v02.api.letsencrypt.org/directory
```

## Wildcard certificate for multi-tenant RAG

One wildcard cert covers all tenant subdomains:

```yaml
# cert-manager/rag-wildcard-cert.yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: rag-api-wildcard
  namespace: rag-production
spec:
  secretName: rag-api-tls
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  dnsNames:
    - "rag.internal.example.com"
    - "*.rag.internal.example.com"
  renewBefore: 720h  # 30 days
```

cert-manager creates CertificateRequest → Order → Challenge → TXT record → validation → Secret with tls.crt and tls.key.

Reference in Ingress:

```yaml
# ingress/rag-api.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: rag-api
  namespace: rag-production
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
    - hosts:
        - "*.rag.internal.example.com"
      secretName: rag-api-tls
  rules:
    - host: "*.rag.internal.example.com"
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: rag-retrieval
                port:
                  number: 8080
```

## IAM permissions for Route53 DNS-01

cert-manager needs permission to create/delete TXT records:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "route53:GetChange",
      "Resource": "arn:aws:route53:::change/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "route53:ChangeResourceRecordSets",
        "route53:ListResourceRecordSets"
      ],
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

Attach via IRSA (IAM Roles for Service Accounts) on EKS:

```yaml
# cert-manager service account annotation
apiVersion: v1
kind: ServiceAccount
metadata:
  name: cert-manager
  namespace: cert-manager
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::123456789012:role/cert-manager-route53
```

Permission drift is the top cause of renewal failure—audit IAM when renewals break.

## Monitoring certificate lifecycle

Alert on Certificate not Ready:

```yaml
# prometheus-rules/cert-manager.yaml
groups:
  - name: cert-manager
    rules:
      - alert: CertificateExpiringSoon
        expr: certmanager_certificate_expiration_timestamp_seconds - time() < 7 * 86400
        labels:
          severity: warning
        annotations:
          summary: "Certificate {{ $labels.name }} expires in <7 days"
      - alert: CertificateNotReady
        expr: certmanager_certificate_ready_status{condition="False"} == 1
        for: 1h
        labels:
          severity: critical
```

Check challenge status on failure:

```bash
kubectl describe challenge -n rag-production
kubectl describe certificaterequest -n rag-production
kubectl logs -n cert-manager deploy/cert-manager
```

Common failures:
- TXT record propagation delay (increase challenge timeout)
- Wrong hosted zone ID
- Cloudflare proxy orange-cloud interfering (DNS-only for ACME)
- Rate limit hit (use staging, wait, or switch CA)

## Private CA alternative for air-gapped RAG

Let's Encrypt requires outbound internet. Air-gapped or strict compliance environments use private CA:

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: rag-private-ca
spec:
  ca:
    secretName: rag-ca-root-secret
```

Issue certs same as ACME flow but signed by internal CA. Clients must trust the CA root—distribute via corporate MDM or SDK configuration.

## cert-manager with service mesh

Istio/Linkerd gateways reference the same Secret:

```yaml
apiVersion: networking.istio.io/v1beta1
kind: Gateway
metadata:
  name: rag-gateway
  namespace: rag-production
spec:
  servers:
    - port:
        number: 443
        name: https
        protocol: HTTPS
      tls:
        mode: SIMPLE
        credentialName: rag-api-tls  # cert-manager Secret
      hosts:
        - "*.rag.internal.example.com"
```

cert-manager rotates Secret; Istio picks up new cert within sync interval (typically minutes).

## Multi-cluster and multi-region

Each cluster needs its own Certificate resource—or use cert-manager's `Certificate` with DNS solver in each cluster pointing to same zone. Let's Encrypt rate limits: 50 certs per registered domain per week. Wildcard counts as one.

For geo-distributed RAG with regional subdomains:

```
us-east.rag.example.com  → cert in us-east-1 cluster
eu-west.rag.example.com   → cert in eu-west-1 cluster
*.rag.example.com         → wildcard if single global ingress
```

## Security considerations

- Store Cloudflare/API tokens in Kubernetes Secrets with RBAC restriction
- Rotate DNS provider tokens annually
- Use separate ClusterIssuers for staging vs production
- Audit cert-manager logs for unauthorized Certificate requests
- mTLS between RAG components is separate from edge TLS—cert-manager handles edge; service mesh handles internal

## Troubleshooting checklist

1. `kubectl get certificate -A` — Ready=True?
2. `kubectl describe challenge` — State=valid?
3. DNS TXT record present? `dig _acme-challenge.rag.internal.example.com TXT`
4. IAM/token permissions current?
5. cert-manager pod logs for ACME errors
6. Let's Encrypt rate limit status

TLS automation removes one ops burden from RAG platform teams—until renewal fails silently. Monitor Certificate Ready condition proactively.

## Multi-cluster certificate management

Organizations running RAG across US and EU clusters need region-appropriate certificates. cert-manager ClusterIssuer per region with DNS-01 solver pointing to regional Route53 hosted zones—or a global zone with geo-routed records. Avoid copying TLS secrets between clusters manually; each cluster's cert-manager manages its own Certificate resource referencing the same DNS names with appropriate regional validation.

Document certificate expiry in runbooks even with auto-renewal—cert-manager failures during holiday weekends have caused production outages when nobody noticed Certificate Ready=False for 72 hours.

## Troubleshooting DNS-01 challenge failures in private clusters

Private GKE/EKS clusters without public DNS resolution sometimes fail DNS-01 propagation checks. cert-manager needs outbound DNS to verify TXT record propagation. Ensure cluster nodes resolve _acme-challenge TXT records via public DNS (8.8.8.8 or Route53 resolver), not internal DNS that lacks ACME challenge records. Split-horizon DNS causes cert-manager to think challenge failed when public resolvers see it correctly—configure recursive resolver for cert-manager pod DNS policy.


## Production rollout notes

Enterprise deployments often require private CA integration alongside Let's Encrypt for external-facing RAG APIs. Run dual Certificate resources: public ACME cert for customer-facing retrieval endpoints, private CA cert for internal service mesh mTLS. cert-manager supports both ClusterIssuers simultaneously—ensure Secret names differ to avoid overwrite in Ingress and Gateway resources.

## Common regressions around cert manager dns01

Teams often pass a demo and then regress under load: retries without jitter, missing idempotency keys, or caches that never invalidate. Write a short regression list specific to cert manager dns01 and turn each item into an automated check or a game-day step. Prefer failing CI on the regression over discovering it from customer tickets. When you change defaults, update alerts in the same pull request so observability stays coupled to behavior.


Also for rag cert manager dns01: change one variable at a time when tuning, keep a rollback path tested quarterly, and verify consumer or replica behavior — not only the primary signal you expected to move.

## Resources

- cert-manager DNS-01 documentation
- Let's Encrypt rate limits
- Route53 IRSA setup for EKS
- Cloudflare API token permissions for DNS edit
