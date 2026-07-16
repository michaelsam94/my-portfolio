---
title: "Artifact Management and Promotion"
slug: "ci-cd-artifact-management"
description: "CI/CD artifacts — container images, binaries, and packages — need versioning, immutable storage, and environment promotion. Build once, promote through staging to production without rebuilding."
datePublished: "2025-02-02"
dateModified: "2025-02-02"
tags: ["DevOps", "CI/CD", "Infrastructure"]
keywords: "CI CD artifact management, container image promotion, immutable artifacts, artifact registry, build once deploy many, environment promotion pipeline"
faq:
  - q: "What does build once, deploy many mean?"
    a: "The same artifact built in CI is promoted through environments — dev, staging, production — without rebuilding. Rebuilding per environment introduces non-determinism: different dependency versions, timestamps, or compiler flags mean staging tested artifact X but production runs artifact Y. Build once, sign it, promote the exact bits."
  - q: "How should I version container images?"
    a: "Tag with git SHA for traceability (myapp:a1b2c3d) and semver or date for human reference (myapp:v2.4.1). Never use :latest in production deployments — it's mutable and untraceable. Immutable tags: once pushed, a SHA tag never changes content."
  - q: "What is artifact promotion vs rebuilding?"
    a: "Promotion copies or retags an existing artifact for the next environment — staging passes, prod deploys the same image digest. Rebuilding checks out the same commit but produces a new image with potentially different layers. Promotion guarantees what you tested is what you ship."
---

Staging passed. Production deploys. Incident within an hour. The diff? Staging ran a Docker build at 2 PM; production rebuilt at 6 PM after a dependency updated on npm. Same commit, different artifact. Build-once-deploy-many isn't a slogan — it's the discipline of treating CI artifacts as immutable, versioned, signed objects that flow through environments unchanged.

## Artifact types and storage

| Artifact | Registry | Immutable? |
|----------|----------|-----------|
| Container images | ECR, GCR, Harbor | Yes (by digest) |
| npm packages | npm, Artifactory | Version pinned |
| JARs/binaries | S3, Artifactory | Yes (by hash) |
| Helm charts | ChartMuseum, ECR | Version pinned |
| Terraform modules | S3, Terraform Cloud | Git tag |

Everything gets a unique identifier tied to the source commit.

## Build pipeline

```yaml
# GitHub Actions — build and push
jobs:
  build:
    runs-on: ubuntu-latest
    outputs:
      image_digest: ${{ steps.build.outputs.digest }}
    steps:
      - uses: actions/checkout@v4

      - name: Build and push
        id: build
        uses: docker/build-push-action@v5
        with:
          push: true
          tags: |
            ${{ env.REGISTRY }}/myapp:${{ github.sha }}
            ${{ env.REGISTRY }}/myapp:build-${{ github.run_number }}
          cache-from: type=registry,ref=${{ env.REGISTRY }}/myapp:buildcache
          cache-to: type=registry,ref=${{ env.REGISTRY }}/myapp:buildcache,mode=max

      - name: Sign image
        run: |
          cosign sign --yes ${{ env.REGISTRY }}/myapp@${{ steps.build.outputs.digest }}
```

Build on every merge to main. Store digest, not just tag.

## Promotion flow

```
main branch → CI build → artifact registry (staging tag)
                              ↓ (automated after tests)
                         deploy to staging
                              ↓ (manual approval or automated gates)
                         retag/promote → production tag
                              ↓
                         deploy to production (same digest)
```

Promotion script:

```bash
#!/bin/bash
# promote.sh — promote staging image to production
DIGEST=$(crane digest "${REGISTRY}/myapp:staging-${VERSION}")
crane tag "${REGISTRY}/myapp@${DIGEST}" "prod-${VERSION}"
crane tag "${REGISTRY}/myapp@${DIGEST}" "prod-latest-${DATE}"

echo "Promoted ${DIGEST} to production"
```

`crane tag` adds a new tag pointing to the same digest — no rebuild.

## Environment-specific config

Artifacts are immutable; config is not. Separate config from code:

```yaml
# Kubernetes — same image, different config
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
        - name: app
          image: registry/myapp@sha256:abc123...  # digest, not tag
          envFrom:
            - configMapRef:
                name: app-config-prod  # environment-specific
```

ConfigMaps, secrets, and feature flags vary per environment. The binary doesn't.

## Artifact retention and cleanup

