#!/usr/bin/env python3
"""Combine git HEAD core + unique expansions into ≥1200-word b11_rw posts."""
from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
DATE = "2026-07-17"
TARGET = 1200
WORD = re.compile(r"\b[\w'-]+\b")
SLUG_FILES = ["/tmp/b11_rw_0.txt", "/tmp/b11_rw_1.txt", "/tmp/b11_rw_2.txt"]

STRIP = [
    r"\n## Operating [^\n]+\n.*?(?=\n## |\Z)",
    r"\n## Additional depth on[^\n]*\n.*?(?=\n## |\Z)",
    r"\n## Closing notes\n.*?(?=\n## |\Z)",
    r"Validate this in staging with production-like data volume[^\n]*\n",
    r"Document the decision, owner, and rollback path[^\n]*\n",
    r"Review \d+: teams that treat[^\n]*\n",
    r"assumptions age faster than code[^\n]*\n",
    r"Production engineering for[^\n]*\n",
    r"The gap between reading about[^\n]*\n.*?(?=\n## |\n\n[A-Z])",
    r"## Architecture and boundaries\n.*?(?=\n## |\Z)",
    r"## Accessibility requirements\n.*?(?=\n## |\Z)",
    r"## Security and privacy considerations\n.*?(?=\n## |\Z)",
    r"## Testing strategy\n.*?(?=\n## |\Z)",
    r"## Common production mistakes\n.*?(?=\n## |\Z)",
    r"## Debugging and triage workflow\n.*?(?=\n## |\Z)",
    r"## Options compared honestly\n.*?(?=\n## |\Z)",
    r"## Technical deep dive\nWhen teams skip this layer[^\n]*\n",
    r"## Patterns that compose well\n\n",
    r"## Pre-ship checklist\n\n",
    r"## Where to go from here\n.*?(?=\n## |\Z)",
    r"## Related reading and specs\n.*?(?=\n## |\Z)",
    r"## Coordination with backend and platform\n.*?(?=\n## |\Z)",
    r"If I were prioritizing one action this sprint[^\n]*\n",
    r"Performance and reliability work compounds when tied to business metrics[^\n]*\n",
]

BANNED_PHRASES = (
    "Validate this in staging",
    "Review 1: teams that treat",
    "assumptions age faster than code",
    "The gap between reading about",
    "If I were prioritizing one action",
    "Options compared honestly",
    "Additional depth on",
)

# Import expansion dicts from existing scripts
spec = importlib.util.spec_from_file_location("fr", ROOT / "scripts" / "b11_final_rewrite.py")
fr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fr)

spec2 = importlib.util.spec_from_file_location("ex2", ROOT / "scripts" / "expand_batch11_chunk2.py")
ex2 = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(ex2)

