---
title: "Implementing Passkeys on the Server"
slug: "webauthn-passkeys-server"
description: "Implement WebAuthn/passkeys server-side: challenge generation, attestation vs assertion, storing public keys, and migration off passwords."
datePublished: "2026-05-22"
dateModified: "2026-05-22"
tags: ["Security", "Authentication", "Web"]
keywords: "WebAuthn server, passkeys implementation, FIDO2 relying party, attestation statement, credential public key storage"
faq:
  - q: "What does the server store for a passkey?"
    a: "The credential ID, the public key, the signature counter (if used), user handle, and metadata (AAGUID, transports). Never a private key — that stays on the authenticator or platform cloud-synced vault."
  - q: "Should I require attestation?"
    a: "Usually no for consumer passkeys — attestation adds complexity and privacy trade-offs. Prefer none/self-attestation for most apps; require attestation only when enterprise policy demands specific authenticators."
  - q: "How do passkeys relate to sessions?"
    a: "WebAuthn proves possession at login (or step-up). After verification, establish your normal session (cookie/token). Passkeys replace password verification, not your entire session architecture."
---

Passkeys move phishing-resistant auth into the platform authenticator. The server's job is a correct relying party: generate challenges, verify signatures, store public keys, and bind credentials to users. Most bugs are wrong origin/RP ID checks or inventing crypto instead of using a vetted library.

## Registration (attestation ceremony)

1. Client asks server for create options (`challenge`, `user`, `rp`, `pubKeyCredParams`)
2. Authenticator creates key pair; client returns attestation
3. Server verifies challenge, origin, RP ID; stores credential ID + public key

## Authentication (assertion)

1. Server issues challenge (+ allowCredentials optional)
2. Client signs with passkey
3. Server verifies signature over authenticator data + client data; check challenge & origin

```typescript
// Conceptual — use @simplewebauthn/server or similar
const options = await generateRegistrationOptions({
  rpName: "Example",
  rpID: "example.com",
  userName: user.email,
});
// save options.challenge on server keyed by user/session
```

## Migration

Offer passkeys alongside passwords; prompt after successful password login. Don't force a hard cutover until recovery paths (email, backup codes, second passkey) exist.

## Pitfalls

- `localhost` vs production RP IDs
- Forgetting to invalidate challenges after use
- Treating WebAuthn as session storage

Pair with [OIDC](https://blog.michaelsam94.com/oidc-openid-connect-explained/) when an IdP manages passkeys for you — many apps should buy, not build.

## Passkey recovery flows

Users lose devices. Provide account recovery via:
- Backup passkeys on secondary devices
- Hardware security key registration
- Recovery codes (single-use, stored hashed)

Never fall back to SMS-only recovery for accounts that support passkeys — SMS is weaker than the passkey you're replacing.

## Enterprise attestation

For managed devices, require specific authenticator attestation formats. Parse attestation objects during registration to verify the authenticator meets corporate policy (e.g., platform authenticator with user verification).

## Measuring success in production

Deploy changes behind feature flags when possible so you can compare metrics between control and treatment groups. Use Real User Monitoring to capture performance data from actual devices and network conditions — lab tools alone miss the long tail of user experiences. Set up alerts for regressions: a 10% LCP increase week-over-week warrants investigation before it hits CrUX.

Document your baseline metrics before making changes. Performance work without measurement is guesswork. Share results with the team — concrete numbers ("LCP improved 800ms on mobile") build support for continued investment in web performance and reliability.

Review changes quarterly. Browser updates, new API support, and traffic pattern shifts can obsolete previous optimizations or create new opportunities. What worked in 2024 may not be the best approach in 2026.

## Additional production considerations

Teams often underestimate the maintenance cost of performance optimizations. Automate what you can: CI bundle budgets, Lighthouse CI on PRs, and RUM dashboards that alert on regressions. Manual audits don't scale past a handful of pages.

Security and performance intersect more than teams expect. Third-party scripts that hurt INP also expand your attack surface. Self-hosting fonts and critical assets reduces both latency and supply-chain risk. Review every external dependency quarterly — remove what you no longer need.

Accessibility and performance share goals: semantic HTML helps screen readers and gives the browser better rendering hints. Native elements like dialog, popover, and details reduce JavaScript while improving accessibility. Prefer platform features over custom implementations when they meet your requirements.

Mobile users dominate traffic for most sites. Test on real mid-tier Android hardware, not just desktop Chrome. Simulated throttling in DevTools approximates network conditions but not CPU constraints. A fix that helps desktop may be invisible on mobile if the bottleneck is JavaScript execution, not network.

Collaborate with backend teams on TTFB and API response times. Frontend optimizations can't fix a 2-second server response. Set SLAs for API endpoints that feed critical pages and measure them in the same RUM pipeline as Core Web Vitals.

## Debugging checklist

When something doesn't work as documented, verify browser support with Can I use before assuming a polyfill bug. Check the Network tab for failed resource loads, incorrect MIME types, and missing CORS headers. Use the Console for CSP violations and Trusted Types errors that silently block operations.

Compare behavior in incognito mode to rule out extension interference. Test with cache disabled during development but validate with realistic caching in staging. Read the specification for edge cases the tutorial skipped — MDN examples cover happy paths, not every boundary condition.

If performance regresses after deployment, roll back first and investigate second. Keep a changelog of performance-related changes linked to metric dashboards. Future you will need to know why that preload tag exists before removing it during a refactor.

## Integration with your stack

Every technique in this guide adapts to your framework and hosting environment. Next.js, Nuxt, Rails, and Django each have conventions for where static assets live, how SSR works, and where to inject resource hints. Map the concepts here to your stack's documentation rather than copying snippets verbatim.

Staging environments should mirror production CDN configuration, HTTP/2 settings, and compression. A fix validated locally over HTTP/1.1 without compression may behave differently behind Cloudflare or Fastly. Deploy performance changes to a canary percentage before full rollout when your platform supports it.

Train the team on these patterns during code review. Performance regressions usually arrive as small PRs — one unoptimized image, one synchronous script, one missing width attribute. Reviewers who recognize LCP and CLS anti-patterns catch issues before they reach production.

## Key takeaways

Start with measurement, ship the smallest fix that addresses the root cause, and validate in field data. Performance and security work is never finished — it evolves with your product, traffic, and the browser platform. Return to these patterns when onboarding new team members or auditing legacy code paths.

## Resources

- [W3C WebAuthn](https://www.w3.org/TR/webauthn-3/)
- [SimpleWebAuthn](https://simplewebauthn.dev/)
- [passkeys.dev](https://passkeys.dev/)
---
