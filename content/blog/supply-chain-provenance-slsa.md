---
title: "Build Provenance with SLSA"
slug: "supply-chain-provenance-slsa"
description: "SLSA provides a framework for securing software build pipelines with provenance attestations, hermetic builds, and tamper-resistant release artifacts. Learn levels, implementation, and GitHub Actions integration."
datePublished: "2025-10-01"
dateModified: "2025-10-01"
tags: ["Security", "Supply Chain", "SLSA", "DevOps"]
keywords: "SLSA provenance, supply chain levels, build attestation, Sigstore cosign, SLSA GitHub Actions, hermetic builds, software supply chain security"
faq:
  - q: "What SLSA level should my project target?"
    a: "Most teams should target SLSA Build Level 2 as a practical first milestone — hosted build platform with provenance generation. Level 3 adds non-falsifiable provenance and hermetic builds, requiring more infrastructure investment. Level 4 (two-person review, reproducible builds) is appropriate for critical infrastructure like crypto libraries or OS packages. Start at Level 1 (documented build process) and increment."
  - q: "How does SLSA provenance differ from an SBOM?"
    a: "An SBOM lists what went into your artifact — dependencies, versions, licenses. SLSA provenance describes how the artifact was built — which source commit, which builder, which workflow, what inputs. SBOM answers 'what's inside?' Provenance answers 'who built this and from what?' Both are complementary; SLSA provenance often references the SBOM as a build material."
  - q: "Can I verify SLSA provenance in my deployment pipeline?"
    a: "Yes — tools like slsa-verifier check that an artifact's provenance attestation matches your policy (expected builder, source repository, branch). Container registries (GitHub Container Registry, Google Artifact Registry) store attestations alongside images. Your deploy pipeline rejects artifacts without valid provenance or with provenance from unexpected sources."
---

After the SolarWinds and Codecov incidents, our security team stopped asking "did we scan for CVEs?" and started asking "can we prove this binary was built from our source code by our CI system?" Vulnerability scanning catches known bad dependencies. Provenance catches the case where someone else's build pipeline — or an attacker who compromised it — produced the artifact you're about to deploy.

SLSA (Supply-chain Levels for Software Artifacts, pronounced "salsa") is a framework from Google and the OpenSSF that defines progressive levels of build pipeline security. At its core is provenance: a signed attestation that links an artifact to its exact source, builder, and build parameters.

## SLSA levels at a glance

| Level | Requirements | What it prevents |
|-------|-------------|-----------------|
| 1 | Documented build process | Undocumented tampering |
| 2 | Hosted build + provenance | Ad-hoc local builds sneaking in |
| 3 | Non-falsifiable provenance, hermetic builds | Builder compromise going undetected |
| 4 | Two-person review, reproducible builds | Single-actor insider threats |

Level 2 is the sweet spot for most engineering teams. You generate provenance automatically in CI, store it with the artifact, and verify it at deployment time.

## What provenance contains

A SLSA provenance attestation is a JSON document signed by the build platform:

```json
{
  "_type": "https://in-toto.io/Statement/v1",
  "subject": [{ "name": "my-app:v1.2.3", "digest": { "sha256": "abc..." } }],
  "predicateType": "https://slsa.dev/provenance/v1",
  "predicate": {
    "buildDefinition": {
      "buildType": "https://github.com/actions/runner",
      "externalParameters": {
        "repository": "https://github.com/org/my-app",
        "ref": "refs/heads/main",
        "workflow": { "path": ".github/workflows/release.yml" }
      }
    },
    "runDetails": {
      "builder": { "id": "https://github.com/actions/runner/v2" },
      "metadata": {
        "invocationId": "https://github.com/org/my-app/actions/runs/12345"
      }
    }
  }
}
```

This says: artifact `my-app:v1.2.3` with SHA256 `abc...` was built by GitHub Actions runner from commit on `main` using the release workflow. An attacker can't produce this attestation without access to your CI system.

## Generating provenance with GitHub Actions

