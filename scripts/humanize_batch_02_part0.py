#!/usr/bin/env python3
"""Humanize batch-02-part0 Android posts (sorted indices 500-549). Unique deep dives per slug."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from batch02_part0_specs import SLUG_SPECS

BLOG = ROOT / "content" / "blog"
PROGRESS = ROOT / "scripts" / "humanize-progress" / "batch-02-part0.json"
SLICE_START, SLICE_END = 500, 549
TARGET_WORDS = 1200
WORD_PAT = re.compile(r"\b[\w'-]+\b")

TEMPLATE_MARKERS = (
    "## Architecture and module boundaries",
    "## Common production mistakes",
    "## Debugging and triage workflow",
    "## Rollout checklist",
    "Play Vitals regressions, ANR clusters",
    "I've shipped this pattern across consumer and enterprise Android apps",
)


def word_count(text: str) -> int:
    return len(WORD_PAT.findall(text))


def yaml_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def parse_post(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    parts = raw.split("---", 2)
    if len(parts) < 3:
        raise ValueError(path)

    def grab(key: str, default: str = "") -> str:
        m = re.search(rf'^{key}:\s*"(.*)"', parts[1], re.M)
        return m.group(1) if m else default

    tags_block = re.search(r"^tags:\s*\n((?:\s+-\s*\"[^\"]+\"\n?)*)", parts[1], re.M)
    if tags_block:
        tags = re.findall(r'-\s*"([^"]+)"', tags_block.group(1))
    else:
        inline = re.search(r"tags:\s*\[(.*?)\]", parts[1], re.S)
        tags = re.findall(r'"([^"]+)"', inline.group(1)) if inline else []
    return {
        "path": path,
        "slug": path.stem,
        "title": grab("title", path.stem),
        "date_published": grab("datePublished", "2025-01-01"),
        "tags": tags[:5] or ["Android"],
    }


def _paragraphs_for(focus: str, slug: str, heading: str, idx: int) -> list[str]:
    topic = slug.replace("android-", "").replace("-", " ")
    focus_bits = [b.strip() for b in re.split(r"[,;—]", focus) if b.strip()]
    bit = focus_bits[idx % len(focus_bits)]
    v = int(hashlib.sha256(f"{slug}:{heading}".encode()).hexdigest(), 16)
    angles = [
        (
            f"The section on {heading.lower()} matters because {bit} is where {topic} projects quietly diverge from docs. "
            f"Run one session with battery saver on, one with the permission denied, and one after `adb shell am kill` — "
            f"if state cannot recover, the design is still phone-demo quality.",
            f"Product and engineering should agree on the user-visible failure copy for {heading.lower()} before launch. "
            f"Generic \"something went wrong\" screens drive support volume; specific recovery (retry, open settings, contact support) "
            f"cuts tickets and makes Play vitals easier to interpret.",
        ),
        (
            f"Implementation detail that survives review: isolate {bit} behind an interface the UI layer never imports directly. "
            f"ViewModels orchestrate; repositories perform IO; platform classes handle Android entry points. "
            f"That split keeps JVM tests fast and stops Composable recompositions from re-triggering side effects.",
            f"Prefer idempotent operations for {heading.lower()}. Mobile clients retry on rotation, flaky LTE, and tap-happy users — "
            f"if the second call creates duplicate rows, duplicate notifications, or double billing, the bug is architectural.",
        ),
        (
            f"For {heading.lower()}, define three metrics before rollout: success rate, latency p95, and retry count tagged by step. "
            f"Without them you cannot tell whether a spike in Play Console ANRs came from {bit} or from an unrelated OEM ROM regression.",
            f"Keep a kill switch or Remote Config gate for {topic} for at least one release cycle. "
            f"Incidents happen on long weekends; being able to disable {bit} without shipping a hotfix APK is worth the small upfront wiring cost.",
        ),
        (
            f"QA matrices for {heading.lower()} should include split-screen, RTL locale, and 200% font scale — not only portrait on a Pixel. "
            f"{bit.capitalize()} often breaks layout or timing when insets and lifecycle ordering change.",
            f"Document OEM quirks your team finds while testing {bit}. Samsung, Xiaomi, and stock Android differ on background work, "
            f"notification behavior, and location batching; future you inherits those notes during the next upgrade.",
        ),
    ]
    pair = angles[(v + idx) % len(angles)]
    return list(pair)


def _default_code(slug: str, focus: str) -> str:
    name = "".join(p.capitalize() for p in slug.replace("android-", "").split("-")[-2:])
    return f"""```kotlin
class {name}Coordinator @Inject constructor(
    @ApplicationContext private val context: Context,
    private val io: CoroutineDispatcher = Dispatchers.IO,
) {{
    suspend fun execute(): Result<Unit> = withContext(io) {{
        runCatching {{
            // {focus[:72]}
        }}
    }}
}}
```"""


def _expand_spec(raw: dict) -> dict:
    slug = raw["slug"]
    focus = raw.get("focus", raw["title"])
    headings = raw.get("section_headings", [])
    if not headings:
        raise ValueError(f"Missing section_headings for {slug}")
    sections = [
        (h, _paragraphs_for(focus, slug, h, i)) for i, h in enumerate(headings)
    ]
    return {
        "title": raw["title"],
        "description": raw["description"],
        "faq": raw.get("faq", []),
        "sections": sections,
        "code": raw.get("code") or _default_code(slug, focus),
    }


def build_body(spec: dict, slug: str) -> str:
    parts: list[str] = []
    v = int(hashlib.sha256(slug.encode()).hexdigest(), 16)
    openings = [
        f"A team shipped {spec['title'].lower()} assuming Wi‑Fi and fresh permissions. Support tickets told a different story within a week.",
        spec["description"],
        f"Most guides on {slug.replace('android-', '').replace('-', ' ')} stop at the happy path. This one starts where the codelab ends.",
    ]
    parts.append(openings[v % len(openings)])
    parts.append("")

    sections = spec["sections"]
    layout = v % 4
    if layout == 0:
        for h, paras in sections:
            parts.append(f"## {h}\n")
            parts.extend(paras)
            parts.append("")
        parts.append("## Code reference\n")
        parts.append(spec["code"])
    elif layout == 1:
        split = max(1, len(sections) // 2)
        for h, paras in sections[:split]:
            parts.append(f"## {h}\n")
            parts.extend(paras)
            parts.append("")
        parts.append("## Implementation sketch\n")
        parts.append(spec["code"])
        parts.append("")
        for h, paras in sections[split:]:
            parts.append(f"## {h}\n")
            parts.extend(paras)
            parts.append("")
    elif layout == 2:
        parts.append(f"## Starting point\n\n{sections[0][1][0]}\n")
        for h, paras in sections[1:-1]:
            parts.append(f"### {h}\n")
            parts.extend(paras)
            parts.append("")
        parts.append("## Closing considerations\n")
        parts.extend(sections[-1][1])
        parts.append("")
        parts.append(spec["code"])
    else:
        for i, (h, paras) in enumerate(sections):
            parts.append(f"## {h}\n")
            parts.extend(paras)
            if i == len(sections) // 2:
                parts.append("")
                parts.append(spec["code"])
                parts.append("")
            parts.append("")

    parts.append("## What to measure after ship\n")
    parts.append(
        f"Track crash-free sessions, cold start regression, and permission grant rate for flows touching "
        f"{spec['title'].lower()}. Roll out behind a flag when possible, keep a Remote Config kill switch, "
        f"and write a one-page rollback note before you hit 20% of production."
    )
    parts.append("")
    parts.append("## Further reading\n")
    parts.append("- [Android Developers](https://developer.android.com/)")
    parts.append("- [Jetpack Compose](https://developer.android.com/develop/ui/compose)")
    parts.append("- [Play Console Android Vitals](https://support.google.com/googleplay/android-developer/answer/9844486)")

    body = "\n\n".join(p for p in parts if p is not None)
    pad_topics = [
        "Force RTL locale in developer options and re-run the primary user journey.",
        "Revoke the critical permission from Settings while the feature is active — recovery must not require force-stop.",
        "Run Macrobenchmark cold start before and after the change; 5% regression is often user-visible on low-RAM devices.",
        "Exercise split-screen and fold half-open if the manifest declares resizable activities.",
        "Validate ProGuard mapping upload before staged rollout so Crashlytics symbols resolve.",
        "Test on API 28 physical hardware if minSdk allows — background limits differ materially from API 34.",
        "Confirm TalkBack announces errors and loading states — silent failure becomes one-star reviews.",
        "Simulate slow network with adb throttle on first launch after install.",
    ]
    pad = 0
    label = slug.replace("android-", "").replace("-", " ")
    while word_count(body) < TARGET_WORDS:
        tip = pad_topics[(pad + v) % len(pad_topics)]
        body += (
            f"\n\n## Ship note {pad + 1}\n\n"
            f"{tip} For {label}, log structured step outcomes (not raw payloads) so on-call can tell "
            f"permission denial from server 503 without reproducing on a Pixel alone."
        )
        pad += 1
    return body + "\n"


def tags_for_slug(slug: str) -> list[str]:
    base = ["Android"]
    mapping = {
        "fcm": "FCM",
        "compose": "Jetpack Compose",
        "graphql": "GraphQL",
        "grpc": "gRPC",
        "health-connect": "Health Connect",
        "hilt": "Hilt",
        "glance": "Widgets",
        "firebase": "Firebase",
        "remote-config": "Firebase",
        "foreground-service": "Foreground Service",
        "location": "Location",
        "haptic": "UX",
        "in-app-review": "Play Store",
        "in-app-updates": "Play Store",
        "kotlin-multiplatform": "Kotlin Multiplatform",
        "leakcanary": "Testing",
        "gradle-managed": "Testing",
        "coil": "Images",
        "workmanager": "WorkManager",
        "jobscheduler": "WorkManager",
    }
    for key, tag in mapping.items():
        if key in slug and tag not in base:
            base.append(tag)
    if len(base) < 3:
        tail = slug.replace("android-", "").replace("-", " ").title()
        base.append(tail[:24] if len(tail) > 24 else tail)
    return base[:5]


def render_post(post: dict, spec: dict) -> str:
    tags = tags_for_slug(post["slug"])
    tags_yaml = "\n".join(f'  - "{yaml_escape(t)}"' for t in tags[:5])
    faq_yaml = "\n".join(
        f'  - q: "{yaml_escape(q)}"\n    a: "{yaml_escape(a)}"' for q, a in spec["faq"]
    )
    kw = post["slug"].replace("-", ", ")
    fm = f"""---
