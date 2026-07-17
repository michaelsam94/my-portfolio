---
title: "Pkce Public Clients"
slug: "llm-pkce-public-clients"
description: "OAuth PKCE for agent public clients—desktop assistants, IDE plugins, and mobile copilots: verifier storage, loopback redirects, token refresh without embedded secrets for teams running LLM features in production."
datePublished: "2026-01-02"
dateModified: "2026-07-17"
tags:
  - "AI"
  - "LLM"
keywords: "PKCE public client, OAuth agent desktop app, authorization code PKCE, loopback redirect, IDE plugin authentication, token refresh without client secret"
faq:
  - q: "Why are AI agent clients treated as OAuth public clients?"
    a: "Desktop agents, IDE extensions, and mobile copilots ship code to environments attackers can inspect. Embedded client secrets are extractable from binaries or JavaScript bundles within minutes. OAuth classifies these as public clients—they authenticate users via Authorization Code + PKCE, not via confidential client secrets at the token endpoint."
  - q: "Where should the code verifier live during the auth flow?"
    a: "In memory for the duration of the flow, keyed by state parameter. For desktop apps using loopback redirects, bind verifier to the local server instance that receives the callback. Never persist verifiers to disk or sync them across devices. Clear verifier immediately after successful token exchange or on flow timeout (typically 10 minutes)."
  - q: "Can agent backends use refresh tokens on behalf of users?"
    a: "Yes, but prefer a backend-for-frontend (BFF) that holds refresh tokens in HttpOnly cookies or a secure server-side store. Pure public clients on desktop may use OS keychains for refresh tokens with rotation enabled. Avoid refresh tokens in plaintext config files beside the agent binary."
  - q: "What redirect URI patterns work for local agent installs?"
    a: "RFC 8252 recommends http://127.0.0.1:{port}/callback with a random port chosen at runtime, registered as a pattern with your IdP where supported. Custom URI schemes (myagent://callback) work but are less portable and prone to inter-app hijacking on some platforms—loopback is preferred for desktop agents."
---
A security researcher demoed credential theft against a popular coding assistant: intercept the authorization code from a custom URI scheme handler, exchange it at the token endpoint using the public `client_id`, and impersonate the victim's GitHub-backed agent session. The vendor had shipped Authorization Code flow without PKCE because "desktop apps are hard." They were right about difficulty. They were wrong about skipping the one RFC that fixes public-client code interception.

AI agent clients—Electron shells, IDE plugins, CLI tools with GUI login, mobile copilots—are **public OAuth clients**. They cannot hold secrets. Proof Key for Code Exchange (PKCE, RFC 7636) binds each authorization code to a verifier generated locally at flow start. Stolen codes are useless without the verifier. This post covers PKCE specifically for agent runtimes, not generic SPA tutorials.

## Threat model: what PKCE actually stops

Without PKCE:

1. User completes login; IdP redirects to agent callback with `?code=AUTH_CODE`.
2. Attacker obtains code via malicious local handler registration, network capture on misconfigured proxy, or phishing clone of the OAuth consent screen.
3. Attacker POSTs to `/token` with `client_id`, `code`, `redirect_uri`.
4. Attacker receives access (and refresh) tokens.

PKCE inserts step 2b: token endpoint requires `code_verifier` matching the `code_challenge` from step 1's authorize request. Attacker lacks verifier.

PKCE does **not** stop:

- Malware with access to agent memory/keychain after login.
- Phishing users into approving malicious OAuth clients (different client_id).
- XSS in web-based agent shells—use CSP and BFF patterns there.

Scope PKCE as necessary, not sufficient, for agent auth.

## End-to-end flow for desktop agents

```
┌──────────────┐   code_verifier (memory)   ┌──────────────┐
│ Agent app    │◀──────────────────────────▶│ Loopback     │
│ (main proc)  │   code_challenge in URL    │ HTTP server  │
└──────┬───────┘                            └──────▲───────┘
       │ open browser                               │ redirect
       ▼                                            │
┌──────────────┐         authorization code        │
│ System       │───────────────────────────────────┘
│ browser      │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Identity     │
│ provider     │
└──────────────┘
```

Sequence:

1. Agent generates `code_verifier` (43–128 chars, cryptographically random).
2. Computes `code_challenge = BASE64URL(SHA256(verifier))`, method `S256`.
3. Starts loopback listener on ephemeral port; launches browser to authorize URL with `code_challenge`, `state`, `redirect_uri=http://127.0.0.1:{port}/callback`.
4. IdP redirects to loopback with `code` and `state`.
5. Agent validates `state`, POSTs token request with `code_verifier`.
6. Stores tokens in OS keychain; shuts down loopback server; zeroes verifier from memory.

