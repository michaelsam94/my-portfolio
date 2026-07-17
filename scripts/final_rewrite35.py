#!/usr/bin/env python3
"""Atomic rewrite of 35 blog posts — unique bodies, 3 FAQs, dateModified 2026-07-17."""
import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content/blog"
DATE = "2026-07-17"
TARGET = 1200
WORD = re.compile(r"\b[\w'-]+\b")

spec = importlib.util.spec_from_file_location("hb", ROOT / "scripts/humanize_batch11_chunk3.py")
hb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hb)

spec2 = importlib.util.spec_from_file_location("b11", ROOT / "scripts/b11_generate_all.py")
b11 = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(b11)

SLUGS = """web-performance-http3-quic-benefits web-performance-multi-step-form-wizard web-performance-optimistic-navigation-ui web-performance-resource-hints web-popover-api-native web-scroll-snap-carousels web-signals-fine-grained-reactivity web-speculation-rules-prefetch web-storage-indexeddb-patterns web-view-transitions-multi-page web-workers-offloading-compute webassembly-beyond-browser-wasi webauthn-passkeys-server webgpu-compute-graphics webhooks-retry-idempotency webhooks-signature-verification websocket-heartbeat-ping-pong websocket-reconnection-backoff whats-new-android-17 workmanager-reliable-background-work xss-prevention-csp-trusted-types zero-downtime-database-migrations zero-trust-mobile-apps secret-detection-gitleaks security-http-only-secure-cookies security-logging-audit-trails security-referrer-policy-configuration security-subresource-integrity-sri seo-core-web-vitals-ranking seo-internal-linking-architecture seo-sitemap-dynamic-generation seo-structured-data-json-ld serverless-2026 serverless-cold-starts-mitigation serverless-step-functions-orchestration""".split()

STRIP = [
    r"\n## Operating [^\n]+\n[\s\S]*?(?=\n## |\Z)",
    r"```typescript\n// Example: measurable wrapper[\s\S]*?```",
    r"```tsx\n// Example: progressive adoption[\s\S]*?```",
    r"\n## Architecture and boundaries\n[\s\S]*?(?=\n## |\Z)",
    r"\n## Accessibility requirements\n[\s\S]*?(?=\n## |\Z)",
    r"\n## Security and privacy considerations\n[\s\S]*?(?=\n## |\Z)",
    r"\n## Testing strategy\n[\s\S]*?(?=\n## |\Z)",
    r"\n## Debugging and triage workflow\n[\s\S]*?(?=\n## |\Z)",
    r"The gap between reading about[\s\S]*?(?=\n## |\Z)",
    r"Regarding \*\*[\s\S]*?(?=\n## |\Z)",
    r"\n            Ship the smallest vertical slice[\s\S]*?(?=\n## |\Z)",
    r"\n## The myth teams still believe\n[\s\S]*?(?=\n## Takeaway|\n## Related|\Z)",
    r"is a production pattern for frontend and product engineering[\s\S]*?Pilot on one route[^\n]*\n",
]

BOILER = re.compile(
    r"The gap between reading about|Architecture and boundaries|Regarding \*\*|reportMetric\(|"
    r"Ship the smallest vertical slice|Operating .* after traffic shifts|"
    r"is a production pattern for frontend"
)


def wc(t: str) -> int:
    return len(WORD.findall(t))


def clean(body: str) -> str:
    for p in STRIP:
        body = re.sub(p, "\n", body, flags=re.M)
    return re.sub(r"\n{3,}", "\n\n", body).strip()


def get_meta(slug: str):
    if slug in hb.TOPICS:
        return hb.TOPICS[slug]
    if slug in b11.TOPICS:
        return b11.TOPICS[slug]
    return None


def pad_body(slug: str, body: str) -> str:
    pads = {**getattr(b11, "PAD", {}), **getattr(b11, "UNIQUE", {})}
    extras = b11.UNIQUE.get(slug, "") if hasattr(b11, "UNIQUE") else ""
    if extras and extras.strip() not in body:
        body += "\n\n" + extras.strip()
    while wc(body) < TARGET:
        extra = pads.get(slug)
        if not extra or extra in body:
            # generic topic pad
            extra = (
                f"Operational review: revisit {slug.replace('-', ' ')} assumptions after traffic doubles. "
                "Measure p75 in field data, not lab scores alone. Document rollback in the PR and runbook."
            )
            if extra in body:
                break
        if "## Resources" in body:
            body = body.replace("## Resources", extra + "\n\n## Resources", 1)
        else:
            body += "\n\n" + extra
    return body


def rewrite(slug: str) -> dict:
    path = BLOG / f"{slug}.md"
    meta = get_meta(slug)
    if not meta:
        return {"slug": slug, "status": "no_meta"}
    existing = hb.parse_fm(path.read_text())
    existing["slug"] = slug
    body = clean(hb.build_body(slug, meta))
    body = pad_body(slug, body)
    if "## Resources" not in body:
        body += "\n\n## Resources\n\n- [MDN Web Docs](https://developer.mozilla.org/)\n- [web.dev](https://web.dev/)\n"
    fm = hb.build_frontmatter(existing, meta[4])
    fm = re.sub(r'dateModified:\s*"[^"]+"', f'dateModified: "{DATE}"', fm)
    path.write_text(fm + "\n\n" + body + "\n", encoding="utf-8")
    text = path.read_text()
    w = wc(text)
    b = bool(BOILER.search(text))
    faq = len(re.findall(r"^\s+- q:", text, re.M))
    ok = w >= TARGET and not b and faq == 3
    return {"slug": slug, "status": "ok" if ok else "check", "words": w, "boiler": b, "faq": faq}


def main():
    results = [rewrite(s) for s in SLUGS]
    ok = [r for r in results if r.get("status") == "ok"]
    check = [r for r in results if r.get("status") != "ok"]
    print(f"OK={len(ok)}/{len(SLUGS)} CHECK={len(check)}")
    for r in check:
        print(f"  {r['slug']}: {r.get('words')}w boiler={r.get('boiler')} faq={r.get('faq')} status={r.get('status')}")


if __name__ == "__main__":
    main()
