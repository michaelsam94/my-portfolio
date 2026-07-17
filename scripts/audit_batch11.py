#!/usr/bin/env python3
"""Track and audit humanize progress for batch-11 (indices 2750-end)."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
PROGRESS = ROOT / "scripts" / "humanize-progress" / "batch-11.json"
WORD_PAT = re.compile(r"\b[\w'-]+\b")
BOILERPLATE_MARKERS = (
    "Validate this in staging with production-like data volume",
    "Additional production considerations",
    "Measuring success in production",
    "We keep a living FAQ in the repo wiki",
    "Document the decision, owner, and rollback path in your team wiki",
    "## Production lessons for",
    "## Further reading notes",
    "### Deepening the practice",
    "## Common production mistakes",
    "## Debugging and triage workflow",
    "Optimizing for Lighthouse lab scores",
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
        "has_boilerplate": any(m in raw for m in BOILERPLATE_MARKERS),
    }


def slice_files():
    files = sorted(BLOG.glob("*.md"))
    return files[2750:]


def audit():
    files = slice_files()
    posts = [parse_post(f) for f in files]
    posts = [p for p in posts if p]
    done = [p for p in posts if not p["has_boilerplate"] and p["words"] >= 1200]
    boiler = [p for p in posts if p["has_boilerplate"]]
    under1200 = [p for p in posts if p["words"] < 1200]
    remaining = [p for p in posts if p["has_boilerplate"] or p["words"] < 1200]
    return {
        "batch": "11",
        "range": [2750, 2750 + len(posts) - 1],
        "total": len(posts),
        "done_count": len(done),
        "remaining_count": len(remaining),
        "boilerplate_remaining": len(boiler),
        "under_1200_count": len(under1200),
        "done": sorted(p["slug"] for p in done),
        "remaining": sorted(p["slug"] for p in remaining),
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }


def main():
    report = audit()
    PROGRESS.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({
        k: report[k] for k in (
            "total", "done_count", "remaining_count",
            "boilerplate_remaining", "under_1200_count",
        )
    }, indent=2))


if __name__ == "__main__":
    main()
