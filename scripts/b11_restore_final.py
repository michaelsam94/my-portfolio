#!/usr/bin/env python3
"""Restore b11 posts from HEAD when corrupted; top up to 1200w with unique sections."""
from __future__ import annotations

import importlib.util
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
TARGET = 1200
WORD = re.compile(r"\b[\w'-]+\b")
DATE = "2026-07-17"

spec = importlib.util.spec_from_file_location("g", Path(__file__).parent / "b11_generate_all.py")
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)

SLUGS = (
    open("/tmp/b11_need_0.txt").read().split()
    + open("/tmp/b11_need_1.txt").read().split()
)

CORRUPT_MARKERS = (
    "## Operating ",
    "## Follow-up",
    "## Sustaining the practice",
    "Validate this in staging",
    "Document the decision, owner",
    "## Production lessons for",
    "Production engineering for",
    "## Implementation patterns",
    "## Common production mistakes",
    "## Accessibility requirements",
    "## Security and privacy considerations",
    "## Testing strategy",
    "## Debugging and triage workflow",
    "## Architecture and boundaries",
)

GENERIC_SECTIONS = (
    "## Architecture and boundaries",
    "## Implementation patterns",
    "## Accessibility requirements",
    "## Security and privacy considerations",
    "## Testing strategy",
    "## Common production mistakes",
    "## Debugging and triage workflow",
    "## How internal linking architecture for product sites works under the hood",
    "## Implementation walkthrough",
    "## Tradeoffs worth documenting",
    "## Failure modes that survive code review",
    "## What to measure in RUM and dashboards",
    "## What I'd ship this week",
    "## Coordination with backend and platform",
    "## Related reading and specs",
)

BANNED_STRIP = (
    "Validate this in staging",
    "Additional production considerations",
    "Document the decision, owner",
)


def wc(text: str) -> int:
    return len(WORD.findall(text))


def git_raw(slug: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "show", f"HEAD:content/blog/{slug}.md"], text=True, cwd=ROOT
        )
    except subprocess.CalledProcessError:
        return None


def parse(raw: str) -> tuple[str, str]:
    parts = raw.split("---", 2)
    return parts[1], parts[2].strip()


def corrupt(text: str) -> bool:
    return any(m in text for m in CORRUPT_MARKERS)


def strip_banned(body: str) -> str:
    body = re.sub(r"\n## Production lessons for[^\n]*\n.*?(?=\n## |\Z)", "\n", body, flags=re.S)
    body = re.sub(r"\n## Operating [^\n]+\n.*?(?=\n## |\Z)", "\n", body, flags=re.S)
    body = re.sub(r"\n## Follow-up\n.*?(?=\n## |\Z)", "\n", body, flags=re.S)
    body = re.sub(r"\n## Sustaining the practice\n.*?(?=\n## |\Z)", "\n", body, flags=re.S)
    for heading in GENERIC_SECTIONS:
        body = re.sub(r"\n" + re.escape(heading) + r"\n.*?(?=\n## |\Z)", "\n", body, flags=re.S)
    for phrase in BANNED_STRIP:
        body = re.sub(re.escape(phrase) + r"[^\n]*\n?", "", body)
    # dedupe consecutive identical paragraphs
    lines = body.split("\n\n")
    deduped: list[str] = []
    for block in lines:
        if deduped and block.strip() == deduped[-1].strip():
            continue
        deduped.append(block)
    body = "\n\n".join(deduped)
    return re.sub(r"\n{3,}", "\n\n", body).strip()


