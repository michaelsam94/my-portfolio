---
title: "Container Scanning with Trivy"
slug: "container-scanning-trivy-grype"
description: "Scan container images for CVEs in CI with Trivy and Grype: SBOM generation, severity gates, base image selection, and false positive triage."
datePublished: "2025-05-03"
dateModified: "2025-05-03"
tags: ["Security"]
keywords: "Trivy container scan, Grype vulnerability scanner, CVE scanning CI, SBOM, image security, distroless"
faq:
  - q: "What does Trivy scan in a container image?"
    a: "Trivy scans OS packages (apk, dpkg, rpm), language-specific dependencies (npm, pip, gem, jar) embedded in layers, misconfigurations in Dockerfiles and Kubernetes manifests, and secrets accidentally baked into images. It matches installed package versions against vulnerability databases (NVD, distro advisories) and reports CVE ID, severity, and fixed version when available."
  - q: "Should CI fail on all CVE findings?"
    a: "Fail on Critical and High with available fixes in production-bound images; warn on Medium. Unfixed upstream vulnerabilities need exception tracking with expiry dates—not silent ignore. Scan on every build and block deploy on regression. Base image updates often clear dozens of findings at once."
  - q: "Trivy vs Grype—which should I use?"
    a: "Both are excellent open-source scanners. Trivy adds misconfiguration scanning, license detection, and Aqua ecosystem integration. Grype (Anchore) pairs tightly with Syft SBOM generation and Grype's own DB. Many teams run one primary scanner in CI; using both is redundancy for high-assurance environments."
---

Container images ship with hundreds of packages you never installed consciously—they came from `node:20`, `python:3.12`, or `ubuntu:22.04`. Each package is a CVE surface. Trivy and Grype turn `docker push` into an audited artifact by diffing installed software against vulnerability databases faster than manual `apt list` grepping. The operational win is gating deploys on severity thresholds, not generating PDF reports nobody reads.

## Trivy in CI (GitHub Actions)

```yaml
- name: Build image
  run: docker build -t myapp:${{ github.sha }} .

- name: Scan with Trivy
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: myapp:${{ github.sha }}
    format: sarif
    output: trivy-results.sarif
    severity: CRITICAL,HIGH
    exit-code: 1
    ignore-unfixed: true

- name: Upload SARIF
  uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: trivy-results.sarif
```

`exit-code: 1` fails the build on findings. `ignore-unfixed: true` skips CVEs with no patched package yet—track those separately.

## Local scanning

```bash
trivy image myapp:latest
trivy image --severity HIGH,CRITICAL --ignore-unfixed myapp:latest
trivy fs --scanners vuln,misconfig .
```

Scan filesystem before building to catch Dockerfile issues early:

```bash
trivy config Dockerfile
```

## Severity gating policy

Define in `.trivyignore` or policy file with justification:

```
# Accept until 2025-06-01 — no fix in alpine 3.19, tracked JIRA-1234
CVE-2024-12345
```

Review quarterly—ignored CVEs expire.

CI policy example:

| Severity | Fixed available | Action |
|----------|-----------------|--------|
| Critical | Yes | Block merge |
| High | Yes | Block merge |
| High | No | Ticket + exception |
| Medium | Yes | Warn |
| Low | Any | Log only |

## SBOM generation

Supply chain compliance asks for SBOMs—Trivy and Syft generate SPDX/CycloneDX:

```bash
trivy image --format cyclonedx --output sbom.json myapp:latest
# or
syft myapp:latest -o cyclonedx-json > sbom.json
```

Attach SBOM to release artifacts; rescan SBOM when new CVEs publish without rebuilding (Grype supports SBOM-as-input).

## Grype equivalent

```bash
syft myapp:latest -o json | grype
grype myapp:latest --fail-on high
```

Anchore Enterprise adds policy-as-code; open-source Grype covers most CI needs.

## Reducing findings at the source

**Smaller base images.** `distroless/java17-debian12` vs full Debian cuts OS CVE count dramatically.

**Multi-stage builds.** Compile in builder; runtime stage copies only artifacts:

```dockerfile
FROM golang:1.22 AS build
WORKDIR /src
COPY . .
RUN CGO_ENABLED=0 go build -o /app

FROM gcr.io/distroless/static-debian12
COPY --from=build /app /app
ENTRYPOINT ["/app"]
```

