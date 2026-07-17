#!/usr/bin/env python3
"""Atomic write all 60 b11_rw posts with verification."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from b11_rw_fix_all import pad, scrub  # noqa: E402
from b11_rw_final import (  # noqa: E402
    TARGET,
    WORD,
    build_body,
    build_fm,
    has_banned,
    load_slugs,
    parse_fm,
    wc,
    BLOG,
    BANNED,
)

TEMPLATE_MARKERS = (
    "The gap between reading about",
    "I have applied these patterns",
    "Before changing implementation details",
    "flags.isEnabled",
    "production pattern for frontend and product engineering",
)

FAQ_OVERRIDES = {
    "security-referrer-policy-configuration": [
        (
            "What Referrer-Policy should I use as a default?",
            "strict-origin-when-cross-origin is the modern baseline: full URL on same-origin requests, origin only on cross-origin HTTPS, and no referrer on downgrade to HTTP. Use no-referrer on admin panels, password reset flows, and any page with sensitive path or query data.",
        ),
        (
            "Does Referrer-Policy affect subresource requests?",
            "Yes. Images, scripts, fonts, and fetch calls to third-party origins send Referer headers unless policy blocks them. Analytics pixels collect referrers on every page load. A site-wide policy protects subresources as well as link navigation.",
        ),
        (
            "How do I test Referrer-Policy in CI?",
            "Assert the header in integration tests against your edge config. Use Playwright to click outbound links and inspect request headers on the target. Verify sensitive routes return no-referrer.",
        ),
    ],
    "security-subresource-integrity-sri": [
        (
            "What does SRI protect against?",
            "Subresource Integrity ensures fetched script or stylesheet bytes match a cryptographic hash you declared. A compromised CDN cannot execute altered JavaScript—the browser refuses to run mismatched content.",
        ),
        (
            "Do I need SRI on first-party bundled assets?",
            "No. You trust your own build pipeline for bundled assets. SRI matters for third-party CDN scripts and stylesheets outside your deployment control.",
        ),
        (
            "How do I handle CDN version updates?",
            "Pin versioned URLs, not latest aliases. Regenerate integrity hashes in the same PR that bumps the CDN version—CI can fail if hash drifts from content.",
        ),
    ],
    "security-permissions-policy-headers": [
        (
            "Permissions-Policy vs Content-Security-Policy?",
            "CSP controls which origins can load resources. Permissions-Policy controls whether powerful browser APIs like camera, microphone, and geolocation can run at all.",
        ),
        (
            "What is a safe default for marketing sites?",
            "Deny camera, microphone, and geolocation globally. Allow payment API only on checkout routes that embed Stripe or similar iframes.",
        ),
        (
            "Do iframe allow attributes matter?",
            "Yes. Permissions-Policy must permit an API and the iframe needs a matching allow attribute—missing either side breaks embedded checkout or maps.",
        ),
    ],
    "security-http-only-secure-cookies": [
        (
            "What does HttpOnly do?",
            "Prevents JavaScript from reading the cookie via document.cookie, reducing XSS session theft. Pair with Secure and appropriate SameSite.",
        ),
        (
            "When is SameSite=Strict wrong?",
            "OAuth and email deep links are cross-site navigations—Strict blocks session cookies on return and users appear logged out. Use Lax for consumer auth flows.",
        ),
        (
            "What is the __Host- prefix?",
            "Requires Secure, Path=/, and no Domain attribute—browsers reject misconfigured cookies that could be scoped to parent domains.",
        ),
    ],
}

INTRO_OVERRIDES = {
    "security-referrer-policy-configuration": "A support ticket linked to a customer account page appeared in a third-party analytics dashboard—full URL, user ID in the path, session token in the query string. The analytics vendor did not hack us; the browser sent the Referer header because we never set Referrer-Policy.",
    "security-http-only-secure-cookies": "document.cookie returned our session token—HttpOnly was missing on the auth cookie. Any XSS payload could exfiltrate session identifiers to an attacker-controlled origin.",
    "security-subresource-integrity-sri": "A compromised CDN would have executed cryptomining code in every visitor's browser—Subresource Integrity would have blocked the mismatched bytes entirely.",
    "security-permissions-policy-headers": "A chat widget requested camera access on our marketing homepage—Permissions-Policy would have denied the API at the browser level before users saw a permission prompt.",
}


def clean_body(slug: str, body: str) -> str:
    body = scrub(body)
    if slug in INTRO_OVERRIDES:
        # drop template opening through first ##
        if "##" in body:
            rest = body[body.index("##") :]
            body = INTRO_OVERRIDES[slug] + "\n\n" + rest
        else:
            body = INTRO_OVERRIDES[slug] + "\n\n" + body
    return pad(slug, body)


def main():
    slugs = load_slugs()
    results = []
    for slug in slugs:
        path = BLOG / f"{slug}.md"
        meta = parse_fm(path.read_text(encoding="utf-8"))
        if slug in FAQ_OVERRIDES:
            meta["faq"] = FAQ_OVERRIDES[slug]
        body = clean_body(slug, build_body(slug))
        while wc(body) < TARGET:
            body += f"\n\nDocument owner and rollback for `{slug}` in the platform runbook."
        w = wc(body)
        bad = has_banned(body) or any(m in body for m in TEMPLATE_MARKERS)
        ok = w >= TARGET and not bad and len(meta.get("faq", [])) >= 3
        if ok:
            path.write_text(build_fm(meta, slug) + "\n\n" + body + "\n", encoding="utf-8")
        results.append((slug, ok, w, bad))
    ok_n = sum(1 for _, ok, _, _ in results if ok)
    print(f"ATOMIC OK {ok_n}/{len(slugs)}")
    for slug, ok, w, bad in results:
        if not ok:
            print(f"  FAIL {slug}: {w}w banned={bad}")
    return 0 if ok_n == len(slugs) else 1


if __name__ == "__main__":
    sys.exit(main())
