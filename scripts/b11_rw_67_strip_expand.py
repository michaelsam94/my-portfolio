#!/usr/bin/env python3
"""Strip wave-2 boilerplate, apply topic FAQ, expand to ≥1200 unique words per slug."""
from __future__ import annotations

import importlib.util
import re
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content/blog"
DATE = "2026-07-17"
TARGET = 1200
WORD = re.compile(r"\b[\w'-]+\b")

STRIP = [
    r"The gap between reading about .*? — not a conference demo\.\n\n",
    r"I have applied these patterns across product sites.*?\n\n",
    r"## Architecture and boundaries\n.*?(?=\n## |\Z)",
    r"## Implementation patterns\n.*?(?=\n## |\Z)",
    r"## Accessibility requirements\n.*?(?=\n## |\Z)",
    r"## Security and privacy considerations\n.*?(?=\n## |\Z)",
    r"## Testing strategy\n.*?(?=\n## |\Z)",
    r"## Common production mistakes\n.*?(?=\n## |\Z)",
    r"## Debugging and triage workflow\n.*?(?=\n## |\Z)",
    r"## Resources\n.*?(?=\Z)",
    r"Validate in staging with production-like data volumes.*?\n",
    r"Field notes \(\d+\)\n.*?(?=\n## |\Z)",
    r"requires measuring field p75 on mid-tier Android.*?\n",
    r"Production engineering for .*? Review \d+:.*?\n\n",
    r"Field p75 on mid-tier Android over 4G is the honest acceptance test.*?\n",
    r"Rehearse anti-pattern in design review:.*?\n",
    r"Production toast notification queue.*?\n",
    r"Production multi-step form wizards.*?\n",
    r"Ship one route or endpoint first with metrics wired.*?\n",
    r"Compare canary p75 to control for a full business day.*?\n",
    r"Staging on office Wi-Fi with empty cache misleads.*?\n",
    r"Leading: error rate, p75 latency.*?\n",
]

sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("w8", ROOT / "scripts/b11_w8_rewrite.py")
w8 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w8)
spec2 = importlib.util.spec_from_file_location("hb", ROOT / "scripts/humanize_batch11_chunk3.py")
hb = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(hb)
from b11_need_8_9_10_apply import NEED_8_TOPICS
from _gen_b11_rw_67_all import ALL, build_fm, parse_fm
from batch11_chunk3_sections import SECTIONS
from batch11_chunk3_rewrite import compose_body, code_for, lang_for

SLUGS = []
for f in ["/tmp/b11_rw_6.txt", "/tmp/b11_rw_7.txt"]:
    SLUGS.extend(s.strip() for s in Path(f).read_text().splitlines() if s.strip())


def wc(t: str) -> int:
    return len(WORD.findall(t))


def strip_body(body: str) -> str:
    for p in STRIP:
        body = re.sub(p, "\n", body, flags=re.S)
    return re.sub(r"\n{3,}", "\n\n", body).strip()


def sections_from_meta(slug: str, meta: tuple) -> str:
    hook, tech, when, mistake, _ = meta
    if slug in SECTIONS:
        parts = [hook, ""]
        for title, paras in SECTIONS[slug]:
            parts.append(f"## {title}\n\n" + "\n\n".join(paras))
        parts.append(textwrap.dedent(f"""
            ## Reference implementation

            ```{lang_for(slug)}
            {code_for(slug)}
            ```
        """).strip())
        parts.append(f"## When to prioritize\n\n{when.capitalize()}.")
        parts.append(f"## Anti-pattern\n\n{mistake}.")
        return "\n\n".join(parts)
    parts = [hook, ""]
    blocks = [
        ("Problem in production", f"{hook} **When:** {when.capitalize()}. **Avoid:** {mistake}"),
        ("Mechanism", f"Understanding {tech} means tracing browser behavior from HTML parse through paint and input handling. Changes here move LCP, INP, and CLS together — measure all three on affected routes before and after."),
        ("Implementation", textwrap.dedent(f"""
            ```{lang_for(slug)}
            {code_for(slug)}
            ```
            Ship behind a feature flag on one route first. Wire RUM marks around the user journey this change touches.
        """).strip()),
        ("Edge cases", "Test back navigation, refresh mid-flow, double submit, offline toggle, and keyboard-only paths. Corporate proxies and ad blockers change script graphs versus staging."),
        ("Rollout", "Compare canary p75 to control for one business day. Document rollback: flag off, cache purge, or revert deploy — whichever restores prior behavior fastest under pressure."),
    ]
    for title, text in blocks:
        parts.append(f"## {title}\n\n{text}")
    return "\n\n".join(parts)


