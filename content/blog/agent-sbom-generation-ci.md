---
title: "AI Agents: SBOM Generation in CI for Agent Platforms"
slug: "agent-sbom-generation-ci"
description: "Generate CycloneDX SBOMs in CI for every agent build — Syft, Grype diff gates, model artifact provenance, and SLSA attestations tied to container digests."
datePublished: "2025-11-04"
dateModified: "2026-07-17"
tags:
  - "AI"
  - "Agent"
  - "Supply Chain"
  - "DevOps"
keywords: "SBOM CI, CycloneDX, Syft, Grype, supply chain security, agent Docker"
faq:
  - q: "When should teams prioritize SBOM Generation in CI for Agent Platforms?"
    a: "Before scaling agent services past a handful of Docker images or passing enterprise security questionnaires."
  - q: "What is the most common mistake with SBOM generation in CI?"
    a: "Generating SBOM only at release while daily main-branch builds drift from what production actually runs."
  - q: "How do we know SBOM Generation in CI for Agent Platforms is working?"
    a: "Define a leading metric for SBOM generation in CI (error rate, stale read rate, recall, verification failures) and a lagging metric (incidents, invoice variance, audit findings). Review both in weekly ops, not only after escalations."
---
The CVE Slack message landed without an SBOM attached to last week's deploy — answering exposure meant guessing from base image tags.

Agent platforms ship Python services, ONNX weights, CUDA base images, and private wheel indexes — a CVE question without a Software Bill of Materials means forensic grep through running pods. CI must emit CycloneDX JSON keyed to image digest before anyone asks "are we exposed?"

## What every agent build publishes

| Artifact | Format | Retention |
|----------|--------|-----------|
| SBOM | CycloneDX 1.5 JSON | Indefinite, keyed by digest |
| Vulnerability scan | Grype SARIF | 90 days |
| Provenance | SLSA in-toto | Indefinite |

Store artifacts in OCI registry as referrer attachments or S3 with tags `git_sha`, `build_id`, `environment`.

## Syft in GitHub Actions

```yaml
- uses: anchore/sbom-action@v0
  with:
    image: agent-api:${{ github.sha }}
    format: cyclonedx-json
    output-file: sbom.cdx.json
- uses: anchore/scan-action@v3
  with:
    sbom: sbom.cdx.json
    fail-build: false
    severity-cutoff: critical
```

## Diff-on-new-critical, not full-tree noise

Baseline main-branch SBOM; fail PRs only when **new** critical CVEs appear in the diff. Nightly full-tree scans track burn-down separately.

```python
added = current_components - baseline_components
critical_new = [c for c in added if grype_severity(c) >= "critical"]
if critical_new:
    sys.exit(1)
```

## AI-specific catalog gaps

Syft misses vendored `.safetensors` and Hugging Face cache paths unless you add file catalogers. Inject custom CycloneDX components for model manifests:

```json
{"name":"llama-3-8b-q4","purl":"pkg:huggingface/meta-llama/Llama-3-8B@sha256:abc123"}
```

Custom rules in `.gitleaks.toml` complement SBOM — keys in repo history still require rotation even when absent from container SBOM.

## Policy gates

| Policy | CI behavior |
|--------|-------------|
| New critical in diff | Block merge |
| Critical in unchanged base image | Warn + ticket |
| Unpinned dependency | Block merge |
| AGPL in proprietary product | Block merge |

## Signing and admission

```bash
cosign attach sbom --sbom sbom.cdx.json agent-api:$SHA
cosign sign agent-api:$SHA
```

Kyverno/Ratify rejects pods whose image lacks valid SBOM referrer. Measure **mean time to answer exposure** — target under five minutes.

## GUAC and Dependency-Track

Central SBOM warehouse enables blast-radius queries: "list services downstream of compromised pkg:pypi/requests@2.28.0." Re-scan stored SBOMs nightly against updated NVD — clean builds go critical when databases update without code changes.

## Incident runbook

1. Identify production digests from deploy log
2. Fetch SBOM per digest
3. Query CVE against component list
4. If affected, rebuild with patched base or bumped dependency
5. Regenerate SBOM, canary deploy, post status update

## Operational readiness

Run game days simulating NVD critical publish in transitive deps. Assign SBOM pipeline owner; quarterly review SBOM policy exceptions and allowlists.

Generating SBOM only at release while daily main-branch builds drift from what production actually runs. Attach SBOM generation to every merge main, store with digest, diff PRs on new criticals, and catalog model artifacts explicitly — supply-chain answers become queryable instead of tribal.

## Supply-chain review cadence

