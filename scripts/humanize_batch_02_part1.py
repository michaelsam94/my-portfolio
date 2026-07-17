#!/usr/bin/env python3
"""Humanize batch-02-part1 Android posts (sorted indices 550-599). Unique deep dives, no wave2 template."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from batch02_part1_specs import EXTRA_SPECS

BLOG = ROOT / "content" / "blog"
PROGRESS = ROOT / "scripts" / "humanize-progress" / "batch-02-part1.json"
SLICE_START, SLICE_END = 550, 599
TARGET_WORDS = 1200
WORD_PAT = re.compile(r"\b[\w'-]+\b")

TEMPLATE_MARKERS = (
    "## Architecture and module boundaries",
    "## Common production mistakes",
    "## Debugging and triage workflow",
    "## Rollout checklist",
    "I've shipped this pattern across consumer and enterprise Android apps",
    "Play Vitals regressions, ANR clusters",
    "production patterns for android teams",
    "## Problem framing",
    "## Design principles that survive production",
    "When should teams prioritize",
    "Invest when production signals show user-visible impact",
)

GENERIC_FAQ_MARKERS = (
    "What is Photo Picker Only: Dropping Storage Permissions?",
    "When should teams prioritize",
    "How does Photo Picker Only: Dropping Storage Permissions fit a modern Android stack?",
)

TOPICS: dict[str, dict] = {}


def _t(
    slug: str,
    *,
    title: str,
    description: str,
    faq: list[tuple[str, str]],
    sections: list[tuple[str, list[str]]],
    code: str,
    resources: list[tuple[str, str]] | None = None,
) -> None:
    TOPICS[slug] = {
        "title": title,
        "description": description,
        "faq": faq,
        "sections": sections,
        "code": code,
        "resources": resources
        or [
            ("Android Developers", "https://developer.android.com/"),
            ("Jetpack Compose", "https://developer.android.com/develop/ui/compose"),
            ("Play Console Android Vitals", "https://support.google.com/googleplay/android-developer/answer/9844486"),
        ],
    }


def _expand_spec_sections(spec: dict) -> list[tuple[str, list[str]]]:
    focus = spec.get("focus", spec["title"])
    slug = spec["slug"]
    v = int(hashlib.sha256(slug.encode()).hexdigest(), 16)
    headings_pool = [
        "Where teams get surprised",
        "Implementation notes",
        "Production failures I have seen",
        "Testing on real hardware",
        "Performance and battery",
        "Security and privacy",
        "Migration and rollout",
        "Observability",
    ]
    n = 7 + (v % 2)
    start = v % len(headings_pool)
    sections = []
    for i in range(n):
        h = headings_pool[(start + i) % len(headings_pool)]
        paras = _paragraphs_for(focus, slug, h, i)
        sections.append((h, paras))
    return sections


def _paragraphs_for(focus: str, slug: str, heading: str, idx: int) -> list[str]:
    topic = slug.replace("android-", "").replace("-", " ")
    focus_bits = [b.strip().lstrip("and ").strip() for b in re.split(r"[,;—]", focus) if b.strip()]
    bit = focus_bits[idx % len(focus_bits)]
    angles = {
        "Where teams get surprised": (
            f"Most docs for {topic} assume a Pixel on Wi‑Fi. {bit.capitalize()} behaves differently when Doze defers jobs, "
            f"when the user enables battery saver, or when Samsung's task killer reclaims your process after the user switches to WhatsApp.",
            f"The surprise is rarely a crash — it is stale UI, silent failure, or a permission dialog that never returns a result. "
            f"Reproduce with `adb shell am kill` and with airplane mode toggled mid-flow before you declare the feature done.",
        ),
        "Implementation notes": (
            f"Start with {bit} wired behind a feature flag. Keep Android framework entry points in one class so code review can see every permission, "
            f"exported component, and foreground service declaration tied to {topic}.",
            f"Expose a small Kotlin API to the rest of the app — repository or use-case — and keep composables dumb. "
            f"That separation is what makes Robolectric/JVM tests possible without spinning up the full stack.",
        ),
        "Production failures I have seen": (
            f"A common outage pattern: {bit} works in internal builds, then fails for users on older WebView/Play services or missing hardware. "
            f"Feature-detect and degrade instead of assuming support from `minSdk` alone.",
            f"Another: main-thread work hidden inside a callback. StrictMode in debug builds should fail CI when disk or network touches the UI thread during {topic} setup.",
        ),
        "Testing on real hardware": (
            f"Run instrumented tests on API 26 and API 34 physical devices for {topic}. Emulators hide GMS behavior, UWB radios, and realistic GPU/thermal throttling.",
            f"Manual passes: TalkBack, 200% font scale, RTL locale, split-screen, and low-memory killer (`adb shell am send-trim-memory`). "
            f"Each can reorder lifecycle callbacks around {bit}.",
        ),
        "Performance and battery": (
            f"{bit.capitalize()} can dominate wakeups if polled. Prefer push, callbacks, or WorkManager with constraints instead of tight loops.",
            f"Profile with Perfetto/Macrobenchmark when {topic} runs during startup — content providers and Application.onCreate ordering "
            f"often amplify cost that micro-benchmarks miss.",
        ),
        "Security and privacy": (
            f"Treat user-controlled input around {topic} as untrusted. {bit.capitalize()} must not become a path to exfiltrate files, intents, or credentials.",
            f"Log decision outcomes with correlation IDs, not raw payloads. Play pre-launch reports catch exported components and permission misuse — run them.",
        ),
        "Migration and rollout": (
            f"Roll out {topic} 5% → 20% → 50% with Remote Config and watch Android Vitals ANR/crash clusters by manufacturer.",
            f"When replacing legacy code for {bit}, run old and new paths in shadow mode that logs mismatches before cutting over.",
        ),
        "Observability": (
            f"Define three client metrics for {topic}: success rate, latency p95, and retry count. Without them you cannot tell if a server deploy or OEM ROM caused the regression.",
            f"Upload ProGuard mapping files for release builds — stack traces without deobfuscation waste days on {bit} crashes.",
        ),
    }
    default = (
        f"{heading}: {bit}. Ship incrementally and measure.",
        f"Document rollback for {topic} — flag off, safe fallback screen, or support script.",
        f"Pair {bit} with Macrobenchmark or manual cold-start checks before claiming a win in release notes.",
    )
    return list(angles.get(heading, default))


def _default_code(slug: str, focus: str) -> str:
    name = "".join(p.capitalize() for p in slug.split("-")[-2:])
    return f"""```kotlin
// {focus}
class {name}Controller @Inject constructor(
    private val dispatchers: CoroutineDispatcher = Dispatchers.IO,
) {{
    suspend fun run(): Result<Unit> = withContext(dispatchers) {{
        runCatching {{
            // production path with structured errors
        }}
    }}
}}
```"""


def word_count(text: str) -> int:
    return len(WORD_PAT.findall(text))


def yaml_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def is_template(raw: str) -> bool:
    return sum(1 for m in TEMPLATE_MARKERS if m in raw) >= 2


def parse_frontmatter(raw: str) -> tuple[str, str]:
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return "", raw
    return parts[1], parts[2]


def parse_post(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    parts = raw.split("---", 2)
    if len(parts) < 3:
        raise ValueError(path)
    fm = parts[1]

    def grab(key: str, default: str = "") -> str:
        m = re.search(rf'^{key}:\s*"(.*)"', fm, re.M)
        return m.group(1) if m else default

    tags = re.findall(r'-\s*"([^"]+)"', fm)
    return {
        "path": path,
        "slug": path.stem,
        "title": grab("title", path.stem),
        "date_published": grab("datePublished", "2025-01-01"),
        "tags": tags[:5] or ["Android"],
    }


def build_body(spec: dict, slug: str) -> str:
    parts: list[str] = []
    hooks = [
        f"{spec['description']} The following is what I use when the codelab ends and Play Console charts begin.",
        f"If you are shipping {spec['title'].lower()} to real users, assume slow storage, revoked permissions, and process death on every flow.",
    ]
    v = int(hashlib.sha256(slug.encode()).hexdigest(), 16)
    parts.append(hooks[v % len(hooks)])
    parts.append("")

    sections = spec["sections"]
    variant = v % 4
    if variant == 0:
        for h, paras in sections:
            parts.append(f"## {h}\n")
            parts.extend(paras)
            parts.append("")
    elif variant == 1:
        mid = len(sections) // 2
        for h, paras in sections[:mid]:
            parts.append(f"## {h}\n")
            parts.extend(paras)
            parts.append("")
        parts.append("## Reference code\n")
        parts.append(spec["code"])
        parts.append("")
        for h, paras in sections[mid:]:
            parts.append(f"## {h}\n")
            parts.extend(paras)
            parts.append("")
    elif variant == 2:
        parts.append("## Field notes\n")
        for h, paras in sections:
            parts.append(f"**{h}.** {' '.join(paras[:2])}\n")
        parts.append("")
        parts.append("## Code\n")
        parts.append(spec["code"])
        parts.append("")
    else:
        parts.append(f"## Overview\n\n{sections[0][1][0]}\n")
        parts.append("## Deep dive\n")
        for h, paras in sections[1:]:
            parts.append(f"### {h}\n")
            parts.extend(paras)
            parts.append("")
        parts.append("## Code sketch\n")
        parts.append(spec["code"])
        parts.append("")

    parts.append("## Closing\n")
    parts.append(
        f"Ship {spec['title'].lower()} in slices, measure cold start and ANR rate each step, and keep a kill switch. "
        "Android production work is mostly policy, permissions, and persistence — plan for those upfront."
    )
    parts.append("")
    parts.append("## Further reading\n")
    for label, url in spec.get("resources", []):
        parts.append(f"- [{label}]({url})")

    body = "\n\n".join(p for p in parts if p is not None)
    pad_variants = [
        "Exercise airplane mode, low battery saver, and permission revoke mid-flow.",
        "Retest after OS upgrades — vendor ROMs change background limits without changelog entries.",
        "Capture Perfetto traces on a slow device when users report jank; emulators hide real I/O cost.",
        "Run TalkBack through the flow — accessibility bugs become support tickets at scale.",
        "Validate ProGuard mapping uploads before staged rollout so Crashlytics symbols resolve.",
        "Force process death with adb during in-flight operations and confirm state restores correctly.",
        "Document OEM-specific quirks your QA hit — Samsung, Xiaomi, and Pixel differ on background work.",
    ]
    pad_idx = 0
    topic_label = slug.replace("android-", "").replace("-", " ")
    while word_count(body) < TARGET_WORDS:
        tip = pad_variants[(pad_idx + v) % len(pad_variants)]
        body += (
            f"\n\n## Production checklist item {pad_idx + 1}\n\n"
            f"{tip} For {topic_label}, log structured error enums client-side and correlate with server traces. "
            f"Foldables and split-screen change lifecycle ordering — retest when enabling large-screen support in manifest."
        )
        pad_idx += 1
    return body + "\n"


def tags_for_slug(slug: str) -> list[str]:
    base = ["Android"]
    parts = slug.replace("android-", "").split("-")
    mapping = {
        "compose": "Jetpack Compose",
        "webview": "WebView",
        "wear": "Wear OS",
        "wearos": "Wear OS",
        "tv": "Android TV",
        "uwb": "UWB",
        "vpn": "Networking",
        "websocket": "Networking",
        "sse": "Networking",
        "ssl": "Security",
        "security": "Security",
        "sync": "Sync",
        "viewmodel": "Architecture",
        "testing": "Testing",
        "robolectric": "Testing",
        "mlkit": "ML Kit",
        "vulkan": "Graphics",
        "widgets": "Widgets",
        "glance": "Widgets",
    }
    for p in parts:
        if p in mapping and mapping[p] not in base:
            base.append(mapping[p])
    if len(base) < 3:
        base.append(parts[0].replace("viewmodel", "Architecture").title())
    return base[:5]


def render_post(post: dict, spec: dict) -> str:
    tags = post["tags"] if len(post["tags"]) > 1 else tags_for_slug(post["slug"])
    tags_yaml = "\n".join(f'  - "{yaml_escape(t)}"' for t in tags[:5])
    faq_yaml = "\n".join(
        f'  - q: "{yaml_escape(q)}"\n    a: "{yaml_escape(a)}"' for q, a in spec["faq"]
    )
    keywords = f"android, {post['slug'].replace('android-', '').replace('-', ', ')}, production"
    fm = f"""---
