#!/usr/bin/env python3
"""Write complete unique deep-dives for b11g batch 12-16 slugs."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

BLOG = Path(__file__).resolve().parents[1] / "content" / "blog"
DATE_MOD = "2026-07-17"
MIN_WC = 1200

FORBIDDEN = [
    "Common production mistakes",
    "Validate this in staging",
    "Deepening the practice",
    "Operational depth for",
    "Shipping ",
    " changes without a rollback",
    "What broke first on dashboards",
    "Handoff to adjacent teams",
]

SLUGS: list[str] = []
for batch in range(12, 17):
    p = Path(f"/tmp/b11g_{batch}.txt")
    if p.exists():
        SLUGS.extend(line.strip() for line in p.read_text().splitlines() if line.strip())


def wc(body: str) -> int:
    return len(re.sub(r"```.*?```", "", body, flags=re.DOTALL).split())


def read_fm(slug: str) -> dict:
    text = (BLOG / f"{slug}.md").read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not m:
        raise ValueError(f"No frontmatter: {slug}")
    return yaml.safe_load(m.group(1))


def write_post(slug: str, body: str, faq: list[dict] | None = None, description: str | None = None) -> int:
    fm = read_fm(slug)
    fm["slug"] = slug
    fm["dateModified"] = DATE_MOD
    if faq:
        fm["faq"] = faq
    if description:
        fm["description"] = description
    for forbidden in FORBIDDEN:
        if forbidden in body:
            raise ValueError(f"{slug}: forbidden pattern {forbidden!r}")
    header = yaml.dump(fm, sort_keys=False, allow_unicode=True, default_flow_style=False)
    (BLOG / f"{slug}.md").write_text(f"---\n{header}---\n\n{body.strip()}\n", encoding="utf-8")
    return wc(body)


# Import bodies from companion modules
from b11g_bodies_a import BODIES_A  # noqa: E402
from b11g_bodies_b import BODIES_B  # noqa: E402
from b11g_bodies_c import BODIES_C  # noqa: E402
from b11g_bodies_d import BODIES_D  # noqa: E402

ALL_BODIES = {**BODIES_A, **BODIES_B, **BODIES_C, **BODIES_D}


def main() -> int:
    missing = [s for s in SLUGS if s not in ALL_BODIES]
    if missing:
        print("Missing bodies:", missing)
        return 1
    counts: dict[str, int] = {}
    for slug in SLUGS:
        data = ALL_BODIES[slug]
        counts[slug] = write_post(
            slug,
            data["body"],
            faq=data.get("faq"),
            description=data.get("description"),
        )
    low = {s: w for s, w in counts.items() if w < MIN_WC}
    print(f"Written: {len(counts)}")
    print(f"Under {MIN_WC}: {len(low)}")
    if low:
        for s, w in sorted(low.items(), key=lambda x: x[1]):
            print(f"  {w} {s}")
        return 1
    print(f"Min: {min(counts.values())}, Max: {max(counts.values())}, Avg: {sum(counts.values()) // len(counts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
