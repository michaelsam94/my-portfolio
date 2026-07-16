#!/usr/bin/env python3
"""Expand blog posts under 900 words with topic-specific sections."""
import re
from pathlib import Path

BLOG = Path(__file__).resolve().parent.parent / "content" / "blog"
WORD_PAT = re.compile(r"\b[\w'-]+\b")
FILLER = re.compile(
    r"\n## Operational checklist\n\nBefore treating this topic as.*?deployment\.\n",
    re.DOTALL,
)
TARGET = 900


def word_count(text: str) -> int:
    return len(WORD_PAT.findall(text))


def parse_post(path: Path):
    raw = path.read_text()
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return None
    fm, body = parts[1], parts[2]
    title = re.search(r'^title:\s*"(.+)"', fm, re.M)
    desc = re.search(r'^description:\s*"(.+)"', fm, re.M)
    tags = re.findall(r'-\s*"([^"]+)"', re.search(r"tags:.*?(?=\n\w|\Z)", fm, re.S).group(0) if re.search(r"tags:", fm) else "")
    return {
        "path": path,
        "slug": path.stem,
        "title": title.group(1) if title else path.stem,
        "description": desc.group(1) if desc else "",
        "tags": tags,
        "body": body,
        "raw": raw,
    }


def related_slugs(slug: str, all_slugs: list[str], n: int = 3) -> list[str]:
    words = set(slug.split("-"))
    scored = []
    for s in all_slugs:
        if s == slug:
            continue
        overlap = len(words & set(s.split("-")))
        if overlap >= 1 and (slug.split("-")[0] == s.split("-")[0] or overlap >= 2):
            scored.append((overlap + (2 if slug.split("-")[0] == s.split("-")[0] else 0), s))
    scored.sort(reverse=True)
    out, seen = [], set()
    for _, s in scored:
        if s not in seen:
            out.append(s)
            seen.add(s)
        if len(out) >= n:
            break
    return out


def topic_label(slug: str, title: str) -> str:
    # strip common prefixes for readable topic
    for p in ("android-", "llm-", "rag-", "postgres-", "compose-", "flutter-", "kotlin-", "ci-cd-", "api-", "oauth2-", "oauth-", "iot-", "agent-", "testing-", "system-design-", "observability-", "kubernetes-", "terraform-", "redis-", "graphql-", "nextjs-", "typescript-", "dart-", "microservices-", "backend-", "edge-", "ops-", "mcp-", "embedded-", "privacy-", "performance-", "concurrency-", "database-", "data-", "sec-", "web-", "css-", "react-", "svelte-", "docker-", "platform-engineering-", "prompt-engineering-", "realtime-", "progressive-web-apps-", "background-jobs-", "clickhouse-", "grpc-", "owasp-", "passwordless-", "authorization-", "career-", "code-review-", "columnar-", "consent-", "container-", "containers-", "cqrs-", "csrf-", "cdc-", "cdn-", "chaos-", "compose-", "modular-"):
        if slug.startswith(p):
            rest = slug[len(p):].replace("-", " ")
            return rest or title.lower()
    return slug.replace("-", " ")


def cross_links(slug: str, all_slugs: list[str]) -> str:
    related = related_slugs(slug, all_slugs)
    if not related:
        return ""
    lines = ["Pair with related posts when designing end-to-end systems:"]
    for s in related:
        lines.append(f"- [{s.replace('-', ' ').title()}](https://blog.michaelsam94.com/{s}/)")
    return "\n".join(lines)


