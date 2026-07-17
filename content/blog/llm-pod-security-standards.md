---
title: "Pod Security Standards"
slug: "llm-pod-security-standards"
description: "Apply Kubernetes Pod Security Standards to LLM inference workloads: restricted vs baseline tradeoffs, GPU sidecars, model volume mounts, and a namespace rollout that does not block deploys."
datePublished: "2026-01-31"
dateModified: "2026-07-17"
tags:
  - "AI"
  - "LLM"
keywords: "Kubernetes Pod Security Standards, PSS restricted baseline, LLM inference security, agent workload hardening, pod security admission, GPU sidecar security"
faq:
  - q: "Which Pod Security Standard level should LLM inference namespaces use?"
    a: "Start at baseline for inference namespaces with GPU drivers and shared model volumes, then tighten to restricted for stateless API gateway and orchestrator pods that do not need hostPath or privileged init containers. Mixed namespaces split by pod labels—do not run gateways and model servers under one blanket policy."
  - q: "How do Pod Security Standards interact with GPU workloads?"
    a: "NVIDIA device plugins and some CSI drivers historically required privileged sidecars or mount propagation. Baseline allows common patterns restricted blocks. Document exceptions in Policy Exceptions (Kubernetes 1.26+) or isolate GPU nodes in a dedicated namespace at baseline while keeping user-facing agent APIs at restricted."
  - q: "Can agent pods mount Hugging Face model caches from hostPath?"
    a: "Avoid hostPath for model weights in multi-tenant clusters—it breaks node isolation and violates restricted policy. Use ReadOnlyMany PVCs, object storage FUSE with securityContext constraints, or preloaded images. If hostPath is unavoidable for bare-metal GPU farms, scope to dedicated node pools with baseline policy and taints."
  - q: "What breaks when you enforce restricted on a running agent stack?"
    a: "Typical failures: containers running as root, missing drop ALL capabilities, allowPrivilegeEscalation true, hostNetwork for legacy metrics agents, and default seccompProfile unset. Audit with kubectl label dry-run before enforce mode—collect Pod Security Admission warnings for one week in warn audit mode."
---
A platform team flipped their agent namespace to Pod Security **enforce: restricted** on a Friday. By Saturday, vLLM inference pods were CrashLooping—init containers needed `CAP_SYS_ADMIN` for GPU memory pinning, and someone's debug sidecar ran as root "temporarily since beta." Rollback took twenty minutes; the postmortem took three weeks of exception paperwork.

Kubernetes Pod Security Standards (PSS) replace the deprecated PodSecurityPolicy with three built-in profiles enforced by Pod Security Admission (PSA). For AI agent stacks—retrieval APIs, orchestrators, embedding workers, GPU inference—you need a rollout plan that respects how model serving actually runs, not a blanket `restricted` label on every namespace.

## The three profiles, translated for agent workloads

| Control | Privileged | Baseline | Restricted |
|---------|------------|----------|------------|
| Run as non-root | Optional | Recommended | Required |
| Privileged containers | Allowed | Denied | Denied |
| hostPath volumes | Allowed | Restricted | Denied |
| hostNetwork | Allowed | Allowed | Denied |
| Capabilities | Any | Limited add | Drop ALL + NET_BIND_SERVICE only |
| seccompProfile | Unset OK | Unset OK | RuntimeDefault required |

**Privileged** — avoid for anything user-facing. Some legacy GPU node agents still live here on isolated bare-metal; treat as tech debt.

**Baseline** — reasonable default for **inference workers** pulling large model artifacts, using device plugins, or FUSE mounts where restricted blocks volume types.

**Restricted** — target for **agent orchestrators**, tool gateways, retrieval APIs, and embedding CPU workers that only need ConfigMaps, Secrets, and PVCs.

Split your agent platform across at least two namespaces if one team owns both inference and orchestration.

## Namespace labeling strategy

