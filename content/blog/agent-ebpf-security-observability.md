---
title: "AI Agents: Ebpf Security Observability"
slug: "agent-ebpf-security-observability"
description: "Deploy eBPF probes for syscall, network, and file integrity observability around agent runtimes—kernel visibility without sidecar tax or log volume explosions."
datePublished: "2025-11-15"
dateModified: "2025-11-15"
tags: ["AI", "Agent", "Ebpf"]
keywords: "eBPF security, Tetragon, Falco, Cilium observability, agent sandbox, syscall tracing, kernel runtime security"
faq:
  - q: "Why use eBPF for agent security observability instead of application logs?"
    a: "Agents invoke tools, subprocesses, and network calls that application code does not always instrument—especially third-party MCP servers and shell plugins. eBPF sees syscalls and socket connects at the kernel boundary, giving ground truth even when user-space logging is disabled, tampered with, or never implemented."
  - q: "Does eBPF replace Falco or Tetragon?"
    a: "No—it is the mechanism they build on. Falco provides a rule language for threat detection; Tetragon focuses on Kubernetes-aware enforcement and tracing. You choose the toolchain; eBPF is the shared substrate. Many teams run Tetragon for policy plus export events to their SIEM alongside application traces."
  - q: "What agent workloads are poor fits for syscall-level monitoring?"
    a: "Windows agent hosts (eBPF is Linux-first), unprivileged local dev laptops without CAP_BPF, and ultra-low-memory edge devices where probe maps compete with model weights. For those, rely on application-level audit logs and OS-specific controls; deploy eBPF where agents run in your Linux K8s fleet."
  - q: "How do you prevent eBPF observability from drowning the SIEM?"
    a: "Aggregate in-kernel with BPF maps—count connects per dst/port before exporting. Sample high-volume syscalls (read/write) and always emit full detail on policy violations. Tag events with Kubernetes workload identity (namespace, pod, container) at collection time so downstream routing filters agent pools separately from batch ETL."
---
An agent tool chain executed `curl` against an internal metadata endpoint nobody remembered exposing. Application logs showed a successful tool response; the agent framework never logged subprocess argv. A **eBPF execve probe** on the node caught `/bin/curl http://169.254.169.254/...` with the pod UID tied to the compromised MCP sidecar. eBPF security observability is how you see what agent runtimes actually do at the kernel boundary—not what they claim in structured JSON.

## Why agents widen the attack surface

Agent architectures blend:

- LLM-orchestrated **tool calls** (HTTP, SQL, shell)
- **MCP servers** and plugins with variable quality bars
- **Sandbox escapes** via misconfigured containers
- **Egress** to model APIs and customer data planes

Traditional APM traces HTTP from your service mesh. It misses `execve`, `connect` to unexpected IPs, `ptrace` attempts, and writes to `/etc/passwd` inside the container mount namespace. eBPF attaches at the kernel hook point—before return to user space completes—so observations are harder for malicious code to suppress than log4j-style appender disables.

## eBPF concepts for platform engineers

| Concept | Role in security observability |
|---------|-------------------------------|
| **Program** | Logic attached to kprobes/tracepoints/cgroup hooks |
| **Map** | Kernel-side hash tables for counts, allowlists, PID sets |
| **CO-RE** | Compile Once — Run Everywhere across kernel versions |
| **BTF** | Type information enabling portable programs |
| **Ring buffer** | Efficient event export to user space |

You rarely write raw BPF C unless maintaining custom probes. Production teams typically deploy **Tetragon**, **Falco (modern BPF backend)**, **Cilium Tetragon policies**, or **Pixie**—this article focuses on patterns those tools implement.

## Threat detection map for agent pods

Prioritize signals by agent risk:

```yaml
# Example Tetragon-like policy sketch (conceptual)
apiVersion: cilium.io/v1alpha1
kind: TracingPolicy
metadata:
  name: agent-runtime-guard
spec:
  kprobes:
    - call: sys_execve
      selectors:
        - matchNamespaces:
            - namespace: agent-workers
          matchArgs:
            - index: 0
              operator: Prefix
              values: ["/bin/bash", "/bin/sh", "/usr/bin/curl", "/usr/bin/wget"]
    - call: tcp_connect
      selectors:
        - matchNamespaces:
            - namespace: agent-workers
          matchArgs:
            - operator: NotIn
              values: ["10.0.0.0/8", "api.openai.com:443"]
```

