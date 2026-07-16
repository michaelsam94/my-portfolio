---
title: "Designing End-to-End Encryption"
slug: "end-to-end-encryption-design"
description: "Design E2EE systems that survive key loss, device changes, and group chat: Double Ratchet basics, key verification, metadata trade-offs, and UX realities."
datePublished: "2025-12-25"
dateModified: "2025-12-25"
tags: ["Security", "Encryption", "E2EE", "Cryptography"]
keywords: "end-to-end encryption design, Signal protocol, Double Ratchet, key verification, E2EE group messaging, forward secrecy, device keys, metadata privacy"
faq:
  - q: "What is the difference between E2EE and TLS?"
    a: "TLS encrypts data between client and server — the service operator can read plaintext at the server. E2EE encrypts so only intended recipients hold decryption keys; the server stores or relays ciphertext it cannot decrypt. E2EE protects against server compromise and honest-but-curious operators; TLS protects against network attackers."
  - q: "How do users recover messages on a new device with E2EE?"
    a: "True E2EE recovery requires key escrow choices: user-held recovery keys (24-word phrase), encrypted backup to cloud with password-derived keys, or accepting message loss on device loss. There is no magic — if only the old device had keys and no backup exists, ciphertext is permanently unreadable."
  - q: "Can group chats be end-to-end encrypted efficiently?"
    a: "Yes — modern designs use sender keys or MLS (Messaging Layer Security) for scalable group key distribution. Trade-offs include membership change complexity, forward secrecy after member removal, and server-assisted key fanout without learning plaintext."
---

The product manager asked for "WhatsApp-level encryption" by Q3 without changing the server-side moderation workflow that scans message text for abuse reports. That contradiction defines most E2EE projects: either the server can read content, or it cannot. Designing end-to-end encryption means committing to key management on clients, accepting metadata visibility on the relay server, and building UX for key verification that normal humans will actually perform — not just drawing a lock icon in Figma.

## Threat model first

Document who you protect against:

| Adversary | E2EE helps? |
|-----------|-------------|
| Network eavesdropper | Yes (with TLS too) |
| Compromised server DB | Yes — ciphertext useless without keys |
| Compromised client device | No — keys and plaintext local |
| Malicious insider with server access | Yes for content; metadata often visible |
| Legal compelled decryption | Depends — server cannot produce what it lacks |

E2EE is not anonymity — server still sees who talks to whom, when, and message sizes unless you add metadata minimization (hard).

## Identity keys and verification

Each device generates long-term identity key pair (Curve25519):

```text
User Alice
  ├── Device 1: IK_A1 (public advertised via server directory)
  └── Device 2: IK_A2

Out-of-band verify: compare safety numbers / QR scan
```

Users must verify they received the correct public keys — otherwise active MITM replaces keys in directory:

```kotlin
// conceptual: display fingerprint of remote identity key
val fingerprint = identityKey.publicKey.fingerprint() // SHA-256 truncated, grouped
// UI: "Verify with contact in person — numbers should match"
```

Without verification UX, E2EE protects against passive attackers only.

## Session setup: X3DH and Double Ratchet

Signal-style protocols:

1. **X3DH** — establish shared secret from identity + ephemeral keys (async first message)
2. **Double Ratchet** — per-message forward secrecy via chain keys and DH ratchet steps

Simplified ratchet intuition:

```
Root key ──► Chain key ──► Message key ──► encrypt plaintext
                │
         each message advances chain; old message keys deleted
```

Compromise of today's keys does not decrypt yesterday's messages (forward secrecy). Compromise of old keys does not decrypt future messages after DH ratchet step (break-in recovery within limits).

Use vetted libraries — libsignal-client, libolm — do not implement ratchets from RFC prose alone.

## Group messaging

Pairwise sessions do not scale to 500-member groups. **Sender Keys** — each member has group distribution key; sender encrypts once with their sender key, members decrypt. Membership changes require key rotation and re-distribution.

**MLS (RFC 9420)** standardizes group E2EE for enterprise — tree-based key updates with formal security proofs. Heavier implementation cost, better for regulated group products.

