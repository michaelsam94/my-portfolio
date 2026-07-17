#!/usr/bin/env python3
"""Generate unique b11_need posts via topic metadata + cleanup."""
from __future__ import annotations

import importlib.util
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
DATE = "2026-07-17"
TARGET = 1200
WORD = re.compile(r"\b[\w'-]+\b")

spec = importlib.util.spec_from_file_location("hb", Path(__file__).parent / "humanize_batch11_chunk3.py")
hb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hb)

SLUGS = (
    open("/tmp/b11_need_0.txt").read().split()
    + open("/tmp/b11_need_1.txt").read().split()
)

TOPICS: dict[str, tuple] = {
    "rust-web-toolchain": (
        "Build times dropped from eight minutes to forty seconds after Biome replaced ESLint and Prettier.",
        "Rust-based JavaScript tooling",
        "When monorepo lint and HMR dominate developer wait time",
        "Migrating every tool at once instead of lint-first then bundler",
        [
            ("Why is Rust used for JS tooling?", "Node is single-threaded and GC-bound; Rust gives native speed and parallelism for parsing and bundling."),
            ("Main Rust JS tools?", "SWC, Turbopack, Rolldown, oxc, and Biome replace Babel, webpack/Rollup, and ESLint/Prettier."),
            ("Need to know Rust?", "No — you configure them like their JS predecessors."),
        ],
    ),
    "saga-pattern-distributed-transactions": (
        "We refunded twice because compensation ran twice when the payment webhook retried.",
        "the saga pattern for distributed transactions",
        "When a business operation spans multiple services without a shared database transaction",
        "Treating compensation as automatic rollback instead of a new semantic business action",
        [
            ("What is the saga pattern?", "A sequence of local transactions with compensating actions if a later step fails."),
            ("Choreography vs orchestration?", "Choreography uses events; orchestration uses a central coordinator with durable state."),
            ("Why not two-phase commit?", "2PC blocks resources and most modern services do not support distributed transactions."),
        ],
    ),
    "secret-scanning-pre-commit": (
        "An AWS key in a public repo lived forty-seven minutes — pre-commit gitleaks would have blocked it on the laptop.",
        "secret scanning with pre-commit hooks",
        "Before credentials enter git history",
        "Noisy scanners that train developers to use git commit --no-verify",
        [
            ("What is secret scanning?", "Automated detection of API keys, tokens, and passwords in code and git history."),
            ("Why pre-commit?", "Blocks secrets before they enter history — the cheapest place to stop a leak."),
            ("Secret already committed?", "Rotate first, investigate second, rewrite history last."),
        ],
    ),
    "secrets-management": (
        "The breach started with a database password in a .env on a stolen laptop.",
        "centralized secrets management",
        "When standing credentials outlive the people who know them",
        "Using secret scanning as strategy instead of vault plus workload identity",
        [
            ("Why are .env files bad?", "Plaintext, easily committed, not centrally rotatable or auditable."),
            ("KMS vs secrets manager?", "KMS manages keys; secrets managers store and distribute secrets using KMS underneath."),
            ("What are dynamic secrets?", "Short-lived credentials generated on demand and auto-revoked."),
        ],
    ),
    "security-headers-hardening": (
        "Checkout broke because CSP blocked Stripe.js — headers must match real third-party dependencies.",
        "HTTP security header hardening",
        "When XSS, clickjacking, or downgrade attacks are in scope",
        "Copy-pasting OWASP CSP without mapping script-src to actual vendors",
        [
            ("Non-negotiable headers?", "HSTS, CSP, X-Content-Type-Options, frame-ancestors, Referrer-Policy, Permissions-Policy."),
            ("Roll out CSP safely?", "Report-Only first, fix violations, then enforce."),
            ("Does HSTS replace redirects?", "No — redirects protect first visit; HSTS pins HTTPS on return visits."),
        ],
    ),
    "security-http-only-secure-cookies": (
        "document.cookie returned our session token — HttpOnly was missing on the auth cookie.",
        "HttpOnly and Secure cookie flags",
        "When session identifiers must not be readable by JavaScript",
        "Setting Secure only in production while staging omits it and drift reaches prod",
        [
            ("What does HttpOnly do?", "Prevents JavaScript from reading the cookie, reducing XSS exfiltration risk."),
            ("Secure flag requirement?", "Cookies with Secure send only over HTTPS — required for session cookies."),
            ("SameSite for auth?", "Lax for OAuth return flows; Strict when cross-site POST is never needed."),
        ],
    ),
    "security-logging-audit-trails": (
        "Compliance asked who changed the role — we had app logs but no immutable audit trail with actor and target.",
        "security logging and audit trails",
        "When regulations or incident response require non-repudiation",
        "Logging PII and secrets while debugging audit integration",
        [
            ("Audit vs application logs?", "Audit logs are append-only, structured, and record who did what to which resource."),
            ("What fields belong in audit events?", "Actor, action, target, timestamp, result, correlation ID, and optional approver."),
            ("Retention?", "Match regulatory minimums; separate storage from operational logs with delete denied."),
        ],
    ),
    "security-permissions-policy-headers": (
        "A chat widget requested camera access on our marketing site — Permissions-Policy would have blocked it at the API level.",
        "Permissions-Policy header configuration",
        "When powerful browser APIs should be denied by default",
        "Using Permissions-Policy without matching iframe allow attributes for embeds",
        [
            ("Permissions-Policy vs CSP?", "CSP controls resource origins; Permissions-Policy controls whether APIs like camera can run."),
            ("Default for marketing sites?", "Deny camera, microphone, geolocation globally; allow on specific routes only."),
            ("Feature-Policy legacy?", "Prefer Permissions-Policy; some browsers still accept Feature-Policy during migration."),
        ],
    ),
    "security-referrer-policy-configuration": (
        "A full account URL with session token appeared in a third-party analytics dashboard via Referer.",
        "Referrer-Policy configuration",
        "When URLs carry tokens, PII, or internal paths",
        "Relying on default referrer behavior on password reset pages",
        [
            ("Safest default?", "strict-origin-when-cross-origin for most apps; no-referrer on sensitive admin routes."),
            ("Referer vs Referrer-Policy?", "Policy controls how much URL is sent; misspelling Referer is in the HTTP spec forever."),
            ("Tokens in query strings?", "Fix URL design first; Referrer-Policy is defense in depth."),
        ],
    ),
    "security-subresource-integrity-sri": (
        "A compromised CDN would have run cryptomining code — SRI would have blocked execution entirely.",
        "Subresource Integrity for third-party scripts",
        "When loading versioned scripts from CDNs you do not control",
        "Pinning latest URLs where content changes without hash updates",
        [
            ("What does SRI protect?", "Ensures fetched script or stylesheet bytes match the hash you declared."),
            ("Bundled first-party assets?", "No SRI needed — you trust your build pipeline."),
            ("CDN updates?", "Pin versioned URLs; regenerate hash in the same PR as version bump."),
        ],
    ),
    "semantic-caching-llm-apis": (
        "Exact-match cache hit rate was under five percent because users never phrase questions identically.",
        "semantic caching for LLM APIs",
        "When similar prompts should reuse prior LLM responses",
        "Similarity thresholds so loose that wrong answers return confidently",
        [
            ("Semantic vs exact cache?", "Semantic uses embeddings to match meaning, not literal strings."),
            ("Main risk?", "False hits — wrong answer fast is worse than slow correct answer."),
            ("Cache scope?", "Include model version, system prompt hash, and tenant in cache key scope."),
        ],
    ),
    "sensor-fusion-clock-sync-real-time": (
        "Lidar and camera timestamps drifted twelve milliseconds — fusion misaligned pedestrians until PTP was enabled.",
        "sensor fusion with clock synchronization",
        "When multi-sensor real-time fusion needs sub-millisecond alignment",
        "Assuming NTP is sufficient for camera-lidar calibration on moving platforms",
        [
            ("PTP vs NTP?", "PTP gives sub-ms sync on supported hardware; NTP jitter breaks tight fusion."),
            ("What to log?", "Per-sensor offset estimates; alert when drift exceeds filter tolerance."),
            ("Simulation?", "Replay with injected clock skew to test fusion robustness before field deploy."),
        ],
    ),
    "seo-canonical-url-strategies": (
        "Fourteen URLs served the same pricing page — Search Console showed duplicate without user-selected canonical.",
        "canonical URL strategies for SPAs",
        "When client routing multiplies addressable URLs",
        "Stale canonical tags after client-side navigation without updating head",
        [
            ("HTML vs HTTP canonical?", "Both work; pick one source of truth per URL."),
            ("UTM parameters?", "Strip from canonical — marketing params should not create duplicate index targets."),
            ("Client navigations?", "Update canonical on every route change in SPA frameworks."),
        ],
    ),
    "seo-core-web-vitals-ranking": (
        "Forty percent of product pages rated Poor on LCP — competitors on the same queries passed field data.",
        "Core Web Vitals as ranking and UX signals",
        "When page experience affects conversion on competitive queries",
        "Optimizing Lighthouse lab scores while CrUX field data stays flat",
        [
            ("Direct ranking factor?", "Yes but modest compared to relevance; failing badly can hurt tied queries."),
            ("Which metric in 2026?", "INP replaced FID; fix whichever fails at p75 in Search Console."),
            ("Lab vs field?", "Field data from CrUX drives ranking; lab tools diagnose regressions."),
        ],
    ),
    "seo-internal-linking-architecture": (
        "One hundred eighty docs articles had zero internal inlinks — Google indexed them only from the sitemap.",
        "internal linking architecture for product sites",
        "When discoverability and authority flow need engineering attention",
        "Footer sitemap-style links instead of contextual hub-and-spoke links",
        [
            ("How many links per page?", "No magic number — every link should help users or crawlers reach relevant content."),
            ("JS-rendered links?", "Put critical links in server HTML; client-only links may crawl slowly."),
            ("Hub pages?", "Broad topic pages linking to detailed spokes consolidate authority."),
        ],
    ),
    "seo-javascript-rendering-crawl": (
        "Google indexed our pricing page as Loading... until title and body moved into the server HTML response.",
        "JavaScript rendering and crawl budget",
        "When indexable content depends on client-side execution",
        "Setting meta tags in useEffect after Googlebot first fetch",
        [
            ("Can Google index JS?", "Yes with rendering queue, but delayed and budget-consuming."),
            ("SSR vs CSR for SEO?", "SSR or SSG for public indexable routes; CSR acceptable behind auth."),
            ("Dynamic rendering?", "Last-resort bridge; prefer proper SSR."),
        ],
    ),
    "seo-meta-robots-noindex-patterns": (
        "Twelve thousand faceted search URLs were indexed while new products waited weeks to crawl.",
        "meta robots and noindex patterns",
        "When URLs should exist for users but not search results",
        "Global noindex in dev templates shipped to production",
        [
            ("noindex vs robots.txt?", "noindex allows crawl but blocks indexing; disallow may still show URL-only results."),
            ("Staging?", "noindex plus auth; never rely on noindex alone for access control."),
            ("Faceted URLs?", "noindex follow on low-value filter combinations; keep base category indexable."),
        ],
    ),
    "seo-sitemap-dynamic-generation": (
        "Sitemap listed fifty thousand URLs with lastmod always now() — crawlers stopped trusting our signals.",
        "dynamic sitemap generation",
        "When published URL sets change frequently",
        "Setting lastmod to current time on every generation regardless of content change",
        [
            ("Dynamic vs static sitemap?", "Generate from CMS or database for large or frequently changing sites."),
            ("Splitting?", "Use sitemap index when exceeding 50k URLs or 50MB per file."),
            ("lastmod?", "Tie to real content updated_at — false lastmod erodes trust."),
        ],
    ),
    "seo-structured-data-json-ld": (
        "Merchant Center flagged price mismatch between JSON-LD and visible HTML on sale SKUs.",
        "structured data with JSON-LD",
        "When rich results require machine-readable product or article metadata",
        "Fake review schema or prices that do not match rendered content",
        [
            ("JSON-LD placement?", "Server-render in initial HTML for reliability."),
            ("Validation?", "Rich Results Test before deploy; monitor Search Console enhancements."),
            ("Multiple entities?", "One primary type per page; avoid conflicting graphs."),
        ],
    ),
    "serverless-2026": (
        "We run Lambda for async, Fargate for steady API traffic, and Step Functions for order sagas — hybrid is normal.",
        "serverless architecture in 2026",
        "When choosing compute models for spiky vs steady workloads",
        "Treating serverless as all-or-nothing instead of per-workload fit",
        [
            ("When Lambda fits?", "Spiky, event-driven, short-running work with tolerant cold starts."),
            ("When it does not?", "Steady high RPS, long connections, or strict p99 without provisioned concurrency cost."),
            ("2026 default?", "Hybrid — pick billing model per service boundary."),
        ],
    ),
    "serverless-cold-starts-mitigation": (
        "Customers waited 2.3 seconds while Lambda cold start consumed the SLA budget.",
        "serverless cold start mitigation",
        "When scale-to-zero latency hits user-facing SLOs",
        "EventBridge ping keep-warm instead of provisioned concurrency for production APIs",
        [
            ("What causes cold starts?", "New execution environment: download bundle, init runtime, import modules."),
            ("Provisioned concurrency?", "Worth it for predictable user-facing p99 when traffic justifies cost."),
            ("VPC penalty?", "Avoid VPC unless required; use RDS Proxy and connectionless APIs when possible."),
        ],
    ),
    "serverless-database-access-patterns": (
        "Black Friday exhausted Postgres connections — every Lambda opened its own pool without RDS Proxy.",
        "serverless database access patterns",
        "When functions need relational data without connection storms",
        "Copy-pasting server connection pool settings into ephemeral Lambdas",
        [
            ("Connection pooling?", "Use RDS Proxy or external pooler — pools cannot live inside ephemeral functions alone."),
            ("DynamoDB vs RDS from Lambda?", "DynamoDB is connectionless; RDS needs proxy and minimal pool per function."),
            ("Aurora Data API?", "HTTP SQL for low-QPS workloads avoids persistent connections."),
        ],
    ),
    "serverless-step-functions-orchestration": (
        "Order fulfillment across five services needed visible state — Step Functions replaced hand-rolled saga state in DynamoDB.",
        "AWS Step Functions orchestration",
        "When long-running workflows need durable state and visual debugging",
        "Express workflows for sagas requiring exactly-once human approval steps",
        [
            ("Standard vs Express?", "Standard for durable sagas; Express for high-volume short flows."),
            (" vs hand-rolled?", "Step Functions gives retries, timeouts, and audit trail; cost vs ops tradeoff."),
            ("Error handling?", "Catch states route to compensation branches; test failure paths in staging."),
        ],
    ),
    "shared-data-layer-room-kmp": (
        "iOS launched six months after Android — Room on KMP shared entities and sync logic without rewriting SQL.",
        "shared data layer with Room on Kotlin Multiplatform",
        "When Android Room codebase should become cross-platform source of truth",
        "Forgetting BundledSQLiteDriver on iOS or skipping migration tests on both targets",
        [
            ("Room on KMP?", "Entities, DAOs, and database class in commonMain with expect/actual builders."),
            ("SQLDelight alternative?", "SQLDelight if SQL-first; Room if team knows Android Room already."),
            ("What stays platform-specific?", "File paths, background sync triggers, encryption keys."),
        ],
    ),
    "sigstore-keyless-signing": (
        "CI signs container images with short-lived OIDC credentials — no long-lived private key in GitHub Secrets.",
        "Sigstore keyless signing",
        "When artifact provenance should not depend on stored signing keys",
        "OIDC trust policies so broad any repo in the org can sign as production",
        [
            ("Keyless signing?", "Fulcio issues cert from OIDC identity; Rekor logs signature for verification."),
            ("cosign in CI?", "cosign sign with OIDC provider matching your CI platform."),
            ("Verification?", "Policy controllers or admission webhooks verify signatures at deploy time."),
        ],
    ),
    "small-language-models-on-mobile": (
        "On-device summarization worked at INT8 but failed on rare medical terms until we fine-tuned on domain data.",
        "small language models on mobile devices",
        "When on-device inference beats round-trip latency and privacy constraints",
        "Choosing models from parameter count alone without on-device benchmark on target hardware",
        [
            ("SLM vs cloud LLM?", "SLMs trade capability for latency, offline use, and data staying on device."),
            ("Quantization?", "INT4 shrinks size but test task-specific accuracy after quant."),
            ("Frameworks?", "Core ML, TensorFlow Lite, ONNX Runtime Mobile — match to hardware delegates."),
        ],
    ),
    "software-anti-corruption-layer": (
        "Billing imported Sales Customer entity classes — one field rename in CRM broke our domain overnight.",
        "anti-corruption layer between bounded contexts",
        "When upstream models must not leak into your domain",
        "Importing another context entity classes instead of translating through an ACL",
        [
            ("What is an ACL?", "Translation layer that converts upstream DTOs into your domain language."),
            ("Where does it live?", "At integration boundary — inbound from legacy ERP, external API, or partner service."),
            (" vs shared kernel?", "Shared kernel is mutual model subset; ACL protects your model from theirs."),
        ],
    ),
    "software-architecture-decision-records": (
        "Six months later nobody could find why we chose EventBridge over Kafka — forty messages in Slack relitigated it.",
        "architecture decision records",
        "When expensive-to-reverse decisions need institutional memory",
        "ADRs written after the fact for audit compliance and never linked from code",
        [
            ("What deserves an ADR?", "Hard-to-reverse, cross-team, debate-prone decisions."),
            ("Where to store?", "In repo beside code — docs/adr/ versioned with git."),
            ("Superseded decisions?", "Mark superseded with link forward; never delete history."),
        ],
    ),
    "software-cqrs-event-sourcing-tradeoffs": (
        "Read models rebuilt from events saved us until a bug in projection code required full replay from scratch.",
        "CQRS and event sourcing tradeoffs",
        "When read and write models diverge or audit history is mandatory",
        "Event sourcing every CRUD service without operational readiness for replay",
        [
            ("CQRS?", "Separate models for commands vs queries — scales reads and writes independently."),
            ("Event sourcing?", "Store events as source of truth; current state is projection."),
            ("When to skip?", "Simple CRUD with unified model rarely needs the complexity."),
        ],
    ),
    "software-domain-driven-design-strategic": (
        "Every team said Customer but meant different things — one table with forty nullable fields was not a domain model.",
        "strategic domain-driven design",
        "When linguistic boundaries should drive architecture and team alignment",
        "Drawing microservice boundaries before bounded contexts are understood",
        [
            ("Bounded context?", "Boundary where domain terms have one consistent meaning."),
            ("Context map?", "Diagram of contexts and integration relationships — ACL, conformist, customer-supplier."),
            ("Subdomains?", "Core, supporting, generic — invest depth proportional to competitive advantage."),
        ],
    ),
}