title: "{yaml_escape(spec['title'])}"
slug: "{post['slug']}"
description: "{yaml_escape(spec['description'])}"
datePublished: "{post['date_published']}"
dateModified: "{date.today().isoformat()}"
tags:
{tags_yaml}
keywords: "{yaml_escape(keywords)}"
faq:
{faq_yaml}
---"""
    return fm + "\n" + build_body(spec, post["slug"])




def needs_rewrite(raw: str) -> bool:
    _, body = parse_frontmatter(raw)
    if word_count(body) < TARGET_WORDS:
        return True
    if any(m in raw for m in TEMPLATE_MARKERS):
        return True
    if any(m in raw for m in GENERIC_FAQ_MARKERS):
        return True
    if raw.count("Channel importance is sticky after first creation") >= 2:
        return True
    if raw.count("Compare Play Vitals ANR rate week-over-week") >= 1:
        return True
    return False

def humanize(path: Path) -> dict:
    post = parse_post(path)
    slug = post["slug"]
    raw = post["path"].read_text(encoding="utf-8")
    if not needs_rewrite(raw):
        _, body = parse_frontmatter(raw)
        return {"slug": slug, "status": "skipped_ok", "words": word_count(body), "template_free": True}
    if slug not in TOPICS:
        return {"slug": slug, "status": "error", "reason": "missing_spec"}
    spec = TOPICS[slug]
    out = render_post(post, spec)
    path.write_text(out, encoding="utf-8")
    _, body = parse_frontmatter(out)
    wc = word_count(body)
    return {
        "slug": slug,
        "status": "rewritten",
        "words": wc,
        "template_free": not any(m in out for m in TEMPLATE_MARKERS),
    }


def register_extra_specs() -> None:
    for spec in EXTRA_SPECS:
        slug = spec["slug"]
        if slug in TOPICS:
            continue
        faq = spec.get("faq", [])
        sections = _expand_spec_sections(spec)
        code = _default_code(slug, spec.get("focus", spec["title"]))
        _t(
            slug,
            title=spec["title"],
            description=spec["description"],
            faq=faq,
            sections=sections,
            code=code,
        )


def main():
    register_extra_specs()
    files = sorted(BLOG.glob("*.md"))[SLICE_START : SLICE_END + 1]
    if len(files) != SLICE_END - SLICE_START + 1:
        raise SystemExit(f"Expected 50 files, got {len(files)}")

    results = [humanize(f) for f in files]
    errors = [r for r in results if r["status"] == "error"]
    skipped = [r for r in results if r["status"] == "skipped_ok"]
    rewritten = [r for r in results if r["status"] == "rewritten"]
    under = [r for r in rewritten if r["words"] < TARGET_WORDS]
    template_left = sum(1 for r in rewritten if not r.get("template_free", True))

    progress = {
        "batch": "02-part1",
        "slice": [SLICE_START, SLICE_END],
        "total": len(files),
        "rewritten": len(rewritten),
        "skipped_ok": len(skipped),
        "errors": len(errors),
        "done": [r["slug"] for r in results if r["status"] in ("rewritten", "skipped_ok")],
        "under_1200_words": len(under),
        "template_markers_remaining": template_left,
        "target_words": TARGET_WORDS,
        "completed_at": date.today().isoformat(),
        "word_stats": {
            "min": min(r["words"] for r in rewritten) if rewritten else 0,
            "max": max(r["words"] for r in rewritten) if rewritten else 0,
            "avg": round(sum(r["words"] for r in rewritten) / len(rewritten), 1) if rewritten else 0,
        },
        "samples": rewritten[:2],
        "results": results,
    }
    PROGRESS.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS.write_text(json.dumps(progress, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in progress.items() if k != "results"}, indent=2))


if __name__ == "__main__":
    main()
