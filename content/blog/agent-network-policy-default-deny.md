---
title: "AI Agents: Network Policy Default Deny"
slug: "agent-network-policy-default-deny"
description: "Lock down agent pod egress and ingress with Kubernetes NetworkPolicy default-deny baselines, label contracts, and a rollout that does not break tool calls on day one."
datePublished: "2026-02-03"
dateModified: "2026-02-03"
tags: ["AI", "Agent", "Network"]
keywords: "kubernetes network policy, default deny, zero trust agents, cilium network policy, egress filtering, agent security"
faq:
  - q: "Does default deny block DNS resolution for agent pods?"
    a: "Only if you forget to allow UDP/TCP 53 to kube-dns or CoreDNS. Every baseline should include an explicit allow to the cluster DNS service IP and to the DNS pods via namespaceSelector. Without it, agents fail tool calls with opaque 'connection refused' errors because hostnames never resolve."
  - q: "Should agent tool gateways live in the same namespace as workers?"
    a: "Separate namespaces improve policy clarity. Workers egress to the gateway namespace on 443; the gateway egresses to the internet or VPC endpoints. If everything shares one namespace, you end up with overly broad podSelector rules that defeat the purpose of segmentation."
  - q: "How do you roll out default deny without breaking production?"
    a: "Start in audit or log-only mode if your CNI supports it, then enforce on new namespaces before legacy ones. Run conntrack-aware connectivity tests from a Job that mimics agent egress paths. Keep a break-glass NetworkPolicy with a distinct label that security reviews monthly."
  - q: "Calico vs Cilium—which matters for agent workloads?"
    a: "Both enforce NetworkPolicy; Cilium adds L7 HTTP policy and Hubble flow visibility useful for debugging agent tool calls. Pick based on what your platform team already operates. The policy semantics that matter—default deny plus explicit allows—are the same; observability and eBPF performance differ."
---
A security review asked a simple question: "Show me every outbound connection an agent pod can make." The answer was a shrug and a `curl` demo that worked because the cluster allowed all egress. Default-deny network policy is how you turn that shrug into a diagram—and how you stop a compromised agent from scanning your internal `/16` or exfiltrating embeddings to an arbitrary IP.

## The trust model agent pods inherit

An agent worker typically holds API keys via projected volumes, talks to an LLM endpoint, hits internal tool gateways, and occasionally reaches a vector database. That is four trust zones, not "the internet."

Without default deny, any RCE in your agent runtime—or a supply-chain compromise in a base image—gets lateral movement for free. Network policy is not a substitute for patching, but it caps blast radius when something executes arbitrary code inside the pod network namespace.

Zero trust here means **deny all, allow by label**. Not "allow all, deny bad IPs." The latter list rots.

## Baseline: deny everything in the namespace

Apply two policies before any allow rules:

```yaml
# deny-all-ingress.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-ingress
  namespace: agents
spec:
  podSelector: {}
  policyTypes:
    - Ingress
---
# deny-all-egress.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-egress
  namespace: agents
spec:
  podSelector: {}
  policyTypes:
    - Egress
```

`podSelector: {}` matches every pod in `agents`. Until you add allows, traffic drops. Schedule this during a maintenance window for existing namespaces; for greenfield agent namespaces, apply deny-first on creation via a Kyverno or OPA Gatekeeper mutating policy.

## Label contract platform teams enforce

Policies select pods by labels. Standardize these on every agent Deployment:

| Label | Purpose |
|-------|---------|
| `app.kubernetes.io/name: agent-worker` | Worker egress bundle |
| `app.kubernetes.io/name: tool-gateway` | Gateway egress bundle |
| `tenant-tier: standard \| enterprise` | Optional stricter rules for enterprise |
| `egress-profile: llm-openai` | Declares approved external endpoints |

CI should fail if agent manifests ship without `app.kubernetes.io/name`. Policies reference stable keys—not image tags.

## Allow DNS before anything else

The first production outage from default deny is always DNS. Explicit allow:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dns-egress
  namespace: agents
spec:
  podSelector: {}
  policyTypes:
    - Egress
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: kube-system
          podSelector:
            matchLabels:
              k8s-app: kube-dns
      ports:
        - protocol: UDP
          port: 53
        - protocol: TCP
          port: 53
```

If you run NodeLocal DNSCache, target those endpoints instead and document the change in the runbook.

## Worker → gateway → world layering

Agents should not reach the public internet directly. Force tool and model traffic through an egress gateway:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: agent-worker-egress
  namespace: agents
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/name: agent-worker
  policyTypes:
    - Egress
  egress:
    # tool gateway in same cluster
    - to:
        - podSelector:
            matchLabels:
              app.kubernetes.io/name: tool-gateway
      ports:
        - protocol: TCP
          port: 8443
    # vector store in data namespace
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: data
          podSelector:
            matchLabels:
              app: qdrant
      ports:
        - protocol: TCP
          port: 6333
```

Gateway namespace gets a separate policy permitting HTTPS to approved CIDR blocks or `egress-gateway` SNAT IPs.

## Ingress: who may call the agent API

Agent HTTP servers should accept traffic only from the ingress controller and internal orchestrators:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: agent-worker-ingress
  namespace: agents
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/name: agent-worker
  policyTypes:
    - Ingress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: ingress-nginx
        - podSelector:
            matchLabels:
              app.kubernetes.io/name: agent-orchestrator
      ports:
        - protocol: TCP
          port: 8080