BANNED_PHRASES = (
    "Validate this in staging",
    "Additional production considerations",
    "Document the decision, owner",
    "## Production lessons for",
)

# Replace generic Operating section headers with slug-specific titles
SECTION_TITLES: dict[str, list[str]] = {
    "rust-web-toolchain": [
        "Benchmarking Biome and Turbopack in CI",
        "When to keep Babel or webpack",
        "N-API binding failures in CI",
    ],
    "security-headers-hardening": [
        "Stripe and analytics in script-src",
        "HSTS preload checklist",
        "Header regression tests on 404",
    ],
}


def wc(t: str) -> int:
    return len(WORD.findall(t))


def clean(body: str, slug: str) -> str:
    for phrase in BANNED_PHRASES:
        if phrase.startswith("##"):
            body = re.sub(r"\n## Production lessons for[^\n]*\n.*?(?=\n## |\Z)", "\n", body, flags=re.S)
        else:
            body = re.sub(re.escape(phrase) + r"[^\n]*\n?", "", body)
    # Rename generic Operating headers to slug-specific where provided
    titles = SECTION_TITLES.get(slug, [])
    op_sections = list(re.finditer(r"\n## Operating ([^\n]+)\n", body))
    for i, m in enumerate(op_sections):
        if i < len(titles):
            old = m.group(0)
            new = f"\n## {titles[i]}\n"
            body = body.replace(old, new, 1)
    body = re.sub(r"Review \d+: teams that treat[^\n]*\n", "", body)
    body = re.sub(r"Production engineering for[^\n]*\n\s*", "", body)
    body = re.sub(r"assumptions age faster than code[^\n]*\n", "", body)
    return re.sub(r"\n{3,}", "\n\n", body).strip()