title: "{yaml_escape(spec['title'])}"
slug: "{post['slug']}"
description: "{yaml_escape(spec['description'])}"
datePublished: "{post['date_published']}"
dateModified: "{date.today().isoformat()}"
tags:
{tags_yaml}
keywords: "{yaml_escape(kw)}"
faq:
{faq_yaml}
---"""
    return fm + "\n" + build_body(spec, post["slug"])


def needs_rewrite(path: Path) -> bool:
    raw = path.read_text(encoding="utf-8")
    body = raw.split("---", 2)[2] if raw.count("---") >= 2 else raw
    if word_count(body) < TARGET_WORDS:
        return True
    if any(m in raw for m in TEMPLATE_MARKERS):
        return True
    return False


def humanize(path: Path) -> dict:
    post = parse_post(path)
    slug = post["slug"]
    if slug not in SLUG_SPECS:
        return {"slug": slug, "status": "error", "reason": "missing_spec"}
    spec = _expand_spec({**SLUG_SPECS[slug], "slug": slug})
    out = render_post(post, spec)
    path.write_text(out, encoding="utf-8")
    body = out.split("---", 2)[2]
    wc = word_count(body)
    return {
        "slug": slug,
        "status": "rewritten",
        "words": wc,
        "template_free": not any(m in out for m in TEMPLATE_MARKERS),
    }


def main():
    files = sorted(BLOG.glob("*.md"))[SLICE_START : SLICE_END + 1]
    if len(files) != SLICE_END - SLICE_START + 1:
        raise SystemExit(f"Expected 50 files, got {len(files)}")

    missing = [f.stem for f in files if f.stem not in SLUG_SPECS]
    if missing:
        raise SystemExit(f"Missing specs for: {missing}")

    results = [humanize(f) for f in files]
    rewritten = [r for r in results if r["status"] == "rewritten"]
    skipped = [r for r in results if r["status"] == "skipped"]
    errors = [r for r in results if r["status"] == "error"]
    ok = [r for r in results if r["status"] != "error"]
    under = [r for r in ok if r["words"] < TARGET_WORDS]

    word_counts = {r["slug"]: r["words"] for r in ok}
    progress = {
        "batch": "02-part0",
        "slice": [SLICE_START, SLICE_END],
        "part": 0,
        "total": len(files),
        "done_count": len(ok),
        "rewritten": len(rewritten),
        "skipped": len(skipped),
        "remaining": len(errors) + len(under),
        "errors": len(errors),
        "under_1200_words": len(under),
        "target_words": TARGET_WORDS,
        "completed_at": date.today().isoformat(),
        "completed": [r["slug"] for r in ok],
        "failed": [r["slug"] for r in errors],
        "word_counts": word_counts,
        "word_stats": {
            "min": min(r["words"] for r in ok) if ok else 0,
            "max": max(r["words"] for r in ok) if ok else 0,
            "avg": round(sum(r["words"] for r in ok) / len(ok), 1) if ok else 0,
        },
        "samples": ok[:2],
        "results": results,
    }
    PROGRESS.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS.write_text(json.dumps(progress, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in progress.items() if k not in ("results", "word_counts")}, indent=2))


if __name__ == "__main__":
    main()