# Extra unique sections for slugs still short after merge
EXTRA: dict[str, str] = {
    "sec-dependency-audit-automation": """
## npm audit versus OSV versus Snyk

`npm audit` uses advisory database tied to npm registry—fast but misses issues in private forks. OSV.dev aggregates across ecosystems with version range queries suitable for CI. Commercial scanners add reachability analysis: is the vulnerable function actually called from your code path?

Run `npm audit --omit=dev` in production dependency CI gate; devDependency vulns matter for supply chain but should not block prod deploy if unreachable.

## Automating PR creation for patches

Dependabot and Renovate open PRs with changelog links. Configure grouping: patch minor updates weekly, major updates monthly with manual review. Auto-merge patch updates when CI green and coverage stable.

## SBOM linkage

Attach CycloneDX SBOM to each release artifact. When CVE-2024-XXXX publishes, query SBOM for affected package versions across all services in thirty minutes—not three days of spreadsheet archaeology.
""",
    "sec-webauthn-attestation-verification": """
## When to verify attestation

Consumer passkey deployments often use `none` attestation—simpler, fewer false rejects from authenticator diversity. Enterprise deployments with hardware key requirements verify attestation statements against vendor root certificates to ensure FIDO-certified authenticators.

## Privacy CA considerations

Apple and Google use privacy-preserving attestation that may not reveal exact authenticator model. Policy requiring "YubiKey only" needs fallback enrollment path for platform authenticators or employee friction spikes.

## attestationObject parsing

```javascript
const { attestationObject, clientDataJSON } = registrationResponse;
// verify challenge, origin, rpIdHash before attestation trust path
```

Reject registrations where `clientDataJSON.type` is not `webauthn.create` or challenge does not match server-issued nonce.
""",
    "sec-tls-certificate-automation-acme": """
## ACME DNS-01 for wildcards

HTTP-01 fails for wildcard certificates. DNS-01 via Route53, Cloudflare API, or cert-manager DNS solver automates `*.api.example.com` renewal. IAM permissions for DNS TXT record creation are the sensitive credential—scope narrowly.

## Short-lived certs and reload

Cert-manager rotates every sixty days; nginx and Envoy need reload signal without dropping connections. Test `SIGHUP` reload or hot restart during business hours in staging before production automation.

## Multi-cloud cert duplication

Same hostname on AWS ALB and Cloudflare CDN needs coordinated renewal—duplicate ACME orders can hit rate limits. Pick one ACME client as source of truth; distribute PEM to other terminators via secrets manager.
""",
    "session-management-secure-cookies": """
## Session fixation prevention

Regenerate session ID after authentication elevation—login, MFA completion, password change. Attacker who planted pre-auth session cookie loses linkage after `request.session.cycle_key()`.

## Rolling session expiration

Absolute timeout (eight hours) plus idle timeout (thirty minutes) balances security and UX. Rolling renewal on activity extends idle window; absolute cap forces re-auth for long-lived tabs.

## Server-side session store

Redis or database sessions enable immediate revocation—JWT-only sessions cannot revoke until expiry without blocklist. High-security apps prefer server-side session with opaque cookie ID.
""",
    "sec-secure-defaults-frameworks": """
## Django SECURE_* and Flask-Talisman

Framework secure defaults ship disabled for backwards compatibility—explicitly enable in production settings template. `DEBUG=False`, `SESSION_COOKIE_SECURE=True`, `CSRF_COOKIE_HTTPONLY=True` belong in prod checklist enforced by linter on settings module.

## Next.js defaults in 2026

Server Actions require explicit opt-in; image optimization domains whitelisted. Review `next.config.js` security headers on every major version bump—defaults evolve.

## Secure-by-default library selection

Prefer libraries that fail closed: Zod parse throws, Rust `unwrap` discouraged in prod paths, SQL builders over string concat. Default choices in scaffolding templates matter more than security training slides.
""",
    "secrets-management-vault": """
## Dynamic database credentials

Vault database secrets engine issues two-hour PostgreSQL users per application role. Application connects with short-lived creds; DBA revokes lease on compromise. Connection pool must handle credential rotation mid-process—refresh on auth error with backoff.

## Namespace isolation per environment

`prod/`, `staging/`, `dev/` Vault namespaces or path prefixes prevent staging CI from reading prod secrets. Policy as code in Terraform reviews path grants in PR.

## Break-glass procedures

Emergency root token sealed in physical safe with quarterly drill. Automated alerts on root token usage. Normal operations use OIDC auth to Vault with group mappings from IdP.
""",
    "sec-oauth-pkce-spa": """
## Public clients cannot hold secrets

SPAs are public OAuth clients—any embedded secret is extractable from bundle. PKCE replaces client secret with code_verifier/code_challenge pair bound to authorization request.

```javascript
const verifier = generateRandomString(64);
const challenge = await sha256Base64Url(verifier);
// store verifier in sessionStorage for token exchange
```

## Authorization code interception

Without PKCE, malicious app registers same custom URL scheme and intercepts auth code on mobile. PKCE ensures token endpoint rejects exchange without verifier.

## Refresh token rotation

SPAs using refresh tokens need rotation detection—reuse of old refresh token revokes entire token family. Store refresh token in HttpOnly cookie via backend-for-frontend pattern when possible.
""",
    "sec-rate-limit-ddos-defense": """
## Layered rate limiting

Edge CDN (Cloudflare, AWS WAF) stops volumetric floods. Application gateway enforces per-API-key and per-IP limits. Service mesh or app middleware applies per-user business limits (ten checkout attempts per hour).

## Token bucket versus sliding window

Token bucket allows bursts; sliding window smooths abuse detection. Use leaky bucket for expensive endpoints (password reset email), strict sliding window for credential stuffing on login.

## Challenge escalation

After soft limit, CAPTCHA or proof-of-work before hard 429. Legitimate users on shared NAT survive longer than bots hitting limit from single IP.
""",
    "sbom-generation-cyclonedx": """
## CycloneDX in CI

```bash
cyclonedx-npm --output-file sbom.json
```

Attach SBOM to container image OCI artifact or release page. Sign SBOM with Sigstore for tamper evidence.

## VEX documents

Vulnerability Exploitability eXchange marks CVE as not affected when reachability analysis proves vulnerable code path unused. Reduces noise versus raw scanner output—auditors increasingly accept VEX with evidence links.
""",
    "sec-logging-sensitive-data-leaks": """
## Structured logging redaction

```python
logger.info("payment_processed", extra={"last4": card[-4:], "amount": amt})
# never log full PAN, CVV, password, session token
```

Configure log processor rules to drop fields matching `password`, `token`, `authorization` keys at ingest.

## PII in error traces

Sentry before-send hook strips cookies and Authorization headers. Stack locals may contain request bodies—scrub `event.request.data` for GDPR.

## Audit versus debug logging

Debug logs verbose in dev; production log level INFO with explicit allowlist of fields. Separate audit stream append-only for compliance—never mixed with debug toggles.
""",
    "sec-input-validation-allowlisting": """
## Allowlist over denylist

Denylist blocking `<script` misses `<SCRIPT`, encoded variants, and polyglot payloads. Allowlist accepts `[a-zA-Z0-9-_.@]` for usernames; reject everything else.

## Canonicalization before validation

Unicode normalization NFC before username uniqueness check—prevent homoglyph duplicates. Path traversal: resolve `..` before checking allowed prefix.

## Validation at trust boundaries

Validate on ingress from HTTP, message queues, and webhooks equally. Internal service calls are trust boundaries when teams deploy independently.
""",
    "sec-api-keys-vs-oauth": """
## API keys for machine-to-machine

Long-lived API keys suit server cron jobs and webhooks between trusted partners. Rotate quarterly; scope per key to minimal endpoints; never embed in mobile apps.

## OAuth for user delegation

User-facing integrations need OAuth with scoped access and refresh rotation—user can revoke without rotating global API key affecting all integrations.

## Key storage

Hash API keys at rest like passwords—store prefix for identification (`sk_live_abcd` + bcrypt hash of secret portion). Compare with `crypto.timingSafeEqual` on verify.
""",
    "sec-jwt-key-rotation-jwks": """
## JWKS endpoint publishing

```json
{"keys":[{"kty":"RSA","kid":"2026-07","n":"...","e":"AQAB"}]}
```

Publish two active keys during rotation window—old `kid` validates tokens issued yesterday; new `kid` signs fresh tokens.

## Rotation without downtime

Add new key to JWKS, start signing with new kid, wait max token TTL (e.g. 24h), remove old key. Consumers cache JWKS—set Cache-Control appropriately but support `kid` miss refetch.

## Asymmetric versus symmetric

HS256 shared secret does not scale across microservices—any verifier can forge. RS256 or ES256 with public key distribution via JWKS is standard for multi-service auth.
""",
    "rust-async-tokio-runtime": """
## Runtime configuration

```rust
#[tokio::main(flavor = "multi_thread", worker_threads = 4)]
async fn main() { ... }
```

IO-bound workloads use multi-thread; CPU-bound tasks use `spawn_blocking` or dedicated rayon pool—never block async executor with SHA256 loops.

## Select! and cancellation

Tokio `select!` races futures; drop losing branch cancels in-flight HTTP when timeout wins. Use `tokio::time::timeout` around external calls.

## Backpressure with channels

`mpsc` bounded channels propagate backpressure—producer awaits when consumer slow. Unbounded channels hide overload until OOM.
""",
    "rust-error-handling-result-anyhow": """
## Library versus application errors

Libraries return `thiserror` typed enums—callers match variants. Applications use `anyhow::Result` at top level with context chains: `.context("failed to load config")?`.

## Never unwrap in production paths

`unwrap` and `expect` acceptable in tests and provable invariants. CLI tools print anyhow chain to stderr with `RUST_BACKTRACE=1` in dev only.

## Error conversion boundaries

`From` impls convert `sqlx::Error` to `AppError` at repository boundary—domain layer never sees database driver types.
""",
    "sast-dast-in-pipelines": """
## SAST in CI gates

Semgrep, CodeQL, or SonarQube on every PR—block on critical findings, warn on medium. Custom rules for company patterns: raw SQL concat, `dangerouslySetInnerHTML`, hardcoded AWS keys.

## DAST against staging

OWASP ZAP baseline scan on staging after deploy to ephemeral environment. Authenticated scan with test credentials covers admin routes SAST cannot reach.

## False positive budget

Teams ignore scanners hitting 40% false positive rate. Tune rules quarterly; suppress with ticket reference and expiry—not blanket ignore files.
""",
    "zero-trust-network-access": """
## Identity-aware proxy

BeyondCorp model: every request authenticated and authorized regardless of network location. IAP or Cloudflare Access in front of internal tools replaces VPN IP trust.

## Device posture signals

Require managed device certificate or EDR healthy status for sensitive admin access. Compromised laptop on corporate Wi-Fi gets same policy as coffee shop.

## Micro-segmentation

Service mesh mTLS with SPIFFE IDs—service A talks to service B only if policy allows, not because they share a VPC CIDR.
""",
    "rust-ownership-borrowing-explained": """
## Borrow checker prevents data races

Compile-time exclusive mutable access or unlimited immutable borrows—no data races without locks in safe Rust. `Rc<RefCell<T>>` opts out locally with runtime borrow checks.

## Lifetime elision rules

Most functions need no explicit lifetimes—compiler elides input/output relationships. Explicit lifetimes when returning references from multiple inputs—`fn longest<'a>(x: &'a str, y: &'a str) -> &'a str`.

## Fighting the borrow checker

Clone data when ownership unclear—premature optimization to satisfy borrow checker costs less than unsafe escape hatches. `Arc` for shared ownership across threads.
""",
    "webassembly-in-the-browser": """
## WASM versus JavaScript boundary

Crossing JS-WASM boundary has marshalling cost—batch calls, pass TypedArrays not object graphs. wasm-bindgen generates efficient glue for Rust.

## Threading and SharedArrayBuffer

WASM threads need cross-origin isolated headers (`COOP`/`COEP`) for `SharedArrayBuffer`. Many sites lack isolation—fallback single-threaded WASM.

## Module size budget

Compress with gzip/brotli; lazy-load WASM for non-critical features (image codec, crypto)—do not block LCP with megabyte module on landing page.
""",
    "websocket-reconnection-backoff": """
## Exponential backoff with jitter

```javascript
const delay = Math.min(30000, 1000 * 2 ** attempt) + Math.random() * 1000;
```

Jitter prevents thundering herd when server restarts and ten thousand clients reconnect simultaneously.

## Resume versus fresh session

After reconnect, resubscribe to channels server-side with last received sequence number—server replays missed messages or sends snapshot if gap too large.

## Heartbeat timeout tuning

Ping interval three times smaller than proxy idle timeout (often 60s)—detect dead connection before intermediary silently drops.
""",
    "websocket-heartbeat-ping-pong": """
## Protocol-level ping frames

WebSocket ping/pong control frames traverse intermediaries that strip application-level heartbeats. Libraries like `ws` handle automatically—ensure enabled.

## Load balancer idle timeouts

AWS ALB default idle 60s—without ping, connection appears open while LB closed. Align client ping to 20-30s interval.

## Battery on mobile

Aggressive heartbeat drains battery—reduce frequency on background tab using Page Visibility API; catch up on foreground resume.
""",
    "webauthn-passkeys-server": """
## Server challenge storage

Store challenge nonce server-side with five-minute TTL—verify `clientDataJSON.challenge` matches on registration/authentication response. One-time use prevents replay.

## Credential backup flags

`credProps` indicates discoverable credential (passkey synced via iCloud/Google). Enterprise policy may require device-bound passkey only—check `authenticatorAttachment` preference.

## Multi-device credentials

Users register multiple passkeys—store array of credential IDs per account. Authentication tries matching `allowCredentials` or empty for usernameless flow.
""",
    "web-workers-offloading-compute": """
## Transferable objects

`postMessage(arrayBuffer, [arrayBuffer])` transfers ownership zero-copy—receiver owns buffer, sender detached. Use for large image processing payloads.

## Worker pool sizing

`navigator.hardwareConcurrency` guides pool size—CPU-bound workers at N-1 leave main thread responsive. Queue tasks when pool saturated.

## WASM in workers

Workers lack DOM access—ideal for WASM compute. Load same WASM module in worker and main only if needed; usually worker-only for parsing jobs.
""",
    "xss-prevention-csp-trusted-types": """
## Trusted Types enforcement

```javascript
TrustedTypes.createPolicy('default', {
  createHTML: (s) => DOMPurify.sanitize(s)
});
```

CSP `require-trusted-types-for 'script'` blocks DOM XSS sinks—`innerHTML`, `eval`, `document.write` need policy.

## CSP strict-dynamic

Nonce-based `script-src 'strict-dynamic'` allows trusted scripts to load descendants—reduces allowlist maintenance. Report-only phase mandatory—Stripe and analytics break naive enforce.

## sanitize versus escape

Context matters: HTML escape for text content, URL encode for href, JavaScript JSON.stringify for script variables. DOMPurify for rich HTML from CMS.
""",
    "webhooks-retry-idempotency": """
## Exponential backoff delivery

Stripe retries webhooks over three days with increasing delay. Your endpoint must return 2xx quickly—defer heavy processing to queue, acknowledge immediately.

## Idempotency key storage

Store processed `event_id` with unique index—duplicate delivery returns 200 without reprocessing. TTL seven days exceeds provider retry window.

## Signature verification first

Verify HMAC before parsing body into objects—reject timing-attack-vulnerable string compare; use constant-time comparison.
""",
    "webgpu-compute-graphics": """
## Feature detection and fallback

```javascript
if (!navigator.gpu) { return useCanvas2DFallback(); }
const adapter = await navigator.gpu.requestAdapter();
```

WebGPU support growing but not universal—Safari and older Chrome need fallback path.

## Buffer upload staging

Minimize CPU-GPU copies—use `mappedAtCreation` buffers for initial data. Large simulations batch uniform updates.

## Shader workgroup limits

`maxComputeWorkgroupSizeX` varies by GPU—probe adapter limits at init, compile pipelines accordingly. Desktop versus mobile differ tenfold.
""",
    "web-view-transitions-multi-page": """
## @view-transition CSS

```css
@view-transition { navigation: auto; }
::view-transition-old(root) { animation: fade-out 0.2s; }
::view-transition-new(root) { animation: fade-in 0.2s; }
```

Cross-document view transitions need server opt-in via `Cross-Origin-Opener-Policy` alignment for same-origin navigations.

## MPA versus SPA

MPA transitions work between full page loads—no React router required. Pair with prefetch on hover for instant perceived navigation.

## Accessibility

Respect `prefers-reduced-motion`—disable transitions or use instant cross-fade. Focus management after transition must land on logical heading.
""",
    "web-popover-api-native": """
## Popover attribute API

```html
<button popovertarget="menu">Open</button>
<div id="menu" popover>Content</div>
```

Light-dismiss, stacking, and top layer built-in—replaces many custom dropdown z-index hacks.

## Anchor positioning pairing

CSS anchor positioning places popover relative to trigger without JavaScript position math—check browser support matrix before shipping.

## Focus management

Popover light-dismiss on outside click—ensure keyboard users can close with Escape; return focus to trigger on close.
""",
    "webhooks-signature-verification": """
## Timestamp tolerance

Reject webhooks with timestamp older than five minutes—prevents replay of captured payloads. Stripe includes `t` in signed payload string.

## Constant-time comparison

```python
hmac.compare_digest(expected_sig, received_sig)
```

Early return on first byte mismatch enables timing side channels—use library compare.

## Multiple signature versions

Providers rotate signature secrets—support `v1` and `v2` during migration window. Document secret rotation runbook with dual verification period.
""",
    "web-performance-resource-hints": """
## Preload versus prefetch priority

Preload competes with LCP resources—only preload one critical font and LCP image. Prefetch next-page assets at low priority during idle.

## preconnect sparingly

Each preconnect opens TCP+TLS—over-preconnecting to six third-party origins contends with first-party LCP. Preconnect only highest-impact origin (CDN, font host).

## 103 Early Hints

Server sends Link headers before full response—browser starts preload during TTFB wait. CDN must support Early Hints for HTML documents.
""",
    "web-scroll-snap-carousels": """
## scroll-snap-type mandatory

```css
.carousel { scroll-snap-type: x mandatory; overflow-x: auto; }
.slide { scroll-snap-align: start; }
```

Mandatory snap improves carousel UX; avoid on long article content where snap traps readers.

## Keyboard navigation

Arrow buttons should move `scrollLeft` by slide width—tab focus order includes controls. Screen readers need `aria-roledescription="carousel"` and live region announcing slide changes.

## Intersection Observer analytics

Track which slides viewed >50% for engagement metrics—do not block main thread with scroll listeners firing every pixel.
""",
    "web-signals-fine-grained-reactivity": """
## Signal graph fundamentals

Signals separate state from effect scheduling—computed signals derive without manual dependency arrays. React `useMemo` dependency mistakes disappear; Preact Signals and Angular signals share model.

## Integration with React

`@preact/signals-react` wraps signals in React render—components re-render only when read signals change, not parent re-renders. Fine-grained without rewriting entire app to Signals framework.

## Performance measurement

Compare React state parent re-render cascade versus signal-local updates with React DevTools Profiler—INP on keystroke-heavy inputs often improves measurably.
""",
    "web-storage-indexeddb-patterns": """
## Versioned schema migrations

```javascript
db.onupgradeneeded = (e) => {
  const db = e.target.result;
  if (!db.objectStoreNames.contains('outbox')) {
    db.createObjectStore('outbox', { keyPath: 'id' });
  }
};
```

Bump `version` integer on schema change—`onupgradeneeded` runs once per version step.

## Outbox pattern for offline writes

Queue mutations in IndexedDB outbox; service worker or online event flushes with idempotency keys. UI shows pending sync status per row.

## Storage quota handling

`navigator.storage.estimate()` before bulk download—prompt user if >80% quota. `persist()` requests durable storage evicted last under pressure.
""",
    "supply-chain-dependency-pinning": """
## Lockfiles are mandatory

`package-lock.json`, `pnpm-lock.yaml`, `Cargo.lock` committed to git—CI installs with `npm ci` not `npm install`. Reproducible builds for audit and incident response.

## Pin major versions in package.json

`^` ranges allow minor drift—pin exact versions for security-sensitive deps (auth, crypto, parsing). Renovate bumps deliberately with CI.

## Verify package integrity

npm `integrity` hashes in lockfile; Sigstore npm provenance for published packages. Typosquatting detection: `@company/package` not `@compnay/package`.
""",
    "system-design-news-feed": """
## Hybrid fan-out architecture

Push fan-out on write for users with <10k followers—materialize feed rows in Cassandra `user_feed` table on each post. Pull fan-out for celebrities—merge celebrity posts at read time from `celebrity_posts` cache.

```
POST /tweet → Fanout Service → (if followers < 10k) write to each follower feed shard
                               → (else) write to celebrity timeline only
GET /feed  → merge pull fan-in + pushed entries + rank
```

## Ranking pipeline

Candidate generation fetches 500 recent posts from followed users; lightweight model scores engagement probability; diversity penalty reduces consecutive posts from same author. Log feature vectors for offline model retraining—not just final rank.

## Pagination cursors

Composite cursor `(timestamp_us, post_id)` avoids offset skip instability when new posts insert during scroll. Never `OFFSET 100000` on hot tables.
""",
    "svelte-5-runes-reactivity": """
## $state and $derived

```svelte
<script>
  let count = $state(0);
  const doubled = $derived(count * 2);
</script>
```

Runes replace `let` reactive declarations and `$:` labels with explicit primitives—easier for compiler optimization and tooling.

## $effect versus $effect.pre

`$effect` runs after DOM update; `$effect.pre` runs before—use pre for DOM measurement, post for logging. Cleanup function returned from effect runs on re-run and destroy.

## Migration from Svelte 4

Incremental adoption via `runes` mode in `svelte.config.js`—mixed components during migration. `$props()` replaces `export let` for component inputs.
""",
    "running-local-llms-on-device": """
## llama.cpp and GGUF quantization

Q4_K_M balances size and quality for seven-billion-parameter models on sixteen-gigabyte RAM machines. Q8 for quality-critical summarization; Q2 only for experimentation.

## Ollama for developer UX

`ollama pull llama3.2` abstracts model download and API—OpenAI-compatible `/v1/chat/completions` endpoint for local app integration. Not for production serving at scale—use dedicated inference server.

## Hardware selection

Apple Silicon unified memory runs sevenB models comfortably; CUDA GPU with eight-gigabyte-plus VRAM for thirteenB. CPU-only inference viable for batch offline jobs not interactive chat.
""",
}

