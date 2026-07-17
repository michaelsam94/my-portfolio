---
title: "Subresource Integrity for Third-Party Scripts"
slug: "security-subresource-integrity-sri"
description: "SRI hashes detect CDN tampering — integrity attribute, fallback when hash rotates, and CSP require-sri-for."
datePublished: "2026-10-20"
dateModified: "2026-07-17"
tags: ["Security", "SRI", "CDN"]
keywords: "Subresource Integrity SRI, integrity attribute CDN, script integrity"
faq:
  - q: "What does SRI protect?"
    a: "Ensures fetched script or stylesheet bytes match the hash you declared."
  - q: "Bundled first-party assets?"
    a: "No SRI needed — you trust your build pipeline."
  - q: "CDN updates?"
    a: "Pin versioned URLs; regenerate hash in the same PR as version bump."
---

The analytics vendor served JavaScript from a CDN with a versioned path. We trusted TLS and DNS and skipped integrity attributes—until a supply-chain advisory proved that CDN edge compromise had happened elsewhere in the industry. Subresource Integrity turns "we hope the CDN is honest" into "the browser verifies bytes before execute."

SRI is not paranoia about major CDNs. It is cheap insurance when a single script tag runs with full page privileges and your CSP still allows that origin.

## Threat model SRI addresses

Attackers who compromise CDN credentials, BGP-hijack traffic, or inject malicious builds into vendor release pipelines change file contents without changing the URL your HTML references. TLS authenticates the connection, not the file at the other end if the server itself serves malware.

SRI adds a cryptographic hash check:

```html
<script
  src="https://cdn.example.com/lib/analytics-v3.2.1.min.js"
  integrity="sha384-oqVuAfXRKap7fdgcCY5uykM6+R9GqQ8K/uxy9rx7HNQlGYl1kPzQho1wx4JwY8wC"
  crossorigin="anonymous"
></script>
```

If bytes differ, the browser blocks execution and fires a console error—fail closed.

## crossorigin is mandatory

SRI on cross-origin resources requires CORS-enabled responses and the `crossorigin="anonymous"` attribute on the tag. Without it, browsers may omit CORS mode and integrity verification fails even when the hash is correct.

Verify CDN sends `Access-Control-Allow-Origin` appropriate for anonymous use. Self-hosted copies through your origin avoid CORS complexity but shift operational burden to you.

## First-party versus third-party scope

| Asset source | SRI needed? | Reason |
| --- | --- | --- |
| Webpack/Vite bundle on your domain | No | CI builds artifact you deploy |
| npm package copied into `/static` | No | Same pipeline control |
| Google Tag Manager container | Partial | Container loads dynamic tags—hash outer loader only |
| Stripe.js from js.stripe.com | Yes if policy requires | Vendor-controlled bytes |
| Font Awesome CDN CSS | Yes | Stylesheets also execute in CSS injection contexts |

Focus SRI effort on scripts with DOM and network access from high-trust CDNs you do not build.

## Generating hashes reliably

OpenSSL one-off:

```bash
curl -s https://cdn.example.com/lib/v1/app.js | openssl dgst -sha384 -binary | openssl base64 -A
```

Prefix with algorithm: `sha384-…`. Prefer sha384 or sha512; sha256 remains common.

Build pipeline injection avoids manual copy-paste rot:

```javascript
// vite.config.js with vite-plugin-sri (conceptual)
import { sri } from "vite-plugin-sri";
export default { plugins: [sri({ algorithms: ["sha384"] })] };
```

HTML templates receive updated integrity on each release. Manual hashes in JSX without automation fail within one deploy cycle.

## CSP require-sri-for escalation

Content-Security-Policy can mandate SRI:

```http
Content-Security-Policy: require-sri-for script;
```

Start in report-only combined with existing script-src allowlist. Third-party widgets without integrity will fail until self-hosted or vendor publishes hashes—inventory before enforce.

Pair with strict script-src to prevent attackers loading unintegrity-checked scripts from allowed origins.

## Fallback strategies when SRI blocks

Production outages occur when vendors patch hotfixes without notifying integrators. Mitigations:

- Pin exact version paths, subscribe to vendor security mailing lists
- Self-host critical libraries with your own integrity checks in CI
- Feature flag non-critical third-party scripts off when integrity fails
- Monitor console error rates for SRI failure messages after CDN deploys

Some teams mirror CDN files to their origin nightly with internal hash verification—SRI then covers same-origin path with hash generated from mirror job.

## Interaction with caching

CDNs cache by URL. Integrity hash is tied to URL plus content. If vendor serves byte-range requests or compresses differently per edge, hashes remain stable on full file content—verify against full download, not partial.

Service workers intercepting script requests must not serve stale mismatched content—bust caches on integrity updates.

## Testing in CI

Fetch pinned URLs in CI, compute hash, compare to committed HTML template values. Fail build on drift. Include check in supply-chain security review for new third-party embeds.

Playwright smoke test: page loads without script integrity errors in console for critical flows.

## Common mistakes

- Omitting `crossorigin="anonymous"`
- Using `latest` or unpinned CDN URLs
- Updating URL without hash in same commit
- Applying SRI to inline scripts (use CSP nonces instead)
- Assuming SRI replaces CSP—it does not stop first-party XSS

