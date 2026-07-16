---
title: "API Keys vs OAuth Tokens"
slug: "sec-api-keys-vs-oauth"
description: "Choose between API keys and OAuth tokens: threat models, rotation, scopes, and patterns for machine-to-machine versus user-delegated access."
datePublished: "2025-05-15"
dateModified: "2025-05-15"
tags: ["Security", "Authentication", "OAuth", "API"]
keywords: "API keys vs OAuth, bearer token security, machine to machine auth, OAuth scopes, API key rotation, client credentials grant"
faq:
  - q: "When is an API key sufficient?"
    a: "API keys fit server-to-server integrations where a single tenant owns the credential, scopes are coarse, and you can rotate on compromise without affecting end users. Internal cron jobs calling your own backend with network isolation are reasonable key users. Never embed long-lived keys in mobile apps or front-end JavaScript—they are extractable."
  - q: "Why prefer OAuth for third-party integrations?"
    a: "OAuth separates resource owner consent from client credentials, supports short-lived access tokens, refresh rotation, and fine-grained scopes. Users revoke one app without resetting their password. Public clients use PKCE instead of shared secrets. Keys cannot express delegated user permission—they are all-or-nothing bearer secrets."
  - q: "How should API keys be transmitted?"
    a: "Send keys in headers (Authorization: Bearer or X-Api-Key), never query strings where they land in access logs and browser history. Require TLS 1.2+. Hash keys at rest like passwords; show the plaintext once at creation. Rate limit and audit per key ID, not per IP alone."
---

The mobile app shipped with `sk_live_abc123` in the APK. Scrapers found it within hours. API keys are shared secrets: whoever possesses the string is the caller. OAuth access tokens are also bearer credentials, but they are short-lived, scoped, auditable, and issuable only after user consent or a vault-stored client secret. Choosing between them is not religious—it is threat modeling for who holds the credential and what happens when it leaks.

## API keys: simple and dangerous

Keys excel for:

- Internal batch jobs in your VPC
- Webhook verification paired with HMAC signatures
- Developer sandboxes with spend caps

Design rules:

```http
GET /v1/balances HTTP/1.1
Authorization: Bearer sk_live_7kQ2...
```

Store `HMAC-SHA256(key)` in the database. Prefix keys (`sk_live_`, `sk_test_`) so grep catches accidents. Enforce one key per integration for blast-radius isolation.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.
## OAuth for user-delegated access

Authorization Code + PKCE flow for SPAs and mobile:

1. User authenticates at IdP
2. App receives code, exchanges for access + refresh tokens
3. Access token carries scopes like `orders:read`

Revocation endpoint invalidates refresh tokens per client. Users disable a rogue integration without rotating their password.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.
## Machine-to-machine OAuth

Client Credentials grant for service accounts:

```bash
curl -X POST https://auth.example.com/oauth/token \
  -d grant_type=client_credentials \
  -d client_id=svc_inventory \
  -d client_secret=$SECRET \
  -d scope=inventory:write
```

Prefer private_key_jwt or mTLS instead of static client secrets for high-assurance partners. Rotate secrets via dual-active window.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.
## Scopes beat monolithic keys

Map scopes to authorization policies:

```json
{
  "sub": "user_42",
  "scope": "reports:read invoices:read",
  "exp": 1710000000
}
```

A leaked read-only token cannot POST transfers. API keys can emulate scopes only by issuing multiple keys—operationally heavier.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.
## Rotation and incident response

| Credential | Rotation trigger | User impact |
|------------|------------------|-------------|
| API key | Quarterly or leak | Update config in one system |
| Refresh token | Re-auth on revoke | Silent if refresh fails gracefully |
| Access token | Expiry (~15 min) | Auto-refresh |

During incidents, disable key ID in admin console immediately; OAuth allows global session revocation at IdP.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.
## Hybrid patterns

Some products expose API keys that mint short-lived JWTs server-side—keys never leave the backend you control. Public documentation keys for try-it-now flows should be rate-limited sandbox keys with no production data.

Prefix keys sk_live_ and sk_test_ so grep catches accidents in repos. Enforce one key per integration for blast-radius isolation. Hash at rest; show plaintext once at creation.

Hybrid products expose server-side keys that mint short-lived JWTs—keys never ship in mobile binaries. Sandbox documentation keys need rate limits and synthetic data only.

During incidents disable key ID in admin console immediately. OAuth allows global session revocation at IdP. Document rotation playbooks for both models with different user impact expectations.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

Document the decision, owner, and rollback path in your team wiki the same week you ship. Future you will not remember which environment variable toggled the behavior unless it is written next to the runbook entry and linked from the alert. That habit costs ten minutes per change and saves hours when pagination or auth misbehaves under a single large tenant.


Run the change through your standard PR checklist: tests, observability, and a two-minute rollback drill in staging. Small operational habits accumulate into systems that survive on-call nights without heroics.


Share a short write-up in your engineering channel after rollout: what shipped, what metric you watch, and who owns follow-up. That closes the loop for teammates who were not in the PR and surfaces gaps in docs before the next person repeats the same investigation.

## Resources

- [OAuth 2.0 RFC 6749](https://www.rfc-editor.org/rfc/rfc6749.html)
- [OAuth 2.1 draft security best current practice](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-security-topics)
- [OWASP API Security: broken authentication](https://owasp.org/API-Security/editions/2023/en/0xa2-broken-authentication/)
- [Stripe API keys documentation](https://docs.stripe.com/keys)
- [Auth0: API vs M2M authorization](https://auth0.com/docs/get-started/applications)