GitHub Actions has built-in SLSA provenance generation for workflows using `slsa-framework/slsa-github-generator`:

```yaml
name: Release
on:
  push:
    tags: ["v*"]

jobs:
  build:
    permissions:
      contents: read
      packages: write
      id-token: write  # Required for OIDC signing
    uses: slsa-framework/slsa-github-generator/.github/workflows/generator_container_slsa3.yml@v2.0.0
    with:
      image: ghcr.io/org/my-app
      digest: ${{ needs.build.outputs.digest }}
```

The generator produces provenance signed via Sigstore's keyless signing (OIDC-based, no long-lived keys to manage). Attestations are stored in the GitHub Container Registry alongside the image or uploaded to a transparency log.

For generic artifacts (JARs, binaries, npm packages):

```yaml
- uses: slsa-framework/slsa-github-generator/.github/workflows/generator_generic_slsa3.yml@v2.0.0
  with:
    base64-subjects: "${{ needs.build.outputs.hashes }}"
    upload-assets: true
```

## Verifying provenance at deploy time

Use `slsa-verifier` to check artifacts before deployment:

```bash
slsa-verifier verify-image \
  ghcr.io/org/my-app@v1.2.3 \
  --source-uri github.com/org/my-app \
  --source-tag v1.2.3
```

In a Kubernetes admission controller or deploy pipeline:

```bash
# Fail deploy if provenance doesn't match policy
slsa-verifier verify-artifact my-app.jar \
  --provenance-path provenance.intoto.jsonl \
  --source-uri github.com/org/my-app \
  --builder-id "https://github.com/actions/runner/v2"
```

Policy-as-code tools (Kyverno, OPA) can enforce that only images with valid SLSA provenance from approved builders enter production clusters.

## Hermetic builds (Level 3)

A hermetic build only uses declared inputs — no network access during compilation, no reading undeclared files. This ensures the provenance fully describes how the artifact was produced.

Practical steps toward hermetic builds:

- Pin all dependencies with lockfiles (see dependency pinning).
- Use `--network=none` in Docker build stages for compilation.
- Cache dependencies in a controlled artifact repository, not fetched live during build.
- Record all build inputs (source hash, dependency hashes, Dockerfile hash) in provenance.

Full hermeticity is hard for ecosystems that fetch dependencies at build time (npm install during Docker build). Mitigate by multi-stage builds that copy pre-resolved `node_modules` from a locked-deps stage.

## Signing artifacts with Sigstore

SLSA provenance uses Sigstore for signing and verification:

- **Cosign** signs container images and blobs.
- **Keyless signing** uses OIDC identity (GitHub Actions, GitLab CI) — no key management.
- **Rekor** transparency log provides public audit trail of all signatures.

```bash
cosign sign ghcr.io/org/my-app@v1.2.3
cosign verify ghcr.io/org/my-app@v1.2.3 \
  --certificate-identity-regexp="https://github.com/org/my-app" \
  --certificate-oidc-issuer="https://token.actions.githubusercontent.com"
```

## Getting started this week

1. Add SLSA provenance generation to your release workflow (Level 2).
2. Commit lockfiles and use frozen installs (foundation for Level 3).
3. Add `slsa-verifier` to your deploy pipeline to reject unprovenanced artifacts.
4. Enable Dependabot/Renovate for controlled dependency updates.
5. Document your build process in a `BUILD.md` (Level 1, if nothing else).

## Common production mistakes

Teams get supply chain provenance slsa wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of supply chain provenance slsa fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When supply chain provenance slsa misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [SLSA specification](https://slsa.dev/spec/v1.0/)
- [SLSA GitHub Generator](https://github.com/slsa-framework/slsa-github-generator)
- [slsa-verifier tool](https://github.com/slsa-framework/slsa-verifier)
- [Sigstore Cosign documentation](https://docs.sigstore.dev/cosign/overview/)
- [OpenSSF Supply Chain Security guide](https://best.openssf.org/)