Alerts fire on **shell execution** in namespaces that should only run your hardened worker binary, and on **egress** outside allowlisted CIDRs and model API domains.

## Custom aggregation to control cardinality

Raw `read()` syscalls generate millions of events per minute. Aggregate before export:

```c
// Simplified BPF map pattern — count connects per dst IP
struct {
  __uint(type, BPF_MAP_TYPE_HASH);
  __uint(max_entries, 65536);
  __type(key, struct ipv4_key);
  __type(value, __u64);
} connect_counts SEC(".maps");

SEC("kprobe/tcp_v4_connect")
int BPF_KPROBE(tcp_connect, struct sock *sk) {
  struct ipv4_key key = {}; // populate from sk
  __u64 *count = bpf_map_lookup_elem(&connect_counts, &key);
  if (count)
    __sync_fetch_and_add(count, 1);
  else {
    __u64 init = 1;
    bpf_map_update_elem(&connect_counts, &key, &init, BPF_NOEXIST);
  }
  return 0;
}
```

User-space exporter flushes map counters every 30s and emits **anomaly events** when a pod connects to a new destination not in its 7-day baseline—rather than logging every SYN.

## Correlating kernel events with agent traces

Security findings without agent context are noisy. Enrich eBPF events with:

- `k8s.namespace`, `k8s.pod`, `k8s.container`
- `trace_id` / `session_id` if you inject cgroup annotations from the agent scheduler at pod create
- `tenant_id` from pod labels

```python
def enrich_ebpf_event(raw: dict, k8s_meta: dict) -> dict:
    return {
        **raw,
        "workload": {
            "namespace": k8s_meta["namespace"],
            "pod": k8s_meta["pod"],
            "labels": k8s_meta["labels"],
        },
        "agent_session": k8s_meta["labels"].get("agent.session_id"),
        "tenant_id": k8s_meta["labels"].get("tenant.id"),
    }
```

Join in your SIEM: eBPF execve event + OpenTelemetry span sharing `agent.session_id` → precise tool invocation postmortem.

## Enforcement vs observe-only

eBPF supports **observe-only** (log) and **enforce** (`SIGKILL`, return `-EPERM`):

| Mode | Use when | Risk |
|------|----------|------|
| Observe | Baseline building, new rule rollout | Alert fatigue if unaggregated |
| Rate-limit enforce | Block obvious egress violations | False positive kills legit traffic |
| Kill on match | Confirmed malware signatures in agent sandbox | Highest blast radius |

Roll out observe-only for two weeks; measure false positive rate against known-good agent regression suites. Promote to enforce on namespaces running untrusted MCP plugins first, not on core API gateways.

## Agent sandbox hardening with cgroup hooks

Attach programs at **cgroup** level so probes follow agent worker containers even if PIDs recycle:

```bash
# Illustrative: attach Tetragon to agent-worker namespace
kubectl annotate namespace agent-workers \
  io.cilium.tetragon.enable=enabled
```

Combine with **seccomp** and **Landlock** profiles; eBPF sees violations seccomp returns as killed syscalls—useful for tuning profiles without silent failures.

Detect **privilege escalation** attempts:

- `setuid` binaries executed from world-writable paths
- `mount` / `unshare` syscalls from non-init PIDs
- `ptrace` attaching across container boundaries

## Performance overhead budgets

Well-written CO-RE programs add low single-digit CPU overhead at moderate probe counts. Budget per agent node pool:

- **CPU**: <3% p95 increase vs uninstrumented baseline
- **Memory**: BPF maps capped—evict LRU for per-IP counters
- **Event lag**: <2s from syscall to SIEM for enforce decisions

Profile with `bpftool prog show` and disable probes that fire on hot paths (per-byte `read`) unless investigating active incidents.

## Deployment architecture

```text
┌─────────────────┐     ring buffer      ┌──────────────────┐
│ Agent worker    │ ───────────────────► │ Tetragon agent   │
│ pods (cgroup)   │                        │ (DaemonSet)      │
└─────────────────┘                        └────────┬─────────┘
                                                  │ gRPC
                                                  ▼
                                         ┌──────────────────┐
                                         │ Event exporter   │
                                         │ (filter/enrich)  │
                                         └────────┬─────────┘
                                                  │
                    ┌─────────────────────────────┼─────────────────────────────┐
                    ▼                             ▼                             ▼
             ┌────────────┐               ┌────────────┐               ┌────────────┐
             │ SIEM       │               │ Prometheus │               │ S3 archive │
             │ (alerts)   │               │ (metrics)  │               │ (forensics)│
             └────────────┘               └────────────┘               └────────────┘
```

