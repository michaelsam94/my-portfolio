---
title: "AI Agents: Helm Chart Security Scan"
slug: "agent-helm-chart-security-scan"
description: "Scan Helm charts before agent workloads reach production—template injection, secret leakage, RBAC sprawl, OPA policies, and CI gates for LLM inference stacks."
datePublished: "2026-01-27"
dateModified: "2026-01-27"
tags: ["AI", "Agent", "Helm"]
keywords: "agent, helm, chart, security, scan, ai, production, engineering, architecture"
faq:
  - q: "What should Helm chart security scans catch that container image scans miss?"
    a: "Charts define runtime behavior—ClusterRole bindings, hostPath mounts, privileged containers, hardcoded secrets in values.yaml, and network policies. An image can be CVE-clean while the chart deploys cluster-admin to an agent sidecar. Scan rendered manifests, not just the chart source."
  - q: "When should chart scanning run—helm template, helm install, or admission?"
    a: "All three layers. CI runs helm template + policy check on every PR. Pre-deploy runs against environment-specific values. Admission validates the final rendered manifest at apply time so manual kubectl patches cannot bypass CI."
  - q: "How do you handle false positives on agent charts that legitimately need GPU nodes?"
    a: "Use image-class and workload-class exceptions with expiry. GPU inference pods may need elevated capabilities; document owner, compensating controls (network policy, no egress), and re-review quarterly. Never global-allowlist privileged mode."
  - q: "Should agent Helm charts pin subchart versions?"
    a: "Yes. Unpinned dependencies pull latest on helm dependency update, silently changing security posture. Lock Chart.lock, scan subcharts recursively, and treat dependency bumps as security-relevant diffs requiring review."
---
The platform team approved a new agent orchestrator Helm chart because the container image passed Trivy with zero critical CVEs. Two weeks later, a red-team exercise found the chart mounted `/var/run/docker.sock`, granted `cluster-admin` to the default service account, and embedded an OpenAI API key in a ConfigMap labeled `environment: prod`. The image was fine. The chart was the breach waiting to happen.

Helm charts are executable infrastructure for AI agent platforms—they declare not just which inference image runs, but how it talks to vector stores, tool sandboxes, and secrets backends. Scanning container images without scanning charts is like inspecting the engine but ignoring the wiring diagram.

## What agent Helm charts uniquely expose

Agent workloads differ from typical microservices in chart design:

| Pattern | Risk | Why agents need it |
|---------|------|-------------------|
| Sidecar tool runners | Privileged mounts, shared volumes | Sandboxed code execution |
| GPU node selectors | Tolerations for tainted nodes | Local model inference |
| Egress to LLM APIs | Wide NetworkPolicy holes | External model calls |
| Ephemeral scratch PVCs | hostPath fallbacks under pressure | Large context caching |
| Webhook ingress | Public endpoints without auth | User-facing chat |

Each pattern is defensible in isolation. Combined without policy guardrails, they produce charts that pass image scans and fail security reviews.

## Scanning pipeline architecture

```
Chart PR → helm template (values-dev/staging/prod)
              │
              ├─▶ Checkov / Kubesec (manifest rules)
              ├─▶ Conftest + OPA/Rego (custom policy)
              ├─▶ helm-secrets / SOPS validation
              └─▶ kube-score / polaris (best practices)
              │
         fail ▶ block merge
         pass ▶ deploy → admission webhook (second scan)
```

Render with **production-shaped values** in CI. Scanning only `values.yaml` defaults misses overrides that inject real secrets and open network paths.

```yaml
# .github/workflows/helm-security.yml
name: Helm Security Scan
on:
  pull_request:
    paths: ['charts/agent-orchestrator/**']

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Render prod manifests
        run: |
          helm template agent-orchestrator ./charts/agent-orchestrator \
            -f ./charts/agent-orchestrator/values-prod.yaml \
            --namespace agent-prod > rendered.yaml

      - name: Checkov
        uses: bridgecrewio/checkov-action@master
        with:
          file: rendered.yaml
          framework: kubernetes
          soft_fail: false

      - name: Conftest policy
        run: |
          conftest test rendered.yaml \
            -p policies/helm/agent \
            --fail-on WARN
```

## Policy rules that matter for agent charts

Generic Kubernetes policies catch baseline issues. Agent-specific Rego adds context:

```rego
# policies/helm/agent/deny_privileged.rego
package agent.helm

deny[msg] {
  input.kind == "Pod"
  container := input.spec.containers[_]
  container.securityContext.privileged == true
  not annotation_allowed(input.metadata.annotations)
  msg := sprintf("privileged container %s in %s", [container.name, input.metadata.name])
}

annotation_allowed(annotations) {
  annotations["agent.security.io/privileged-review"]
  annotations["agent.security.io/privileged-expiry"]
}
```

Additional high-value rules:

**No secrets in ConfigMaps** — agent charts often stash `OPENAI_API_KEY` in ConfigMaps for convenience. Deny unless referenced from ExternalSecrets.

**Service account least privilege** — flag `cluster-admin`, `create` on secrets cluster-wide, or wildcard verbs on `pods/exec`.

**hostPath mounts** — deny except allowlisted paths (`/dev/nvidia*`) with annotation.

**Image tag mutability** — require digest-pinned images or semver tags; deny `:latest` in production values.

**NetworkPolicy presence** — agent namespaces handling tenant data must have default-deny egress with explicit LLM API allowlist.