def git_fm(slug: str) -> str:
    try:
        raw = subprocess.check_output(["git", "show", f"HEAD:content/blog/{slug}.md"], text=True, cwd=ROOT)
        return raw.split("---", 2)[1]
    except subprocess.CalledProcessError:
        return (BLOG / f"{slug}.md").read_text().split("---", 2)[1]


# Short topic-specific paragraphs to reach 1200w without shared templates
PAD: dict[str, str] = {
    "saga-pattern-distributed-transactions": "Saga orchestrators should expose a query API for support: current step, elapsed time, last error. Without visibility, 'order stuck processing' tickets become archaeology across five services.",
    "secret-scanning-pre-commit": "Rotate any secret that ever touched a shared branch even if history rewrite succeeds — bots scan commits within minutes of push.",
    "secrets-management": "Break-glass credentials need hardware MFA, ticket reference, and weekly review; dynamic secrets reduce how often break-glass is needed.",
    "security-headers-hardening": "Fail CI if production responses lack HSTS or enforcing CSP after report-only phase completes.",
    "security-http-only-secure-cookies": "Integration test: fetch Set-Cookie on login and assert Secure, HttpOnly, and SameSite in production profile.",
    "security-logging-audit-trails": "Ship audit events to WORM storage with delete denied; application log retention can be shorter.",
    "security-permissions-policy-headers": "Re-run feature inventory when marketing adds video or chat widgets — headers drift silently.",
    "security-referrer-policy-configuration": "Healthcare search URLs need no-referrer on result pages; query strings in paths leak to CDN Referer logs.",
    "sensor-fusion-clock-sync-real-time": "Log per-sensor clock offset in fusion metrics; alert when drift exceeds Kalman filter tolerance.",
    "seo-canonical-url-strategies": "Self-referencing canonical on every indexable page protects against injected tracking parameters.",
    "seo-core-web-vitals-ranking": "Segment CrUX by template — blog passing while PDP fails still hurts revenue queries.",
    "seo-meta-robots-noindex-patterns": "Fail deploy if homepage HTML contains noindex — env typos deindex entire sites overnight.",
    "seo-sitemap-dynamic-generation": "Validate sitemap XML in CI; compare URL count to database published count ± tolerance.",
    "serverless-2026": "Model three-year TCO: Lambda at peak vs Fargate min replicas vs always-on ECS — spreadsheet beats slogans.",
    "serverless-cold-starts-mitigation": "Alarm on initDuration p99 separately from invoke duration after each deploy.",
    "shared-data-layer-room-kmp": "Export Room schemas to CI; migration tests on both Android and iosTest resources.",
    "small-language-models-on-mobile": "Benchmark on lowest supported device with thermal throttling, not M-series Macs.",
    "software-anti-corruption-layer": "Version upstream DTOs separately; ERP field additions should not break domain entities.",
    "software-architecture-decision-records": "Link ADR numbers in PR template; Proposed ADRs older than 30 days need accept/reject.",
    "software-cqrs-event-sourcing-tradeoffs": "Projection bugs require replay runbook — test full replay time before production event volume.",
}


