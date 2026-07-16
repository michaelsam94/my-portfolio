---
title: "Helm vs Kustomize"
slug: "kubernetes-helm-vs-kustomize"
description: "Choose between Helm and Kustomize for Kubernetes manifests: templating vs patches, release lifecycle, GitOps fit, and hybrid patterns that work in production."
datePublished: "2026-01-28"
dateModified: "2026-01-28"
tags: ["Kubernetes", "DevOps"]
keywords: "Helm, Kustomize, Kubernetes manifests, GitOps, templating, helm vs kustomize, overlays"
faq:
  - q: "Can I use Helm and Kustomize together?"
    a: "Yes. Common pattern: helm template or helm install produces base manifests, Kustomize overlays patch images, replicas, and config per environment. Some teams wrap Helm charts in Kustomize bases; others use Helm for third-party charts and Kustomize for in-house apps only."
  - q: "Which tool is better for GitOps with Argo CD or Flux?"
    a: "Both integrate well. Argo CD natively renders Helm and Kustomize. Kustomize fits pure YAML repos with strategic merge patches. Helm fits packaged releases with semver charts and values.yaml per environment. Pick based on whether you ship reusable charts or environment overlays."
  - q: "When does Helm templating become unmaintainable?"
    a: "When charts accumulate complex conditionals, global values spaghetti, and nested includes that obscure final YAML. If helm template output requires mental compilation to review in PRs, consider flattening with Kustomize or splitting charts by bounded context."
---

Two teams, same cluster, opposite tool religions. One shipped **Helm charts** with fourteen values files nobody could diff. The other had **Kustomize overlays** copying 200-line Deployments per environment. Both worked; both hurt at scale. The answer is not universal—it is matching tool to packaging vs customization problems.

**Helm** packages Kubernetes apps as charts with templating and release versioning. **Kustomize** is patch-based customization built into kubectl—no templating language, overlays on plain YAML.

## Mental model comparison

| Aspect | Helm | Kustomize |
|--------|------|-----------|
| Output | Template → YAML | Base + patches → YAML |
| Packaging | Chart repos, semver | Directories in Git |
| Params | values.yaml | patches, replacements, images |
| Release tracking | helm list / history | Git commit = source of truth |
| Learning curve | Go templates, hooks | Strategic merge, resources |

## Helm example

```yaml
# values-production.yaml
replicaCount: 5
image:
  tag: "2.4.1"
ingress:
  host: api.example.com
```

```yaml
# templates/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "app.fullname" . }}
spec:
  replicas: {{ .Values.replicaCount }}
  template:
    spec:
      containers:
        - name: app
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
```

```bash
helm upgrade --install api ./chart -f values-production.yaml -n production
```

Helm hooks handle pre/post upgrade jobs; chart dependencies bundle subcharts.

## Kustomize example

```
deploy/
  base/
    deployment.yaml
    service.yaml
    kustomization.yaml
  overlays/
    production/
      kustomization.yaml
      replica-patch.yaml
```

```yaml
# overlays/production/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ../../base
replicas:
  - name: api
    count: 5
images:
  - name: ghcr.io/org/api
    newTag: "2.4.1"
patches:
  - path: replica-patch.yaml
```

```bash
kubectl apply -k deploy/overlays/production
```

`kubectl kustomize` prints final YAML for PR review—excellent GitOps hygiene.

## When Helm wins

- Distributing apps to external users (chart museum, Artifact Hub)
- Third-party software (Prometheus, Kafka operators) shipped as charts
- Release rollback via `helm rollback`
- Complex conditional resources (optional ServiceMonitor, ingress toggles)

## When Kustomize wins

- Internal apps with stable base manifests
- Teams who reject templating in YAML reviews
- Fine-grained per-env patches without abstraction leakage
- Simple image tag promotion in CI (`kustomize edit set image`)

## Hybrid pattern

```bash
helm template prometheus prometheus-community/kube-prometheus-stack \
  -f monitoring-values.yaml > base/rendered/prometheus.yaml
```

Kustomize overlay patches retention and external labels on rendered output—or use Helm support in Argo CD directly.

## GitOps considerations

Argo CD Application:

```yaml
spec:
  source:
    helm:
      valueFiles:
        - values-prod.yaml
    path: charts/api
```

vs

```yaml
spec:
  source:
    path: deploy/overlays/production
    kustomize: {}
```

Both support drift detection and sync waves. Helm adds release secret metadata; Kustomize relies purely on Git.

## Decision guide

Choose **Helm** if you publish reusable packages or depend heavily on community charts.

Choose **Kustomize** if environments differ incrementally and you want reviewable YAML.

Choose **both** if platform distributes Helm and apps overlay with Kustomize.

Neither replaces valid base manifests, resource limits, or network policies.

## helm test vs smoke job

Helm chart hooks run on install/upgrade; add `helm test` pod that curls Service health endpoint before marking release successful in CI pipeline.


## What to measure after rollout

Track error rates, tail latency, and resource utilization for two weeks after changes land—most regressions appear under real traffic mixes, not in staging smoke tests. Keep a rollback path documented: feature flags, Helm revision, or Git revert with known good digest. Review on-call pages tied to the topic quarterly; delete alerts that never fire and add thresholds that would have caught your last incident.

Run a short blameless postmortem if production surprised you, even for minor issues. The goal is updating this runbook section with one concrete lesson per quarter so the next engineer inherits context, not just configuration snippets.


## Documentation your team should maintain

Maintain a one-page runbook link from your main service README: prerequisites, owner rotation, last drill date, and known sharp edges. Link to vendor docs in the Resources section below but capture org-specific decisions (CIDR ranges, cluster names, approval gates) in internal docs that stay current. New hires should deploy a safe canary within a week using only that runbook—if they cannot, the doc is incomplete.


## Pre-production checklist

Before promoting to production, walk through this list with someone who was not the primary author—fresh eyes catch assumptions.

- **Staging parity**: The staging environment exercises the same code paths as production, including failure modes you expect to handle (timeouts, retries, partial outages).
- **Observability**: Dashboards and alerts exist for the metrics and log patterns discussed above; on-call knows where to look first.
- **Rollback**: You can revert to the previous known-good state in one documented step without improvising.
- **Access control**: Only the principals that need access have it; audit logs are enabled where the topic touches secrets or infrastructure APIs.
- **Load test**: You have evidence—not intuition—about behavior at expected peak plus headroom.

If any item is "we will do that later," treat it as a release blocker for tier-1 services.


## Common questions from reviewers

Reviewers and auditors often ask whether this approach scales with team growth and whether it fails safely. Answer explicitly in your design doc: what happens when dependencies are down, when credentials expire, and when traffic doubles overnight. Prefer defaults that deny or degrade gracefully over defaults that fail open. Document known limits (throughput ceilings, supported versions, regions) in the same place operators look during incidents—avoid scattering critical constraints across Slack threads.


Helm for third-party charts, Kustomize for your manifests — mixing both on same release without documentation confuses on-call.

## Resources

- [Helm documentation](https://helm.sh/docs/) — charts, values, and hooks
- [Kustomize documentation](https://kubectl.docs.kubernetes.io/references/kustomize/) — overlays and generators
- [Argo CD Helm support](https://argo-cd.readthedocs.io/en/stable/user-guide/helm/) — GitOps with charts
- [Artifact Hub](https://artifacthub.io/) — discover Helm charts