def unique_topup(slug: str, body: str) -> str:
    """Append slug-specific sections until TARGET met — no shared templates."""
    extras: list[str] = []
    if slug in g.LONG_PAD:
        title = slug.replace("-", " ").title()
        extras.append(f"## Sustaining {title}\n\n{g.LONG_PAD[slug]}")
    if slug in g.PAD:
        extras.append(g.PAD[slug])
    # slug-specific hardcoded sections for common shortfalls
    MORE: dict[str, list[str]] = {
        "rust-web-toolchain": [
            "## CI integration\n\nTrack `pnpm exec biome check` and `next build` duration as CI metrics. Alert when p95 cold build exceeds baseline by twenty percent after a toolchain upgrade. Pin Biome and oxc versions in package.json resolutions so Renovate bumps are intentional, not accidental parser changes.",
            "## Migration checklist\n\nPhase one: replace ESLint and Prettier with Biome on one package. Phase two: enable Turbopack or Rolldown in dev. Phase three: evaluate production bundler swap only after dev metrics stabilize. Keep Babel fallback documented for plugins without Rust equivalents.",
        ],
        "security-headers-hardening": [
            "## Stripe and analytics in CSP\n\nCheckout requires explicit `script-src`, `connect-src`, and `frame-src` entries for js.stripe.com and api.stripe.com. Tag managers need the same treatment — marketing adds domains without security review. Maintain allowed-domain JSON in repo reviewed quarterly.",
            "## Header regression tests\n\nPlaywright or supertest should assert HSTS, CSP, X-Content-Type-Options, and Referrer-Policy on 200 and 404 responses. nginx without `always` drops headers on error pages — attackers probe 502 paths during outages.",
        ],
        "seo-core-web-vitals-ranking": [
            "## INP on product pages\n\nThird-party chat widgets and non-deferred analytics dominate INP failures on PDP templates. Use islands architecture — hydrate only the add-to-cart widget. Defer analytics with `requestIdleCallback` or interaction triggers.",
            "## Reporting to stakeholders\n\nReport field p75 movement and Search Console Good URL counts — not Lighthouse 100 scores. Tie CWV fixes to conversion on templates that failed LCP or INP where possible.",
        ],
        "seo-internal-linking-architecture": [
            "## Hub page editorial workflow\n\nWhen product launches features, hub pages must gain contextual links in the same release — not a follow-up SEO ticket. Assign hub owners in the content calendar alongside feature PMs.",
            "## Orphan detection\n\nMonthly crawl: sitemap URLs minus URLs with zero internal inlinks. Each orphan gets a hub owner decision — add contextual link, merge content, or noindex if low value.",
        ],
        "seo-sitemap-dynamic-generation": [
            "## Next.js sitemap.ts pattern\n\nGenerate sitemap from database with cursor pagination — never load all URLs into memory. Split into sitemap index when exceeding fifty thousand URLs or fifty megabytes per file.",
            "## lastmod honesty\n\nTie `lastmod` to editorial `contentUpdatedAt`, not CMS cache-bust timestamps. False lastmod erodes crawler trust when every URL shows today's date without content change.",
        ],
        "seo-structured-data-json-ld": [
            "## Price sync pipeline\n\nJSON-LD price must come from the same function that renders visible HTML price — not a separate cache layer. When sales events change prices hourly, regenerate JSON-LD in the same pipeline that updates HTML.",
            "## Rich Results CI\n\nRun Google Rich Results Test or schema validator in CI for product and article templates. Merchant Center rejects price mismatches between JSON-LD and visible DOM.",
        ],
        "shared-data-layer-room-kmp": [
            "## Migration testing on both targets\n\nExport Room schemas to CI artifacts. Run migration tests on Android instrumented tests and iosTest before merge. BundledSQLiteDriver on iOS avoids subtle WAL differences from system SQLite.",
            "## Sync conflict policy\n\nDocument last-write-wins versus merge rules in commonMain KDoc so iOS and Android product owners share one specification. Platform-specific background sync triggers stay behind expect/actual.",
        ],
        "small-language-models-on-mobile": [
            "## Quantization evaluation\n\nMeasure perplexity on domain vocabulary after INT4 quantization — generic benchmarks miss rare medical or legal terms. Fallback to cloud when on-device confidence falls below threshold.",
            "## Battery and thermal testing\n\nBenchmark on lowest supported device over thirty-minute sessions. Thermal throttling changes latency mid-session — not visible on M-series Macs or simulators.",
        ],
        "secret-scanning-pre-commit": [
            "## Custom rules for internal APIs\n\nWrite gitleaks allowlist entries for test fixtures only after security review — blanket allowlists defeat the purpose. Custom regex rules catch internal API key formats that generic rules miss.",
            "## Developer education\n\nFirst blocked commit should include a one-page doc on where secrets belong — vault references, not literals. Teams that only punish without teaching get `--no-verify` culture.",
        ],
        "secrets-management": [
            "## Dynamic database credentials\n\nRDS IAM authentication and Vault database secrets engine issue credentials with TTL measured in minutes. Application connection pools must refresh leases before expiry — stale connections fail auth silently until restart.",
            "## Break-glass procedure\n\nEmergency root credentials require hardware MFA, ticket reference, and automatic expiry. Weekly audit of break-glass usage catches teams bypassing dynamic secrets for convenience.",
        ],
        "semantic-caching-llm-apis": [
            "## Cache key composition\n\nInclude model version, system prompt hash, retrieval corpus version, and tenant ID in cache scope. Omitting any dimension serves stale policy answers after prompt updates.",
            "## False positive handling\n\nWhen users report wrong cached answers, log prompt pair and similarity score for threshold tuning. Lower threshold increases hits but raises false-positive rate — monitor both.",
        ],
        "sensor-fusion-clock-sync-real-time": [
            "## PTP hardware requirements\n\nPrecision Time Protocol needs switch and NIC support — verify hardware before software rollout. NTP jitter of milliseconds breaks tight camera-lidar alignment on moving platforms.",
            "## Replay testing\n\nRecord sensor bags with ground-truth timestamps. Replay with injected clock skew in CI when fusion algorithms change — field drift appears only under real thermal load.",
        ],
        "seo-canonical-url-strategies": [
            "## SPA canonical updates\n\nNext.js App Router metadata API must update canonical on every client navigation — stale canonical after route change duplicates index targets. Middleware can strip UTM params before canonical emission.",
            "## Trailing slash policy\n\nPick one policy in next.config, nginx, and sitemap generator together. Mixed slash policies create duplicate URLs that Search Console reports as duplicate without user-selected canonical.",
        ],
        "security-subresource-integrity-sri": [
            "## Version pinning workflow\n\nThird-party script URL changes require hash update in the same PR. CI fails when fetched bytes do not match declared integrity attribute.",
            "## Vendor without SRI support\n\nWhen vendors cannot provide stable versioned URLs, document accepted risk and use iframe sandbox isolation as alternative in security review ticket.",
        ],
        "security-http-only-secure-cookies": [
            "## Cookie prefix hardening\n\n`__Host-` prefix requires Secure, Path=/, and no Domain attribute — strongest session cookie shape for modern browsers. Integration test Set-Cookie on login in production profile.",
        ],
        "security-permissions-policy-headers": [
            "## iframe allow attribute pairing\n\nPermissions-Policy deny for camera is useless if embedded iframe has allow=\"camera\" — audit marketing embeds quarterly when widgets change.",
        ],
        "serverless-database-access-patterns": [
            "## RDS Proxy tuning\n\nGraph Lambda concurrent executions against DatabaseConnections during peak. Proxy max connections percent must match instance class — proxy is not infinite capacity.",
        ],
    }
    for block in MORE.get(slug, []):
        if block.split("\n")[0] not in body:
            extras.append(block)
    for block in extras:
        if wc(body) >= TARGET:
            break
        heading = block.split("\n")[0]
        if heading in body:
            continue
        if "## Resources" in body:
            body = body.replace("## Resources", block + "\n\n## Resources", 1)
        else:
            body += "\n\n" + block
    return body