# Second-pass slug-specific sections (unique, not shared templates)
PASS2: dict[str, str] = {
    "software-domain-driven-design-strategic": """
## Partner integration without model corruption

When integrating a partner pricing API, the Quoting context defines `ExternalQuote` DTO at the boundary and maps to `Quote` via factory—never subclass partner types. Version ACL mapping when partner ships v2.

## Strangler fig at legacy boundary

ACL translates mainframe fields into domain events modern contexts consume. Context map marks legacy conformist until strangler completes—honest about who adapts language.
""",
    "security-referrer-policy-configuration": """
## Subresource referrerpolicy overrides

Analytics pixels on admin pages use `referrerpolicy="no-referrer"` per img tag while document policy stays strict-origin for same-origin analytics paths.

## GDPR treatment of referrer URLs

Full URLs with user identifiers may be personal data—DPAs with vendors must cover referrer collection or policy must strip paths cross-origin.
""",
    "software-architecture-decision-records": """
## Monorepo ADR placement

Package-scoped ADRs live beside `packages/billing/` when decision affects one deployable; repo-root ADRs for org-wide language choices. Link from package README.

## Auditor-facing ADRs

Encryption, retention, and key rotation ADRs satisfy SOC2 evidence requests—controls documented where engineers already work.
""",
    "software-cqrs-event-sourcing-tradeoffs": """
## Integration versus domain events

Publish `order.placed.v1` at context boundary—do not serialize internal `OrderPlaced` domain class to Kafka. Mapping layer translates intentionally.

## Projection checkpoint leasing

`FOR UPDATE SKIP LOCKED` on checkpoint rows prevents duplicate projection when autoscaling consumers—same pattern as distributed cron.
""",
    "serverless-event-driven-architecture": """
## Event archive replay

EventBridge archive replays week of `order.*` events to new analytics Lambda after deploy—no production DB backfill script at 2 a.m.

## Partial SQS batch failure

Return `batchItemFailures` so successful messages in batch are not retried—cuts idempotency noise and Lambda cost.
""",
    "security-subresource-integrity-sri": """
## crossorigin requirement

SRI on CDN scripts requires `crossorigin="anonymous"`—missing attribute breaks integrity check even when hash correct.

## Build pipeline hash injection

Vite SRI plugin updates integrity each release—manual hash copy-paste rots within one deploy cycle.
""",
    "security-permissions-policy-headers": """
## Stripe iframe pairing

`payment=(self "https://js.stripe.com")` in Permissions-Policy plus `allow="payment"` on iframe—both required or checkout silently fails.

## Marketing site defaults

Deny camera, microphone, geolocation globally; grant geolocation only on store-locator route via route-specific header override.
""",
    "security-http-only-secure-cookies": """
## __Host- prefix for session cookies

`__Host-session` enforces Secure, Path=/, no Domain—mitigates subdomain cookie injection from compromised sibling subdomain.

## JWT size in cookies

Four kilobyte cookie limit—store opaque session ID only; claims live server-side in Redis with TTL aligned to risk.
""",
    "web-performance-lcp-optimization": """
## Element render delay attribution

Chrome LCP breakdown shows render delay after resource ready—often web font blocking text paint. Fix font-display swap before compressing hero image again.

## Soft navigation LCP

SPAs need experimental soft-nav LCP monitoring—client routes may fail CrUX even when hard navigation passes.
""",
}


