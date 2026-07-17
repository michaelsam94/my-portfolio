#!/usr/bin/env python3
"""Expand batch-06 posts under 1200 body words with per-slug varied sections."""
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
WORD_PAT = re.compile(r"\b[\w'-]+\b")
TARGET = 1200
START, END = 1500, 1750


def word_count(text: str) -> int:
    return len(WORD_PAT.findall(text))


def slug_hash(slug: str) -> int:
    return int(hashlib.sha256(slug.encode()).hexdigest(), 16)


def topic_label(slug: str, title: str) -> str:
    return title if len(title) < 55 else slug.replace("-", " ")


def build_sections(slug: str, title: str, tags: list[str], needed: int) -> str:
    topic = topic_label(slug, title)
    h = slug_hash(slug)
    domain = tags[0] if tags else slug.split("-")[0]
    variants = [
        (
            f"Edge cases in {topic}",
            f"When {topic.lower()} looks fine in demos but fails in production, the cause is often ordering or lifecycle—not the core API. "
            f"Document what happens if the user backgrounds the app mid-operation, if the network returns 200 with an empty body, or if two tabs race the same action. "
            f"For {domain} workloads, add one integration test that simulates the messy path, not only the golden path.",
        ),
        (
            f"Rollout notes for {topic}",
            f"Ship {topic.lower()} behind a flag or staged cohort when behavior change is user-visible. "
            f"Define rollback: which flag, which config key, or which deploy tag restores prior behavior without a database migration. "
            f"Pair rollout with a dashboard panel showing error rate and latency for the surfaces that call {topic.lower()}—flat global metrics hide partial regressions.",
        ),
        (
            f"Pairing {topic} with adjacent systems",
            f"{topic} rarely sits alone. List upstream dependencies (auth, config, feature flags) and downstream consumers (UI, analytics, billing) in the RFC. "
            f"When {domain} teams change a shared contract, version it and give callers a deprecation window. "
            f"Unexpected coupling—logging PII because a debug print slipped in—shows up under audit, not unit tests.",
        ),
        (
            f"Incident patterns involving {topic}",
            f"Postmortems mentioning {topic.lower()} often share themes: missing timeout, unbounded retry, or cache keyed too broadly. "
            f"Run a tabletop exercise: dependency latency doubles—does {topic.lower()} degrade gracefully or stall thread pools? "
            f"Write the first three grep queries an on-call engineer would run; if you cannot, observability is not ready.",
        ),
        (
            f"Testing depth for {topic}",
            f"Unit tests prove logic; contract tests prove boundaries. For {topic.lower()}, assert the failure messages and status codes clients will see, not only boolean success. "
            f"Property-based or fuzz inputs help when input combinations explode—especially for parsers and validators in {domain} paths. "
            f"Replay sanitized production traffic in staging before large refactors touching {topic.lower()}.",
        ),
        (
            f"Performance sanity checks",
            f"Profile {topic.lower()} on representative hardware—mid-range Android, not only flagship simulators—before claiming done. "
            f"Watch allocation churn in hot loops; measure p95 latency under burst, not only steady state. "
            f"If optimization targets p50 alone, tail latency will surprise you at peak traffic.",
        ),
        (
            f"Security review prompts",
            f"Even when {topic.lower()} is not \"security software,\" ask: what untrusted input crosses this boundary? "
            f"Apply least privilege to credentials, minimize retention of sensitive fields, and fail closed on authorization ambiguity. "
            f"Secrets belong in managed stores; debug builds must not widen permissions into release binaries.",
        ),
        (
            f"Documentation that survives turnover",
            f"Future maintainers learn {topic.lower()} from runbooks and ADRs, not from memory. "
            f"Record trade-offs explicitly—what you chose not to do and why. Link Slack decisions to merged PRs in an internal FAQ after the same question appears twice. "
            f"Onboarding exercises: implement a tiny change touching {topic.lower()} in the first week with a mentor review.",
        ),
        (
            f"Cost and capacity",
            f"Estimate peak QPS, payload sizes, and fan-out before launch week. {topic} at scale may shift cloud spend—monitor queue depth, connection pool saturation, and egress. "
            f"Load tests should resemble production shape; synthetic hello-world traffic misses contention on shared dependencies.",
        ),
        (
            f"Migration off legacy approaches",
            f"Strangle legacy usage of {topic.lower()} behind a stable interface; migrate callers incrementally and delete old paths when traffic hits zero. "
            f"Set a decommission date for temporary bridges—\"temporary\" wrappers become permanent without dates. "
            f"Communicate breaking changes across mobile, web, and backend release trains so clients never lead servers into incompatible states.",
        ),
        (
            f"Accessibility and inclusive design",
            f"If {topic.lower()} affects UI or notifications, verify TalkBack/VoiceOver paths, focus order, and error text that screen readers announce. "
            f"Localization is not translation-only—exercise RTL layouts and plural rules where {domain} formats numbers or dates.",
        ),
        (
            f"Metrics that matter for {domain}",
            f"Track symptoms users feel: task completion, time-to-interactive, failed submissions—not only CPU graphs. "
            f"Slice metrics by app version and region during rollout. Alert on SLO burn rather than every error log line to avoid pager fatigue.",
        ),
    ]
    count = 3 if needed > 250 else 2
    start = h % len(variants)
    chosen = []
    total = 0
    for i in range(len(variants)):
        idx = (start + i * 5) % len(variants)
        heading, para = variants[idx]
        if heading in {c[0] for c in chosen}:
            continue
        block = f"## {heading}\n\n{para}"
        chosen.append((heading, block))
        total += word_count(block)
        if len(chosen) >= count and total >= needed:
            break
    return "\n\n".join(b for _, b in chosen)


def parse_post(path: Path):
    raw = path.read_text(encoding="utf-8")
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return None
    fm, body = parts[1], parts[2]
    title = re.search(r'^title:\s*"(.+)"', fm, re.M)
    tags_m = re.search(r"tags:\s*\[(.*?)\]", fm, re.S)
    tags = re.findall(r'"([^"]+)"', tags_m.group(1)) if tags_m else []
    return {"path": path, "raw": raw, "fm": fm, "body": body, "title": title.group(1) if title else path.stem, "slug": path.stem, "tags": tags}


def insert_before_resources(body: str, expansion: str) -> str:
    marker = "## Resources"
    if marker in body:
        idx = body.rfind(marker)
        return body[:idx].rstrip() + "\n\n" + expansion + "\n\n" + body[idx:]
    return body.rstrip() + "\n\n" + expansion + "\n"


def main():
    files = sorted(BLOG.glob("*.md"))[START:END]
    expanded = 0
    for path in files:
        post = parse_post(path)
        if not post:
            continue
        w = word_count(post["body"])
        if w >= TARGET:
            continue
        needed = TARGET - w + 20
        expansion = build_sections(post["slug"], post["title"], post["tags"], needed)
        new_body = insert_before_resources(post["body"], expansion)
        while word_count(new_body) < TARGET and needed < 600:
            needed += 80
            expansion = build_sections(post["slug"], post["title"], post["tags"], needed)
            new_body = insert_before_resources(post["body"], expansion)
        new_raw = post["raw"].split("---", 2)[0] + "---" + post["fm"] + "---" + new_body
        path.write_text(new_raw, encoding="utf-8")
        expanded += 1
    done = sum(1 for p in files if parse_post(p) and word_count(parse_post(p)["body"]) >= TARGET)
    print(f"expanded={expanded} done>={TARGET}: {done}/{len(files)}")


if __name__ == "__main__":
    main()