Pod Security Admission reads namespace labels:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: agent-orchestration
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/enforce-version: latest
    pod-security.kubernetes.io/warn: restricted
    pod-security.kubernetes.io/audit: restricted
---
apiVersion: v1
kind: Namespace
metadata:
  name: llm-inference
  labels:
    pod-security.kubernetes.io/enforce: baseline
    pod-security.kubernetes.io/enforce-version: latest
    pod-security.kubernetes.io/warn: restricted
    pod-security.kubernetes.io/audit: restricted
```

Use **warn** and **audit** at the stricter level while **enforce** stays at the achievable profile—warnings surface in audit logs without blocking deploys during migration.

Progression:

1. Week 1–2: enforce privileged (document current state), audit restricted.
2. Week 3–4: enforce baseline on inference, audit restricted.
3. Week 5+: enforce restricted on orchestration; baseline on inference until GPU exceptions resolved.

## Hardening agent orchestrator pods

Orchestrator pods (LangGraph runners, tool routers, RAG pipelines) should run restricted without exceptions:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agent-orchestrator
  namespace: agent-orchestration
spec:
  template:
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 10001
        runAsGroup: 10001
        fsGroup: 10001
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: orchestrator
          image: registry.example/agent-orchestrator:1.4.2
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop: ["ALL"]
          volumeMounts:
            - name: tmp
              mountPath: /tmp
            - name: cache
              mountPath: /app/.cache
      volumes:
        - name: tmp
          emptyDir: {}
        - name: cache
          emptyDir: {}
```

`readOnlyRootFilesystem` forces writable paths to emptyDir—agents that download plugins at runtime need explicit cache volumes or init containers that copy artifacts to emptyDir before main container starts non-root.

Drop `ALL` capabilities. If something fails with `permission denied` binding port 8080, run on 8080 as non-root (unprivileged ports >1024) rather than adding `NET_BIND_SERVICE` unless you truly bind 443 in-container—which you should not; use a Service or ingress.

## Inference pods: baseline with tight boundaries

Model servers often need:

- Larger `emptyDir` or PVC for weights.
- `nvidia.com/gpu` resources.
- Sometimes init containers fixing permissions on mounted volumes—fix ownership in init running as root is blocked under restricted; use fsGroup or pre-chowned PVC snapshots.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: vllm-worker
  namespace: llm-inference
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    fsGroup: 1000
  containers:
    - name: vllm
      image: vllm/vllm-openai:v0.6.0
      securityContext:
        allowPrivilegeEscalation: false
        capabilities:
          drop: ["ALL"]
      resources:
        limits:
          nvidia.com/gpu: "1"
      volumeMounts:
        - name: model-cache
          mountPath: /models
          readOnly: true
  volumes:
    - name: model-cache
      persistentVolumeClaim:
        claimName: llama-70b-weights
```

ReadOnly model mounts prevent runtime model swap attacks from compromised agents—pair with image digest pinning for orchestrator → inference RPC auth.

## Policy Exceptions without going back to PSP chaos

Kubernetes 1.26+ **Pod Security Admission exceptions** grant named exemptions:

```yaml
apiVersion: policy/v1alpha1
kind: PodSecurityConfiguration
# Use Policy Binding / exceptions API per cluster version docs
```

Prefer narrow exceptions: single ServiceAccount, single Deployment name, expiry date in ticket. Quarterly review exceptions—GPU driver sidecars often disappear after upgrading device plugin versions.

Alternative: **dedicated node pool** tainted `gpu=true`, namespace at baseline, NetworkPolicy blocking inference pods from talking to metadata API or cluster control plane.

## NetworkPolicy complements PSS

PSS hardens pod spec; it does not stop lateral movement. Agent stacks should add:

- Default deny ingress in namespace.
- Allow orchestrator → inference on gRPC port only.
- Deny inference → internet egress except model registry allowlist.
- Deny all pods → `169.254.169.254` cloud metadata unless using workload identity via dedicated node agents.

LLM pods exfiltrating weights or prompts via DNS tunneling is an agent-specific threat—egress logging on orchestration namespace catches odd destinations PSS never sees.

## Workload Identity and secrets

Restricted pods still mount Secrets. Prefer:

- **Projected service account tokens** with audience bound to inference API.
- **External Secrets Operator** syncing short-lived creds.
- Never bake API keys into container images agent orchestrators pull at runtime.

Rotate Secrets without pod restart where possible; agent sessions are long—rolling restart during Secret rotation should be graceful via preStop hooks draining in-flight tool calls.

## Migration playbook

**Inventory** — run admission audit mode cluster-wide; collect violating pods:

```bash
kubectl get pods -A -o json | jq -r '
  .items[] |
  select(.metadata.namespace | startswith("agent")) |
  "\(.metadata.namespace)/\(.metadata.name)"'