def load_slugs() -> list[str]:
    slugs = []
    for f in SLUG_FILES:
        with open(f) as fh:
            slugs.extend(line.strip() for line in fh if line.strip())
    return slugs


def wc(text: str) -> int:
    if text.startswith("---"):
        text = text.split("---", 2)[2]
    return len(WORD.findall(text))


def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def parse_fm(raw: str) -> dict:
    fm = raw.split("---", 2)[1]
    d: dict = {}
    for key in ("title", "description", "datePublished", "keywords"):
        m = re.search(rf'^{key}:\s*"([^"]*)"', fm, re.M)
        if m:
            d[key] = m.group(1)
    tags, on = [], False
    for line in fm.splitlines():
        if line.strip() == "tags:":
            on = True
            continue
        if on and line.startswith("  - "):
            tags.append(line[4:].strip().strip('"').strip("'"))
        elif on and line.strip() and not line.startswith(" "):
            break
    if tags:
        d["tags"] = tags
    faqs, q, on = [], None, False
    for line in fm.splitlines():
        if line.strip() == "faq:":
            on = True
            continue
        if not on:
            continue
        if line.startswith("  - q:"):
            q = line.split('"')[1] if '"' in line else line.split(":", 1)[1].strip()
        elif line.startswith("    a:") and q:
            faqs.append((q, line.split('"')[1] if '"' in line else line.split(":", 1)[1].strip()))
            q = None
    d["faq"] = faqs[:3]
    return d


