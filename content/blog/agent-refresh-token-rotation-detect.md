---
title: "AI Agents: Refresh Token Rotation Detect"
slug: "agent-refresh-token-rotation-detect"
description: "Rotate OAuth refresh tokens on every exchange and detect reuse—the standard defense when an agent dashboard credential leaks but you cannot revoke every active session instantly."
datePublished: "2026-01-04"
dateModified: "2026-01-04"
tags: ["AI", "Agent", "Refresh"]
keywords: "refresh token rotation, token reuse detection, OAuth 2.0 BCP, agent session security, refresh token family, stolen credential response"
faq:
  - q: "What happens when refresh token reuse is detected?"
    a: "Invalidate the entire refresh token family for that user-agent binding—revoke all outstanding refresh tokens and access tokens derived from that chain—and force re-authentication. Treat reuse as evidence of token theft or a duplicated client store, not as a benign retry."
  - q: "How do mobile agent apps handle rotation without logging users out on every refresh?"
    a: "Persist the latest refresh token atomically on the client before acknowledging success, serialize refresh calls through a single mutex, and on 401 from reuse detection show one re-login flow. Never run parallel refresh requests from background sync and foreground UI threads."
  - q: "Should agent service accounts use rotating refresh tokens?"
    a: "Prefer short-lived client credentials or workload identity federation for machine agents. Refresh token rotation targets human-in-the-loop OAuth clients; service accounts rarely benefit and complicate unattended recovery when reuse fires at 3 a.m."
  - q: "Does rotation replace refresh token binding and PKCE?"
    a: "No. Rotation detects theft after the fact; PKCE and token binding reduce theft probability. Production agent stacks use PKCE on public clients, HTTPS-only redirect URIs, and rotation with reuse detection together."
---
A security researcher reported that our agent console's refresh token never changed. Anyone who exfiltrated `refresh_abc123` from a compromised laptop could mint access tokens indefinitely until the user changed their password—if they noticed. We implemented rotation within a week. Two days later, on-call pages spiked: legitimate users with two browser tabs open were getting logged out en masse. The rotation logic worked; **reuse detection** did not distinguish theft from a race between tabs. Fixing that distinction is the engineering depth this post covers.

## Rotation in one paragraph, precisely

On each `POST /oauth/token` grant type `refresh_token`:

1. Validate presented refresh token hash against storage.
2. Issue new access token **and** new refresh token.
3. Invalidate the presented refresh token immediately (or mark consumed).
4. Link new refresh token to the same **family** identifier as its predecessor.

If a client ever presents a refresh token already marked consumed, that is **reuse**—someone kept a copy. Response: revoke family, audit log, require fresh login.

OAuth 2.0 Security Best Current Practice (RFC 9700) recommends this pattern for public clients; agent dashboards, IDE plugins, and mobile companions fit that profile.

## Token family graph

Store families explicitly:

```sql
CREATE TABLE refresh_token_families (
  family_id     uuid PRIMARY KEY,
  user_id       text NOT NULL,
  client_id     text NOT NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  revoked_at    timestamptz
);

CREATE TABLE refresh_tokens (
  token_hash    text PRIMARY KEY,
  family_id     uuid NOT NULL REFERENCES refresh_token_families(family_id),
  parent_hash   text,
  consumed_at   timestamptz,
  expires_at    timestamptz NOT NULL,
  issued_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_refresh_family_active ON refresh_tokens(family_id) WHERE consumed_at IS NULL;
```

Hash tokens with SHA-256 before persistence; never store raw refresh strings. The `parent_hash` chain helps forensics: which token was replayed, and when was its successor issued?

## Exchange handler with atomic consume

The critical section must be transactional:

```typescript
type RefreshResult =
  | { ok: true; accessToken: string; refreshToken: string; expiresIn: number }
  | { ok: false; reason: "invalid" | "expired" | "reuse_detected" | "family_revoked" };

async function rotateRefreshToken(
  presentedRaw: string,
  clientId: string,
  db: Db
): Promise<RefreshResult> {
  const presentedHash = sha256(presentedRaw);

  return db.transaction(async (tx) => {
    const row = await tx.getRefreshToken(presentedHash);
    if (!row) return { ok: false, reason: "invalid" };
    if (row.expires_at < new Date()) return { ok: false, reason: "expired" };

    const family = await tx.getFamily(row.family_id);
    if (family.revoked_at) return { ok: false, reason: "family_revoked" };

    if (row.consumed_at) {
      await tx.revokeFamily(row.family_id, "reuse_detected");
      await tx.auditSecurityEvent({
        type: "refresh_token_reuse",
        userId: family.user_id,
        familyId: row.family_id,
        clientId,
      });
      return { ok: false, reason: "reuse_detected" };
    }

    await tx.markConsumed(presentedHash);

    const newRaw = generateRefreshToken(); // 256-bit entropy
    const newHash = sha256(newRaw);
    await tx.insertRefreshToken({
      tokenHash: newHash,
      familyId: row.family_id,
      parentHash: presentedHash,
      expiresAt: addDays(new Date(), 30),
    });

    const access = await issueAccessToken(family.user_id, clientId);
    return {
      ok: true,
      accessToken: access.token,
      refreshToken: newRaw,
      expiresIn: access.expiresIn,
    };
  });
}
```

