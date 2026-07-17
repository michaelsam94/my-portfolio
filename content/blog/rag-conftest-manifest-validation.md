---
title: "Conftest and Rego for Kubernetes Manifest Validation"
slug: "rag-conftest-manifest-validation"
description: "Gate agent deployments with Conftest and Rego: validate Kubernetes manifests for GPU quotas, secret mounts, network policies, and OPA policy bundles before anything reaches the cluster."
datePublished: "2026-01-24"
dateModified: "2026-07-17"
tags: ["AI", "Rag", "Conftest"]
keywords: "Conftest manifest validation, Rego Kubernetes policies, OPA agent deployments, policy as code CI gate, GPU workload validation"
faq:
  - q: "Why use Conftest instead of kubeval or kubeconform for agent manifests?"
    a: "kubeval and kubeconform check schema validity — correct fields, correct types. Conftest checks organizational intent: GPU requests match node selectors, agent pods cannot mount hostPath, secrets must come from ExternalSecrets, and sidecars must run as non-root. Schema-valid manifests still violate security baselines daily."
  - q: "Should Conftest policies live in the agent repo or a central policy repo?"
    a: "Central repo for shared baseline policies (PSA, network policy, resource limits). Agent repo for workload-specific rules (model server image allowlist, required OTEL sidecar). CI in the agent repo pulls the central bundle as a submodule or OCI artifact versioned by tag."
  - q: "How do you test Rego policies without a live cluster?"
    a: "Use conftest verify with Rego test files alongside policies. Feed fixture manifests representing valid and invalid agent deployments. Run opa test ./policies in CI. Add regression fixtures every time a production incident reveals a gap."
---

An platform team shipped a Helm chart that passed every JSON Schema check. The Deployment was valid Kubernetes. It also mounted the host Docker socket, ran the inference sidecar as root, and omitted NetworkPolicy — so when a prompt-injection path triggered arbitrary code execution inside the sandbox container, lateral movement was trivial.

Schema validation catches malformed YAML. It does not catch **policy violations that are syntactically legal**. Conftest closes that gap by evaluating rendered manifests against Rego policies in CI, in admission hooks, and in pre-deploy gates — before a bad manifest touches a cluster running production traffic.

## Where Conftest sits in the delivery pipeline

```
Developer edits Helm/Kustomize
        ↓
helm template / kustomize build
        ↓
conftest test (CI — fail PR)
        ↓
image build + sign
        ↓
conftest test (CD — fail promote)
        ↓
optional: OPA Gatekeeper / Kyverno (admission — fail apply)
        ↓
cluster
```

Data-intensive workloads add policy dimensions beyond typical web apps: GPU resource claims, model artifact volumes, outbound network restrictions for code execution sandboxes, and secrets that must never appear as plain env vars in rendered YAML.

Conftest is the **portable policy runner**. The same Rego bundle runs locally, in GitHub Actions, and can be synced to Gatekeeper ConstraintTemplates for defense in depth.

## Project layout

```
policies/
  kubernetes/
    deployment.rego
    deployment_test.rego
    networkpolicy.rego
    secrets.rego
  agent/
    gpu.rego
    sandbox.rego
    observability.rego
fixtures/
  valid/
    deployment.yaml
  invalid/
    missing-networkpolicy.yaml
    hostpath-mount.yaml
.conftest.yaml
```

`.conftest.yaml` pins policy namespaces and combine behavior:

```yaml
policy:
  - policies/kubernetes
  - policies/agent
namespace: main
combine: true
output: json
failOnWarn: true
```

`combine: true` merges multiple policy files into one evaluation context — useful when application-specific rules import shared helpers.

## Baseline Deployment policy

Every agent Deployment must declare resource limits, run as non-root, and forbid privileged mode:

```rego
# policies/kubernetes/deployment.rego
package main

deny contains msg if {
  input.kind == "Deployment"
  container := input.spec.template.spec.containers[_]
  not container.resources.limits
  msg := sprintf("Deployment %v container %v missing resource limits", [input.metadata.name, container.name])
}

deny contains msg if {
  input.kind == "Deployment"
  container := input.spec.template.spec.containers[_]
  container.securityContext.privileged == true
  msg := sprintf("Deployment %v container %v must not be privileged", [input.metadata.name, container.name])
}

deny contains msg if {
  input.kind == "Deployment"
  container := input.spec.template.spec.containers[_]
  not container.securityContext.runAsNonRoot
  msg := sprintf("Deployment %v container %v must set runAsNonRoot", [input.metadata.name, container.name])
}
```

