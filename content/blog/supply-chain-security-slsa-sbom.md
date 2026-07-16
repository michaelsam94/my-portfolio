---
title: "Software Supply Chain Security with SLSA and SBOMs"
seoTitle: "Supply Chain Security: SLSA and SBOMs in Practice"
slug: "supply-chain-security-slsa-sbom"
description: "A practical guide to software supply chain security using SLSA provenance and SBOMs — how to generate them, sign artifacts with Sigstore, and verify at deploy."
datePublished: "2026-07-09"
dateModified: "2026-07-09"
tags: ["Security", "Supply Chain", "DevSecOps", "CI/CD"]
keywords: "supply chain security, SLSA, SBOM, dependency security, provenance, sigstore, artifact signing"
faq:
  - q: "What is the difference between SLSA and an SBOM?"
    a: "An SBOM is an inventory — it lists what components and dependencies are inside an artifact. SLSA is a set of provenance and integrity guarantees about how that artifact was built. You need both: the SBOM tells you what's inside, SLSA tells you the build wasn't tampered with."
  - q: "What SLSA level should I target first?"
    a: "Aim for SLSA Build Level 2 or 3, which require a hosted build service that generates signed, non-falsifiable provenance. Level 1 (provenance exists) is easy but weak; Level 3 (hardened, isolated builds) is the meaningful bar for most production teams."
  - q: "How do I verify a build's provenance at deploy time?"
    a: "Use a policy engine like Sigstore's cosign with a verification policy, or Kyverno/OPA in Kubernetes, to check that the artifact's signature and SLSA provenance match your expected builder identity and source repo before the image is allowed to run."
---

The fastest way to compromise a thousand companies is to compromise one dependency they all trust. That's why software supply chain security stopped being a niche concern after SolarWinds, Codecov, and the xz backdoor — the attacks target the build, not the running app. Two artifacts do most of the heavy lifting in a defensible supply chain: an **SBOM** (Software Bill of Materials) that inventories what's inside your build, and **SLSA** (Supply-chain Levels for Software Artifacts) provenance that proves how the build happened and that nobody tampered with it.

I've wired this into CI for mobile and backend projects, and the useful framing is: the SBOM answers "what am I shipping?" and SLSA answers "can I trust how it got built?" You want both, generated automatically, and — this is the part teams skip — actually *verified* before an artifact deploys. An SBOM that sits in a build log nobody reads is theater.

## Start with the SBOM

An SBOM is a machine-readable list of every component in an artifact: direct and transitive dependencies, versions, licenses, and hashes. The two formats worth knowing are **SPDX** (an ISO standard) and **CycloneDX** (OWASP, popular in security tooling). Pick one and be consistent; most scanners read both.

Generating one is a single step with `syft`:

```bash
# Generate a CycloneDX SBOM from a container image
syft registry.example.com/api:1.4.2 -o cyclonedx-json > sbom.json

# Or from a project directory
syft dir:. -o spdx-json > sbom.spdx.json
```

The SBOM only earns its keep when you scan it against vulnerability data. `grype` consumes the SBOM directly, so you scan once and reuse:

```bash
grype sbom:sbom.json --fail-on high
```

The failure mode I see most: teams generate SBOMs but never diff them. The value compounds when you store each build's SBOM and can answer "which of our 40 services ship log4j-core, and what version?" in seconds when the next zero-day drops. That question took days during Log4Shell for teams without SBOMs; minutes for teams with them.

## SLSA: provenance you can't forge

An SBOM tells you what's inside, but it says nothing about whether the build was honest. SLSA fills that gap with **provenance** — signed metadata describing the builder, the source commit, the build parameters, and the resulting artifact digest.

The [SLSA framework](https://slsa.dev/) defines build levels:

| Level | Guarantee | Roughly means |
| --- | --- | --- |
| **L1** | Provenance exists | You document the build process |
| **L2** | Signed provenance from a hosted builder | Attestation is authenticated |
| **L3** | Hardened, isolated builds | Provenance is non-falsifiable, build is tamper-resistant |

The jump that matters is L2 to L3: the build has to run in an isolated environment where a compromised build step can't forge its own provenance. GitHub Actions with the official SLSA generator reaches L3 without you standing up infrastructure, which is why it's the pragmatic starting point.

## Signing with Sigstore

Provenance is only useful if it's signed and the signature is verifiable. [Sigstore](https://www.sigstore.dev/) made this dramatically easier by removing long-lived signing keys — you sign with a short-lived certificate tied to an OIDC identity (your CI's workload identity), and the signature is logged in a public transparency log (Rekor).

In practice, `cosign` signs the image and attaches the SBOM as an attestation:

```bash
# Sign the image keylessly using the CI's OIDC identity
cosign sign registry.example.com/api:1.4.2

# Attach the SBOM as a signed attestation
cosign attest --predicate sbom.json \
  --type cyclonedx registry.example.com/api:1.4.2
```

No key material to leak, rotate, or store in a secret manager. The identity is the pipeline itself, which is exactly the property you want.

## Verify at the door, not in the logs

Here's where most implementations fall down. Generating provenance is worthless if nothing checks it. Verification has to be a gate — a deploy fails closed if the artifact isn't signed by the expected builder from the expected repo.

```bash
cosign verify \
  --certificate-identity-regexp "https://github.com/myorg/.*" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com" \
  registry.example.com/api:1.4.2
```

In Kubernetes, encode this as an admission policy so unsigned or unverifiable images can't be scheduled at all. This is the same shift-left-then-enforce discipline I cover in [DevSecOps: shifting security left](https://blog.michaelsam94.com/devsecops-shift-left/) — a control that isn't enforced is a suggestion. Pair it with SBOM-based scanning in the pipeline so both "what's inside" and "how it was built" are gated before anything reaches production.

## A realistic rollout

You don't do all of this on day one. The order that works:

1. **Generate SBOMs** for every build and store them as artifacts. Zero enforcement — just visibility. This alone pays off during the next CVE scramble.
2. **Scan SBOMs** in CI and fail on high/critical with an allowlist for accepted risks, so the gate doesn't become noise everyone ignores.
3. **Emit SLSA provenance** using a hosted builder, targeting L3.
4. **Sign artifacts and attestations** with keyless Sigstore.
5. **Verify at deploy** with an admission policy that fails closed.

Steps 1–2 are an afternoon. Steps 3–5 are a sprint. The reason to bother is concrete: when the next dependency is backdoored — and there will be a next one — you want to answer "are we affected, and can we prove our builds weren't touched?" without a war room. This complements broader hardening work like [container image security and SBOM scanning](https://blog.michaelsam94.com/container-image-security-sbom/) and locking down [secrets management](https://blog.michaelsam94.com/secrets-management/), since a leaked signing credential or unscanned base image undoes the whole chain.

Supply chain security isn't one tool. It's making "what did we ship and how was it built" a queryable, enforced fact rather than an act of faith.

## Resources

- [SLSA — Supply-chain Levels for Software Artifacts](https://slsa.dev/)
- [Sigstore — keyless signing and transparency](https://www.sigstore.dev/)
- [OWASP CycloneDX SBOM standard](https://cyclonedx.org/)
- [SPDX (ISO/IEC 5962) SBOM standard](https://spdx.dev/)
- [CISA — Software Bill of Materials guidance](https://www.cisa.gov/sbom)
- [NIST Secure Software Development Framework (SSDF)](https://csrc.nist.gov/projects/ssdf)
- [Syft and Grype (Anchore)](https://github.com/anchore/syft)