Database row locks on `token_hash` prevent double-rotation under concurrent requests **when both arrive with the same token**. They do not solve the two-tab problem—that requires client behavior.

## The benign reuse race (and how not to nuke users)

Scenario: Tab A and Tab B hold refresh token `R0`. Tab A refreshes first, receives `R1`, persists it. Tab B still has `R0` and refreshes seconds later. Server sees consumed `R0` → reuse → revokes family → both tabs dead.

Mitigations, pick at least two:

**Grace window (controversial but common):** Allow one reuse of the immediately previous token within 10–30 seconds if the replacement token was already issued. Log as `grace_reuse`, do not revoke. Tighten window aggressively; document in security review.

**Client-side refresh mutex:** Single-flight refresh; queue API calls until new tokens land in secure storage.

**Silent retry after 401:** On reuse response, if secure storage already has a newer refresh token from another tab, retry once with that token before forcing login.

```typescript
let refreshInFlight: Promise<TokenPair> | null = null;

async function getValidAccessToken(): Promise<string> {
  if (!isExpired(stored.accessToken)) return stored.accessToken;

  if (!refreshInFlight) {
    refreshInFlight = refresh(stored.refreshToken)
      .then((pair) => {
        persist(pair);
        return pair;
      })
      .finally(() => {
        refreshInFlight = null;
      });
  }
  const pair = await refreshInFlight;
  return pair.accessToken;
}
```

## Agent-specific surfaces

Agent products multiply OAuth clients: web console, VS Code extension, CLI, Slack bot installer. Each client_id gets **separate families**—revoking CLI theft must not logout the web session unless policy ties them.

Long-running agent workers sometimes stash refresh tokens in Kubernetes secrets. Rotation means updating the secret after every refresh—prefer workload identity instead.

Log `family_id`, `client_id`, and geo/IP on reuse events. Agent accounts with impossible travel plus reuse is a stronger incident signal than reuse alone.

## Metrics and dashboards

Track:

- `refresh_success_total` by client_id
- `refresh_reuse_detected_total` — alert threshold > 0 in prod after grace tuning
- `refresh_grace_reuse_total` — should stay small; spike indicates client bug
- `family_revocation_total` with reason label
- p95 refresh latency — agent UIs block tool calls during refresh

Run quarterly game days: replay stolen refresh token in staging, verify family revocation and audit trail within 60 seconds.

## Migration from static refresh tokens

1. Issue new tokens with `family_id` on next natural refresh; backfill families lazily.
2. Feature-flag reuse detection in **audit-only** mode for two weeks—log would-be revocations without acting.
3. Enable enforcement client-by-client after mutex fixes ship in extensions.
4. Deprecate non-rotating tokens with hard cutoff date communicated to API consumers.

## Storage hardening details

Refresh tokens deserve stronger protection than access tokens because they live longer. At rest:

- Encrypt `token_hash` rows with a KMS-backed key if the database volume is not encrypted by default
- Restrict database roles: the auth service account gets `SELECT/INSERT/UPDATE` on `refresh_tokens`; analytics gets none
- Never log raw refresh tokens—even debug builds should redact `refresh_token` form fields in HTTP dumps

Rotation frequency trades security for churn. Thirty-day refresh expiry with rotation on every access-token renewal means a stolen token window is bounded by the shorter of theft-to-detection time and the next legitimate refresh. Aggressive five-minute access token TTL plus rotation shrinks exposure but increases refresh QPS—watch database transaction rate on `rotateRefreshToken` before tightening.

## Incident response playbook

When `refresh_reuse_detected_total` fires for a enterprise tenant:

1. Pull audit row: `family_id`, `client_id`, IP, user agent, timestamp of reuse vs prior successful rotation
2. Correlate with access token grants—did unusual tool scopes appear between rotation and reuse?
3. Revoke family (already automatic); optionally force password reset if reuse came from unknown client_id
4. Notify tenant admin with non-technical summary; preserve forensic chain for legal if needed

False positive triage: if reuse clusters on one `client_id` release version, roll back that client build before assuming breach.

## Compliance and session evidence

SOC 2 and ISO audits ask how you detect stolen sessions. Export quarterly samples showing reuse detection fired, family revoked, user re-authenticated, and no further reuse on replaced families. Auditors care about **closed loops**, not algorithm descriptions.

Pair rotation with device binding where platforms allow (DPoP, mTLS client certs for CLI agents). Rotation catches theft; binding raises theft cost.

## Resources

- [RFC 9700 — OAuth 2.0 Security BCP](https://www.rfc-editor.org/rfc/rfc9700.html) — normative guidance on refresh token rotation and reuse detection
- [OAuth 2.0 for Browser-Based Apps (BCP)](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-browser-based-apps) — public client patterns for agent dashboards
- [Auth0 — Refresh Token Rotation](https://auth0.com/docs/secure/tokens/refresh-tokens/refresh-token-rotation) — operational walkthrough of family revocation semantics
- [OWASP — Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html) — secure token storage on clients
- [IETF OAuth WG mailing list archive](https://mailarchive.ietf.org/arch/browse/oauth/) — edge-case discussions that precede formal RFC language