```

Adjust namespace labels to match your ingress installation—`ingress-nginx` vs `traefik` vs Gateway API implementation.

## Cilium L7 policy for tool URLs

When you need domain-level control—not just IP—CiliumNetworkPolicy can enforce HTTP `:path` and `:method`:

```yaml
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: gateway-egress-llm
  namespace: agents
spec:
  endpointSelector:
    matchLabels:
      app.kubernetes.io/name: tool-gateway
  egress:
    - toFQDNs:
        - matchName: api.openai.com
        - matchPattern: "*.openai.azure.com"
      toPorts:
        - ports:
            - port: "443"
              protocol: TCP
          rules:
            http:
              - method: POST
                path: "/v1/chat/completions"
```

L7 rules carry CPU overhead. Apply them on gateways, not on every worker replica.

## Progressive rollout playbook

**Phase 0 — inventory.** Run Hubble `hubble observe --namespace agents` or Calico flow logs for 72 hours. Export unique `(src, dst, port)` tuples. Unknown tuples become allow candidates or bugs.

**Phase 1 — new namespaces.** Deny-all on `agents-staging-*` only. Run connectivity Job after each deploy.

**Phase 2 — audit mode.** If using Cilium, enable policy audit annotations before enforcement. Watch for dropped-flow counters.

**Phase 3 — production enforce.** Roll one tenant shard at a time via namespace label `netpol-enforced: true`.

**Phase 4 — remove break-glass.** Delete temporary `allow-all-debug` policies created during migration. Grep Git for `allow-all` weekly until zero hits.

Connectivity test Job:

```bash
kubectl run netcheck -n agents --rm -it --restart=Never \
  --image=curlimages/curl:8.5.0 \
  --labels="app.kubernetes.io/name=agent-worker" \
  -- curl -sf --max-time 5 https://tool-gateway.agents.svc:8443/healthz
```

Wire this into CI against a kind cluster with the same policies.

## Debugging drops without guessing

Symptoms map to causes:

- **ImagePullBackOff** — usually not NetworkPolicy; check image registry egress on nodes.
- **Tool timeout after 30s** — likely egress deny or DNS; check CNI drop counters.
- **Intermittent 503** — policy may allow pod IP but not Service ClusterIP path; verify `to` blocks include namespaceSelectors for Service backends.
- **Works in staging, fails in prod** — label drift on namespace or missing `kubernetes.io/metadata.name` label on system namespaces (common on older clusters).

Hubble CLI example:

```bash
hubble observe --namespace agents --verdict DROPPED --follow
```

Correlate drops with agent trace IDs if your mesh adds them.

## Interaction with service mesh mTLS

Istio/Linkerd mTLS encrypts pod-to-pod traffic but does not replace NetworkPolicy—they are complementary. Policy still decides *which* pods may connect; mesh decides *how* bytes are authenticated. Sidecar outbound ports must appear in allow rules or traffic dies at the sidecar before the CNI sees it.

Document whether policies select **pod IP** or **service account identity** when mesh is enabled. Mixed modes confuse on-call.

## Compliance and evidence collection

SOC2 auditors ask for periodic proof that prod matches Git. Store rendered NetworkPolicy manifests in a GitOps repo; Argo CD diff alerts on drift. Export monthly Hubble flow summaries showing zero DROPPED flows from agent workers to non-approved destinations.

Break-glass policies require ticket IDs in annotations:

```yaml
metadata:
  annotations:
    security.example.com/break-glass-ticket: "INC-4821"
    security.example.com/expires: "2026-02-10T00:00:00Z"
```

Automated policy lint rejects break-glass without expiry.

## Namespace-per-tenant isolation for enterprise agents

Enterprise contracts sometimes require **hard network separation** between tenants—not just logical RBAC. Namespace-per-tenant with cloned policy templates achieves this without bespoke rules per customer:

```yaml
# templated per tenant namespace agents-tenant-acme
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: tenant-isolation
  namespace: agents-tenant-acme
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              tenant-access: acme
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              tenant-access: acme
```

Platform automation renders this from a tenant onboarding CRD. The `tenant-access` label on namespaces is the only variable—policies stay auditable and diffable in review. Pair with ResourceQuota so a noisy tenant cannot exhaust IP tables or conntrack entries on shared nodes.

## What changes after default deny lands

Incident triage gets faster: if an agent cannot reach a tool, the answer is in policy Git history, not tcpdump on a node. New integrations require an explicit allow PR—security sees them before production. Compromised pods stop scanning internal subnets because there was never a rule permitting it.

Default deny is tedious to adopt and cheap to operate. That asymmetry is the point.

## Resources

- [Kubernetes NetworkPolicy documentation](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
- [Cilium — network policy editor and guides](https://docs.cilium.io/en/stable/security/policy/)
- [Calico — network policy tutorial](https://docs.tigera.io/calico/latest/network-policy/get-started/kubernetes-policy)
- [Hubble — network observability for Cilium](https://github.com/cilium/hubble)
- [NSA/CISA — Kubernetes hardening guide (network segmentation)](https://media.defense.gov/2022/Aug/29/2003066362/-1/-1/0/KUBERNETES-HARDENING-GUIDE-1.2-PDF.pdf)