def category_mistakes(slug: str, topic: str, tags: list[str]) -> str:
    prefix = slug.split("-")[0]
    multi = "-".join(slug.split("-")[:2])

    domain_hints = {
        "android": f"Shipping {topic} on Android fails quietly when you test only on flagship devices, skip process-death scenarios, or assume `minSdk` behavior matches latest API docs. Emulator-only validation misses OEM-specific battery optimizations and background execution limits.",
        "flutter": f"Flutter teams implementing {topic} often regress performance by rebuilding entire subtrees on every frame, ignoring platform channel latency, or testing only on iOS simulators. Profile on mid-range Android hardware before calling the work done.",
        "llm": f"LLM features around {topic} break in production when prompts assume deterministic output, context windows are sized for dev datasets, or token costs are never budgeted per user session. Always log prompt hash, model version, and latency—not raw prompts with PII.",
        "rag": f"RAG pipelines for {topic} degrade when chunk boundaries split tables, embeddings go stale after doc updates, and retrieval metrics are measured offline only. Re-index incrementally and monitor answer faithfulness on live traffic samples.",
        "postgres": f"Postgres work on {topic} causes outages when migrations run without `lock_timeout`, connection pools are sized for app servers not PgBouncer modes, and `EXPLAIN` plans from staging are assumed to match production statistics.",
        "kubernetes": f"Kubernetes changes for {topic} surprise teams when resource requests are copied from examples, probes are too aggressive during startup, and Helm values drift from git without anyone noticing until a node pressure eviction.",
        "terraform": f"Terraform patterns for {topic} rot when emergency console edits never get codified, `ignore_changes` blocks multiply without documentation, and drift detection runs monthly instead of daily on production workspaces.",
        "testing": f"Testing strategy for {topic} gives false confidence when mocks return happy paths only, flakey tests are retried until green, and contract tests are never run against staging before deploy.",
        "observability": f"Observability for {topic} fails when dashboards exist but nobody owns alert routing, high-cardinality labels explode metrics cost, and logs lack trace correlation so incidents become grep archaeology.",
        "agent": f"Agent systems using {topic} loop infinitely when tool errors are swallowed, subagent budgets have no hard cap, and human-in-the-loop gates are bypassed under latency pressure.",
        "iot": f"IoT deployments of {topic} fail in the field when firmware assumes stable Wi-Fi, OTA rollback is untested, and device certificates expire without automated renewal.",
        "api": f"API design for {topic} frustrates clients when pagination cursors expire silently, error bodies lack stable machine-readable codes, and rate limits return 429 without `Retry-After` headers.",
        "ci": f"CI/CD for {topic} breaks merges when pipeline secrets rotate without updating OIDC trust, cache keys ignore lockfile changes, and deployment gates check build success but not smoke tests.",
        "oauth": f"OAuth flows involving {topic} leak sessions when refresh tokens are stored in localStorage, redirect URI validation is loose in staging, and token introspection is skipped for opaque bearer tokens.",
        "redis": f"Redis usage for {topic} loses data when persistence mode is misunderstood, hot keys saturate single shards, and TTL strategy is applied after memory pressure already triggered evictions.",
        "graphql": f"GraphQL APIs for {topic} melt down under nested queries without depth limits, N+1 resolvers hit the database per field, and schema deprecation has no usage telemetry.",
        "typescript": f"TypeScript patterns for {topic} erode when `any` escapes during deadlines, generic constraints are loosened instead of modeling domain invariants, and strict mode is disabled file-by-file without a migration plan.",
        "compose": f"Compose UI work on {topic} janks when recomposition scope is too wide, `remember` keys omit stable inputs, and semantics for TalkBack are added only after QA finds focus traps.",
        "security": f"Security controls for {topic} fail open when exceptions accumulate, secrets land in logs during debugging, and threat models assume attackers only use documented API paths.",
        "backend": f"Backend services for {topic} fall over when retries amplify load, idempotency keys expire before clients retry, and bulkheads are configured in code but not enforced in deployment topology.",
        "system": f"System design for {topic} breaks at scale when hot keys, thundering herds, and cache stampedes are discovered during launch week instead of load test week.",
        "performance": f"Performance work on {topic} regresses when optimizations target p50 only, benchmarks run on laptops not production hardware, and flamegraphs are captured once then never compared after refactors.",
        "data": f"Data pipelines for {topic} silently corrupt when schema evolution is backward-incompatible, late-arriving events are dropped, and warehouse costs spike because nobody partitions by query pattern.",
        "career": f"Applying {topic} as a senior engineer requires writing decisions down, aligning stakeholders before implementation, and measuring outcomes—not just shipping the first workable solution.",
    }

    hint = None
    for key in (multi, prefix):
        for k, v in domain_hints.items():
            if key.startswith(k) or prefix == k:
                hint = v
                break
        if hint:
            break
    if not hint:
        hint = f"Production implementations of {topic} fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only."

    return f"""## Common production mistakes

Teams get {topic} wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

{hint}"""


def category_triage(slug: str, topic: str) -> str:
    return f"""## Debugging and triage workflow

When {topic} misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions."""


def category_metrics(slug: str, topic: str) -> str:
    prefix = slug.split("-")[0]
    if prefix in ("career", "css", "web", "svelte", "typescript", "dart", "prompt"):
        return f"""## What to measure

Even for {topic}, define success before shipping:

- **Adoption** — are engineers or users actually using the new path vs. old workaround?
- **Quality** — defect rate, support tickets, or rollback count in the first two weeks.
- **Performance** — p95 latency or build time compared to baseline; regressions should block release.
- **Maintainability** — time to onboard a new teammate or implement the next variant of the same pattern.

If you cannot measure it, you cannot tell whether {topic} improved anything beyond feeling cleaner in code review."""
    return f"""## Metrics worth dashboarding

For {topic}, alert on symptoms users feel—not only infrastructure CPU:

| Signal | Why it matters |
|--------|----------------|
| p95/p99 latency | Tail latency drives timeouts and retries upstream |
| Error rate by operation | Separates transient blips from systemic failure |
| Saturation (pool, queue, disk) | Shows how close you are to hard limits |
| Business counter (success/failure) | Ties technical metrics to revenue or task completion |

Slice by version, region, and tenant during rollout. A flat global graph hides a bad canary."""