def build_fm(slug: str, head_fm: str, disk_fm: str) -> str:
    """Prefer disk title/description/tags; FAQ from TOPICS; dateModified fixed."""
    meta = g.TOPICS.get(slug)
    faqs = meta[4] if meta else []
    # parse minimal fields from head or disk
    src = disk_fm if disk_fm else head_fm
    def grab(key: str, default: str = "") -> str:
        m = re.search(rf'^{key}:\s*"?([^"\n]+)"?\s*$', src, re.M)
        return m.group(1).strip() if m else default

    title = grab("title", slug.replace("-", " ").title())
    desc = grab("description", "")
    pub = grab("datePublished", "2026-01-01")
    kw = grab("keywords", "")
    tags_m = re.search(r"^tags:\n((?:  - .+\n)+)", src, re.M)
    tags_block = tags_m.group(1).rstrip() if tags_m else '  - "Engineering"\n'

    lines = [
        "---",
        f'title: "{title}"',
        f'slug: "{slug}"',
        f'description: "{desc}"',
        f'datePublished: "{pub}"',
        f'dateModified: "{DATE}"',
        "tags:",
    ]
    for t in re.findall(r'  - "([^"]+)"', tags_block + "\n"):
        lines.append(f'  - "{t}"')
    lines.append(f'keywords: "{kw}"')
    lines.append("faq:")
    for q, a in faqs[:3]:
        qe = q.replace('"', '\\"')
        ae = a.replace('"', '\\"')
        lines.append(f'  - q: "{qe}"')
        lines.append(f'    a: "{ae}"')
    lines.append("---")
    return "\n".join(lines)


def choose_body(slug: str) -> str:
    disk = (BLOG / f"{slug}.md").read_text()
    _, disk_body = parse(disk)
    head = git_raw(slug)
    head_body = parse(head)[1] if head else ""
    # Prefer HEAD when disk is corrupted or uses generic templates
    if head and (corrupt(disk) or corrupt(disk_body)):
        body = head_body
    elif not corrupt(disk_body) and wc(disk_body) >= wc(head_body):
        body = disk_body
    elif head_body:
        body = head_body
    else:
        body = disk_body
    return strip_banned(body)


def main():
    results = []
    for slug in SLUGS:
        head = git_raw(slug)
        disk = (BLOG / f"{slug}.md").read_text()
        head_fm = parse(head)[0] if head else ""
        disk_fm = parse(disk)[0]
        body = choose_body(slug)
        body = unique_topup(slug, body)
        fm = build_fm(slug, head_fm, disk_fm)
        (BLOG / f"{slug}.md").write_text(fm + "\n\n" + body + "\n", encoding="utf-8")
        w = wc(body)
        bad = corrupt(fm + body)
        faq = fm.count("  - q:")
        ok = w >= TARGET and faq == 3 and not bad
        results.append({"slug": slug, "words": w, "ok": ok, "bad": bad})

    ok_n = sum(1 for r in results if r["ok"])
    print(f"DONE={ok_n}/{len(SLUGS)}")
    for r in results:
        if not r["ok"]:
            print(f"  FAIL {r['slug']}: {r['words']}w bad={r['bad']}")
    samples = sorted([r for r in results if r["ok"]], key=lambda x: -x["words"])[:3]
    for r in samples:
        print(f"SAMPLE {r['slug']}: {r['words']}w")


if __name__ == "__main__":
    main()