Agent-specific: require an `app.kubernetes.io/component: agent-runtime` label for anything in the application namespace:

```rego
# policies/agent/sandbox.rego
package main

deny contains msg if {
  input.kind == "Deployment"
  input.metadata.namespace == "agents"
  not input.metadata.labels["app.kubernetes.io/component"]
  msg := sprintf("Deployment %v in application namespace missing component label", [input.metadata.name])
}

deny contains msg if {
  input.kind == "Deployment"
  input.metadata.namespace == "agents"
  volume := input.spec.template.spec.volumes[_]
  volume.hostPath
  msg := sprintf("Deployment %v must not use hostPath volumes", [input.metadata.name])
}
```

## GPU and model server validation

GPU workloads fail silently when requests and node selectors disagree:

```rego
# policies/agent/gpu.rego
package main

deny contains msg if {
  input.kind == "Deployment"
  container := input.spec.template.spec.containers[_]
  container.resources.limits["nvidia.com/gpu"]
  not input.spec.template.spec.nodeSelector["nvidia.com/gpu.present"]
  msg := sprintf("Deployment %v requests GPU but lacks nvidia.com/gpu.present nodeSelector", [input.metadata.name])
}

warn contains msg if {
  input.kind == "Deployment"
  container := input.spec.template.spec.containers[_]
  gpu := container.resources.limits["nvidia.com/gpu"]
  to_number(gpu) > 1
  not input.metadata.annotations["agents.example.com/multi-gpu-approved"]
  msg := sprintf("Deployment %v requests %v GPUs without multi-gpu approval annotation", [input.metadata.name, gpu])
}
```

Warnings vs denies: use `deny` for security invariants, `warn` for cost-review triggers. Set `failOnWarn: true` in CI only after teams adjust existing manifests — otherwise migrate with warns first, then promote to denies.

## Secret and config validation

Plaintext secrets in Git are the most common agent-platform incident. Conftest catches them at render time:

```rego
# policies/kubernetes/secrets.rego
package main

deny contains msg if {
  input.kind == "Secret"
  input.metadata.namespace == "agents"
  not input.metadata.labels["managed-by"] == "external-secrets"
  msg := sprintf("Secret %v must be managed by ExternalSecrets operator", [input.metadata.name])
}

deny contains msg if {
  input.kind == "Deployment"
  container := input.spec.template.spec.containers[_]
  env := container.env[_]
  env.name == "OPENAI_API_KEY"
  env.value
  msg := sprintf("Deployment %v has plaintext OPENAI_API_KEY — use secretKeyRef", [input.metadata.name])
}
```

Pair with gitleaks in the same CI job. Conftest catches secrets that enter through Helm values; gitleaks catches secrets in source.

## NetworkPolicy requirements for code sandboxes

Agent sandboxes that execute user-adjacent code need default-deny egress with explicit allowlist:

```rego
# policies/kubernetes/networkpolicy.rego
package main

expected_sandbox := {name |
  input.kind == "Deployment"
  input.metadata.labels["app.kubernetes.io/component"] == "code-sandbox"
  name := input.metadata.name
}

deny contains msg if {
  name := expected_sandbox[_]
  not networkpolicy_covers(name)
  msg := sprintf("Sandbox Deployment %v has no matching NetworkPolicy", [name])
}

networkpolicy_covers(deploy_name) if {
  some np
  np.kind == "NetworkPolicy"
  np.spec.podSelector.matchLabels["app.kubernetes.io/name"] == deploy_name
}
```

Adjust matching logic to your label conventions. The point is **structural enforcement**: every sandbox Deployment triggers a corresponding NetworkPolicy check.

## CI integration

GitHub Actions example:

```yaml
name: manifest-policy
on: [pull_request]

jobs:
  conftest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: helm/kind-action@v1
      - name: Render manifests
        run: |
          helm template rag-platform ./charts/rag-platform \
            -f values/ci.yaml \
            > rendered.yaml
      - uses: openpolicyagent/conftest-action@v0.1
        with:
          files: rendered.yaml
          policy: policies/
          fail-on-warn: true
```