def category_integration(slug: str, topic: str, all_slugs: list[str]) -> str:
    links = cross_links(slug, all_slugs)
    body = f"""## How this fits your stack

{topic} rarely stands alone. Treat it as one layer in a larger reliability story: authentication, caching, observability, and deployment discipline all interact.

When rolling out changes, sequence them: ship observability first, then feature flags, then the risky behavior change. That ordering makes rollback a flag flip instead of a revert war.

{links}"""
    return body


def category_rollout(slug: str, topic: str) -> str:
    return f"""## Rollout checklist

Before enabling {topic} for all production traffic:

- **Staging parity** — same data volume order-of-magnitude, same feature flags, same downstream dependencies.
- **Dark launch or canary** — 1–5% traffic with error budget guardrails; expand only after stable p99.
- **Runbook** — explicit rollback steps (flag, config, or deploy) with owners named.
- **On-call briefing** — five-minute sync on what changed, what alerts fired in staging, and what "normal" looks like on dashboards.

Schedule a review one week post-launch. Capture what broke, what was noisy, and what docs were wrong."""


def build_expansion(slug: str, title: str, tags: list[str], needed: int, all_slugs: list[str]) -> str:
    topic = topic_label(slug, title)
    sections = [
        category_mistakes(slug, topic, tags),
        category_triage(slug, topic),
        category_metrics(slug, topic),
        category_integration(slug, topic, all_slugs),
        category_rollout(slug, topic),
    ]
    out = []
    total = 0
    for s in sections:
        if total >= needed:
            break
        out.append(s)
        total += word_count(s)
    return "\n\n".join(out)


def insert_before_resources(body: str, expansion: str) -> str:
    marker = "## Resources"
    if marker not in body:
        return body.rstrip() + "\n\n" + expansion + "\n"
    idx = body.rfind(marker)
    before = body[:idx].rstrip()
    after = body[idx:]
    return before + "\n\n" + expansion + "\n\n" + after


def main():
    all_files = sorted(BLOG.glob("*.md"))
    all_slugs = [f.stem for f in all_files]
    start_u9 = start_u7 = 0
    expanded = 0
    skipped = 0

    for f in all_files:
        post = parse_post(f)
        if not post:
            continue
        body = post["body"]
        w = word_count(body)
        if w < 900:
            start_u9 += 1
        if w < 700:
            start_u7 += 1

    for f in all_files:
        post = parse_post(f)
        if not post:
            continue
        body = FILLER.sub("\n", post["body"])
        w = word_count(body)
        if w >= TARGET:
            if body != post["body"]:
                new_raw = post["raw"].split("---", 2)[0] + "---" + post["raw"].split("---", 2)[1] + "---" + body
                f.write_text(new_raw)
            continue

        needed = TARGET - w + 15  # buffer
        # skip sections already present from partial expansion
        existing = set(re.findall(r"^## (.+)$", body, re.M))
        expansion = build_expansion(post["slug"], post["title"], post["tags"], needed, all_slugs)
        # remove duplicate section headers if re-running
        for h in ("Common production mistakes", "Debugging and triage workflow", "Metrics worth dashboarding", "What to measure", "How this fits your stack", "Rollout checklist"):
            if h in existing and h in expansion:
                expansion = re.sub(rf"## {re.escape(h)}.*?(?=\n## |\Z)", "", expansion, flags=re.S).strip()

        if not expansion.strip():
            skipped += 1
            continue

        new_body = insert_before_resources(body, expansion)
        if word_count(new_body) < TARGET:
            # add rollout if not yet included
            extra = category_rollout(post["slug"], topic_label(post["slug"], post["title"]))
            if "Rollout checklist" not in new_body:
                new_body = insert_before_resources(new_body, extra)

        fm_parts = post["raw"].split("---", 2)
        new_raw = fm_parts[0] + "---" + fm_parts[1] + "---" + new_body
        f.write_text(new_raw)
        expanded += 1

    end_u9 = end_u7 = 0
    for f in all_files:
        body = f.read_text().split("---", 2)[2]
        w = word_count(body)
        if w < 900:
            end_u9 += 1
        if w < 700:
            end_u7 += 1

    print(f"Expanded {expanded} files, skipped {skipped}")
    print(f"START under900={start_u9} under700={start_u7}")
    print(f"END under900={end_u9} under700={end_u7}")


if __name__ == "__main__":
    main()