**Pin digests, not tags.**

```dockerfile
FROM node:20.11.1-bookworm-slim@sha256:abc123...
```

**Regular rebuilds.** Same Dockerfile produces new patches when base digest updates—schedule weekly rebuilds even without code changes.

## False positives and noise

- **Language ecosystems in wrong context** — devDependencies scanned in production stage; exclude with `--skip-dirs` or separate build stages
- **Unfixed upstream** — track, don't panic
- **Rejected CVEs** — NVD disputes; verify against distro advisory (Debian security tracker often backports fixes with different versioning)

Triage workflow: security bot opens ticket → owner confirms fix version → bump base or package → rescan green.

## Kubernetes cluster scanning

```bash
trivy k8s --report summary cluster
```

Catches running images not scanned in CI (pulled from external registries) and manifest misconfigurations.

## Integrating scans into the deploy pipeline

Scanning at build time isn't enough — defense in depth:

```
Developer push → CI build → Trivy scan → merge gate
                                    ↓
                              deploy to staging → Trivy rescan → promote gate
                                    ↓
                              production deploy → admission controller scan
```

**Admission controller** (Kyverno, OPA Gatekeeper) blocks deployment of images with Critical CVEs:

```yaml
# Kyverno policy: block critical CVEs
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: block-critical-cves
spec:
  validationFailureAction: Enforce
  rules:
    - name: check-trivy-scan
      match:
        any:
          - resources:
              kinds: [Pod]
      verifyImages:
        - imageReferences: ["*"]
          attestors:
            - entries:
                - keys:
                    publicKeys: |-
                      -----BEGIN PUBLIC KEY-----
                      ...
```

Sign scan results with Cosign for verifiable attestation — see [Sigstore keyless signing](https://blog.michaelsam94.com/sigstore-keyless-signing/).

## Vulnerability exception management

Unfixed CVEs need tracked exceptions, not silent ignores:

```yaml
# .trivyignore with metadata
# CVE-2024-12345 — no fix in alpine 3.19, tracked in SEC-1234, expires 2025-09-01
CVE-2024-12345
```

Process:
1. Scanner finds CVE without fix → auto-create ticket
2. Security team assesses exploitability in your context (is the vulnerable library actually called?)
3. If accepted risk → add to `.trivyignore` with expiry date
4. Quarterly review — remove expired exceptions, re-scan

Never permanently ignore Critical CVEs — expire and re-evaluate.

## Container base image strategy

Most CVEs come from the base image, not your code:

| Base image | Approx OS packages | Typical CVE count |
|---|---|---|
| ubuntu:22.04 | ~200 | 50–100+ |
| node:20-bookworm | ~300 | 80–150 |
| node:20-alpine | ~20 | 5–15 |
| gcr.io/distroless/nodejs20 | ~15 | 2–5 |
| scratch (Go static) | 0 | 0 |

Migration path: Ubuntu → Alpine → distroless, measuring CVE reduction at each step. Distroless removes shell — harder to debug but dramatically smaller attack surface.

## Failure modes

- **Scanning but not gating** — findings logged but merges proceed; enforce exit-code in CI
- **Scanning devDependencies in production** — false positives from build tools in runtime image; use multi-stage builds
- **Stale base images** — same Dockerfile, months-old CVEs; schedule weekly rebuilds
- **Ignoring unfixed CVEs permanently** — `.trivyignore` grows forever; expire exceptions
- **No admission controller** — CI-scanned image replaced by unscanned `:latest` pull at deploy

## Production checklist

- Trivy/Grype scan on every CI build with exit-code gate
- Severity policy documented (block Critical/High with fix available)
- `.trivyignore` entries have expiry dates and ticket references
- Multi-stage builds exclude devDependencies from runtime image
- Base images pinned by digest, not tag
- Weekly scheduled rebuilds even without code changes
- SBOM generated and attached to release artifacts
- Admission controller blocks unscanned or non-compliant images in production

## Common production mistakes

Teams get scanning trivy grype wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of scanning trivy grype fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [Trivy documentation](https://aquasecurity.github.io/trivy/)
- [Grype vulnerability scanner](https://github.com/anchore/grype)
- [Syft SBOM generator](https://github.com/anchore/syft)
- [Distroless images](https://github.com/GoogleContainerTools/distroless)