## Vendor negotiation

Enterprise contracts can require vendors publish integrity hashes in documentation or npm package metadata. Open-source CDNs like cdnjs expose SRI values on file pages—copy from authoritative source, not blog posts.

When vendor refuses pinning, self-host or accept risk explicitly in security review minutes.

## Sustaining production quality

Store third-party script inventory in repo JSON with URL, integrity, owner team, and review date. PRs adding external scripts must update inventory and CI hash verification. When vendors cannot support SRI, document accepted risk and iframe isolation alternative in security review ticket.

## Version pinning workflow

Third-party script URL changes require hash update in the same PR. CI fails when fetched bytes do not match declared integrity attribute.

## require-sri-for rollout

Enable CSP `require-sri-for script` in report-only first. Third-party widgets without SRI will break until self-hosted or vendor provides hashes.

## Resources

- [MDN Subresource Integrity](https://developer.mozilla.org/en-US/docs/Web/Security/Subresource_Integrity)
- [W3C SRI specification](https://www.w3.org/TR/SRI/)
- [web.dev SRI guide](https://web.dev/articles/sri)
- [cdnjs SRI hashes](https://cdnjs.com/)
- [CSP require-sri-for](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Security-Policy/require-sri-for)

## Operational checklist (1)

Before promoting Security Subresource Integrity Sri changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Field validation (2)

Re-baseline Security Subresource Integrity Sri after browser upgrades or CDN configuration changes. Mobile share above seventy percent shifts median device class — optimizations tuned on desktop lab profiles may not transfer.

## Coordination (3)

Align with platform and backend owners on cache TTL, deploy windows, and API contracts when Security Subresource Integrity Sri touches shared infrastructure — single-layer wins often disappear when another tier invalidates caches.

## Operational checklist (4)

Before promoting Security Subresource Integrity Sri changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Field validation (5)

Re-baseline Security Subresource Integrity Sri after browser upgrades or CDN configuration changes. Mobile share above seventy percent shifts median device class — optimizations tuned on desktop lab profiles may not transfer.

## Coordination (6)

Align with platform and backend owners on cache TTL, deploy windows, and API contracts when Security Subresource Integrity Sri touches shared infrastructure — single-layer wins often disappear when another tier invalidates caches.

## Operational checklist (7)

Before promoting Security Subresource Integrity Sri changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Field validation (8)

Re-baseline Security Subresource Integrity Sri after browser upgrades or CDN configuration changes. Mobile share above seventy percent shifts median device class — optimizations tuned on desktop lab profiles may not transfer.

## Coordination (9)

Align with platform and backend owners on cache TTL, deploy windows, and API contracts when Security Subresource Integrity Sri touches shared infrastructure — single-layer wins often disappear when another tier invalidates caches.

## Operational checklist (10)

Before promoting Security Subresource Integrity Sri changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Invariants to enforce for security subresource integrity sri

Name three invariants that must hold after every deploy of security subresource integrity sri. Encode at least one in an automated test that fails when the invariant is disabled. Reviewers should reject PRs that only cover the primary UI path.

| Check | Expected for security subresource integrity sri |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 1: inject the failure mode you fear for security subresource integrity sri in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Telemetry and ownership for security subresource integrity sri

Pair a leading operational signal with a lagging user or risk outcome. Page on burn related to security subresource integrity sri, not vanity counters. Keep a named owner and a dashboard link in the service catalog entry.

Concrete probe 2: inject the failure mode you fear for security subresource integrity sri in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Rollout sequence for security subresource integrity sri

Prefer flags, weighted routes, or dual-running configs. Rehearse rollback once in staging. The on-call note for security subresource integrity sri should include the revert command and the expected user-visible effect within five minutes.

| Check | Expected for security subresource integrity sri |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 3: inject the failure mode you fear for security subresource integrity sri in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Cross-team contracts for security subresource integrity sri

Document producers, consumers, timeouts, and idempotency keys. Silent schema or policy changes are how security subresource integrity sri breaks without a clear owner in the incident channel.

Concrete probe 4: inject the failure mode you fear for security subresource integrity sri in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Capacity and cost notes for security subresource integrity sri

Estimate QPS, payload size, cardinality, and downstream saturation. Functionally correct security subresource integrity sri changes still cause outages through pool exhaustion, crawl waste, or CPU amplification.

| Check | Expected for security subresource integrity sri |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 5: inject the failure mode you fear for security subresource integrity sri in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Reviewer checklist for security subresource integrity sri

Ask what happens when the dependency is slow, when authz is skipped on batch jobs, and when clients retry. Those three questions catch most security subresource integrity sri regressions before production.

Concrete probe 6: inject the failure mode you fear for security subresource integrity sri in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Incident patterns around security subresource integrity sri

Most incidents involving security subresource integrity sri start as a silent drift: a secondary path skips the control, a retry amplifies load, or a config default from a tutorial ships to production. Write the failure story before the happy path.

| Check | Expected for security subresource integrity sri |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 7: inject the failure mode you fear for security subresource integrity sri in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.
