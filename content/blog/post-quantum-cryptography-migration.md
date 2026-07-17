---
title: "Post-Quantum Cryptography: Migrating Before It's Late"
seoTitle: "Post-Quantum Cryptography: Migrate Before It's Late"
slug: "post-quantum-cryptography-migration"
description: "Why post-quantum cryptography migration matters now: harvest-now-decrypt-later, the NIST PQC standards, ML-KEM, hybrid key exchange, and where to start."
datePublished: "2026-07-06"
dateModified: "2026-07-17"
tags: ["Cryptography", "Security", "Post-Quantum", "Infrastructure"]
keywords: "post-quantum cryptography, PQC, harvest now decrypt later, ML-KEM, quantum-safe, NIST PQC, hybrid key exchange"
faq:
  - q: "Why migrate to post-quantum cryptography before quantum computers exist?"
    a: "Because of 'harvest now, decrypt later.' Adversaries can record encrypted traffic today and decrypt it once a cryptographically relevant quantum computer arrives. Any data that must stay confidential for years — health records, state secrets, long-lived credentials — is already at risk, so key exchange needs to be quantum-safe now."
  - q: "What are the NIST post-quantum standards?"
    a: "NIST finalized its first PQC standards in 2024: FIPS 203 (ML-KEM, based on CRYSTALS-Kyber) for key encapsulation, FIPS 204 (ML-DSA, based on CRYSTALS-Dilithium) for digital signatures, and FIPS 205 (SLH-DSA, hash-based) for signatures. ML-KEM is the priority for protecting confidentiality."
  - q: "Do I need to replace all my cryptography at once?"
    a: "No. Prioritize key exchange and long-lived data confidentiality first, since those face harvest-now-decrypt-later. Signatures are less urgent because forging one requires a quantum computer that exists at the time of the attack, not retroactively. Most teams start with hybrid key exchange in TLS."
---

The threat model for post-quantum cryptography is unusual: the attack hasn't been invented yet, but the damage is already accruing. It's called **harvest now, decrypt later**. An adversary records your encrypted traffic today — TLS sessions, VPN tunnels, backups — and stores it. When a cryptographically relevant quantum computer eventually arrives, Shor's algorithm breaks the RSA and elliptic-curve key exchange that protected it, and everything they harvested becomes readable retroactively. So the question isn't "when will quantum computers arrive." It's "how long does your data need to stay secret," and if that answer is measured in years, you're already exposed.

That reframing is why serious teams are migrating now, well ahead of any working quantum machine. Post-quantum cryptography migration is about protecting today's confidentiality against tomorrow's decryption.

## What quantum actually breaks (and what it doesn't)

Be precise here, because the panic is often misdirected.

- **Public-key crypto is the casualty.** RSA, Diffie-Hellman, and ECC rely on problems (factoring, discrete log) that Shor's algorithm solves efficiently on a large quantum computer. This is the real exposure, and it hits **key exchange** hardest.
- **Symmetric crypto is largely fine.** Grover's algorithm halves the effective security of symmetric ciphers, which you fix by doubling key sizes. AES-256 stays comfortably secure; SHA-256 and SHA-3 are fine. You do not need to panic about your bulk encryption.

So the migration is overwhelmingly about the asymmetric parts: the key encapsulation that establishes session keys, and digital signatures. And key exchange comes first, because that's what harvest-now-decrypt-later attacks.

## The standards exist now

For years PQC was research. In 2024 NIST finalized the first standards, which turns this from "watch this space" into "there are algorithms you can deploy."

| Standard | Algorithm | Purpose | Priority |
|---|---|---|---|
| FIPS 203 | ML-KEM (Kyber) | Key encapsulation | High — do first |
| FIPS 204 | ML-DSA (Dilithium) | Digital signatures | Medium |
| FIPS 205 | SLH-DSA (SPHINCS+) | Hash-based signatures | Conservative fallback |

**ML-KEM** (Module-Lattice Key Encapsulation Mechanism, formerly CRYSTALS-Kyber) is the one to focus on first — it's what protects the confidentiality that harvest-now attacks target. Signatures (ML-DSA) are less time-critical, because forging a signature requires a quantum computer *at the moment of the attack*; there's no retroactive break. That asymmetry should drive your sequencing.

## Hybrid is the pragmatic answer

Nobody wants to bet everything on relatively young algorithms by ripping out battle-tested classical crypto. The consensus approach is **hybrid**: run a classical key exchange (like X25519) *and* a post-quantum one (ML-KEM) together, and combine both shared secrets. The session is secure unless *both* are broken — so you get quantum resistance without giving up the decades of scrutiny behind the classical primitive.

This is already shipping. Modern TLS stacks support hybrid key exchange groups, and major browsers and servers have rolled out `X25519MLKEM768` as a hybrid group. If you terminate TLS, enabling it can be as light as a config change on a recent stack:

```nginx
# OpenSSL 3.5+ / recent stacks: prefer the hybrid PQC group
ssl_ecdh_curve X25519MLKEM768:X25519:secp256r1;
ssl_protocols TLSv1.3;
```

