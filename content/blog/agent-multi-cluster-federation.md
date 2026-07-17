---
title: "AI Agents: Multi Cluster Federation"
slug: "agent-multi-cluster-federation"
description: "How to federate agent runtimes across Kubernetes clusters without turning DNS, identity, and placement into a weekly incident."
datePublished: "2026-03-02"
dateModified: "2026-03-02"
tags: ["AI", "Agent", "Multi"]
keywords: "kubernetes federation, multi-cluster agents, kubefed, placement policy, cross-cluster service discovery, agent orchestration"
faq:
  - q: "When does multi-cluster federation beat a single large cluster for agent workloads?"
    a: "Federation pays off when you need regional latency isolation, blast-radius containment between tenants, or GPU capacity that no single cluster can hold. A single cluster with good node pools is simpler until you hit quota ceilings, compliance boundaries that require data residency, or an outage that takes down every agent at once."
  - q: "Should agent pods be replicated identically in every member cluster?"
    a: "No. Placement should follow demand and data locality. Inference replicas belong near users; batch embedding jobs can sit in cheaper regions; control-plane components that coordinate tool calls need quorum but not full duplication. Treat each cluster as a capacity pool with explicit placement rules rather than mirroring everything everywhere."
  - q: "What breaks first when teams adopt federation without planning?"
    a: "Cross-cluster DNS and identity. Agents resolve tool endpoints by hostname; if federated services expose inconsistent names or certificates, tool calls fail intermittently. The second failure mode is split-brain scheduling—two clusters both think they own the same tenant shard and duplicate side effects."
  - q: "How do you test federation before production traffic?"
    a: "Run a shadow tenant whose tool calls are routed through federated DNS but whose writes land in an isolated database. Inject cluster failure by cordoning a member cluster during business hours in staging. Verify that placement policies reschedule work and that no agent session loses idempotency keys mid-flight."
---
The pager went off at 2:14 a.m. because the `us-east` cluster lost its API server etcd quorum, and every agent session pinned to that region started timing out on tool calls. What saved the night was not a bigger cluster—it was federation: workloads re-homed to `eu-west` within four minutes because placement policies, service exports, and identity trust had been wired months earlier. Multi-cluster federation for agent platforms is less about Kubernetes trivia and more about deciding which failures your users never see.

## Why one cluster stops being enough

Agent platforms differ from stateless APIs in three ways that push you toward multiple clusters.

First, **latency follows the model**. An agent that calls a CRM, a vector store, and a payment API on every turn cannot sit halfway across an ocean from two of those dependencies without blowing p95 budgets. Regional clusters let you colocate inference with data residency requirements.

Second, **blast radius is nonlinear**. A runaway tool loop or a poisoned embedding batch can saturate GPU nodes and starve unrelated tenants. Federation lets you cordon a region without draining the entire fleet.

Third, **capacity is lumpy**. Cloud providers sell GPU in blocks; your largest customer may need an entire node pool for a week during quarter-end automation. Federating placement across clusters turns capacity into a fungible pool instead of a single choke point.

The mistake is treating federation as "many clusters, same yaml." Without explicit contracts for naming, identity, and scheduling, you inherit N copies of every operational sharp edge.

## A reference topology

Picture three member clusters—`prod-use1`, `prod-euw1`, `prod-apse2`—fronted by a global control plane that holds tenant metadata, session state, and placement decisions. Agents run as Deployments in member clusters; the orchestrator decides *where* based on tenant region, GPU SKU, and maintenance windows.

```
                    ┌─────────────────────┐
                    │  Global control     │
                    │  (tenant registry,  │
                    │   session router)   │
                    └──────────┬──────────┘
           ┌───────────────────┼───────────────────┐
           ▼                   ▼                   ▼
    ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
    │ prod-use1   │     │ prod-euw1   │     │ prod-apse2  │
    │ agent-worker│     │ agent-worker│     │ agent-worker│
    │ tool-proxy  │     │ tool-proxy  │     │ tool-proxy  │
    └─────────────┘     └─────────────┘     └─────────────┘
```

Tool proxies terminate mTLS inside each region so outbound integrations never hairpin through a distant cluster. Session stickiness lives in the global layer; compute is fungible below it.

## Placement policies that actually get used

Kubernetes Cluster API and projects like KubeFed (or managed fleet products) expose placement through policies. The useful ones for agents encode business rules, not generic anti-affinity.

```yaml
apiVersion: policy.kubefed.io/v1alpha1
kind: ReplicaSchedulingPreference
metadata:
  name: tenant-acme-agents
  namespace: agents
spec:
  targetKind: FederatedDeployment
  totalReplicas: 12
  clusters:
    prod-use1:
      minReplicas: 4
      maxReplicas: 8
      weight: 2
    prod-euw1:
      minReplicas: 2
      maxReplicas: 6
      weight: 1
    prod-apse2:
      minReplicas: 0
      maxReplicas: 4
      weight: 1
  rebalance: true
```

Pair this with a **tenant label** on every namespaced object. Your orchestrator should refuse to schedule if `tenant_id` is missing—silent sharing of a default namespace is how cross-tenant leaks start.

For GPU-heavy inference, add a **capacity-aware scheduler plugin** or use taints that only lift when `nvidia.com/gpu` free count exceeds a floor. Federation without capacity signal sends pods to clusters that accept the spec but never pull the image in time.