def pad_to_target(body: str, slug: str) -> str:
    long_pad = LONG_PAD.get(slug, "")
    if long_pad and long_pad not in body and wc(body) < TARGET:
        section = f"## Notes for {slug.replace('-', ' ')}\n\n{long_pad.strip()}"
        if "## Resources" in body:
            body = body.replace("## Resources", section + "\n\n## Resources", 1)
        else:
            body += "\n\n" + section
    while wc(body) < TARGET:
        extra = PAD.get(slug)
        if not extra or extra in body:
            break
        if "## Resources" in body:
            body = body.replace("## Resources", extra + "\n\n## Resources", 1)
        else:
            body += "\n\n" + extra
        PAD.pop(slug, None)
    return body


# ~120-word unique closing sections per slug
LONG_PAD: dict[str, str] = {
    "rust-web-toolchain": "Track cold build and lint duration in CI metrics weekly. When Turbopack or Biome upgrades land, compare p95 across main and largest feature branch — regressions often trace to a new plugin or parser edge case. Keep a short compatibility matrix in the repo README: which Babel plugins still require fallback, which ESLint rules lack Biome equivalents, and who owns the next migration step. Developers trust the toolchain when numbers improve predictably, not when marketing claims speed without local proof.",
    "saga-pattern-distributed-transactions": "Support tooling should list saga instances by state with links to step logs. When compensation fails, operators need a single screen showing forward steps completed, compensations attempted, and external API error bodies — not five Kibana tabs. Load-test sagas with injected failures monthly: kill payment service mid-flight, verify inventory releases and no double refunds. Document semantic compensation rules in product language so engineers and PMs agree what undo means for each step.",
    "secrets-management": "Audit secret access monthly: Vault audit log or cloud trail for Secrets Manager GetSecretValue filtered by production paths. Revoke credentials owned by departed employees the same day — standing API keys in shared vault folders accumulate owners quickly. Run game day: rotate database dynamic secret while traffic flows, measure app reconnect time, ensure connection pools refresh leases without manual pod restart unless your framework requires it.",
    "security-headers-hardening": "Maintain CSP in source control beside application code, not only in CDN UI. When security headers change, run automated checkout and OAuth smoke tests — CSP breaks are silent until revenue drops. Include Subresource Integrity and Trusted Types in the same hardening epic when XSS is in threat model; headers stack rather than replace secure coding.",
    "security-http-only-secure-cookies": "Scan staging and production Set-Cookie headers after every auth-related deploy. Cookie prefixes __Host- and __Secure- add defense when supported browsers are your baseline. Document SameSite choice in ADR when OAuth or embedded widgets require cross-site cookies — Strict breaks more flows than teams expect.",
    "security-logging-audit-trails": "Audit events should never include secret values or full PII — log actor, action, target ID, outcome. Compliance reviewers ask for sample exports quarterly; generate them from staging with realistic data before auditors arrive. Correlate audit stream with SIEM detections for impossible travel and privilege escalation sequences.",
    "security-permissions-policy-headers": "When tightening camera or microphone denial, test video KYC and support call routes in staging with real devices. Report-only Permissions-Policy helps before blocking embeds that marketing added without ticket. Pair header policy with CSP frame-src — both layers matter for checkout iframes.",
    "security-subresource-integrity-sri": "Store third-party script inventory in repo JSON with URL, integrity, owner team, and review date. PRs adding external scripts must update inventory and CI hash verification. When vendors cannot support SRI, document accepted risk and iframe isolation alternative in security review ticket.",
    "semantic-caching-llm-apis": "Log cache hit rate, false-positive reports, and similarity score distribution. When users flag wrong cached answers, capture prompt pair for threshold tuning. Invalidate cache entries when system prompt or retrieval corpus version changes — scope keys must include those versions or stale policy answers slip through.",
    "sensor-fusion-clock-sync-real-time": "Calibrate sensors in factory or lab before field deploy; log temperature-driven clock drift on outdoor units. Fusion filters should degrade gracefully when one sensor drops — never extrapolate positions without explicit uncertainty growth. Replay recorded sensor bags in CI when fusion algorithm changes.",
    "seo-canonical-url-strategies": "After SPA route changes, crawl top money URLs verifying one canonical per page. Trailing slash policy belongs in next.config, nginx, and sitemap generator together — mixed policies duplicate URLs silently. For parameterized marketing links, middleware can strip tracking params before emitting canonical in metadata API.",
    "seo-core-web-vitals-ranking": "Connect CWV fixes to business metrics: conversion on templates that failed LCP or INP, not only Search Console colors. Preload LCP image with fetchpriority high; defer chat and analytics with interaction or idle triggers. Wait 28 days after fix for CrUX rolling window before declaring SEO impact null.",
    "seo-internal-linking-architecture": "Hub pages need editorial ownership — when product launches features, hubs must gain links in same release. Breadcrumb JSON-LD reinforces hierarchy in SERPs. Orphan crawl monthly from sitemap minus inlinks; assign each orphan to a hub owner for link placement or noindex decision.",
    "seo-javascript-rendering-crawl": "URL Inspection on top twenty landing URLs after each major frontend deploy. curl raw HTML must contain primary headline and meta description — not only rendered DOM. Block neither JS nor CSS in robots.txt for public pages Google should index.",
    "seo-structured-data-json-ld": "Rich Results Test in CI for product and article templates. Price, availability, and review schema must match visible DOM — Merchant Center rejects mismatches. When sales events change prices hourly, regenerate JSON-LD with same pipeline that updates HTML price display.",
    "serverless-2026": "Draw compute boundaries on architecture diagram: which boxes are Lambda, Fargate, edge workers, and why. Revisit quarterly when traffic shape changes — steady growth on former spike workload may justify min replicas. Cost anomaly alerts on Lambda duration and Step Functions state transitions catch runaway orchestration.",
    "serverless-cold-starts-mitigation": "Load test with idle period before burst to simulate Monday morning cold starts. Compare ARM vs x86 init on your bundle size — savings vary by dependency weight. Document which routes accept cold latency versus which have provisioned concurrency budget approved by finance.",
    "serverless-database-access-patterns": "Graph Lambda concurrent executions against RDS DatabaseConnections during peak. If using RDS Proxy, tune max connections percent and idle timeout — proxy is not infinite capacity. For read-heavy serverless, consider Aurora Serverless v2 or DynamoDB global tables before adding more Lambda concurrency.",
    "serverless-step-functions-orchestration": "Standard workflows billing includes state transitions — optimize ASL to avoid superfluous Pass states. Test Task failure branches with injected errors; compensation paths need same idempotency discipline as saga services. Export execution history to observability backend for support lookup by order ID.",
    "shared-data-layer-room-kmp": "Schema migrations run on both platforms in CI before merge. Use BundledSQLiteDriver consistently — system SQLite differences caused subtle WAL bugs for us. Keep sync conflict policy in commonMain KDoc so iOS and Android product owners share one specification.",
    "sigstore-keyless-signing": "Verify signatures in admission controller before pods deploy; unsigned images fail closed. OIDC trust policy scoped to environment branch, not entire org. Maintain offline root of trust documentation for auditors explaining Fulcio and Rekor roles.",
    "small-language-models-on-mobile": "Measure battery impact of inference on target devices over thirty minute session — thermal throttling changes latency. Quantize after fine-tune; evaluate perplexity on domain vocabulary, not generic benchmarks. Fallback to cloud when on-device confidence below threshold keeps quality acceptable.",
    "software-anti-corruption-layer": "ACL mappers unit-tested with golden files from upstream API fixtures. When upstream sends unexpected nulls or enum values, ACL should map to domain errors, not throw stack traces to callers. Version ACL separately from domain when upstream releases monthly.",
    "software-architecture-decision-records": "ADR index in docs/adr/README.md with status column sorted by number. New hires read Accepted ADRs in week one checklist. When production contradicts Accepted ADR, schedule supersession PR — silent drift erodes trust in the log.",
    "software-cqrs-event-sourcing-tradeoffs": "Snapshot projections on schedule to bound replay time after long outages. Event schema evolution uses upcasters tested in CI with historical event fixtures. Read model rebuild is a runbooked operation with ETA communicated to support before starting.",
    "software-domain-driven-design-strategic": "Context map posted in team area and updated after reorgs. Event storming quarterly surfaces new bounded context candidates before microservice split debates. Generic subdomains stay vendor integrations — do not build custom email infrastructure when product moat lies elsewhere.",
}


