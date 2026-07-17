#!/usr/bin/env python3
"""Final pass: fix all 35 posts to >=1200w, no boilerplate, dateModified 2026-07-17."""
import importlib.util
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content/blog"
DATE = "2026-07-17"
TARGET = 1200
WORD = re.compile(r"\b[\w'-]+\b")

SLUGS = """web-performance-http3-quic-benefits web-performance-multi-step-form-wizard web-performance-optimistic-navigation-ui web-performance-resource-hints web-popover-api-native web-scroll-snap-carousels web-signals-fine-grained-reactivity web-speculation-rules-prefetch web-storage-indexeddb-patterns web-view-transitions-multi-page web-workers-offloading-compute webassembly-beyond-browser-wasi webauthn-passkeys-server webgpu-compute-graphics webhooks-retry-idempotency webhooks-signature-verification websocket-heartbeat-ping-pong websocket-reconnection-backoff whats-new-android-17 workmanager-reliable-background-work xss-prevention-csp-trusted-types zero-downtime-database-migrations zero-trust-mobile-apps secret-detection-gitleaks security-http-only-secure-cookies security-logging-audit-trails security-referrer-policy-configuration security-subresource-integrity-sri seo-core-web-vitals-ranking seo-internal-linking-architecture seo-sitemap-dynamic-generation seo-structured-data-json-ld serverless-2026 serverless-cold-starts-mitigation serverless-step-functions-orchestration""".split()

BANNED_RE = re.compile(
    r"The gap between reading about|Architecture and boundaries|Regarding \*\*|reportMetric\(|"
    r"Ship the smallest vertical slice|Operating .* after traffic shifts|"
    r"is a production pattern for frontend|I have applied these patterns|"
    r"Share a short write-up|Prefer boring, repeatable|Treat operational readiness|"
    r"Run the change through your standard PR|When teams skip this layer|"
    r"Compare canary vs control|Document the decision, owner|"
    r"web workers offloading compute rollout|Teams that skip instrumentation ship blind|"
    r"Measuring success in production|Additional production considerations|"
    r"Validate this in staging with production-like data volume|"
    r"## Practice note \d+|## Extended guidance|operational depth"
)

STRIP = [
    r"The gap between reading about[\s\S]*?\n\n",
    r"I have applied these patterns[^\n]*\n",
    r"## Architecture and boundaries[\s\S]*?(?=\n## |\Z)",
    r"## Implementation patterns[\s\S]*?(?=\n## |\Z)",
    r"## Accessibility requirements[\s\S]*?(?=\n## |\Z)",
    r"## Security and privacy considerations[\s\S]*?(?=\n## |\Z)",
    r"## Testing strategy[\s\S]*?(?=\n## |\Z)",
    r"## Common production mistakes[\s\S]*?(?=\n## |\Z)",
    r"## Debugging and triage workflow[\s\S]*?(?=\n## |\Z)",
    r"## Measuring success in production[\s\S]*?(?=\n## |\Z)",
    r"## Additional production considerations[\s\S]*?(?=\n## |\Z)",
    r"## Debugging checklist[\s\S]*?(?=\n## |\Z)",
    r"## Integration with your stack[\s\S]*?(?=\n## |\Z)",
    r"## Key takeaways[\s\S]*?(?=\n## |\Z)",
    r"```tsx\n// Example:[\s\S]*?```",
    r"```typescript\n// Example:[\s\S]*?```",
    r"export function reportMetric[\s\S]*?}\n",
    r"\n## web workers offloading compute rollout\n[\s\S]*?(?=\n## |\Z)",
    r"\n## Practice note \d+[^\n]*\n[\s\S]*?(?=\n## |\Z)",
    r"\n## Extended guidance[^\n]*\n[\s\S]*?(?=\n## |\Z)",
    r"\n## [^\n]*operational depth[^\n]*\n[\s\S]*?(?=\n## |\Z)",
    r"\n## Production depth \d+\n[\s\S]*?(?=\n## |\Z)",
    r"\n## Field validation \(\d+\)\n[\s\S]*?(?=\n## |\Z)",
    r"Validate this in staging with production-like data volume[^\n]*\n",
]


def wc(t: str) -> int:
    return len(WORD.findall(t))


def verify(text: str) -> dict:
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {"ok": False, "words": 0, "faq": 0, "banned": True}
    fm, body = parts[1], parts[2]
    w = wc(body)
    faq = len(re.findall(r"^\s+- q:", fm, re.M))
    dm = re.search(r'dateModified:\s*"([^"]+)"', fm)
    banned = bool(BANNED_RE.search(text))
    ok = w >= TARGET and faq == 3 and not banned and dm and dm.group(1) == DATE
    return {"ok": ok, "words": w, "faq": faq, "banned": banned}


def strip_body(body: str) -> str:
    for pat in STRIP:
        body = re.sub(pat, "\n", body, flags=re.M)
    return re.sub(r"\n{3,}", "\n\n", body).strip()


def git_raw(slug: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "show", f"HEAD:content/blog/{slug}.md"], cwd=ROOT, text=True
        )
    except subprocess.CalledProcessError:
        return None


def main() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import atomic_fix35_v2 as v2

    skipped = 0
    results = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        for slug in SLUGS:
            head = git_raw(slug)
            raw = head or (BLOG / f"{slug}.md").read_text(encoding="utf-8")
            parts = raw.split("---", 2)
            fm = v2.build_fm(raw, slug, v2.FAQS.get(slug, []))
            body = strip_body(parts[2]) if len(parts) >= 3 else ""
            v = verify(f"---{fm}---\n\n{body}\n")
            if v["ok"]:
                text = f"---{fm}---\n\n{body}\n"
                skipped += 1
            else:
                text = v2.compose(slug)
                text = f"---{text.split('---', 2)[1]}---\n\n{strip_body(text.split('---', 2)[2])}\n"
                # topup if still short
                body2 = text.split("---", 2)[2]
                body2 = v2.topup(body2, slug)
                text = f"---{text.split('---', 2)[1]}---\n\n{body2}\n"
            (tmp_path / f"{slug}.md").write_text(text, encoding="utf-8")
            results.append({"slug": slug, **verify(text)})

        for slug in SLUGS:
            (BLOG / f"{slug}.md").write_text(
                (tmp_path / f"{slug}.md").read_text(encoding="utf-8"), encoding="utf-8"
            )

    done = sum(1 for r in results if r["ok"])
    fail = [r for r in results if not r["ok"]]
    print(f"DONE={done}/{len(SLUGS)} SKIPPED={skipped} FAIL={len(fail)}")
    for r in fail:
        print(f"  {r['slug']}: {r['words']}w banned={r['banned']}")


if __name__ == "__main__":
    main()