```yaml
# Example failing snippet often found in agent charts
apiVersion: v1
kind: ConfigMap
metadata:
  name: agent-config
data:
  OPENAI_API_KEY: sk-proj-xxxxx   # ← CI must fail this
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: agent-runner-binding
subjects:
  - kind: ServiceAccount
    name: default
    namespace: agent-prod
roleRef:
  kind: ClusterRole
  name: cluster-admin          # ← deny
```

## Secret management patterns

Charts should reference secrets, not contain them:

```yaml
# values-prod.yaml — correct pattern
externalSecrets:
  enabled: true
  llmApiKey:
    secretStore: aws-secrets-manager
    key: prod/agent/llm-api-key

# templates/deployment.yaml
env:
  - name: OPENAI_API_KEY
    valueFrom:
      secretKeyRef:
        name: {{ include "agent.fullname" . }}-llm
        key: api-key
```

Scan for:

- Base64-encoded secrets in manifests (even if Kubernetes "expects" encoding)
- `.Values` keys matching `*password*`, `*token*`, `*key*` with non-empty defaults in git
- Helm notes that echo secrets to install output

Integrate `git-secrets` or `trufflehog` on the chart directory alongside manifest policy.

## Subchart and dependency risk

Agent platforms often bundle:

- `redis` for session state
- `postgresql` for conversation persistence
- `kafka` for event streaming
- Vendor `gpu-operator` subcharts

Run `helm dependency list` and scan each subchart's rendered output. A compromised or outdated subchart version can reintroduce `runAsUser: 0` after your parent chart enforces non-root.

Lock file discipline:

```bash
helm dependency update charts/agent-orchestrator
# Commit Chart.lock — CI fails if lock out of sync
helm dependency build charts/agent-orchestrator
```

## Admission control as last line

CI can be bypassed by emergency hotfixes. Deploy an admission webhook (Kyverno, OPA Gatekeeper) that re-runs the same policies:

```yaml
# Kyverno ClusterPolicy example
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: agent-chart-baseline
spec:
  validationFailureAction: Enforce
  rules:
    - name: require-non-root
      match:
        any:
          - resources:
              kinds: [Pod]
              namespaces: ["agent-*"]
      validate:
        message: "Agent pods must run as non-root"
        pattern:
          spec:
            securityContext:
              runAsNonRoot: true
```

Admission adds latency—cache policy decisions and scope narrowly to agent namespaces.

## Operational concerns

**Policy drift** — when Kubernetes upgrades deprecate APIs, charts may silently render differently. Re-scan on cluster upgrade.

**Values sprawl** — ten environment files mean ten render targets in CI. Automate matrix renders; fail if any environment violates policy.

**Exception debt** — track allowlisted findings with expiry dates in a CSV consumed by Conftest:

```csv
rule_id,resource,owner,expires,reason
deny_privileged,agent-sandbox,pipeline-team,2026-06-01,gVisor requires CAP_SYS_PTRACE
```

Review weekly in agent platform standup.

## Testing the scan itself

Policy tests prevent regressions:

```rego
# policies/helm/agent/deny_privileged_test.rego
test_deny_privileged_pod {
  deny["privileged container sandbox in agent-worker"] with input as {
    "kind": "Pod",
    "metadata": {"name": "agent-worker", "annotations": {}},
    "spec": {"containers": [{"name": "sandbox", "securityContext": {"privileged": true}}]}
  }
}
```

Include **golden bad manifests** in repo—known-vulnerable chart snippets that must always fail. When someone weakens policy to unblock a deploy, golden tests scream.

## Rollout checklist for agent platform teams

Before merging the first chart scan gate, align platform and ML teams on ownership:

1. **Inventory charts** — list every Helm release touching agent inference, tool sandboxes, and vector DB sidecars. Unknown charts bypass CI.
2. **Baseline render matrix** — produce `rendered.yaml` for dev, staging, and prod values; store artifacts in CI for diff review on PRs.
3. **Severity rubric** — document which Checkov/Conftest rules are `deny` vs. `warn` during a two-week burn-in. Promote warn→deny once false-positive rate drops below 5%.
4. **Exception workflow** — require ticket ID in chart annotations for any temporary allowlist; auto-fail CI when expiry date passes.
5. **On-call runbook** — when admission blocks a hotfix deploy at 2am, engineers need a documented escalation path that does not disable the webhook globally.

Pair chart scanning with **SBOM export** from the same CI job. When a CVE hits a base image, you can trace which chart version promoted that digest and roll back the release—not just the image tag.

## The takeaway

Helm chart security scanning closes the gap between "safe image" and "safe deployment." Render with real values, enforce agent-specific RBAC and secret policies, scan dependencies recursively, and duplicate enforcement at admission. AI agent platforms move fast; chart policy is how you move fast without handing cluster-admin to a prompt injection.

## Resources

- [Checkov Helm and Kubernetes policies](https://www.checkov.io/5.Policy%20Index/kubernetes.html)
- [Open Policy Agent Conftest](https://www.conftest.dev/)
- [Kyverno policy library](https://kyverno.io/policies/)
- [Helm best practices — values and secrets](https://helm.sh/docs/chart_best_practices/secrets/)
- [NSA Kubernetes hardening guidance](https://media.defense.gov/2022/Aug/29/2003067252/-1/-1/0/KUBERNETES-HARDENING-GUIDANCE-1.2-PDF.PDF)