Security reviews agent Dockerfiles when base images or pip constraints change — SBOM diff attached to PR. Enterprise customers request quarterly SBOM export filtered to components shipping in their tenant isolation boundary.


## Supply-chain review cadence

Security reviews agent Dockerfiles when base images or pip constraints change — SBOM diff attached to PR. Enterprise customers request quarterly SBOM export filtered to components shipping in their tenant isolation boundary.


## Supply-chain review cadence

Security reviews agent Dockerfiles when base images or pip constraints change — SBOM diff attached to PR. Enterprise customers request quarterly SBOM export filtered to components shipping in their tenant isolation boundary.


## Supply-chain review cadence

Security reviews agent Dockerfiles when base images or pip constraints change — SBOM diff attached to PR. Enterprise customers request quarterly SBOM export filtered to components shipping in their tenant isolation boundary.


## Supply-chain review cadence

Security reviews agent Dockerfiles when base images or pip constraints change — SBOM diff attached to PR. Enterprise customers request quarterly SBOM export filtered to components shipping in their tenant isolation boundary.


## Supply-chain review cadence

Security reviews agent Dockerfiles when base images or pip constraints change — SBOM diff attached to PR. Enterprise customers request quarterly SBOM export filtered to components shipping in their tenant isolation boundary.


## Supply-chain review cadence

Security reviews agent Dockerfiles when base images or pip constraints change — SBOM diff attached to PR. Enterprise customers request quarterly SBOM export filtered to components shipping in their tenant isolation boundary.


## Supply-chain review cadence

Security reviews agent Dockerfiles when base images or pip constraints change — SBOM diff attached to PR. Enterprise customers request quarterly SBOM export filtered to components shipping in their tenant isolation boundary.


## Supply-chain review cadence

Security reviews agent Dockerfiles when base images or pip constraints change — SBOM diff attached to PR. Enterprise customers request quarterly SBOM export filtered to components shipping in their tenant isolation boundary.


## Supply-chain review cadence

Security reviews agent Dockerfiles when base images or pip constraints change — SBOM diff attached to PR. Enterprise customers request quarterly SBOM export filtered to components shipping in their tenant isolation boundary.


## Supply-chain review cadence

Security reviews agent Dockerfiles when base images or pip constraints change — SBOM diff attached to PR. Enterprise customers request quarterly SBOM export filtered to components shipping in their tenant isolation boundary.


## Supply-chain review cadence

Security reviews agent Dockerfiles when base images or pip constraints change — SBOM diff attached to PR. Enterprise customers request quarterly SBOM export filtered to components shipping in their tenant isolation boundary.


## Supply-chain review cadence

Security reviews agent Dockerfiles when base images or pip constraints change — SBOM diff attached to PR. Enterprise customers request quarterly SBOM export filtered to components shipping in their tenant isolation boundary.


## Supply-chain review cadence

Security reviews agent Dockerfiles when base images or pip constraints change — SBOM diff attached to PR. Enterprise customers request quarterly SBOM export filtered to components shipping in their tenant isolation boundary.


## Supply-chain review cadence

Security reviews agent Dockerfiles when base images or pip constraints change — SBOM diff attached to PR. Enterprise customers request quarterly SBOM export filtered to components shipping in their tenant isolation boundary.


## Supply-chain review cadence

Security reviews agent Dockerfiles when base images or pip constraints change — SBOM diff attached to PR. Enterprise customers request quarterly SBOM export filtered to components shipping in their tenant isolation boundary.


## Supply-chain review cadence

Security reviews agent Dockerfiles when base images or pip constraints change — SBOM diff attached to PR. Enterprise customers request quarterly SBOM export filtered to components shipping in their tenant isolation boundary.



## Agent platform rollout notes

Agent traffic spikes when customers enable new tools fleet-wide — load-test SBOM generation in CI after every magnitude change. Game-day duplicate webhook delivery, index swap rollback, and credential rotation without overlap window.

Cross-team review after launches touching billing, auth, or retrieval: platform, product, security, finance agree on leading metrics and rollback owners. Document lessons in the runbook header — future on-call should not rediscover the same failure mode.

Progressive rollout: internal tenants → canary → full promote. Keep previous config hot-swappable one release. Pin versions affecting SBOM generation in CI in the service catalog with named DRIs.


## Resources

- [CycloneDX specification](https://cyclonedx.org/specification/overview/)
- [Anchore Syft](https://github.com/anchore/syft)
- [Grype scanner](https://github.com/anchore/grype)
- [SLSA provenance](https://slsa.dev/spec/v1.0/provenance)
- [Dependency-Track](https://dependencytrack.org/)
