---
title: "RAG: Dependency Confusion Defense"
slug: "rag-dependency-confusion-defense"
description: "Defending against dependency confusion in ML and RAG pipelines — private package namespaces, lockfile integrity, registry proxies, and CI verification."
datePublished: "2025-10-30"
dateModified: "2026-07-17"
tags: ["AI", "Rag", "Dependency"]
keywords: "rag, dependency, confusion, ai, production, engineering, architecture"
faq:
  - q: "What is dependency confusion in the context of RAG services?"
    a: "An attacker publishes a public package with the same name as your internal private package—often with a higher semver version. Build tools that check public registries first may install the malicious package instead of your internal one, compromising embedding workers, document parsers, or evaluation harnesses at build or runtime."
  - q: "Which RAG pipeline components are highest risk?"
    a: "Custom Python ingestion workers, internal npm packages for chunking utilities, private Docker base images referenced without digest pinning, and CI jobs that pip install from requirements.txt without hash verification. Any step that resolves package names against both private and public registries is in scope."
  - q: "Does scoped npm package naming eliminate the risk?"
    a: "Scoped packages (@org/name) reduce accidental public squatting but do not eliminate it if CI is misconfigured to pull unscoped fallbacks or if attackers register similarly named scopes. Combine scope enforcement with registry proxy rules and explicit allowlists."
---
A document ingestion worker started exfiltrating chunk text to an unknown endpoint after a routine deploy. The diff showed no application code changes—only a patch version bump in `requirements.txt` resolved by CI. Investigation found that `acme-chunk-utils`, a private PyPI package used across RAG pipelines, had a namesake on the public index at version `99.0.0`. `pip` preferred the higher public version because the job's index URL order listed PyPI before the internal mirror. The malicious package wrapped the real chunker and forwarded decoded document content on every `split()` call.

**Dependency confusion** exploits the gap between how developers name internal packages and how package managers resolve versions across registries. RAG systems amplify impact: ingestion workers handle pre-redaction document content, embedding jobs hold API keys, and eval runners often execute in CI with broad secrets access.

## How confusion attacks work

Classic sequence (Alex Birsan, 2021):

1. Attacker enumerates internal package names from leaked manifests, public repos, or JS bundle source maps.
2. Attacker publishes those names to public registries with inflated version numbers.
3. Build or runtime resolver picks the public package because semver comparison favors `99.0.0` over your internal `1.4.2`.
4. Malicious code runs with the privileges of your pipeline or service.

Variants targeting RAG stacks:

- **Typosquat** on popular OSS (`langchian` vs `langchain`) in notebooks copied into production Dockerfiles.
- **Transitive confusion** when an internal meta-package depends on a squatted public name.
- **Container base image** tags that float to unexpected digests when registry namespaces collide across cloud accounts.

## Registry architecture that fails closed

Configure package managers so internal names never resolve from public registries:

### Python (pip)

Use an **explicit index strategy** with `--index-url` pointing only to your Artifactory/CodeArtifact/proxy, and `--extra-index-url` for PyPI only when needed—or better, mirror PyPI internally and use a single index.

```ini
# pip.conf on build agents
[global]
index-url = https://pypi.internal.example.com/simple
# No extra-index-url unless controlled mirror
```

Enable **`--require-hashes`** or pip-tools with locked hashes for production builds. CI rejects lockfiles missing hashes on direct dependencies.

Block package names matching internal namespace patterns from public install:

```yaml
# Artifactory virtual repo rule
deny_public_if_internal_name_matches:
  - "acme-*"
  - "corp-rag-*"
```

### npm

Publish internal packages under **`@yourorg/` scope**. Configure `.npmrc`:

```
@yourorg:registry=https://npm.internal.example.com/
registry=https://registry.npmjs.org/
```

CI fails if a dependency resolves outside expected registry per scope. Use **npm provenance** and **lockfile-only** installs (`npm ci`).

### Go modules

Use **`GOPRIVATE=*.internal.example.com,github.com/yourorg/*`** and a module proxy (Athens) that refuses to fetch private module paths from the public sum database incorrectly.

## CI verification gates

Automated checks catch misconfiguration before merge:

1. **Resolution audit**: dry-run install logs every package source registry. Flag any internal-named package fetched from public URL.
2. **Version ceiling test**: assert internal packages never resolve to versions not published on internal registry.
3. **Source map / manifest leak scan**: block commits exposing internal package names without corresponding public squatting monitoring.
4. **Dependabot with registry scope**: alerts when new dependencies introduce dual-registry resolution.