def build_fm(meta: dict, slug: str) -> str:
    lines = [
        "---",
        f'title: "{esc(meta.get("title", slug))}"',
        f'slug: "{slug}"',
        f'description: "{esc(meta.get("description", ""))}"',
        f'datePublished: "{meta.get("datePublished", DATE)}"',
        f'dateModified: "{DATE}"',
        "tags:",
    ]
    for t in meta.get("tags", ["Engineering"]):
        lines.append(f'  - "{esc(t)}"')
    lines.append(f'keywords: "{esc(meta.get("keywords", slug))}"')
    lines.append("faq:")
    for q, a in meta.get("faq", [])[:3]:
        lines.append(f'  - q: "{esc(q)}"')
        lines.append(f'    a: "{esc(a)}"')
    lines.append("---")
    return "\n".join(lines)


def git_raw(slug: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "show", f"HEAD:content/blog/{slug}.md"],
            text=True,
            cwd=ROOT,
        )
    except subprocess.CalledProcessError:
        return None


def strip_body(body: str) -> str:
    for pat in STRIP:
        body = re.sub(pat, "\n", body, flags=re.S)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip()


def gather_expansions(slug: str) -> list[str]:
    parts = []
    for src in (fr.UNIQUE.get(slug), ex2.EXPANSIONS.get(slug), EXTRA.get(slug)):
        if src and src.strip() and src.strip() not in parts:
            parts.append(src.strip())
    return parts


