#!/usr/bin/env python3
"""Final pass: best body per slug, strip boilerplate, expand to 1200+, fix FAQ/date."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLOG = ROOT / "content/blog"
SCRIPTS = Path(__file__).parent
DATE = "2026-07-17"
TARGET = 1200
WORD = re.compile(r"\b[\w'-]+\b")
BANNED = [
    "Validate this in staging",
    "Additional production considerations",
    "Measuring success in production",
    "We keep a living FAQ",
    "Document the decision, owner",
    "production pattern for frontend",
    "Architecture and boundaries",
    "The gap between reading about",
]

STRIP = [
    r"\n## Common production mistakes\n[\s\S]*?(?=\n## Resources|\Z)",
    r"The gap between reading about[\s\S]*?\n\n",
    r"## Architecture and boundaries[\s\S]*?(?=\n## |\n## Resources|\Z)",
    r"## Implementation patterns[\s\S]*?(?=\n## |\n## Resources|\Z)",
    r"Validate this in staging[\s\S]*?(?=\n\n|\Z)",
    r"Document the decision, owner[\s\S]*?(?=\n\n|\Z)",
    r"\n## Operating [^\n]+\n[\s\S]*?(?=\n## |\Z)",
    r"\n## Follow-up\n[\s\S]*?(?=\n## |\Z)",
    r"\n## Deep dive: edge case[^\n]*\n[\s\S]*?(?=\n## |\Z)",
    r"\n## Production lessons for[^\n]*\n[\s\S]*?(?=\n## |\Z)",
]

# Unique ~180-word expansions per slug (only appended if under TARGET)
EXPAND: dict[str, list[str]] = {
    "riverpod-vs-bloc-2026": [
        "## AsyncValue versus explicit BLoC states\n\nRiverpod bundles loading, data, and error into `AsyncValue`, which keeps widget code small on fetch-heavy screens. BLoC models the same three outcomes as named state classes that show up clearly in logs and `bloc_test` output. Neither approach removes the need to design error UX — both can hide failures behind generic spinners if you skip that work in review.",
        "## Rebuild scope with select and buildWhen\n\nList screens jank when the whole tree rebuilds on unrelated field changes. Riverpod `select` and BLoC `buildWhen` narrow subscriptions to the one field the widget displays. Profile with Flutter DevTools before blaming the state library — I have seen `setState` on a parent cause more rebuilds than either framework choice.",
    ],
    "rust-web-toolchain": [
        "## CI cache keys for Rust artifacts\n\nCache `target/` keyed on `Cargo.lock` hash in CI, not branch name alone. Cold builds dominate feedback loops when cache misses every merge. Pair `sccache` or `mold` linker with measured before/after timings when pitching toolchain adoption to leadership.",
    ],
    "saga-pattern-distributed-transactions": [
        "## Sweeper jobs for stuck sagas\n\nOrchestrators crash mid-step. Persist saga state at every transition and run a sweeper that marks timed-out instances for compensation or human review. Without durable checkpoints, you duplicate charges or release inventory twice after a network partition.",
    ],
    "secret-detection-gitleaks": [
        "## Baseline scans on long-lived repos\n\nFirst Gitleaks run on a ten-year repo surfaces hundreds of historical findings. Triage by secret class and rotation status — not all matches are live credentials. Establish baseline allowlists with ticket IDs and expiry review, not permanent blind ignores.",
    ],
    "secret-scanning-pre-commit": [
        "## Hook latency and developer trust\n\nPre-commit scans slower than three seconds get skipped with `--no-verify`. Keep rules focused on high-confidence patterns; run full history scans in CI nightly. Developers tolerate hooks that catch real keys, not every high-entropy string in fixtures.",
    ],
    "secrets-management": [
        "## Break-glass versus automated paths\n\nEmergency admin credentials still need rotation and audit, just on a different schedule. Document split-knowledge procedures and log every break-glass use within 24 hours. Manual-only secrets become decade-old liabilities without explicit ownership.",
    ],
    "secrets-rotation-automation": [
        "## Vault dynamic database credentials\n\nVault database secrets engine issues short-lived users per lease — rotation becomes issuance, not password editing. Tune lease TTL against connection pool recycle; pools outliving lease hold dead passwords until recycle.",
    ],
    "security-headers-hardening": [
        "## Third-party registry in pull requests\n\nRequire marketing analytics PRs to update CSP allowlists in the same change as script tags. Checkout failures from missing Stripe or PDF.js entries are silent to users until revenue drops — catch in CI header assertions on staging.",
    ],
    "security-http-only-secure-cookies": [
        "## OAuth flows and SameSite=Lax\n\nSameSite=Strict breaks IdP return redirects because the cross-site navigation will not send session cookies. Use Lax for consumer auth flows; reserve Strict for admin panels where users tolerate re-login from external links.",
    ],
    "security-logging-audit-trails": [
        "## Quarterly audit sample exports\n\nGenerate sample audit bundles from staging with realistic actors and targets before auditors arrive. Reviewers ask for field definitions and redaction proof — preparing exports quarterly avoids scramble weeks before SOC2.",
    ],
    "security-referrer-policy-configuration": [
        "## Zone-specific policies at the CDN\n\nPublic blog zones can use strict-origin-when-cross-origin while `/account/*` emits no-referrer via path rules. Document zone maps so new microsites inherit defaults instead of copying unrelated nginx snippets.",
        "## Analytics attribution after tightening\n\nCross-origin analytics sees origins only under strict policies — migrate campaign tracking to UTMs you control and first-party server-side collection before tightening referrers globally.",
    ],
    "seo-canonical-url-strategies": [
        "## hreflang paired with self-canonical\n\nEach locale page self-canonicals while hreflang declares alternates. Pointing all locales at English canonical tells Google to ignore translations — a frequent multilingual SEO regression after CMS migrations.",
        "## CMS preview and staging hosts\n\nPreview URLs with query tokens must noindex and must not appear in production canonical logic — middleware should detect preview mode before metadata generation runs.",
    ],
    "seo-core-web-vitals-ranking": [
        "## Template-level CrUX segmentation\n\nSite-wide CWV pass rates hide failing product detail templates. Segment field data by route template in RUM and fix revenue pages first even when blog posts already pass Search Console thresholds.",
        "## Wait 28 days before SEO impact claims\n\nCrUX uses a rolling window — RUM improves first; Search Console color changes lag. Do not revert INP fixes because Search Console still shows Poor on day ten.",
    ],
    "seo-internal-linking-architecture": [
        "## Monthly orphan remediation\n\nDiff sitemap URLs against internal inlink crawls monthly. Each orphan gets a contextual hub link or an explicit noindex decision — sitemap-only pages rank poorly and recrawl slowly.",
        "## Docs versioning cross-links\n\nWhen `/v2/` docs launch, hub pages must link prominently from `/v1/` retirement notices — otherwise authority stays on deprecated URLs crawlers still discover.",
    ],
    "security-subresource-integrity-sri": [
        "## Self-hosting when vendors omit hashes\n\nIf a vendor cannot publish integrity hashes, mirror the file to your origin and SRI the mirror. Nightly jobs verify mirror bytes against upstream and alert on drift before users hit a blocked script tag.",
    ],
    "semantic-caching-llm-apis": [
        "## Tenant-scoped cache keys\n\nInclude model version, system prompt hash, and tenant ID in semantic cache keys. Cross-tenant hits return wrong answers confidently — worse than a miss that triggers a fresh completion.",
    ],
    "sensor-fusion-clock-sync-real-time": [
        "## PTP versus NTP for lidar-camera fusion\n\nSub-millisecond alignment needs PTP on supported hardware; NTP jitter breaks calibration filters. Log per-sensor offset estimates and alert when drift exceeds fusion tolerance.",
    ],
    "seo-javascript-rendering-crawl": [
        "## URL Inspection after major deploys\n\nRun Search Console URL Inspection on top twenty landing URLs after each frontend release. Raw HTML from curl must contain primary headline text — not only the post-JavaScript DOM snapshot.",
        "## Dynamic rendering as a last resort\n\nGoogle's dynamic rendering service (or self-hosted Prerender) can serve static HTML to bots while users get CSR — treat as bridge debt. Budget crawl on rendered pages still applies; migrate to SSR as soon as engineering capacity allows.",
        "## Block neither JS nor CSS in robots.txt\n\nBlocking `.js` or `.css` for public pages prevents Googlebot from rendering your app — you get empty previews and wasted crawl on broken renders. robots.txt disallows are for admin paths, not assets required for indexing.",
    ],
    "seo-meta-robots-noindex-patterns": [
        "## Production smoke test for accidental noindex\n\nFail deploy pipeline if homepage HTML contains noindex. Environment typos in meta components have deindexed entire properties overnight — automated smoke tests are cheaper than recovery.",
        "## Faceted search at scale\n\nEcommerce filters generating millions of thin combinations need noindex on low-value tuples while keeping base category indexable. Log internal search to learn which filter combos deserve indexation versus consolidation.",
        "## Sitemap must exclude noindex URLs\n\nListing noindex pages in sitemap.xml sends conflicting signals. Generate sitemaps from the same indexability function that emits robots meta tags.",
    ],
    "security-permissions-policy-headers": [
        "## iframe allow attribute pairing\n\nPermissions-Policy must permit payment for Stripe origin AND the iframe needs allow=\"payment\". Missing either side breaks checkout with opaque console errors unrelated to CSP.",
        "## Feature policy migration from legacy headers\n\nOlder Feature-Policy header names differ from Permissions-Policy — audit CDN configs after browser deprecation cycles. Duplicate conflicting headers leave effective policy undefined across browsers.",
    ],
    "secret-detection-gitleaks": [
        "## Baseline scans on long-lived repos\n\nFirst Gitleaks run on a ten-year repo surfaces hundreds of historical findings. Triage by secret class and rotation status — not all matches are live credentials. Establish baseline allowlists with ticket IDs and expiry review, not permanent blind ignores.",
        "## Pre-receive hooks on default branch\n\nBlock pushes containing verified live secrets to main while allowing feature branch scans with warnings. Emergency bypass requires security team approval logged in ticket system.",
    ],
}

FAQS: dict[str, list[tuple[str, str]]] = json.loads((SCRIPTS / "b11_w0_faq.json").read_text())


def wc(t: str) -> int:
    return len(WORD.findall(t))


def strip_body(body: str) -> str:
    for pat in STRIP:
        body = re.sub(pat, "", body, flags=re.M)
    return re.sub(r"\n{3,}", "\n\n", body).strip()


def has_banned(text: str) -> bool:
    return any(b in text for b in BANNED)


def git_head(slug: str) -> str:
    r = subprocess.run(
        ["git", "show", f"HEAD:content/blog/{slug}.md"],
        cwd=ROOT, capture_output=True, text=True,
    )
    return r.stdout if r.returncode == 0 else ""


def load_posts() -> dict[str, str]:
    import importlib.util
    spec = importlib.util.spec_from_file_location("b11_w0_complete", SCRIPTS / "b11_w0_complete.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.POSTS


def parse_meta(fm: str, slug: str) -> dict:
    meta = {"slug": slug}
    for line in fm.splitlines():
        if line.startswith("title:"):
            meta["title"] = line.split(":", 1)[1].strip().strip('"')
        elif line.startswith("description:"):
            meta["description"] = line.split(":", 1)[1].strip().strip('"')
        elif line.startswith("datePublished:"):
            meta["datePublished"] = line.split(":", 1)[1].strip().strip('"')
        elif line.startswith("keywords:"):
            meta["keywords"] = line.split(":", 1)[1].strip().strip('"')
        elif line.startswith("tags:"):
            meta["tags"] = []
        elif line.strip().startswith("- ") and meta.get("tags") is not None and "keywords" not in meta:
            meta["tags"].append(line.strip()[2:].strip('"'))
    return meta


def build_fm(meta: dict, faqs: list[tuple[str, str]]) -> str:
    tags = meta.get("tags") or ["Engineering"]
    lines = [
        "---",
        f'title: "{meta.get("title", meta["slug"])}"',
        f'slug: "{meta["slug"]}"',
        f'description: "{meta.get("description", "")}"',
        f'datePublished: "{meta.get("datePublished", "2026-01-01")}"',
        f'dateModified: "{DATE}"',
        "tags:",
    ]
    for t in tags:
        lines.append(f'  - "{t}"')
    if meta.get("keywords"):
        lines.append(f'keywords: "{meta["keywords"]}"')
    lines.append("faq:")
    for q, a in faqs:
        lines.append(f'  - q: "{q}"')
        lines.append(f'    a: "{a}"')
    lines.append("---")
    return "\n".join(lines)


def extract_faq(fm: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    q = None
    for line in fm.splitlines():
        m = re.match(r'^\s*-\s+q:\s*"(.*)"\s*$', line)
        if m:
            q = m.group(1)
            continue
        m = re.match(r'^\s*a:\s*"(.*)"\s*$', line)
        if m and q:
            a = m.group(1)
            if "production pattern for frontend" not in a:
                out.append((q, a))
            q = None
    return out


def faqs_for(slug: str, fm: str) -> list[tuple[str, str]]:
    if slug in FAQS:
        return FAQS[slug]
    extracted = extract_faq(fm)
    return extracted if len(extracted) >= 3 else extracted


def best_body(slug: str, posts: dict[str, str]) -> str:
    candidates = []
    path = BLOG / f"{slug}.md"
    if path.exists():
        candidates.append(strip_body(path.read_text().split("---", 2)[2]))
    head = git_head(slug)
    if head.count("---") >= 2:
        candidates.append(strip_body(head.split("---", 2)[2]))
    if slug in posts:
        candidates.append(strip_body(posts[slug].split("---", 2)[2]))
    candidates = [c for c in candidates if c and not has_banned(c)]
    if not candidates:
        return ""
    body = max(candidates, key=wc)
    for section in EXPAND.get(slug, []):
        if wc(body) >= TARGET:
            break
        if section.strip() not in body:
            body += "\n\n" + section.strip()
    return body


def main() -> None:
    slugs = Path("/tmp/b11_w0.txt").read_text().strip().split("\n")
    posts = load_posts()
    results = []
    for slug in slugs:
        path = BLOG / f"{slug}.md"
        cur = path.read_text(encoding="utf-8") if path.exists() else git_head(slug)
        if cur.count("---") < 2:
            results.append({"slug": slug, "ok": False, "words": 0})
            continue
        meta = parse_meta(cur.split("---", 2)[1], slug)
        faqs = faqs_for(slug, cur.split("---", 2)[1])
        if len(faqs) < 3:
            # keep from fm if 3 valid
            fm_faqs = faqs_for(slug, cur.split("---", 2)[1])
            if len(fm_faqs) == 3:
                faqs = fm_faqs
        body = best_body(slug, posts)
        fm = build_fm(meta, faqs) if len(faqs) == 3 else build_fm(meta, faqs_for(slug, git_head(slug).split("---", 2)[1] if git_head(slug).count("---") >= 2 else cur.split("---", 2)[1]))
        if len(faqs) < 3 and slug in posts:
            pf = posts[slug].split("---", 2)[1]
            faqs = faqs_for(slug, pf)
            fm = build_fm(meta, faqs)
        path.write_text(f"{fm}\n\n{body.strip()}\n", encoding="utf-8")
        text = path.read_text()
        w = wc(text.split("---", 2)[2])
        faq_n = len(re.findall(r"^\s*-\s+q:", fm, re.M))
        bad = has_banned(text)
        ok = w >= TARGET and faq_n == 3 and not bad
        results.append({"slug": slug, "ok": ok, "words": w, "faq": faq_n, "banned": bad})

    done = sum(1 for r in results if r["ok"])
    samples = sorted([(r["slug"], r["words"]) for r in results if r["ok"]], key=lambda x: -x[1])[:3]
    print(json.dumps({"done": done, "total": len(slugs), "samples": samples, "fail": [r for r in results if not r["ok"]]}, indent=2))


if __name__ == "__main__":
    main()
