#!/usr/bin/env python3
"""Track and audit humanize progress for batch-06 (indices 1500-1749)."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
PROGRESS = ROOT / "scripts" / "humanize-progress" / "batch-06.json"
WORD_PAT = re.compile(r"\b[\w'-]+\b")
TARGET = 1200
TEMPLATE_MARKERS = (
    "Problem framing",
    "Design principles that survive production",
    "production patterns for kotlin teams",
)


def word_count(text: str) -> int:
    return len(WORD_PAT.findall(text))


def parse_post(path: Path):
    raw = path.read_text(encoding="utf-8")
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return None
    fm, body = parts[1], parts[2]
    slug_m = re.search(r'^slug:\s*"(.+)"', fm, re.M)
    title_m = re.search(r'^title:\s*"(.+)"', fm, re.M)
    return {
        "path": str(path.relative_to(ROOT)),
        "slug": slug_m.group(1) if slug_m else path.stem,
        "title": title_m.group(1) if title_m else path.stem,
        "words": word_count(body),
        "is_template": any(m in raw for m in TEMPLATE_MARKERS),
    }


def slice_files():
    return sorted(BLOG.glob("*.md"))[1500:1750]


def audit():
    files = slice_files()
    posts = [parse_post(f) for f in files]
    posts = [p for p in posts if p]
    templates = [p for p in posts if p["is_template"]]
    under = [p for p in posts if p["words"] < TARGET]
    done = [p for p in posts if not p["is_template"] and p["words"] >= TARGET]
    slugs = [p["slug"] for p in posts]
    return {
        "batch": "06",
        "indices": "1500-1749",
        "total": len(posts),
        "target_words": TARGET,
        "done_count": len(done),
        "template_remaining": len(templates),
        "under_1200_count": len(under),
        "templates": [p["slug"] for p in templates],
        "under_1200": [{"slug": p["slug"], "words": p["words"]} for p in under],
        "samples": {
            "first": slugs[:3],
            "last": slugs[-3:],
            "rewritten_templates": [
                "kotlin-scope-functions-let-apply",
                "kotlin-sam-conversions-lambdas",
                "kotlin-multiplatform-navigation",
            ],
            "word_counts": {
                p["slug"]: p["words"]
                for p in posts
                if p["slug"]
                in (
                    "forms-validation-zod-react-hook-form",
                    "go-error-handling-wrapping",
                    "kotlin-scope-functions-let-apply",
                    "kotlin-multiplatform-spm",
                    "kafka-exactly-once-semantics",
                )
            },
        },
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "status": "complete" if len(done) == len(posts) and not templates else "partial",
    }


def main():
    report = audit()
    PROGRESS.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(
        {k: report[k] for k in ("total", "done_count", "template_remaining", "under_1200_count", "status")},
        indent=2,
    ))


if __name__ == "__main__":
    main()
