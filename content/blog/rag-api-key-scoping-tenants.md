---
title: "API Key Scoping for Multi-Tenant SaaS"
slug: "rag-api-key-scoping-tenants"
description: "Hashing keys at rest, prefix lookup, least-privilege scopes, and rotation without breaking tenant integrations."
datePublished: "2025-09-28"
dateModified: "2026-07-17"
tags:
  - "Security"
  - "API"
  - "SaaS"
keywords: "api keys, multi-tenant, scoping, authentication"
faq:
  - q: "Should API keys be stored encrypted or hashed?"
    a: "Hash with slow KDF like bcrypt or Argon2 — same as passwords — so DB leak does not expose usable keys; show prefix only for UI identification."
  - q: "How granular should scopes be?"
    a: "Resource plus action level (invoices:read) beats coarse read/write; default deny with explicit grants per integration use case."
  - q: "How do tenants rotate keys safely?"
    a: "Support overlapping validity windows — two active keys per integration — with audit log of creation and revocation events."
---
Long-lived API keys remain the integration default for B2B SaaS despite OAuth's finer grain. Multi-tenant platforms must ensure one tenant's key never reads another's data, scopes limit blast radius when keys leak, and rotation does not require midnight maintenance windows. Implementation details — prefix indexes, constant-time compare, metadata on keys — separate secure platforms from those that store plaintext secrets in Mongo.

## Key generation and display-once semantics

Generate high-entropy secrets; show full key once at creation. Store only hash and public prefix for support lookup. Never email full keys — deep links to rotate instead.

Integration tests should assert 403/404 on cross-tenant resource access with valid key for different tenant — unit tests on scope parser alone miss middleware ordering bugs.

## Tenant binding in authorization middleware

Every request resolves key to tenant_id and scope set before handler. Cross-tenant ID in URL must match key tenant or return 404 not 403 to avoid existence leaks.

## Scope enforcement patterns

Embed scopes in signed token derived from key at auth layer or join scope table on each request. Cache scope bitmap in memory with TTL; invalidate on revocation pubsub event.

## Rate limits per key and per tenant

Abuse of one integration key should not throttle whole tenant — separate buckets. Alert on anomalous geo or error rate per key.

## Rotation and emergency revoke

Admin UI lists keys by prefix, last used, created by. One-click revoke propagates to edge cache within seconds. Webhook notify tenant on forced revoke.

## Audit and compliance

Log key create, rotate, revoke with actor. Exporters for SOC2 evidence — who accessed production API with which key when.

## Detecting leaked keys quickly

Subscribe to GitHub secret scanning and rotate keys found in public repos within SLA hours. Hash prefix indexing lets support identify leaked key from paste snippet without storing plaintext. Alert tenant admin on first use from new country ASN after leak window.

## SDK and mobile embedded keys

Mobile apps embedding API keys are extractable — use short-lived tokens exchanged server-side, not long-lived tenant keys in binary. Rotate mobile exchange credentials independently of backend integration keys.

## Webhook signing versus API keys

Outbound webhooks should sign payloads with per-tenant secret distinct from inbound API key — leak of inbound key must not forge events to customer systems.

API keys are passwords for machines — hash them, scope them, bind them to tenants, and make rotation boring. Plaintext storage and global keys are incidents waiting for a backup leak.

Include API key rotation in customer offboarding checklist — orphaned keys on forgotten integrations remain active until explicitly revoked.

Design review checklist item 1 for API key scoping for tenants: validate failure modes, owner, and rollback before merge to main.

Observability gap 1 in API key scoping for tenants often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 1 for API key scoping for tenants should assert behavior under duplicate requests and slow dependencies.

Runbook section 1 for API key scoping for tenants documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 2 for API key scoping for tenants: validate failure modes, owner, and rollback before merge to main.

Observability gap 2 in API key scoping for tenants often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 2 for API key scoping for tenants should assert behavior under duplicate requests and slow dependencies.

Runbook section 2 for API key scoping for tenants documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 3 for API key scoping for tenants: validate failure modes, owner, and rollback before merge to main.

Observability gap 3 in API key scoping for tenants often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 3 for API key scoping for tenants should assert behavior under duplicate requests and slow dependencies.

Runbook section 3 for API key scoping for tenants documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 4 for API key scoping for tenants: validate failure modes, owner, and rollback before merge to main.

Observability gap 4 in API key scoping for tenants often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 4 for API key scoping for tenants should assert behavior under duplicate requests and slow dependencies.

Runbook section 4 for API key scoping for tenants documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 5 for API key scoping for tenants: validate failure modes, owner, and rollback before merge to main.

Observability gap 5 in API key scoping for tenants often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 5 for API key scoping for tenants should assert behavior under duplicate requests and slow dependencies.

Runbook section 5 for API key scoping for tenants documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 6 for API key scoping for tenants: validate failure modes, owner, and rollback before merge to main.

Observability gap 6 in API key scoping for tenants often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 6 for API key scoping for tenants should assert behavior under duplicate requests and slow dependencies.

Runbook section 6 for API key scoping for tenants documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 7 for API key scoping for tenants: validate failure modes, owner, and rollback before merge to main.

Observability gap 7 in API key scoping for tenants often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 7 for API key scoping for tenants should assert behavior under duplicate requests and slow dependencies.

Runbook section 7 for API key scoping for tenants documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 8 for API key scoping for tenants: validate failure modes, owner, and rollback before merge to main.

Observability gap 8 in API key scoping for tenants often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 8 for API key scoping for tenants should assert behavior under duplicate requests and slow dependencies.

Runbook section 8 for API key scoping for tenants documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 9 for API key scoping for tenants: validate failure modes, owner, and rollback before merge to main.

Observability gap 9 in API key scoping for tenants often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 9 for API key scoping for tenants should assert behavior under duplicate requests and slow dependencies.

Runbook section 9 for API key scoping for tenants documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 10 for API key scoping for tenants: validate failure modes, owner, and rollback before merge to main.

Observability gap 10 in API key scoping for tenants often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 10 for API key scoping for tenants should assert behavior under duplicate requests and slow dependencies.

## Common regressions around api key scoping tenants

Teams often pass a demo and then regress under load: retries without jitter, missing idempotency keys, or caches that never invalidate. Write a short regression list specific to api key scoping tenants and turn each item into an automated check or a game-day step. Prefer failing CI on the regression over discovering it from customer tickets. When you change defaults, update alerts in the same pull request so observability stays coupled to behavior.