```bash
# Confirm what your endpoint negotiated
openssl s_client -connect acme.com:443 -groups X25519MLKEM768 </dev/null \
  | grep -i "Negotiated\|group"
```

The beauty of hybrid key exchange for TLS is that it protects the confidentiality of *session establishment* immediately — before you've touched a single certificate or signature. That's the highest-leverage first move.

## Crypto-agility is the real deliverable

Here's the thing most PQC coverage undersells: the specific algorithm matters less than whether your systems can *change* algorithms without a rewrite. PQC standards will evolve; some may be weakened by future cryptanalysis. If swapping your key-exchange or signature algorithm means touching hardcoded assumptions scattered across the codebase, you'll be stuck.

Crypto-agility means:

- Algorithms are named and configurable, not hardcoded.
- You have an inventory of where cryptography is used — every TLS endpoint, every signed token, every stored encrypted blob, every embedded certificate.
- You can rotate primitives via configuration and deployment, not code archaeology.

That inventory is the unglamorous prerequisite. You cannot migrate what you can't find, and most organizations genuinely don't know everywhere they use public-key crypto — it's buried in libraries, TLS terminators, JWT signing, code signing, and IoT firmware. Building the inventory is often the longest part of the project. If you already invest in [designing for observability](https://blog.michaelsam94.com/designing-for-observability-slos/), extend that discipline to a cryptographic bill of materials.

## A sane migration sequence

1. **Inventory.** Map everywhere public-key crypto lives and, crucially, tag each by how long its data must stay confidential. Long-lived secrets are your first priority.
2. **Enable hybrid key exchange** on TLS for high-value, long-confidentiality traffic. This is often a config change and immediately blunts harvest-now-decrypt-later.
3. **Make your stack crypto-agile.** Remove hardcoded algorithm assumptions; centralize crypto behind configurable interfaces.
4. **Plan signature migration.** Less urgent, but PKI, code signing, and certificate chains need PQC signatures eventually. These migrations are slower because of ecosystem dependencies.
5. **Watch the constraints.** PQC keys and ciphertexts are larger than classical ones, which matters for bandwidth-sensitive and embedded contexts — a real concern for the [IoT-at-scale](https://blog.michaelsam94.com/mqtt-iot-at-scale/) and mobile systems I work on, where handshake size and battery cost aren't free. And it dovetails with a broader [zero-trust posture for mobile apps](https://blog.michaelsam94.com/zero-trust-mobile-apps/).

## Don't roll your own

The strongest advice: use vetted implementations — OpenSSL 3.5+, BoringSSL, the AWS/Cloudflare stacks, liboqs for experimentation — and let your TLS terminators and platform providers do the heavy lifting. PQC algorithms are new and subtle; hand-rolled lattice crypto is a great way to introduce a side-channel that undoes the point.

The honest timeline: you don't need everything done this quarter, but if you handle data that must stay secret for a decade, hybrid key exchange on your sensitive endpoints is a this-year task, not a someday task. The data you're protecting is being harvested on the classical timeline, whatever the quantum one turns out to be.

## Crypto inventory spreadsheet

List every system using TLS, VPN, code signing, email S/MIME, database TDE, and backup encryption. Columns: algorithm, key size, data classification, retention years, owner. Prioritize rows where retention times sensitivity exceeds migration lead time.

## Certificate authority roadmap

Public CAs adding ML-DSA chains slowly. Plan internal CA hybrid issuance for mTLS east-west first — smaller blast radius than public web PKI migration.

## HSM and key ceremony updates

PQC keys larger — HSM firmware and PKCS#11 libraries need upgrade paths. Test ML-KEM key generation in staging HSM before promising compliance date.

## Application-layer crypto beyond TLS

JWT signed RS256, encrypted backups with RSA-OAEP, SSH host keys — inventory often misses these. Pin dependency versions in SBOM review.

## Field notes on post quantum cryptography migration

Teams shipping this in production should baseline metrics before changing defaults, then validate under representative load — not empty staging databases. Document rollback paths alongside forward changes so on-call can revert without improvising. Review configuration quarterly even when dashboards look flat; schema drift and traffic growth change optimal settings silently until an incident exposes them. Pair automated checks with occasional game-day exercises that rehearse failure modes specific to this component rather than generic outage drills.

## Resources

- [NIST — Post-Quantum Cryptography project](https://csrc.nist.gov/projects/post-quantum-cryptography)
- [NIST FIPS 203 — ML-KEM](https://csrc.nist.gov/pubs/fips/203/final)
- [NIST FIPS 204 — ML-DSA](https://csrc.nist.gov/pubs/fips/204/final)
- [Cloudflare — post-quantum cryptography](https://blog.cloudflare.com/pq-2024/)
- [Open Quantum Safe — liboqs](https://openquantumsafe.org/)
- [NSA — Commercial National Security Algorithm Suite 2.0](https://www.nsa.gov/Cybersecurity/Post-Quantum-Cryptography/)