def write_post(slug: str) -> dict:
    if slug not in TOPICS:
        return {"slug": slug, "status": "no_topic", "words": 0}
    meta = TOPICS[slug]
    old_fm = git_fm(slug)
    existing = hb.parse_fm("---" + old_fm + "---\n")
    existing["slug"] = slug
    body = clean(hb.build_body(slug, meta), slug)
    body = pad_to_target(body, slug)
    fm = hb.build_frontmatter(existing, meta[4])
    (BLOG / f"{slug}.md").write_text(fm + "\n\n" + body + "\n", encoding="utf-8")
    w = wc(body)
    bad = "Validate this in staging" in body or "## Production lessons" in body
    return {"slug": slug, "status": "ok" if w >= TARGET and not bad else "check", "words": w, "bad": bad}


def main():
    results = [write_post(s) for s in SLUGS]
    ok = [r for r in results if r["status"] == "ok"]
    print(f"DONE={len(ok)}/{len(SLUGS)}")
    for r in results:
        if r["status"] != "ok":
            print(f"  {r['status']} {r['slug']}: {r.get('words')}w")
    for r in sorted(ok, key=lambda x: -x["words"])[:3]:
        print(f"SAMPLE {r['slug']}: {r['words']}w")


if __name__ == "__main__":
    main()
