---
title: "Container Image Security and SBOMs"
slug: "container-image-security-sbom"
description: "How to secure container images: distroless base images, vulnerability scanning with Trivy, generating SBOMs, signing, and gating CI on real, fixable risk."
datePublished: "2026-07-01"
dateModified: "2026-07-01"
tags: ["Container Security", "Supply Chain", "SBOM", "DevSecOps"]
keywords: "container security, SBOM, image scanning, supply chain, distroless, Trivy, image signing"
faq:
  - q: "What is an SBOM and why do I need one?"
    a: "A Software Bill of Materials is a machine-readable inventory of every component in an image — packages, versions, licenses. You need it so that when a new CVE drops, you can answer 'are we affected?' in seconds by querying your SBOMs instead of rebuilding and rescanning everything under pressure."
  - q: "How do I reduce the number of vulnerabilities in my container images?"
    a: "Start with a minimal base image. Distroless or Alpine images ship far fewer packages than a full Debian or Ubuntu base, so there's simply less to be vulnerable. Most reported CVEs come from OS packages you never use; removing them removes the findings."
  - q: "What is the difference between scanning and signing an image?"
    a: "Scanning checks an image's contents against vulnerability databases to find known CVEs. Signing cryptographically proves who built the image and that it hasn't been tampered with since. You need both — scanning for 'is it safe?' and signing for 'is it really ours?'"
---

Most container images are mostly attack surface you never use. A typical app built on a full `ubuntu` base ships a shell, a package manager, dozens of system libraries, and a pile of utilities your service never calls — and every one of them is a line item a scanner can flag and an attacker can leverage. Container image security is, more than anything, an exercise in shipping less: fewer packages, fewer layers, fewer secrets baked in, and a paper trail proving what's actually inside.

I got religion about this after a scan on a "simple" Node service turned up over 200 findings, none of them in code I wrote. They were all in OS packages the base image dragged along. Switching the base image cut that to single digits in an afternoon. That's the shape of the whole discipline.

## Start with a minimal base image

The base image is the biggest single lever. A distroless image contains your runtime and its dependencies — and essentially nothing else. No shell, no package manager, no busybox. That removes both attack surface and, conveniently, most of the CVEs a scanner would otherwise report.

```dockerfile
# Multi-stage: build with a full image, ship on distroless
FROM golang:1.23 AS build
WORKDIR /src
COPY . .
RUN CGO_ENABLED=0 go build -o /app ./cmd/server

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=build /app /app
USER nonroot
ENTRYPOINT ["/app"]
```

Two things earn their keep here. Multi-stage builds keep your compiler, source, and build tools out of the final image entirely. And running as a non-root user (`nonroot` above) means a compromise inside the container doesn't start with root. The lack of a shell is a feature — an attacker who lands in a distroless container can't `curl | sh` their next stage because there's no curl and no sh.

If distroless is too austere for your runtime, `alpine` or the `-slim` variants are a solid middle ground. The point is the same: don't ship what you don't run.

## Scan, but scan the right thing

Scanning compares your image's contents against vulnerability databases. Trivy, Grype, and the scanners built into most registries all do this. Run it in CI so a vulnerable image never reaches production.

```bash
# Fail the build on fixable high/critical CVEs
trivy image --severity HIGH,CRITICAL \
  --ignore-unfixed \
  --exit-code 1 \
  registry.acme.io/payments-api:$GIT_SHA
```

`--ignore-unfixed` matters. A scanner that fails your build on a CRITICAL with no available patch just teaches the team to bypass the gate — there's nothing they can do about it today. Gate on **fixable** high and critical findings, and track the unfixable ones separately rather than blocking on them. This is exactly the "shift left, but stay signal-rich" balance that good [DevSecOps](https://blog.michaelsam94.com/devsecops-shift-left/) is about: gates that fire on things people can act on.

