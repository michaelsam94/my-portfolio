---
title: "Runtime Security Falco"
slug: "llm-runtime-security-falco"
description: "Runtime security for AI agent workloads with Falco — eBPF syscall rules, Kubernetes detection for shell escapes and crypto miners, tuning false positives, and alert routing when agents run untrusted code for teams running LLM features in production."
datePublished: "2025-11-13"
dateModified: "2026-07-17"
tags:
  - "AI"
  - "LLM"
keywords: "Falco runtime security, eBPF Kubernetes, AI agent security, container syscall monitoring, Falco rules, CNCF Falco, agent sandbox escape, runtime threat detection"
faq:
  - q: "Why do AI agent pods need runtime security beyond network policies?"
    a: "Agents increasingly run code interpreters, shell tools, and user-supplied plugins inside containers. Network policies block lateral movement; Falco detects in-container behavior — unexpected shells, binary downloads, credential file reads, reverse shells — that indicates escape or compromise."
  - q: "Falco vs admission control — what is the division of labor?"
    a: "Admission controllers (OPA Gatekeeper, Kyverno) decide whether a pod may start — image allowlists, seccomp, dropped caps. Falco watches syscalls after the pod is running and alerts on suspicious runtime behavior admission could not predict."
  - q: "How do you reduce Falco false positives for legitimate agent tools?"
    a: "Scope rules by Kubernetes labels (agent tier, tool profile), maintain allowlists for known interpreter invocations, tune file paths per base image, and run in log-only mode for two weeks before paging. Agents that legitimately spawn subprocesses need narrower rules than static API pods."
  - q: "What agent behaviors should trigger immediate Falco alerts?"
    a: "Shell spawned from inference process, write to /etc or /root, outbound connection from unexpected binary, mount of hostPath, read of cloud metadata combined with curl/wget, crypto miner process names, and ptrace attach attempts inside agent sandboxes."
---
A security researcher on our red team pasted Python into a "code assistant" tool. The sandbox was supposed to block filesystem access. The agent wrapper called `subprocess.run(["python", "-c", user_code])` without seccomp. Twenty seconds later, Falco fired `Sensitive file read below /etc` tied to a pod labeled `agent-code-runner`. We killed the pod before credentials in a mounted ConfigMap were exfiltrated.

Static scanning did not catch that — the vulnerability was runtime behavior in a container that passed image signing and admission checks. That is Falco's lane.

## Where Falco sits in the agent security stack

Agent workloads in Kubernetes typically stack defenses:

```
┌─────────────────────────────────────────────────────────────┐
│ Admission: signed images, no privileged, dropped CAP_SYS_ADMIN│
├─────────────────────────────────────────────────────────────┤
│ NetworkPolicy: egress allowlist to LLM API + tool endpoints │
├─────────────────────────────────────────────────────────────┤
│ Pod Security: seccomp RuntimeDefault, readOnlyRootFilesystem │
├─────────────────────────────────────────────────────────────┤
│ Falco (eBPF): syscall + K8s audit events → detect anomalies │
└─────────────────────────────────────────────────────────────┘
```

Falco uses the Linux kernel via **eBPF probes** (modern driver) or kernel module (legacy) to observe syscalls without modifying application code. For agents executing untrusted logic, that visibility is non-optional.

## Deploying Falco for agent namespaces

Helm install with eBPF driver enabled:

```bash
helm repo add falcosecurity https://falcosecurity.github.io/charts
helm install falco falcosecurity/falco \
  --namespace falco --create-namespace \
  --set driver.kind=ebpf \
  --set falcosidekick.enabled=true \
  --set falcosidekick.config.webhook.address="http://alert-router.security.svc/alerts"
```

Scope collection to agent namespaces to reduce noise:

```yaml
# values-agent-cluster.yaml
 collectors:
   enabled: true
   containerd:
     enabled: true
 customRules:
   agent-runtime.yaml: |-
     # custom rules loaded from ConfigMap
 falco:
   jsonOutput: true
   priority: notice
   bufferedOutputs: false
   rules_file:
     - /etc/falco/falco_rules.yaml
     - /etc/falco/k8s_audit_rules.yaml
     - /etc/falco/rules.d/agent-runtime.yaml
```

Run Falco as a DaemonSet on nodes hosting agent sandboxes. Sidecar Falco per pod is rarely worth the overhead.