On member removal, rotate sender keys so removed member cannot read future messages — define this in protocol spec before launch.

## Server role in E2EE

Server stores:

- Public key directory (identity keys, one-time prekeys)
- Encrypted message blobs + routing metadata
- Optional sealed-sender wrappers hiding sender from other users' metadata (advanced)

Server never has message keys. Push notifications leak metadata ("you have a message") — minimize notification payload content.

## Backup and multi-device

Hard problems users feel immediately:

- **New phone** — restore from encrypted backup (user passphrase → key encryption key) or scan QR transfer from old device
- **Lost device** — messages gone unless backup existed
- **Legal hold** — enterprise E2EE may implement transparent key escrow for compliance (not consumer Signal model)

Document trade-offs in privacy policy and in-app copy — "We cannot recover your chats" is a feature and a support cost.

## Testing E2EE systems

- Property tests on ratchet state machines
- Cross-platform vector tests (same session vectors decrypt identically)
- Simulated MITM in QA — unverified key change must surface loud UI
- Fuzz ciphertext parsing — no crashes, no oracle leaks

## Signal Protocol key exchange (X3DH)

Initial session setup uses Extended Triple Diffie-Hellman:

```
Alice (sender)                          Bob (receiver)
─────────────────────────────────────────────────────
1. Fetch Bob's prekey bundle from server
   (identity key + signed prekey + one-time prekey)
2. DH1 = DH(IK_A, SPK_B)    ← identity × signed prekey
3. DH2 = DH(EK_A, IK_B)     ← ephemeral × identity
4. DH3 = DH(EK_A, SPK_B)    ← ephemeral × signed prekey
5. DH4 = DH(EK_A, OPK_B)    ← ephemeral × one-time prekey
6. SK = KDF(DH1 || DH2 || DH3 || DH4)
7. Send initial message + EK_A public key
```

One-time prekeys consumed on use — server replenishes Bob's prekey count. Low prekey count alert indicates Bob hasn't been online to replenish.

## Group messaging with Sender Keys

Group E2EE uses Sender Keys (not pairwise Double Ratchet — too expensive for large groups):

```
Each member has a Sender Key they distribute to group
Message encrypted once with Sender Key → distributed to all members
New member: existing members re-distribute their Sender Keys
Member removed: all remaining members rotate Sender Keys
```

Member removal requires Sender Key rotation — removed member's old keys must not decrypt future messages. Define rotation protocol before launching group chat.

## Metadata minimization

E2EE protects message content, not metadata:

| Protected | Not protected (without extra measures) |
|---|---|
| Message body | Who messaged whom |
| Attachments | When messages sent |
| Message count | Message size/frequency |
| | IP address of sender |

Sealed sender (Signal's implementation) hides sender identity from server for delivery routing. Push notification content should be generic ("New message") not message preview.

## Failure modes

- **Key not rotated on member removal** — removed member reads future group messages
- **One-time prekey exhaustion** — new sessions fail silently; monitor prekey count
- **Backup without user passphrase** — "we can't recover your chats" support burden
- **Push notification leaks content** — metadata exposure despite E2EE
- **No MITM detection UI** — key change goes unnoticed; user continues compromised session

## Production checklist

- X3DH key exchange implemented per Signal spec
- One-time prekey count monitored; alert when <100
- Sender Key rotation on group member removal
- Push notifications contain no message content
- Key change surfaces loud UI warning (MITM detection)
- Encrypted backup requires user passphrase — document trade-off clearly

## Resources

- [Signal Specifications (Double Ratchet, X3DH)](https://signal.org/docs/)
- [RFC 9420 — Messaging Layer Security (MLS)](https://www.rfc-editor.org/rfc/rfc9420)
- [libsignal-client (GitHub)](https://github.com/signalapp/libsignal)
- [Signal Server (reference implementation)](https://github.com/signalapp/Signal-Server)
- [Electronic Frontier Foundation — Surveillance Self-Defense](https://ssd.eff.org/)
