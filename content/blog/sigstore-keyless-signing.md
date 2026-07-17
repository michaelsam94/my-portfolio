---
title: "Keyless Signing with Sigstore"
slug: "sigstore-keyless-signing"
description: "How Sigstore keyless signing works: cosign, OIDC identity, ephemeral certificates, and the Rekor transparency log — signing artifacts without managing private keys."
datePublished: "2026-02-28"
dateModified: "2026-07-17"
tags:
  - "Engineering"
keywords: "Sigstore, cosign, keyless signing, OIDC signing, artifact signing, Rekor transparency log, provenance"
faq:
  - q: "Keyless signing?"
    a: "Fulcio issues cert from OIDC identity; Rekor logs signature for verification."
  - q: "cosign in CI?"
    a: "cosign sign with OIDC provider matching your CI platform."
  - q: "Verification?"
    a: "Policy controllers or admission webhooks verify signatures at deploy time."
---

The oldest problem in code signing isn't the cryptography — it's the key. Somebody has to generate a private signing key, store it somewhere safe, rotate it, keep it out of CI logs, and pray it never leaks. Sigstore's keyless signing throws that whole problem out. Instead of a durable private key, you sign with a short-lived certificate bound to an OIDC identity — your CI workflow, your Google account, a service identity — and the key material evaporates after a few minutes. There's no signing key to steal because none survives the operation.

I've cleaned up after a leaked signing key once, and it's exactly as bad as it sounds: you can't easily tell what was signed maliciously, and rotating trust downstream is a slog. Keyless signing makes that class of incident structurally impossible. Here's the machinery, the `cosign` workflow, and where the model's trust actually rests.

## The three moving parts

Keyless signing coordinates three Sigstore services, and understanding them demystifies the whole thing:

- **Fulcio** — a certificate authority that issues *ephemeral* X.509 certificates. You prove your identity via OIDC, Fulcio mints a certificate valid for roughly ten minutes that binds your public key to that identity, and that's it.
- **Rekor** — a public, append-only transparency log. Every signing event is recorded immutably, so anyone can later audit that artifact X was signed by identity Y at time Z.
- **OIDC identity provider** — the thing that vouches for who you are. In CI, this is the platform's workload identity (a GitHub Actions OIDC token, for instance); for a human, it's a Google/GitHub/Microsoft login.

The flow: you authenticate via OIDC, Fulcio issues a short-lived cert for your identity, you sign the artifact with the ephemeral key, the signature and certificate go into Rekor, and the private key is discarded. Verification later checks the signature, confirms the certificate chains to Fulcio, and asserts the recorded identity matches your policy.

## Signing an image with cosign

In CI, keyless signing is close to a one-liner. The `COSIGN_EXPERIMENTAL` flag is no longer needed in current cosign; keyless is the default when you don't pass a key.

```bash
# In a CI job with OIDC configured, sign an image by digest
cosign sign \
  --yes \
  registry.example.com/payments-api@sha256:abc123...
```

There's no `--key` flag. Cosign detects the ambient OIDC token, requests a certificate from Fulcio, signs, and uploads to Rekor. Always sign by **digest**, not tag — tags are mutable, so signing `:latest` signs whatever `latest` happens to point at right now, which is a signature that means nothing tomorrow.

## Verifying with an identity policy

Verification is where the security payoff lands, and it's stricter than people expect. You don't just check "is this signed?" — you assert *who* signed it and *from where*:

```bash
cosign verify \
  --certificate-identity="https://github.com/myorg/payments-api/.github/workflows/release.yml@refs/heads/main" \
  --certificate-oidc-issuer="https://token.actions.githubusercontent.com" \
  registry.example.com/payments-api@sha256:abc123...
```

Read that carefully: you're asserting the image was signed by a specific GitHub Actions workflow, on a specific branch, authenticated by GitHub's OIDC issuer. An attacker who compromises your registry can't forge that — they'd need to sign from that exact identity, which means compromising the CI identity itself. This identity-pinned verification is the whole game. A signature you don't verify against an expected identity is theater.