```bash
# Example: fail CI if acme-* came from pypi.org
pip install -r requirements.lock --report /tmp/report.json
jq -e '.install[] | select(.metadata.name | startswith("acme-")) | select(.download_info.url | contains("pypi.org")) | halt_error(1)' /tmp/report.json
```

## Runtime and supply chain hardening

Build-time defense is necessary; runtime limits blast radius:

- **Minimal base images** for ingestion workers; no compilers in production stage.
- **Read-only root filesystem** and dropped capabilities in Kubernetes.
- **Network egress allowlists**—a poisoned chunker cannot phone home if only embedding API endpoints are reachable.
- **Secret scoping**: embedding API keys in worker pods, not in CI images shared with untrusted fork PRs.

Sign internal packages and verify signatures in CI. Cosign for containers, npm sigstore for JS where supported.

## Monitoring for squatting

Proactive threat intel:

- Subscribe to alerts when new public packages match internal name list (GitHub Dependabot, Sonatype, custom RSS on PyPI search).
- Quarterly audit: export all unique dependency names from lockfiles across RAG repos; check public registry for exact matches.
- Run **dependency confusion canary packages**—harmless internal names you never use; alert if anything attempts to install them from public.

Document an incident runbook: isolate affected workers, rotate secrets touched by compromised build agents, rebuild images from known-good lock hashes, scan artifact registry for packages published during exposure window.

## Developer experience without unsafe shortcuts

Engineers reach for `pip install acme-chunk-utils` in notebooks when internal docs are thin. Reduce temptation:

- Template `pyproject.toml` with correct index configuration checked into every RAG repo.
- Internal package catalog with copy-paste install snippets including hash pins.
- Pre-commit hook rejecting `requirements.txt` without lock companion for deployable services.

Security policies fail when they add friction without alternatives. Make the secure path the easy path.

Dependency confusion is not exotic— it is misordered index URLs and unpinned resolution doing exactly what semver math dictates. RAG pipelines processing sensitive documents need registry proxies that deny public resolution of internal names, lockfiles with cryptographic integrity, and CI that proves every package came from where you think it did. The exfiltrating chunker incident ends when `acme-chunk-utils` cannot resolve from PyPI, period.

## Container and OCI registry confusion

Dependency confusion extends beyond npm and PyPI. Internal base images like `corp/rag-ingest-worker` on a private registry compete with public Docker Hub if CI resolves unqualified names. Pin images by **digest** in Kubernetes manifests; deny pulls from docker.io for namespaces matching internal patterns.

Helm charts referencing external subcharts should verify chart museum provenance— attackers publish chart names mirroring internal releases. Sign charts with Cosign and verify in Argo CD sync hooks.

## Developer onboarding and education

New hires copy Stack Overflow `pip install` lines into ingestion notebooks that bypass internal index config. Run **30-minute supply chain onboarding** covering pip.conf, `.npmrc`, and how to request new public dependency approval. Gamified phishing-style tests ("click to install faster embeddings package") measure whether lessons stuck.

Quarterly report to leadership: blocked confusion attempts, new dependencies approved, mean time to add allowlisted vendor. Security becomes visible wins, not invisible denials.

## SBOM and dependency review automation

Generate **Software Bill of Materials** on every RAG worker image build; compare against previous release for unexpected new package names. Syft/Grype pipeline flags packages never seen in org before—human approves or blocks deploy.

Dependabot PRs for OSS dependencies require two reviewers when package downloads exceed 1M weekly—popular typosquat targets. Internal package registry search before approving new public dep with similar name to internal library.

## Long-term culture and metrics

Track **mean time to approve** new public dependencies—if process takes two weeks, engineers bypass with creative package names. Streamline approval for well-known OSS with good SBOM while keeping strict path for packages matching internal namespace patterns.

Annual tabletop exercise: red team attempts dependency confusion against staging CI; blue team detects via SBOM diff and registry alerts. Results presented to engineering all-hands with anonymized near-miss stories reinforcing why pip.conf matters more than once-a-year security training slides.

Supply chain security is cumulative: dependency confusion defense works only alongside pinned lockfiles, signed commits, and least-privilege CI tokens. Treat internal package names as sensitive identifiers in threat models the same way you treat API keys—because in practice, they are keys to your build pipeline.

## Acceptance criteria for dependency confusion defense

Ship only when staging demonstrates the failure modes you claim to handle. Record the evidence — load test output, chaos result, or screenshot of the alert firing — in the PR. Revisit the settings after the first real incident; production will teach you which timeout or retention value was optimistic. Prefer boring, documented tradeoffs over clever defaults that only exist in one engineer's head.