## Cross-cluster naming and service export

Agents resolve tools by hostname. If `tools.internal` resolves differently per cluster, you get heisenbugs.

Standardize on **Multi-Cluster Services (MCS)** or an equivalent service export CRD:

```yaml
apiVersion: networking.k8s.io/v1alpha1
kind: ServiceExport
metadata:
  name: tool-gateway
  namespace: agents
---
apiVersion: networking.k8s.io/v1alpha1
kind: ServiceImport
metadata:
  name: tool-gateway
  namespace: agents
spec:
  ports:
    - port: 443
      protocol: TCP
  type: ClusterSetIP
```

Clients in any member cluster dial `tool-gateway.agents.svc.clusterset.local`. DNS must be identical everywhere—verify with a CronJob that curls the clusterset name from each region and emits a metric when resolution fails.

TLS certificates should be issued for the clusterset hostname, not per-cluster variants. cert-manager with a shared ACME DNS-01 solver across zones is the usual pattern.

## Identity across cluster boundaries

Workloads need to prove *which tenant* they act for when calling tools. SPIFFE/SPIRE or cloud workload identity federated through OIDC trust bundles is the durable approach.

Each member cluster runs a SPIRE server agent pair; agents receive SVIDs with selectors like `tenant:acme` and `region:eu-west`. Tool gateways validate JWT-SVID at the edge and map to OAuth client credentials stored in the tenant's region.

Rotate trust bundles on a schedule and **version them**. During rotation, accept both bundle N and N+1 for a overlap window equal to your longest agent session TTL.

## Session routing without sticky disasters

When a user reconnects, the global router must find an existing session or assign a home cluster. Store session metadata in a globally replicated store (CockroachDB, DynamoDB Global Tables, or Redis with active-active conflict rules).

```typescript
interface AgentSession {
  sessionId: string;
  tenantId: string;
  homeCluster: string;
  lastSeenAt: Date;
  idempotencyKey: string;
}

async function routeSession(sessionId: string): Promise<string> {
  const session = await sessionStore.get(sessionId);
  if (session && clusterHealth.isReady(session.homeCluster)) {
    return session.homeCluster;
  }
  const candidate = await placement.pickCluster({
    tenantId: session?.tenantId,
    preferRegions: geoHintFromRequest(),
  });
  await sessionStore.upsert({ ...session, homeCluster: candidate });
  return candidate;
}
```

Never migrate a session mid-tool-call without checkpointing partial results. Either wait for idle or serialize tool state to object storage before re-homing.

## Failure modes worth rehearsing

| Scenario | Symptom | Mitigation |
|----------|---------|------------|
| Member API server down | New pods stuck Pending | Pre-declare overflow replicas in sibling clusters |
| Split placement | Duplicate side effects | Leader election on tenant shard + idempotency keys |
| Stale DNS cache | 503 on tool-gateway | Lower TTL on clusterset records; alert on NXDOMAIN spikes |
| Image pull storm | GPU nodes idle while queue grows | Harbor/ECR pull-through cache per region |
| etcd restore | Old placement state | Version placement generation; reject schedules from stale gen |

Run game days that cordon one cluster during peak staging traffic. Measure time-to-recover and document which runbook steps were missing.

## Observability that spans clusters

Unified labels beat unified clusters. Every metric and log line should carry `cluster`, `tenant_id`, `agent_version`, and `session_id` (hashed if PII-sensitive). Dashboards grouped by cluster reveal skew; dashboards grouped by tenant reveal noisy neighbors.

Trace context must propagate across the global router into member clusters. If your tracing backend charges per span, sample aggressively on health checks but never sample tool-call failures.

Alert on **federation control plane lag**—the time between a placement change and all member clusters acknowledging it. Lag above two reconciliation intervals means you are flying blind during failover.

## Rollout sequence that avoids Friday surprises

Week 1: Stand up two member clusters with identical baseline addons (CNI, CSI, ingress, metrics). No agent workloads yet.

Week 2: Export a hello-world service via MCS; verify DNS and TLS from both clusters.

Week 3: Migrate one internal tenant with feature flag `federation_enabled`. Compare error rates to the single-cluster baseline.

Week 4: Enable placement policies for new tenants only; grandfather existing ones until confidence is high.

Week 5+: Automate cluster join with Terraform modules that pin addon versions. Manual join steps do not scale past three clusters.

## What good looks like six months in

On-call engineers can drain a cluster in under ten minutes without customer-visible errors. Tenant onboarding picks a region and gets capacity without a ticket to platform. GPU utilization graphs look like a single pool even though etcd never shared a byte between regions.

Federation is operational glue. The clusters are interchangeable; the contracts—placement, naming, identity, session routing—are the product.

## Resources

- [Kubernetes Multi-Cluster Services API](https://multicluster.sigs.k8s.io/concepts/multicluster-services-api/)
- [KubeFed documentation](https://github.com/kubernetes-sigs/kubefed)
- [Cluster API — cluster lifecycle](https://cluster-api.sigs.k8s.io/)
- [SPIFFE — workload identity standard](https://spiffe.io/docs/latest/spiffe-about/overview/)
- [Google Anthos multi-cluster architecture](https://cloud.google.com/anthos/clusters/docs/multi-cluster-gke)