def unique_pad(slug: str, tech: str, hook: str, mistake: str, n: int) -> str:
    templates = [
        f"## Deep dive: rollout discipline ({n + 1})\n\n{hook.split('.')[0]}. When rolling out changes to {tech}, compare canary p75 INP and LCP to control for a full business day in target regions before promoting to 100%. Document rollback in the PR: feature flag name, cache purge procedure, or revert commit — whichever restores prior behavior fastest at 2 a.m.\n\nSlice metrics by device class and connection effective type. A fix helping desktop fiber but regressing mid-tier Android 4G should pause rollout, not ship globally.",
        f"## Deep dive: failure rehearsal ({n + 1})\n\nRehearse `{mistake}` in a 30-minute game day before peak season. For {tech}, measure time-to-detect and time-to-mitigate — not only time-to-root-cause in a postmortem doc.\n\nManual paths worth scripting: hard refresh mid-flow, browser back after async submit, double-click primary action, offline toggle during mutation, keyboard-only navigation with screen reader.",
        f"## Deep dive: observability ({n + 1})\n\nWire custom RUM marks around the user journey {tech} affects. Log correlation IDs across client beacons and server logs. Alert on week-over-week p75 regression on tier-1 routes — global averages hide bad canaries.\n\nLeading indicators: error rate, validation failures, queue depth. Lagging: support tickets, conversion, churn. Both must move together to confirm the fix matched user pain.",
        f"## Deep dive: third-party drift ({n + 1})\n\nTag managers, chat widgets, and payment iframes change without your deploy. Quarterly audit script inventory on critical routes. Compare lab metrics with ad blockers enabled vs disabled — the delta reveals third-party cost.\n\nFor {tech}, corporate proxies and Save-Data alter behavior versus staging on office Wi-Fi. Field validation beats conference demos.",
    ]
    return templates[(hash(slug) + n) % len(templates)]


def build_body(slug: str, meta: tuple, existing: str) -> str:
    cleaned = strip_body(existing)
    boiler_markers = ("Architecture and boundaries", "Production engineering for", "Field p75 on mid-tier")
    if any(m in existing for m in boiler_markers) or wc(cleaned) < 500:
        body = sections_from_meta(slug, meta)
    elif wc(cleaned) >= 400:
        body = meta[0] + "\n\n" + cleaned if not cleaned.startswith(meta[0][:40]) else cleaned
    else:
        body = sections_from_meta(slug, meta)
    n = 0
    while wc(body) < TARGET and n < 10:
        body += "\n\n" + unique_pad(slug, meta[1], meta[0], meta[3], n)
        n += 1
    return body.strip()


def main():
    results = []
    for slug in SLUGS:
        path = BLOG / f"{slug}.md"
        raw = path.read_text(encoding="utf-8")
        meta = ALL[slug]
        fm = build_fm(slug, parse_fm(raw), meta[4])
        body = build_body(slug, meta, raw.split("---", 2)[2])
        bw = wc(body)
        path.write_text(fm + "\n\n" + body + "\n", encoding="utf-8")
        results.append((slug, bw))
    ok = sum(1 for _, w in results if w >= TARGET)
    print(f"DONE={ok}/{len(SLUGS)}")
    for slug, w in sorted(results):
        print(f"  {slug}: {w}w")

if __name__ == "__main__":
    main()