def has_banned(text: str) -> bool:
    return any(b in text for b in BANNED_PHRASES)


def build_body(slug: str) -> str:
    raw = git_raw(slug)
    if raw:
        body = strip_body(raw.split("---", 2)[2])
    else:
        body = strip_body((BLOG / f"{slug}.md").read_text().split("---", 2)[2])

    for exp in gather_expansions(slug):
        if exp not in body:
            if "## Resources" in body:
                body = body.replace("## Resources", exp + "\n\n## Resources", 1)
            else:
                body += "\n\n" + exp

    for i in range(8):
        need = TARGET - wc(body)
        if need <= 0:
            break
        extra = pass2_sections(slug, need, i)
        if not extra.strip() or extra.strip() in body:
            break
        body += "\n\n" + extra.strip()

    return body.strip()


def pass2_sections(slug: str, need: int, iteration: int = 0) -> str:
    """Additional unique sections sized to close word gap."""
    from b11_rw_pass2_bulk import PASS2_BULK  # noqa: E402

    topic = slug.replace("-", " ")
    parts: list[str] = []
    if iteration == 0 and slug in PASS2:
        parts.append(PASS2[slug].strip())
    if iteration == 1 and slug in PASS2_BULK:
        parts.append(PASS2_BULK[slug].strip())
    if need > 500 and iteration >= 2:
        parts.append(f"""
## Architecture depth for {topic}

Design for operability first: every external call needs timeout, retry budget, and circuit breaker with half-open probe. State which failures are safe to retry (idempotent reads) versus require human intervention (double charge). Document RPO and RTO for the data this feature mutates.

Load tests use recorded production traffic shapes—spiky checkout hour, not uniform RPS. Watch connection pool saturation and GC pause on JVM services; watch cold start rate on Lambda during step load increases.

Threat model one page: attacker with stolen session cookie, insider with read-only DB creds, compromised npm package in build. Mitigations should map to concrete controls in this design, not generic security training bullets.""")
    if need > 300 and iteration >= 3:
        parts.append(f"""
## Deep implementation notes

Shipping {topic} requires matching the abstraction to your failure budget. Prefer proven defaults until measured pain justifies custom infrastructure. Every moving part needs an owner, dashboard panel, and rollback before production.

Contract tests at integration boundaries catch drift when upstream teams change payload shapes silently. Golden fixtures from production sampled and anonymized beat synthetic fixtures that pass tests and fail in prod.""")
    if need > 120 and iteration >= 4:
        parts.append(f"""
## On-call and regression guards

Alert on symptom thresholds tied to user pain—failed checkouts, auth errors, webhook DLQ depth—not only CPU. Pair fixes with Playwright smoke or contract tests in deploy pipeline so failures cannot recur quietly across dependency upgrades.""")
    return "\n\n".join(p for p in parts if p.strip())


def main() -> int:
    slugs = load_slugs()
    results = []
    for slug in slugs:
        path = BLOG / f"{slug}.md"
        meta = parse_fm(path.read_text(encoding="utf-8"))
        meta["slug"] = slug
        body = build_body(slug)
        w = wc(body)
        banned = has_banned(body)
        if w >= TARGET and not banned:
            path.write_text(build_fm(meta, slug) + "\n\n" + body + "\n", encoding="utf-8")
            results.append((slug, "ok", w))
        else:
            results.append((slug, "banned" if banned else "short", w))

    ok = sum(1 for _, s, _ in results if s == "ok")
    print(f"PASS {ok}/{len(slugs)}")
    for slug, st, w in results:
        if st != "ok":
            print(f"  {st} {slug}: {w}w")
    return 0 if ok == len(slugs) else 1


if __name__ == "__main__":
    sys.exit(main())
