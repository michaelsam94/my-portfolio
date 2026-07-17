---
title: "AI Agents: Gitops Promotion Environments"
slug: "agent-gitops-promotion-environments"
description: "Promote agent workloads dev→staging→prod with GitOps—Kustomize overlays, Argo CD sync waves, eval gates, and model-version pinning that prevent silent config drift."
datePublished: "2026-03-04"
dateModified: "2026-03-04"
tags: ["AI", "Agent", "Gitops"]
keywords: "gitops, promotion, environments, Argo CD, Flux, Kustomize, agent deployment, model versioning, progressive delivery"
faq:
  - q: "How should agent model versions differ across GitOps environments?"
    a: "Pin model IDs and embedding versions explicitly in Kustomize overlays per environment—never rely on provider defaults that change silently. Staging should run the candidate model; production runs the last promoted SHA. Record model card hash in the Git commit that triggers promotion so rollbacks restore both code and model."
  - q: "What gates belong between staging and production promotion?"
    a: "Automated eval suites (accuracy, latency p95, cost per session), security scan of container images, and manual approval for prompt or tool-registry changes. Block promotion if eval regression exceeds thresholds or if vector index schema differs without migration job completion."
  - q: "Should each environment have its own Git branch or Kustomize overlay?"
    a: "Prefer trunk-based development with environment overlays in one repo (apps/agent/overlays/staging). Branch-per-env creates merge debt. Promotion is a PR that updates image digest and config in overlays/prod—or an Argo CD ApplicationSet parameter change—not a cherry-pick between long-lived branches."
  - q: "How do we prevent staging-only secrets from leaking into prod manifests?"
    a: "External Secrets Operator or Sealed Secrets per cluster. Overlays reference secret keys, not values. CI validates prod overlays contain no staging hostnames, test API keys, or debug log levels. Use policy-as-code (OPA, Kyverno) to reject forbidden keys in prod paths."
---
Production served GPT-4o while staging still pointed at a deprecated snapshot because nobody updated the Kustomize overlay after the model vendor renamed the endpoint. Argo CD showed green—sync succeeded—but agent quality regressed for two weeks before eval dashboards caught it. Promotion had meant "merge to main," not "verified artifact chain across environments."

GitOps promotion for agent systems is harder than deploying stateless APIs. You are promoting container images, prompt ConfigMaps, tool allowlists, vector index versions, and eval baselines together. A green sync with wrong model ID is worse than a failed deploy. This post covers environment overlays, promotion PRs, sync waves, and gates that treat LLM config as first-class release artifacts.

## GitOps promotion model for agent stacks

```text
dev overlay     → auto-sync on commit to main (internal only)
staging overlay → auto-sync + eval CI gate
prod overlay    → manual approve + progressive sync (canary → full)
```

Each overlay pins:

- Container image digest (not `:latest`)
- `MODEL_ID`, `EMBEDDING_MODEL`, temperature defaults
- RAG collection name and index version
- Feature flags for tools and MCP servers
- Resource limits (GPU/CPU, max concurrent sessions)

Promotion is updating prod overlay fields to match a **verified staging SHA**, not redeploying ambiguous tags.

## Repository layout

```text
apps/agent/
  base/
    deployment.yaml
    configmap-prompts.yaml
    service.yaml
  overlays/
    dev/
      kustomization.yaml
      patch-model.yaml
    staging/
      kustomization.yaml
      patch-model.yaml
      patch-replicas.yaml
    prod/
      kustomization.yaml
      patch-model.yaml
      patch-hpa.yaml
clusters/
  staging/
    application.yaml      # Argo CD Application
  prod/
    application.yaml
```

```yaml
# apps/agent/overlays/staging/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ../../base
patches:
  - path: patch-model.yaml
images:
  - name: agent-api
    newName: ghcr.io/org/agent-api
    newTag: sha-a1b2c3d4
configMapGenerator:
  - name: agent-config
    behavior: merge
    literals:
      - MODEL_ID=gpt-4o-2024-08-06
      - EMBEDDING_MODEL=text-embedding-3-large
      - VECTOR_COLLECTION=agent-docs-staging-v12
```