Run the collector as a **DaemonSet** on agent nodes only—do not pay probe overhead on unrelated batch clusters. Separate Kafka topics for `ebpf.enforce` (page) vs `ebpf.audit` (ticket).

## Runbooks and alert routing

Page-worthy:

- Shell spawned in `agent-workers` namespace from non-allowlisted binary
- Egress to RFC1918 metadata IPs from tool sandbox pods
- BPF program load failure on >10% of daemonset pods (blind spot)

Ticket-worthy:

- New destination domain first seen (after baseline period)
- Elevated `connect_counts` to model API (capacity planning signal)

Runbook steps: cordon pod → snapshot eBPF event bundle from S3 archive → correlate `agent.session_id` → revoke tenant API keys if exfil suspected → patch MCP allowlist.

## Compliance and data handling

eBPF events may contain **argv strings** with PII if agents pass user content to shell tools. Redact in the exporter:

```python
REDACT_PATTERNS = [
    (re.compile(r"email=[^&\s]+"), "email=[REDACTED]"),
    (re.compile(r"Bearer\s+\S+"), "Bearer [REDACTED]"),
]

def redact_argv(argv: str) -> str:
    for pattern, repl in REDACT_PATTERNS:
        argv = pattern.sub(repl, argv)
    return argv
```

Document kernel-level collection in your DPIA. Retention: hot SIEM 30 days, cold archive 1 year for incident investigations unless regulation mandates less.

## Testing before production

- **Regression agent suite** — Run golden tool paths; assert zero enforce events.
- **Red team fixtures** — Deliberate `curl` metadata, reverse shell attempts in staging; assert detect within SLA.
- **Kernel upgrade canary** — CO-RE programs survive most upgrades; still canary new node images with `bpftool` verification job in CI.

```bash
# CI smoke: verify critical programs attached
bpftool prog list | grep -E 'tcp_connect|sys_execve'
tetragon getpolicy agent-runtime-guard -o json | jq '.spec.kprobes | length'
```

## The takeaway

eBPF security observability closes the gap between what agent frameworks log and what runtimes actually execute. Deploy cgroup-scoped probes on Linux agent worker pools, aggregate before SIEM export, enrich with Kubernetes and session labels, and graduate rules from observe to enforce with measured false positive budgets. Kernel visibility is not a replacement for secure tool design—but it is how you catch the subprocess your application never logged.

## FAQ

### Why use eBPF for agent security observability instead of application logs?

Agents invoke tools, subprocesses, and network calls that application code does not always instrument—especially third-party MCP servers and shell plugins. eBPF sees syscalls and socket connects at the kernel boundary, giving ground truth even when user-space logging is disabled, tampered with, or never implemented.

### Does eBPF replace Falco or Tetragon?

No—it is the mechanism they build on. Falco provides a rule language for threat detection; Tetragon focuses on Kubernetes-aware enforcement and tracing. You choose the toolchain; eBPF is the shared substrate. Many teams run Tetragon for policy plus export events to their SIEM alongside application traces.

### What agent workloads are poor fits for syscall-level monitoring?

Windows agent hosts (eBPF is Linux-first), unprivileged local dev laptops without CAP_BPF, and ultra-low-memory edge devices where probe maps compete with model weights. For those, rely on application-level audit logs and OS-specific controls; deploy eBPF where agents run in your Linux K8s fleet.

### How do you prevent eBPF observability from drowning the SIEM?

Aggregate in-kernel with BPF maps—count connects per dst/port before exporting. Sample high-volume syscalls (read/write) and always emit full detail on policy violations. Tag events with Kubernetes workload identity (namespace, pod, container) at collection time so downstream routing filters agent pools separately from batch ETL.

## Resources

- [ebpf.io](https://ebpf.io/) — eBPF overview and documentation
- [github.com/cilium/tetragon](https://github.com/cilium/tetragon) — Tetragon eBPF security observability
- [falco.org/docs](https://falco.org/docs/) — Falco cloud-native runtime security
- [docs.cilium.io/en/stable/observability](https://docs.cilium.io/en/stable/observability/) — Cilium observability guides
- [www.kernel.org/doc/html/latest/bpf/index.html](https://www.kernel.org/doc/html/latest/bpf/index.html) — Linux kernel BPF documentation