## Why a transparency log instead of a key

The conceptual leap that trips people up: if there's no persistent key, what stops someone from signing malware as you? The answer is Rekor plus the ephemeral certificate's short lifetime. Every signature is a public, timestamped, immutable record tied to an OIDC identity. If a signature exists for your identity that you didn't make, that's detectable — it's in a log you can audit. The accountability moves from "trust that a secret was never misused" to "everything is publicly recorded and verifiable."

| Traditional key signing | Sigstore keyless |
|---|---|
| Long-lived private key to protect | Ephemeral cert, ~10 min lifetime |
| Key leak = silent forgery risk | No key to leak; signings are logged |
| Rotation is painful | Nothing to rotate |
| Trust = "key wasn't stolen" | Trust = OIDC identity + public log |

This slots directly into a broader provenance strategy. Signing is one control among several in [supply chain security with SLSA and SBOMs](https://blog.michaelsam94.com/supply-chain-security-slsa-sbom/) — SLSA describes the build provenance, and Sigstore is how you attach a verifiable, identity-bound signature to that provenance and to the artifact itself.

## Signing attestations, not just images

Cosign can attach and sign *attestations* — structured claims about an artifact — using the in-toto format. The most useful pairing is signing your SBOM as an attestation, so consumers get a cryptographically verifiable bill of materials rather than a loose file that could've been swapped:

```bash
cosign attest \
  --yes \
  --predicate sbom.spdx.json \
  --type spdxjson \
  registry.example.com/payments-api@sha256:abc123...
```

Now the SBOM is bound to the image and signed by your CI identity. This is where keyless signing stops being "sign the binary" and becomes the trust backbone for your whole artifact story — the SBOM you generate as part of [container image security](https://blog.michaelsam94.com/container-image-security-sbom/) becomes tamper-evident and attributable, not just present.

## The caveats worth stating plainly

Keyless is excellent, but be honest about the dependencies. You're trusting the public Sigstore infrastructure (Fulcio, Rekor) unless you self-host — and self-hosting the whole stack is real operational work. Your security now hinges on the integrity of your **OIDC identity**: if an attacker can make CI sign on their behalf, keyless signing faithfully signs their malware with your identity. Protect the CI identity and the workflows that can trigger signing as carefully as you'd have protected the old private key.

There's also an availability consideration — signing and verification depend on those services being reachable, so bake in retries and think about your verification path in air-gapped environments (cosign supports offline verification with bundled Rekor proofs for exactly this).

My take after adopting it across pipelines: keyless signing is one of the rare security improvements that also *reduces* operational burden. No key vault, no rotation runbook, no "who has access to the signing key" audit. You trade a secret you have to guard for an identity you already manage and a public log anyone can audit — and that trade is almost always the right one.

## OIDC identity binding

Fulcio cert must match expected `issuer` + `subject` (GitHub repo ref). Consumers verifying signature without identity check accept any signed malware. Mirror Rekor queries if air-gapped verify; transparency log proves artifact existed at build time for compliance asks.

## OIDC identity binding

Fulcio cert must match expected `issuer` + `subject` (GitHub repo ref). Consumers verifying signature without identity check accept any signed malware. Mirror Rekor queries if air-gapped verify; transparency log proves artifact existed at build time for compliance asks.

## Notes on sigstore keyless signing

Verify signatures in admission controller before pods deploy; unsigned images fail closed. OIDC trust policy scoped to environment branch, not entire org. Maintain offline root of trust documentation for auditors explaining Fulcio and Rekor roles.

## Resources

- [Sigstore — official documentation](https://docs.sigstore.dev/)
- [cosign on GitHub](https://github.com/sigstore/cosign)
- [Fulcio — certificate authority](https://github.com/sigstore/fulcio)
- [Rekor — transparency log](https://github.com/sigstore/rekor)
- [in-toto attestation framework](https://in-toto.io/)
- [OpenID Connect specifications](https://openid.net/developers/specs/)