Scanning only base and OS packages misses application dependencies. Make sure your scanner also inspects your language-level dependencies (npm, Go modules, Gradle) — that's increasingly where the real supply-chain risk lives.

## Generate an SBOM for every image

An SBOM is a complete, machine-readable inventory of what's in the image. The value isn't at build time — it's the day a new CVE lands and someone asks "are we affected?" With SBOMs stored per image, you query your inventory and answer in seconds. Without them, you're rebuilding and rescanning everything while the clock runs.

```bash
# Generate a CycloneDX SBOM with Syft
syft registry.acme.io/payments-api:$GIT_SHA \
  -o cyclonedx-json > sbom.json
```

The two common formats are SPDX and CycloneDX; pick one and be consistent. Store the SBOM as an attestation attached to the image in your registry, not as a loose file that gets lost. This feeds directly into broader [supply chain security with SLSA and SBOMs](https://blog.michaelsam94.com/supply-chain-security-slsa-sbom/) — the SBOM is the raw material provenance is built on.

## Sign images so you know they're yours

Scanning tells you an image is *safe*. Signing tells you it's *yours*. Without signing, anyone who can push to your registry — or intercept a pull — can substitute a malicious image and your cluster will run it happily.

Cosign, part of the Sigstore project, signs images and stores signatures alongside them. Keyless signing ties the signature to an OIDC identity (your CI's workload identity), so there's no long-lived key to leak.

```bash
# Keyless sign in CI, verify at admission
cosign sign registry.acme.io/payments-api:$GIT_SHA
cosign verify registry.acme.io/payments-api:$GIT_SHA \
  --certificate-identity-regexp '.*acme.*' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
```

Then enforce it. A policy controller (Kyverno, or Sigstore's policy-controller) at the cluster's admission stage rejects any image that isn't signed by your CI. That closes the loop: only images your pipeline built and signed can run.

## Put it together in the pipeline

| Stage | Tool | Gate |
|---|---|---|
| Build minimal image | Docker/BuildKit, distroless | — |
| Scan for CVEs | Trivy / Grype | Fail on fixable HIGH/CRITICAL |
| Generate SBOM | Syft | Attach as attestation |
| Sign image | Cosign (keyless) | — |
| Admission control | Kyverno / policy-controller | Reject unsigned/unscanned |

The ordering matters: build lean so there's less to scan, scan so you don't ship known-vulnerable images, SBOM so you can answer future questions, sign so provenance is verifiable, and enforce at admission so the whole chain isn't optional.

## The habits that actually keep images clean

Tooling degrades without habits behind it. Rebuild images regularly even when your code hasn't changed — base images accumulate CVEs over time, and a service you deployed six months ago is running six months of unpatched packages. Pin base images by digest rather than a floating `:latest` tag so builds are reproducible, then bump the digest deliberately. Keep secrets out of images entirely; a secret in a layer is in the image forever, even if a later layer "removes" it. And expire old tags out of your registry so you're not sitting on a museum of vulnerable images.

## The short version

Ship less (distroless, multi-stage, non-root), scan for fixable CVEs and gate on those, generate and store an SBOM per image, sign with Cosign, and enforce signatures at admission. Rebuild on a cadence and pin by digest. None of these steps is hard on its own; the security comes from having all of them wired into the pipeline so none of it depends on someone remembering.

## Resources

- [Trivy — container vulnerability scanner](https://trivy.dev/)
- [Syft — SBOM generation](https://github.com/anchore/syft)
- [Sigstore Cosign — signing and verification](https://docs.sigstore.dev/cosign/signing/overview/)
- [Google distroless images](https://github.com/GoogleContainerTools/distroless)
- [CycloneDX — SBOM standard](https://cyclonedx.org/)
- [OWASP — Docker security cheat sheet](https://cheatsheetseries.owasp.org/cheatsheets/Docker_Security_Cheat_Sheet.html)
- [SLSA — supply chain levels](https://slsa.dev/)