## Custom rules for agent threat patterns

Default Falco rules catch generic bad behavior. Agent pods need additions for **interpreter abuse** and **tool escape**.

```yaml
# rules.d/agent-runtime.yaml
- macro: agent_namespace
  condition: k8s.ns.name in (agent-sandbox, agent-tools-prod)

- macro: agent_pod
  condition: agent_namespace and k8s.pod.label.app.kubernetes.io/component = "code-runner"

- list: agent_allowed_binaries
  items: [python3, node, tini, dumb-init]

- rule: Agent Unexpected Shell
  desc: Shell spawned inside agent code-runner pod
  condition: >
    agent_pod and spawned_process and proc.name in (bash, sh, zsh, dash)
    and not proc.pname in (agent_allowed_binaries)
  output: >
    Unexpected shell in agent sandbox
    (user=%user.name pod=%k8s.pod.name ns=%k8s.ns.name
     shell=%proc.name parent=%proc.pname cmdline=%proc.cmdline)
  priority: CRITICAL
  tags: [agent, shell, mitre_execution]

- rule: Agent Sensitive File Read
  desc: Read credential or cloud metadata paths from agent pod
  condition: >
    agent_pod and open_read and
    (fd.name startswith /etc/kubernetes or
     fd.name startswith /var/run/secrets or
     fd.name = /etc/passwd)
  output: >
    Sensitive file read in agent pod
    (file=%fd.name pod=%k8s.pod.name cmdline=%proc.cmdline)
  priority: CRITICAL
  tags: [agent, credential_access]

- rule: Agent Outbound Recon Tool
  desc: curl/wget/nc from agent sandbox to non-allowlisted destination
  condition: >
    agent_pod and spawned_process and
    proc.name in (curl, wget, nc, ncat) and
    not fd.sip in (10.0.0.0/8)
  output: >
    Network recon tool in agent sandbox
    (proc=%proc.name cmdline=%proc.cmdline pod=%k8s.pod.name)
  priority: WARNING
  tags: [agent, exfiltration]
```

Tune `agent_allowed_binaries` to match your base image. A pod that never legitimately needs `curl` should alert on any invocation.

## Kubernetes audit integration

Syscalls tell you what happened inside the container. **Kubernetes audit logs** tell you who created the risky pod.

Enable audit policy capturing pod exec and privileged escalations:

```yaml
# k8s-audit-policy.yaml
apiVersion: audit.k8s.io/v1
kind: Policy
rules:
  - level: Metadata
    omitStages: ["RequestReceived"]
  - level: RequestResponse
    verbs: ["create"]
    resources:
      - group: ""
        resources: ["pods/exec", "pods/attach"]
  - level: RequestResponse
    users: ["system:serviceaccount:agent-sandbox:*"]
    verbs: ["create", "update", "patch"]
    resources:
      - group: ""
        resources: ["pods"]
```

Falco's `k8s_audit` rules correlate: `kubectl exec` into agent pod followed by shell spawn = higher confidence incident.

## Seccomp and Falco together

Do not choose between seccomp and Falco — stack them.

Agent code-runner seccomp profile (partial):

```json
{
  "defaultAction": "SCMP_ACT_ERRNO",
  "syscalls": [
    { "names": ["read", "write", "exit", "exit_group", "futex", "clock_gettime"], "action": "SCMP_ACT_ALLOW" },
    { "names": ["execve", "execveat"], "action": "SCMP_ACT_ALLOW", "args": [{ "index": 0, "op": "SCMP_CMP_EQ", "value": "/usr/bin/python3.11" }] }
  ]
}
```

Seccomp blocks many escapes silently. Falco alerts when something **attempted** a blocked syscall — useful signal for tuning profiles and detecting probing.

Pod spec:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: agent-code-runner
  namespace: agent-sandbox
  labels:
    app.kubernetes.io/component: code-runner
spec:
  securityContext:
    runAsNonRoot: true
    seccompProfile:
      type: Localhost
      localhostProfile: profiles/agent-code-runner.json
  containers:
    - name: runner
      image: ghcr.io/org/agent-sandbox:2025.11.1
      securityContext:
        allowPrivilegeEscalation: false
        readOnlyRootFilesystem: true
        capabilities:
          drop: ["ALL"]
