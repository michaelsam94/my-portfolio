---
title: "Verifying WebAuthn Attestation"
slug: "sec-webauthn-attestation-verification"
description: "Verify WebAuthn attestation statements: formats, privacy tradeoffs, enterprise policy, and when none attestation is enough."
datePublished: "2025-06-20"
dateModified: "2025-06-20"
tags: ["Security", "WebAuthn", "Authentication", "FIDO2"]
keywords: "WebAuthn attestation verification, FIDO2 attestation, packed attestation, none attestation, authenticator metadata, enterprise passkeys"
faq:
  - q: "Do consumer apps need attestation verification?"
    a: "Most consumer passkey deployments use attestation none or accept any authenticator—registration succeeds based on cryptographic challenge validation alone. Attestation verification matters when policy requires specific authenticator types, FIPS-certified hardware, or blocking rooted software authenticators in high-assurance environments."
  - q: "What does attestation prove?"
    a: "Attestation proves which manufacturer model signed the credential's initial key pair, via certificate chain to a trusted root. It does not prove user identity—that comes from your auth flow. Attestation answers 'what device created this passkey?' which enterprises map to allowed device lists."
  - q: "Does attestation harm user privacy?"
    a: "Yes if misused—unique attestation certificates can track users across sites. Browsers increasingly use privacy-preserving attestation or none for consumer flows. Relying parties should store only what policy requires and prefer none unless enterprise compliance mandates hardware provenance."
---

Your security team asked to "only allow YubiKeys" for admin access. WebAuthn registration returns an `attestationObject` alongside the public key—signed metadata about the authenticator. Verifying attestation means checking that signature chain against known roots and mapping the authenticator model to policy. Consumer passkey products often skip this entirely (`none` attestation) because tracking users by authenticator certificate is a privacy failure and most sites do not need hardware inventory.

## Registration response structure

The client sends:

```json
{
  "id": "credential-id-base64url",
  "rawId": "...",
  "type": "public-key",
  "response": {
    "attestationObject": "...",
    "clientDataJSON": "..."
  }
}
```

Parse `attestationObject` (CBOR) for `fmt` (format), `authData`, and `attStmt`.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.
## Common attestation formats

| fmt | Typical source |
|-----|----------------|
| none | Platform passkeys, privacy mode |
| packed | Many USB security keys |
| tpm | Windows Hello TPM |
| android-key | Android Keystore |
| apple | Apple Secure Enclave |

Use a WebAuthn library (webauthn4j, SimpleWebAuthn, @simplewebauthn/server) rather than hand-rolling CBOR.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.
## Verification steps

1. Verify clientDataJSON challenge matches server session
2. Verify origin and RP ID hash in authData
3. Parse attestation format and validate signature over authData
4. Chain attestation certificate to trusted root (if not `none`)
5. Optionally check AAGUID against FIDO Metadata Service

```java
RegistrationResult result = relyingParty.finishRegistration(
    FinishRegistrationOptions.builder()
        .request(startOptions.getRequest())
        .response(clientResponse)
        .build()
);
// Library validates attestation per configured policy
```

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.
## Enterprise policy example

```yaml
attestation: direct
allowed_aaguids:
  - 00000000-0000-0040-8000-000000000000  # example YubiKey AAGUID
reject_none: true
```

Maintain AAGUID allowlist from FIDO Alliance Metadata Service updates. Document exception process for executives with platform passkeys if policy loosens.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.
## When to accept none

Public consumer signup: accept `none` and `packed` broadly; rate limit registration; monitor for credential stuffing. Risk is low if user verification (email, existing password) binds the passkey to account.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.
## Storage and GDPR

Store credential ID, public key, sign counter, and optionally AAGUID—not entire attestation chain unless audit requires. Users deleting account should remove all credentials.

Consumer passkey signup often accepts none attestation—focus on challenge validation and user verification binding. Enterprise admin flows map AAGUID allowlists from FIDO Metadata Service with update process.

Store credential ID, public key, sign counter—not full attestation chain unless audit mandates. Account deletion removes all credentials per GDPR expectations.

Test registration and authentication ceremonies in CI with virtual authenticators where possible.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

Document the decision, owner, and rollback path in your team wiki the same week you ship. Future you will not remember which environment variable toggled the behavior unless it is written next to the runbook entry and linked from the alert. That habit costs ten minutes per change and saves hours when pagination or auth misbehaves under a single large tenant.


Run the change through your standard PR checklist: tests, observability, and a two-minute rollback drill in staging. Small operational habits accumulate into systems that survive on-call nights without heroics.


Share a short write-up in your engineering channel after rollout: what shipped, what metric you watch, and who owns follow-up. That closes the loop for teammates who were not in the PR and surfaces gaps in docs before the next person repeats the same investigation.


Prefer boring, repeatable process over one heroic migration weekend.


Treat operational readiness as part of definition-of-done: dashboards, alerts, runbook links, and a named owner. Skipping those steps ships code that works in demo and fails quietly in production until a customer or auditor finds the gap.

## Resources

- [WebAuthn Level 3 specification](https://www.w3.org/TR/webauthn-3/)
- [FIDO Alliance Metadata Service](https://fidoalliance.org/metadata/)
- [MDN Web Authentication API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Authentication_API)
- [webauthn.guide](https://webauthn.guide/)
- [W3C WebAuthn attestation formats](https://www.w3.org/TR/webauthn-3/#sctn-defined-attestation-formats)
