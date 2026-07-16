---
title: "StatefulSets and Persistent Storage"
slug: "kubernetes-statefulsets-storage"
description: "How to run stateful workloads on Kubernetes: StatefulSet identity, PVC templates, storage classes, volume expansion, and backup patterns that survive pod rescheduling."
datePublished: "2024-10-01"
dateModified: "2024-10-01"
tags: ["DevOps", "Kubernetes", "Infrastructure", "Storage"]
keywords: "Kubernetes StatefulSet, persistent volume claims, stateful workloads, PVC templates, storage class, pod identity"
faq:
  - q: "When should I use a StatefulSet instead of a Deployment?"
    a: "Use a StatefulSet when each replica needs stable network identity (predictable DNS names), ordered startup/shutdown, or its own persistent volume that follows the pod across reschedules. Databases, message brokers, and distributed systems with local state are the common cases. Stateless APIs belong on Deployments."
  - q: "What happens to PVCs when I delete a StatefulSet?"
    a: "By default, PVCs created from volumeClaimTemplates are not deleted when you remove the StatefulSet. This protects data but leaves orphaned volumes. Use `kubectl delete statefulset my-app --cascade=orphan` only when you understand the cleanup path, and automate PVC lifecycle with your backup/retention policy."
  - q: "Can StatefulSet pods use different storage classes per replica?"
    a: "Not directly from a single volumeClaimTemplate — every replica gets the same template. For heterogeneous storage, use separate StatefulSets, operator-managed PVCs, or dynamic provisioning hooks. Most teams pick one storage class tuned for their workload (IOPS vs cost) and scale horizontally within that tier."
---

A Postgres pod that loses its data directory on reschedule is not a database — it's a time bomb with good uptime metrics. I learned this the hard way running a three-node cluster on a Deployment with `emptyDir` volumes: rolling updates looked fine until a node drain moved a replica to another machine and it booted with an empty data folder. StatefulSets exist because stateful workloads need identity and storage that survive the chaos of Kubernetes scheduling.

## What StatefulSets guarantee

A StatefulSet gives each pod three things a Deployment does not:

1. **Stable hostname**: `my-db-0`, `my-db-1`, `my-db-2` — always, even after crashes
2. **Stable storage**: PVC `data-my-db-0` binds to pod 0 and reattaches when pod 0 reschedules
3. **Ordered operations**: pods start 0 → 1 → 2; terminate in reverse

Headless Services (`clusterIP: None`) expose per-pod DNS:

```
my-db-0.my-db-headless.default.svc.cluster.local
```

Distributed systems use this for peer discovery. etcd, Kafka, and Cassandra all assume members can find each other by stable name.

## Volume claim templates

Define storage once; Kubernetes creates one PVC per replica:

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
spec:
  serviceName: postgres-headless
  replicas: 3
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
        - name: postgres
          image: postgres:16
          volumeMounts:
            - name: data
              mountPath: /var/lib/postgresql/data
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes: ["ReadWriteOnce"]
        storageClassName: gp3-retain
        resources:
          requests:
            storage: 100Gi
```

Key decisions in that snippet:

- **ReadWriteOnce** — one node at a time; correct for most databases
- **storageClassName** — pick explicitly; don't rely on cluster defaults in production
- **Retain reclaim policy** on the StorageClass — PVC data survives even if someone deletes the PV object incorrectly

## Storage class selection

Match the class to access patterns:

| Workload | IOPS profile | Typical class |
|----------|-------------|---------------|
| OLTP database | Sustained random write | Provisioned IOPS SSD |
| Analytics / logs | Sequential, large blocks | Throughput-optimized HDD |
| Dev/staging | Cheap, disposable | Standard, Delete policy |

On AWS EBS, `gp3` with explicit IOPS/throughput settings beats `gp2` for predictable latency. On GKE, `pd-ssd` vs `pd-balanced` is the same tradeoff. Benchmark with your actual query mix — provider marketing IOPS numbers rarely match ORM-heavy workloads.

## Scaling and storage gotchas

**Scale up** (2 → 3 replicas): Kubernetes creates `data-postgres-2`, starts pod 2, done.

**Scale down** (3 → 2): pod 2 terminates, but its PVC remains. If you scale back up, pod 2 reclaims the same volume — good. If you wanted to *remove* that data, you must delete the PVC manually.

**Volume expansion**: most cloud providers support expanding PVCs in-place:

```bash
kubectl patch pvc data-postgres-0 -p '{"spec":{"resources":{"requests":{"storage":"200Gi"}}}}'
```

The filesystem resize may require a pod restart depending on your CSI driver. Test this in staging before a 2 AM page.

## Backup and restore

StatefulSet storage is not backed up by Kubernetes itself. You need a strategy:

- **Volume snapshots** via CSI (`VolumeSnapshot`) — fast, crash-consistent unless the app quiesces
- **Logical backups** (`pg_dump`, `mongodump`) — portable, slower, consistent
- **Operator-managed backups** (CloudNativePG, Strimzi, Velero) — automate both

Velero can snapshot PVCs and restore to a new cluster, but cross-AZ restore times depend on snapshot size. For RPO under five minutes, combine WAL shipping with periodic snapshots.

## Pod disruption budgets and updates

StatefulSets update one pod at a time by default (`RollingUpdate`). Set a PodDisruptionBudget so node maintenance doesn't take down your quorum:

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: postgres-pdb
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: postgres
```

For a three-node Postgres cluster using synchronous replication, `minAvailable: 2` prevents voluntary evictions from killing a majority.

## Anti-patterns I've seen

- Running primary databases on Spot/preemptible nodes without replication — savings until the first eviction
- Sharing one RWX volume across StatefulSet pods — RWO exists for a reason; use a proper distributed filesystem if you need shared storage
- Omitting `podManagementPolicy` when parallel startup is safe — default `OrderedReady` slows recovery unnecessarily for read replicas

Use volumeClaimTemplates with storage class tested for your cloud — default StorageClass may use magnetic disks unsuitable for databases.

## StatefulSet pod identity

Pods get stable names: `web-0`, `web-1`, `web-2`. Headless service returns individual pod DNS. Use for:
- Databases with persistent identity
- Kafka brokers
- Elasticsearch nodes

Not for stateless web apps — use Deployment.

## Common production mistakes

Teams get statefulsets storage wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Kubernetes changes for statefulsets storage surprise teams when resource requests are copied from examples, probes are too aggressive during startup, and Helm values drift from git without anyone noticing until a node pressure eviction.

## Debugging and triage workflow

When statefulsets storage misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Kubernetes StatefulSets documentation](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/)
- [Persistent Volumes and Claims](https://kubernetes.io/docs/concepts/storage/persistent-volumes/)
- [CSI Volume Snapshots](https://kubernetes.io/docs/concepts/storage/volume-snapshots/)
- [Velero backup and restore](https://velero.io/docs/)
- [CloudNativePG operator for PostgreSQL](https://cloudnative-pg.io/documentation/current/)