Prod overlay differs only in pinned values—same structure, different literals.

## Argo CD Application and sync waves

Order dependencies with sync waves so migrations complete before traffic shifts:

```yaml
# clusters/prod/application.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: agent-prod
  annotations:
    argocd.argoproj.io/sync-wave: "10"
spec:
  project: production
  source:
    repoURL: https://github.com/org/gitops-agent
    targetRevision: main
    path: apps/agent/overlays/prod
  destination:
    server: https://kubernetes.default.svc
    namespace: agent-prod
  syncPolicy:
    automated: null  # manual promote only
```

Migration job runs at wave 0; Deployment at wave 10:

```yaml
# base/job-index-migrate.yaml
metadata:
  annotations:
    argocd.argoproj.io/sync-wave: "0"
spec:
  template:
    spec:
      containers:
        - name: migrate
          image: agent-migrate:sha-a1b2c3d4
          env:
            - name: TARGET_COLLECTION
              valueFrom:
                configMapKeyRef:
                  name: agent-config
                  key: VECTOR_COLLECTION
```

## Promotion PR workflow

Automate opening promotion PRs when staging eval passes:

```typescript
// scripts/open-promotion-pr.ts — simplified
interface PromotionCandidate {
  stagingSha: string;
  imageDigest: string;
  modelId: string;
  vectorCollection: string;
  evalReportUrl: string;
}

async function createPromotionPr(candidate: PromotionCandidate) {
  const prodKustomization = await readFile("apps/agent/overlays/prod/kustomization.yaml");
  const updated = bumpImageTag(prodKustomization, candidate.imageDigest);
  await writeFile("apps/agent/overlays/prod/kustomization.yaml", updated);
  await patchConfigMap("prod", {
    MODEL_ID: candidate.modelId,
    VECTOR_COLLECTION: candidate.vectorCollection,
  });
  await gh.createPullRequest({
    title: `promote(agent): ${candidate.stagingSha} → prod`,
    body: `Eval report: ${candidate.evalReportUrl}\nStaging verified: ${candidate.stagingSha}`,
    labels: ["promotion", "requires-platform-approval"],
  });
}
```

PR checklist embedded in template:

- [ ] Eval latency p95 within SLO vs previous prod
- [ ] Cost per session delta < 10%
- [ ] No new tools without security review
- [ ] Index migration job succeeded in staging

## Eval gates as promotion blockers

Wire CI to fail promotion PRs when regressions exceed thresholds:

```yaml
# .github/workflows/agent-eval-gate.yml
name: Agent eval gate
on:
  pull_request:
    paths:
      - "apps/agent/overlays/prod/**"
jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - name: Run staging eval suite against candidate
        run: |
          python eval/run_suite.py \
            --base-url https://agent-staging.internal \
            --baseline-report eval/baselines/prod-latest.json \
            --max-regression 0.02
      - name: Assert cost ceiling
        run: |
          python eval/check_cost.py --max-delta-percent 10
```

Store eval baselines as JSON artifacts in the GitOps repo or S3 with SHA references in promotion PRs.

## Secrets and config separation

Never promote literal secrets. Use External Secrets:

```yaml
# overlays/prod/external-secret.yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: agent-llm-keys
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: ClusterSecretStore
  target:
    name: agent-llm-keys
  data:
    - secretKey: OPENAI_API_KEY
      remoteRef:
        key: prod/agent/openai
```

Kyverno policy rejects prod overlays containing staging hostnames:

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: block-staging-in-prod
spec:
  rules:
    - name: no-staging-urls
      match:
        resources:
          kinds: [ConfigMap]
          namespaces: [agent-prod]
      validate:
        message: "Staging URLs forbidden in prod"
        deny:
          conditions:
            - key: "{{ request.object.data }}"
              operator: AnyIn
              value: ["staging.internal", "sk-test-"]