```

## Alert routing and response playbooks

Falco noise kills response quality. Route by priority and namespace:

```yaml
# falcosidekick values snippet
config:
  slack:
    webhookurl: "https://hooks.slack.com/services/..."
    minimumpriority: warning
    outputformat: "all"
  pagerduty:
    routingkey: "${PD_AGENT_SECURITY_KEY}"
    minimumpriority: critical
customLabels: "team=agent-security"
```

Slack for WARNING during tuning; PagerDuty only for CRITICAL rules with low false-positive rates.

Response runbook steps tied to Falco output fields:

1. **Capture** — `kubectl logs` + Falco event JSON + agent trace ID from pod annotation
2. **Isolate** — NetworkPolicy deny-all on pod label, or delete pod if stateless
3. **Preserve** — snapshot container filesystem if forensic need (rare for agents)
4. **Review** — was user prompt, plugin supply chain, or cluster compromise?

```bash
# emergency isolate agent pod
kubectl label pod -n agent-sandbox "$POD" security.isolated=true --overwrite
kubectl apply -f networkpolicies/agent-isolated-deny-all.yaml
```

## Tuning false positives systematically

Agent pods generate more process noise than stateless APIs. Tuning workflow:

| Week | Mode | Action |
|------|------|--------|
| 1–2 | `priority: DEBUG`, log-only | Collect top 20 rules by volume |
| 3 | Adjust macros/lists | Exclude known CI test namespaces |
| 4 | Promote stable rules to WARNING | Page only CRITICAL |
| Ongoing | Review monthly | New base image → re-baseline |

Document every macro change in git next to the rule. "We silenced shell alerts" without context guarantees a miss during real incident.

## Supply chain: Falco for plugin and MCP sidecars

Agents loading third-party MCP servers or plugins introduce binaries outside your main image scan path. Run plugin sidecars in dedicated namespace with **stricter** Falco rules than core inference pods:

```yaml
- macro: mcp_sidecar_pod
  condition: k8s.ns.name = "agent-mcp" and k8s.pod.label.role = "mcp-server"

- rule: MCP Binary Write to Tmp
  desc: Unexpected executable written to tmp by MCP sidecar
  condition: >
    mcp_sidecar_pod and open_write and
    (fd.name startswith /tmp/ or fd.name startswith /dev/shm/) and
    (proc.name in (chmod, mv, cp))
  output: "MCP sidecar wrote executable path (file=%fd.name pod=%k8s.pod.name)"
  priority: CRITICAL
```

Combine with image digest pinning in admission — Falco catches what slipped through.

## Performance overhead

eBPF Falco on modern kernels typically adds **1–3% CPU** on busy nodes — acceptable for agent sandbox nodes. Watch for:

- Rule complexity (`condition` with many OR branches evaluated per syscall)
- High-churn short-lived pods (batch eval jobs) amplifying event volume

Use `falco --dry-run` and `falcoctl rules check` in CI when adding custom rules.

## Compliance and audit trail

Falco JSON output to immutable storage (S3 Object Lock, SIEM) satisfies "detective control" narratives for SOC2 / ISO audits. Include fields: `k8s.pod.name`, `k8s.ns.name`, `proc.cmdline`, `container.id`, `rule`, `priority`, `time`.

Retention: 90 days hot, 1 year cold — align with your incident investigation windows.

## Practical starting set

If you are adding Falco to agent infrastructure this week, ship these before exotic rules:

1. Unexpected shell in sandbox namespace
2. Read `/var/run/secrets` or cloud metadata IP `169.254.169.254`
3. `kubectl exec` into agent production namespace (audit rule)
4. Process running as root in agent pod
5. Outbound connection from sandbox to public IP not on allowlist

Each rule links to a runbook. Detection without response is telemetry theater.

Agents blur the line between data plane and compute plane — they execute intent, not just serve it. Falco watches that execution layer with kernel fidelity. Pair it with tight admission, seccomp, and network policy, and you get defense in depth that survives the first creative prompt injection carrying shellcode ambition.

## Resources

- [Falco official documentation](https://falco.org/docs/)
- [Falco rules repository](https://github.com/falcosecurity/rules)
- [CNCF Falco project page](https://www.cncf.io/projects/falco/)
- [Kubernetes Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/)
- [MITRE ATT&CK: Container Escape techniques](https://attack.mitre.org/techniques/T1611/)