For multi-document YAML, conftest evaluates each document. Use `conftest test --all-namespaces` when combining Kubernetes resources with CRDs.

Local developer loop:

```bash
helm template rag-platform ./charts/rag-platform | conftest test - -p policies/
conftest verify -p policies/
```

## Testing policies with conftest verify

Every deny rule needs a regression test:

```rego
# policies/kubernetes/deployment_test.rego
package main

test_deny_privileged if {
  deny with input as {
    "kind": "Deployment",
    "metadata": {"name": "bad-deploy"},
    "spec": {"template": {"spec": {"containers": [{
      "name": "runtime",
      "securityContext": {"privileged": true},
      "resources": {"limits": {"cpu": "1"}}
    }]}}}
  }
  with data as {}
  count(deny) > 0
}

test_allow_non_privileged if {
  deny with input as {
    "kind": "Deployment",
    "metadata": {"name": "good-deploy"},
    "spec": {"template": {"spec": {"containers": [{
      "name": "runtime",
      "securityContext": {"runAsNonRoot": true, "privileged": false},
      "resources": {"limits": {"cpu": "1"}}
    }]}}}
  }
  with data as {}
  count(deny) == 0
}
```

Run `conftest verify -p policies/` in CI alongside policy linting. Broken tests block merges — policies are code.

## Sharing policies via OCI bundles

Centralize policies as versioned OCI artifacts:

```bash
opa build -b policies/ -o bundle.tar.gz
oras push ghcr.io/org/platform-policies:v1.4.0 bundle.tar.gz:application/vnd.cncf.opa.policy.layer.v1+tar+gzip
```

Consumer CI:

```bash
oras pull ghcr.io/org/platform-policies:v1.4.0
conftest test rendered.yaml -p bundle.tar.gz
```

Pin policy versions in repos. Unexpected policy upgrades should not break main on a Monday because someone tagged `:latest`.

## Admission-time enforcement

CI gates catch developer mistakes. Admission catches bypass attempts and emergency kubectl applies. Sync Conftest Rego to Gatekeeper:

```yaml
apiVersion: templates.gatekeeper.sh/v1
kind: ConstraintTemplate
metadata:
  name: nonroot
spec:
  crd:
    spec:
      names:
        kind: RequireNonRoot
  targets:
    - target: admission.k8s.gatekeeper.sh
      rego: |
        package nonroot
        violation[{"msg": msg}] {
          input.review.object.kind == "Deployment"
          container := input.review.object.spec.template.spec.containers[_]
          not container.securityContext.runAsNonRoot
          msg := "application containers must run as non-root"
        }
```

Keep CI and admission policies identical where possible — drift between the two creates "works in PR, fails in prod" confusion.

## Keeping policies maintainable at scale

- **Policy exceptions**: use annotations with expiry dates reviewed weekly, not permanent whitelists
- **CRD coverage**: agent platforms increasingly use InferenceService, RayCluster, or custom Operator CRDs — extend policies beyond core kinds
- **Performance**: admission evaluation must stay under 50 ms; precompile bundles and avoid O(n²) scans over large ConfigMaps
- **Observability**: export `gatekeeper_denied_total` and conftest CI failure rates — spikes indicate chart changes or policy that's too strict

When an incident reveals a gap, add a fixture representing the bad manifest before writing the deny rule. The fixture is the spec; Rego is the implementation.

## The takeaway

Conftest turns deployment safety from a checklist in a design doc into an executable gate. Render your manifests, validate organizational intent with Rego, test policies like application code, and mirror the same bundle at admission. Schema-valid YAML is necessary; policy-valid YAML is what keeps a compromised container from becoming a cluster compromise.

## Resources

- [Conftest documentation](https://www.conftest.dev/)
- [Rego language reference](https://www.openpolicyagent.org/docs/latest/policy-language/)
- [OPA Gatekeeper constraints](https://open-policy-agent.github.io/gatekeeper/website/docs/)
- [Kubernetes Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/)
- [External Secrets Operator](https://external-secrets.io/latest/)