```

## Progressive delivery within GitOps

For prod, split traffic before full overlay promotion:

1. Deploy canary overlay (`overlays/prod-canary`) with 5% traffic via service mesh or ingress weight
2. Compare error rate and eval sample against stable prod
3. Merge full prod overlay bump after 24h clean burn

Flagger or Argo Rollouts integrate with GitOps by referencing the same image digest promoted through overlays.

## Rollback

Rollback is revert the promotion PR—or `argocd app rollback agent-prod`. Because model ID and vector collection live in Git, revert restores the full artifact set. Keep previous image digest in PR history for one-click revert.

Document rollback runbook: if vector schema migrated forward-only, rollback may require restore from snapshot—note in promotion PR when migration is irreversible.

## Observability across environments

Dashboards must slice by `environment` and `git_sha`:

| Panel | Purpose |
|-------|---------|
| Sync status per Application | Drift detection |
| Model ID label on requests | Config mismatch alert |
| Eval score vs baseline | Post-promote regression |
| Cost per 1k tokens | Budget guard |

Alert when prod `MODEL_ID` label differs from prod overlay ConfigMap for >5 minutes—indicates manual kubectl edit bypassing GitOps.

## Common failure modes

**`:latest` tags.** Sync succeeds; content unknown.

**Prompt changes without eval.** ConfigMap update skips CI because only image changed.

**Shared vector collection across envs.** Staging reindex corrupts prod retrieval.

**Auto-sync prod.** One bad merge hits customers—keep prod manual or canary-gated.

**Drift from emergency hotfix.** kubectl patch not backported to Git—enable Argo CD self-heal only after hotfix PR merges.

## Coordinating prompt and tool registry promotion

Agent behavior changes when ConfigMaps update even if the container image is unchanged. Treat prompt diffs as release artifacts:

**Diff visibility.** Promotion PRs must include rendered prompt diff, not only image digest. Use `kustomize build` output in CI comments so reviewers see token limit and tool allowlist changes.

**Tool registry versioning.** MCP server entries and function-calling schemas live in Git separate from Deployment. Bump `toolRegistryVersion` in overlay literals; application refuses startup if registry version ≠ expected—prevents half-updated tool surfaces.

```yaml
# overlays/staging/patch-tools.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: agent-tools
data:
  registry.json: |
    {"version":"2026.03.04-staging","tools":["search","calendar"]}
```

**Shadow traffic in staging.** Before prod promotion, replay sanitized production session samples against staging overlay. Compare tool invocation patterns and refusal rates—not only aggregate eval scores.

## Multi-cluster and multi-region promotion

Global agent products may run separate Argo CD instances per region with identical overlay structure:

```text
overlays/prod-eu  → cluster-eu (data residency)
overlays/prod-us  → cluster-us
```

Promotion PR updates both overlays with the same image digest but region-specific `VECTOR_COLLECTION` and model endpoint URLs. CI validates EU overlay never references US-only hostnames. Stagger sync: EU first if GDPR review required, then US after smoke tests pass.

ApplicationSet generators can fan out one commit to many clusters—ensure eval gates run per region because latency SLOs differ.

## The takeaway

GitOps promotion for agent workloads means promoting a verified bundle: image digest, model ID, prompts, tools, and index version together. Use Kustomize overlays per environment, Argo CD sync waves for migrations, eval gates on promotion PRs, and External Secrets for credentials. Green sync status means nothing if the overlay pins yesterday's model—treat LLM configuration as part of the release artifact, not ambient environment noise.

## Resources

- [Argo CD sync waves](https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/)
- [Kustomize overlays](https://kubectl.docs.kubernetes.io/references/kustomize/)
- [External Secrets Operator](https://external-secrets.io/latest/)
- [Flagger progressive delivery](https://flagger.app/)
- [OPA/Gatekeeper policy examples](https://open-policy-agent.github.io/gatekeeper/website/docs/)