```yaml
# ECR lifecycle policy
{
  "rules": [
    {
      "rulePriority": 1,
      "description": "Keep last 30 production images",
      "selection": {
        "tagStatus": "tagged",
        "tagPrefixList": ["prod-"],
        "countType": "imageCountMoreThan",
        "countNumber": 30
      },
      "action": { "type": "expire" }
    },
    {
      "rulePriority": 2,
      "description": "Expire untagged after 7 days",
      "selection": {
        "tagStatus": "untagged",
        "countType": "sinceImagePushed",
        "countUnit": "days",
        "countNumber": 7
      },
      "action": { "type": "expire" }
    }
  ]
}
```

Keep enough history to roll back; don't store every CI build forever.

## SBOM and provenance

Attach Software Bill of Materials to every artifact:

```bash
syft registry/myapp:${SHA} -o spdx-json > sbom.spdx.json
cosign attach sbom --sbom sbom.spdx.json registry/myapp:${SHA}
```

Provenance attestation links artifact to source commit, builder, and pipeline run — supply chain security requirement for many enterprises now.

## Rollback

Because artifacts are immutable and retained:

```bash
# Rollback = deploy previous digest
kubectl set image deployment/myapp \
  app=registry/myapp@sha256:previous_digest
```

No emergency rebuild. The previous artifact is in the registry waiting.

## Anti-patterns

| Anti-pattern | Problem |
|-------------|---------|
| `:latest` in prod | Untraceable, mutable |
| Rebuild per environment | Non-deterministic |
| No digest pinning | Tag overwrite possible |
| Artifacts without SBOM | Supply chain blind spot |
| Promoting by branch merge | Tests != same artifact |

## Build once, deploy everywhere

The core principle: one build artifact promoted through environments:

```
CI build → artifact@sha256:abc123
  → deploy to staging (same digest)
  → integration tests pass
  → deploy to production (same digest)
```

```yaml
# GitHub Actions: build once
jobs:
  build:
    outputs:
      digest: ${{ steps.build.outputs.digest }}
    steps:
      - id: build
        run: |
          docker build -t app:${{ github.sha }} .
          docker push app:${{ github.sha }}
          echo "digest=$(docker inspect --format='{{index .RepoDigests 0}}' app:${{ github.sha }})" >> $GITHUB_OUTPUT

  deploy-staging:
    needs: build
    steps:
      - run: kubectl set image deployment/app app=${{ needs.build.outputs.digest }}

  deploy-production:
    needs: [build, deploy-staging]
    if: github.ref == 'refs/heads/main'
    steps:
      - run: kubectl set image deployment/app app=${{ needs.build.outputs.digest }}
```

Never rebuild for production — the staging artifact IS the production artifact.

## Artifact retention and cleanup

Registry storage grows unbounded without policy:

```yaml
# Harbor retention policy
- repo: "myapp/*"
  tag_selectors:
    - tags: ["latest", "main-*"]
      untagged: false
  retain_count: 20  # keep last 20 tagged versions
  untagged_retention_days: 7
```

Keep: last 20 tagged versions, all production digests (pinned in deployment manifests), SBOM attachments. Delete: untagged after 7 days, PR build artifacts after merge.

## Supply chain attestation

Attach SBOM and provenance to every artifact:

```bash
# Generate SBOM with Syft
syft app:${{ github.sha }} -o spdx-json > sbom.spdx.json

# Sign with cosign
cosign sign --key cosign.key app@${{ digest }}
cosign attach sbom --sbom sbom.spdx.json app@${{ digest }}
```

SLSA Level 2+ requires provenance attestation — document who built what, from which source, with which dependencies.

## Failure modes

- **`:latest` tag in production** — untraceable deployments; pin by digest
- **Rebuild per environment** — staging tests don't validate production artifact
- **No retention policy** — registry storage costs grow unbounded
- **Artifacts without SBOM** — supply chain vulnerabilities undetected
- **Tag overwrite** — same tag points to different content; use immutable digests

## Production checklist

- All production deployments pin image by digest (not tag)
- Build once, promote same artifact through environments
- Registry retention policy configured (20 tagged versions minimum)
- SBOM generated and attached to every release artifact
- cosign signature on production artifacts
- Rollback tested: deploy previous digest without rebuild

Sign artifacts at build time and verify signatures at deploy — promoted artifacts without provenance chain fail supply-chain audits.

## Resources

- [OCI image spec — digests](https://github.com/opencontainers/image-spec)
- [Sigstore cosign documentation](https://docs.sigstore.dev/cosign/)
- [Google Cloud — build once deploy many](https://cloud.google.com/architecture/devops/devops-tech-deployment-automation)
- [crane CLI for registry operations](https://github.com/google/go-containerregistry/tree/main/cmd/crane)
- [SLSA supply chain levels](https://slsa.dev/)