```typescript
import { createHash, randomBytes } from "crypto";
import { createServer } from "http";

function base64UrlEncode(buf: Buffer): string {
  return buf.toString("base64url");
}

function generateVerifier(): string {
  return base64UrlEncode(randomBytes(32));
}

function challengeFromVerifier(verifier: string): string {
  return createHash("sha256").update(verifier).digest("base64url");
}

async function authorizeWithPkce(config: {
  clientId: string;
  authorizeUrl: string;
  tokenUrl: string;
  scopes: string[];
}): Promise<{ accessToken: string; refreshToken?: string }> {
  const verifier = generateVerifier();
  const challenge = challengeFromVerifier(verifier);
  const state = base64UrlEncode(randomBytes(16));
  const port = await pickEphemeralPort();

  const codePromise = waitForLoopbackCode(port, state, 600_000);

  const params = new URLSearchParams({
    response_type: "code",
    client_id: config.clientId,
    redirect_uri: `http://127.0.0.1:${port}/callback`,
    scope: config.scopes.join(" "),
    state,
    code_challenge: challenge,
    code_challenge_method: "S256",
  });

  await openSystemBrowser(`${config.authorizeUrl}?${params}`);

  const code = await codePromise;

  const tokenRes = await fetch(config.tokenUrl, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "authorization_code",
      client_id: config.clientId,
      code,
      redirect_uri: `http://127.0.0.1:${port}/callback`,
      code_verifier: verifier,
    }),
  });

  if (!tokenRes.ok) throw new Error(`token exchange failed: ${tokenRes.status}`);
  return tokenRes.json();
}
```

Use `S256` exclusively. The `plain` challenge method is deprecated in OAuth 2.1.

## IDE plugins and multi-process runtimes

VS Code and JetBrains plugins often split UI (extension host) and auth (external browser). Pitfalls:

- **Verifier in extension storage** — readable if another extension compromises storage APIs. Keep verifier in the extension host memory only for the auth session; use a one-shot message channel from auth helper process.
- **Shared redirect port** — two plugins starting loopback on the same port: bind `127.0.0.1:0`, register dynamic redirect with IdP if supported, or document fixed port ranges per product.
- **Headless CI agents** — device code flow (RFC 8628) replaces PKCE loopback for unattended automation; do not disable PKCE in production to " simplify CI."

For Electron agents, run loopback in the main process, not the renderer. Renderer compromise should not steal verifiers mid-flow.

## Token storage after exchange

| Storage | Access token | Refresh token |
|---------|--------------|---------------|
| OS keychain (Keytar, libsecret) | Acceptable | Preferred |
| Encrypted local file (DPAPI/macOS Keychain wrapper) | Acceptable with rotation | Acceptable |
| Environment variables | Never | Never |
| Repo config / `.env` | Never | Never |

Enable refresh token rotation if IdP supports it. On refresh reuse detection, revoke all sessions and force re-login—agents are high-value targets for long-lived refresh tokens.

Access tokens for tool calls should be short-lived (5–15 minutes). Agent orchestration layers refresh proactively at 80% TTL, not on 401 from first tool failure, to avoid half-completed multi-step plans failing mid-flight.

## Backend-for-frontend variant

Enterprise agents often proxy OAuth through a vendor cloud:

1. Desktop agent opens browser to *your* BFF `/auth/start`, not directly to IdP.
2. BFF completes PKCE with IdP using server-side session storage for verifier.
3. BFF sets HttpOnly session cookie; agent receives opaque device session token.

Benefits: centralized audit, IP allowlists, refresh tokens never touch desktop. Tradeoff: offline mode requires explicit design—cached credentials or degraded local-only features.

If you use BFF, desktop still uses PKCE on the BFF leg unless BFF uses mTLS device attestation instead (uncommon).

## IdP configuration checklist

- Register exact loopback pattern or dynamic port policy.
- Disable implicit and password grants for agent client IDs.
- Require PKCE (`code_challenge` required) via IdP policy—do not rely on client behavior.
- Restrict redirect URIs—no `http://localhost` wildcard without port binding rules.
- Set consent screen product name matching shipped binary to reduce phishing clones.

For multi-tenant SaaS agents, separate OAuth clients per tenant only when tenants bring own IdP. Shared client with tenant routing simplifies PKCE redirect management.

## Testing PKCE implementations

Automated:

- Unit test `challengeFromVerifier` against RFC 7636 appendix B vectors.
- Integration test with WireMock IdP: reject token exchange when verifier wrong, challenge wrong, or code replayed.

Manual red team:

- Capture authorize redirect, attempt token exchange without verifier—expect `invalid_grant`.
- Replay code with old verifier after successful exchange—expect failure.
- Swap `state`—loopback handler must reject before token exchange.

Log auth failures with `error_code` from IdP, never log verifiers or codes.

## Migration from implicit or static secrets

If legacy agent shipped implicit flow or embedded `client_secret`:

1. Register new public client with PKCE required.
2. Ship agent update that migrates users on next login—force re-consent if scopes change.
3. Revoke old client credentials after 90-day sunset.
4. Monitor token endpoint for old `client_id` usage; alert on non-zero after cutoff.

Communicate downtime window for CLI agents used in CI—provide device code path before killing legacy flow.

## Closing thought

PKCE for agent public clients is baseline hygiene, not advanced hardening. Generate verifiers locally, use S256, bind loopback redirects tightly, store refresh tokens in OS secure storage, and test failure paths where attackers present stolen codes. The coding-assistant breach pattern is public knowledge now—shipping without PKCE is a choice auditors and attackers both understand.

## Resources

- [RFC 7636: Proof Key for Code Exchange (PKCE)](https://datatracker.ietf.org/doc/html/rfc7636) — normative specification.
- [RFC 8252: OAuth 2.0 for Native Apps](https://datatracker.ietf.org/doc/html/rfc8252) — loopback redirect guidance for desktop agents.
- [OAuth 2.1 Draft](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-v2-1-11) — PKCE required for all clients; implicit flow removed.
- [OAuth 2.0 Security BCP (RFC 9700)](https://datatracker.ietf.org/doc/html/rfc9700) — current best current practice for public clients.
- [Auth0: PKCE for mobile and native apps](https://auth0.com/docs/get-started/authentication-and-authorization-flow/authorization-code-flow-with-pkce) — practical implementation notes for native runtimes.