```

Fix generators first—Helm charts, Kustomize bases—before one-off kubectl patches.

**Common fixes**:

| Violation | Fix |
|-----------|-----|
| `runAsUser: 0` | Set non-zero USER in Dockerfile; chart override |
| `privileged: true` debug | Remove; use ephemeral debug containers (K8s 1.23+) with separate RBAC |
| `hostPath` model cache | Migrate to PVC or node-local storage class |
| Missing seccompProfile | Add `RuntimeDefault` at pod level |
| `capabilities.add: [SYS_PTRACE]` | Remove; use dedicated profiling namespace |

**CI gate** — conftest or kyverno policies in pipeline rejecting manifests that violate target profile before apply.

**Game day** — attempt deploy of intentionally bad pod; verify PSA rejects with clear message.

## Observability

Alert on PSA audit events exceeding baseline—often the first sign a chart regressed. Include `pod-security.kubernetes.io/enforce` label in deployment dashboards so on-call knows which profile applies.

Track CrashLoop reasons after migration—OOM from read-only root without tmp volume masquerades as "security broke GPU."

## Agent platform checklist before enforce mode

Before flipping a namespace from warn to enforce, walk this list with the team owning charts—not only platform SRE:

- Every container image declares a non-zero `USER`; no Dockerfile ends on implicit root.
- Debug tooling uses `kubectl debug` ephemeral containers with their own RBAC, not privileged long-lived sidecars.
- Model weights and vector index volumes are ReadOnly where the serving runtime allows it.
- ServiceAccounts are per deployment, not one shared cluster-admin SA for "simplicity."
- Resource requests and limits are set—PSS does not replace quota management, but OOMKill loops during migration look like policy regressions in triage.

Run a one-hour load test in staging at enforce level while watching PSA audit logs and pod events. If nothing fires except expected GPU namespace baseline warnings, promote to production namespace-by-namespace, not cluster-wide.

## Closing thought

Pod Security Standards give agent platforms a default-deny posture without maintaining bespoke PodSecurityPolicies. Use restricted for orchestration and retrieval, baseline for GPU inference until hardware stacks catch up, migrate with warn-before-enforce, and pair PSS with NetworkPolicy because hardened pods still talk to each other. The Friday CrashLoop is optional if you audit first.

## Resources

- [Kubernetes Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/) — official profile definitions.
- [Pod Security Admission](https://kubernetes.io/docs/concepts/security/pod-security-admission/) — namespace labels and enforce/warn/audit modes.
- [Kubernetes hardening guide ( NSA / CISA )](https://www.nsa.gov/Press-Room/News-Highlights/Article/Article/3148990/nsa-and-cisa-release-kubernetes-hardening-guide/) — complementary cluster-level guidance.
- [NVIDIA GPU Operator: security context notes](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/index.html) — GPU node requirements affecting PSS level choice.
- [Kyverno Pod Security policies](https://kyverno.io/policies/pod-security/) — optional policy-as-code beyond built-in PSA.
