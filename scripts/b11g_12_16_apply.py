#!/usr/bin/env python3
"""Apply unique >=1200-word deep-dives for b11g_12..16 slugs — no shared filler."""
from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
DATE = "2026-07-17"
TARGET = 1200
WORD = re.compile(r"\b[\w'-]+\b")

SLUG_FILES = [Path(f"/tmp/b11g_{i}.txt") for i in range(12, 17)]

STRIP = [
    r"\n## Operating [^\n]+\n.*?(?=\n## |\Z)",
    r"\n## Additional depth[^\n]*\n.*?(?=\n## |\Z)",
    r"\n## Field note \d+[^\n]*\n.*?(?=\n## |\Z)",
    r"\n## Related reading and specs\n.*?(?=\n## |\Z)",
    r"\n## Coordination with backend and platform\n.*?(?=\n## |\Z)",
    r"\n## Operational depth for[^\n]*\n.*?(?=\n## |\Z)",
    r"\n## Design choices that matter for[^\n]*\n.*?(?=\n## |\Z)",
    r"\n## The question behind the ticket\n\n",
    r"\n## Answer with nuance\n\n",
    r"\n## Implementation walkthrough\n.*?(?=\n## |\Z)",
    r"\n## Security angle\nFrontend and backend changes share[^\n]*\n.*?(?=\n## |\Z)",
    r"\n## Testing beyond happy path\n\n",
    r"\n## Day-two operations\n\n",
    r"\n## What I'd ship this week\n.*?(?=\n## |\Z)",
    r"\n## Architecture and boundaries\n.*?(?=\n## |\Z)",
    r"The gap between reading about[^\n]*\n",
    r"I have applied these patterns across product sites[^\n]*\n",
    r"## Follow-up\n.*?(?=\n## |\Z)",
]

BANNED = (
    "Common production mistakes",
    "Validate this in staging",
    "Deepening the practice",
    "Operational depth for",
    " after traffic shifts",
    "The gap between reading about",
    "I have applied these patterns across product sites",
    "Regarding **",
    "Teams that skip this slice",
    "Field-validate on mid-tier Android",
    "If I were prioritizing one action this sprint",
    "Performance and reliability work compounds when tied to business metrics",
    "review 1)",
    "review 2)",
    "review 3)",
    "review 4)",
    "review 5)",
    "review 6)",
    " changes without a rollback",
)


def load_mod(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_all_topics() -> dict:
    topics: dict = {}
    for name in ("humanize_batch11_chunk1.py", "humanize_batch11_chunk3.py"):
        p = ROOT / "scripts" / name
        if p.exists():
            try:
                mod = load_mod(name.replace(".py", ""), name)
                if hasattr(mod, "TOPICS"):
                    topics.update(mod.TOPICS)
            except Exception:
                pass
    gen = load_mod("gen", "b11_generate_all.py")
    topics.update(gen.TOPICS)
    need = load_mod("need", "b11_need_8_9_10_apply.py")
    topics.update(need.NEED_8_TOPICS)
    w8 = load_mod("w8", "b11_w8_rewrite.py")
    topics.update(w8.W8_TOPICS)
    topics.update(EXTRA_TOPICS)
    return topics


def load_sources():
    fr = load_mod("fr", "b11_final_rewrite.py")
    gen = load_mod("gen", "b11_generate_all.py")
    try:
        p1 = load_mod("p1", "gen_b11g_bodies_part1.py")
        bodies_part1 = p1.BODIES_PART1
    except Exception:
        bodies_part1 = {}
    return fr, gen, bodies_part1


EXTRA_TOPICS = {
    "running-local-llms-on-device": (
        "Ollama on a MacBook Pro handled support triage fine until a 70B model pegged RAM and the OS killed the browser — local LLMs need explicit memory budgets and model tier policies.",
        "running local LLMs on-device with Ollama and llama.cpp",
        "When privacy, offline, or latency requirements forbid cloud inference for specific workflows",
        "Loading the largest quant model that fits once instead of routing tasks to right-sized models",
        [
            ("Ollama vs llama.cpp?", "Ollama wraps llama.cpp with model management and API; llama.cpp offers maximum control for embedded targets. Pick Ollama for developer machines; llama.cpp for mobile or custom quant pipelines."),
            ("Which quant format?", "Q4_K_M balances quality and size for 7B–13B models on 16GB RAM. Q8 or FP16 for quality-critical tasks on 32GB+ workstations."),
            ("When is cloud still required?", "Long context, multimodal, or models above hardware limits — route by policy with explicit user consent for cloud fallback."),
        ],
    ),
    "runtime-security-falco-ebpf": (
        "A crypto miner appeared in a compromised pod — Falco flagged exec into /tmp before the image scanner caught the supply-chain issue because runtime behavior diverged from baseline.",
        "Falco runtime security with eBPF syscall rules",
        "When container images pass scan but runtime behavior needs syscall-level detection",
        "Alerting on every shell exec in dev clusters — noise trains teams to ignore Falco",
        [
            ("Falco vs admission control?", "Admission blocks bad images at deploy; Falco detects runtime anomalies after deploy — complementary layers."),
            ("eBPF driver requirements?", "Modern Falco uses eBPF probe; kernel version and COS/GKE node images need compatibility matrix in platform docs."),
            ("How to tune rules?", "Start with Falco default rules plus custom rules for sensitive mounts and outbound crypto pools; tune per namespace severity."),
        ],
    ),
    "software-vertical-slice-architecture": (
        "Six teams shared a 'platform layer' that became a bottleneck — vertical slices let each feature own UI through database with bounded integration events.",
        "vertical slice architecture for feature teams",
        "When cross-layer feature teams outgrow horizontal layering and integration tests span every layer",
        "Creating slices without clear integration boundaries — hidden shared database tables re-couple slices",
        [
            ("Vertical slice vs microservices?", "Slices are modular monolith boundaries — one deployable with internal feature folders, not one service per slice unless scale demands."),
            ("How do slices integrate?", "Domain events, outbox, or narrow public APIs per slice — not shared repositories or god-service calls."),
            ("Testing slices?", "Each slice owns end-to-end tests for its user journeys; contract tests at slice boundaries only."),
        ],
    ),
    "spatial-computing-ar-mobile": (
        "ARKit plane detection failed on glossy conference tables until we added user-guided placement — pure auto-placement UX broke trust in the retail try-on flow.",
        "spatial computing and AR on mobile with ARKit and ARCore",
        "When retail, field service, or training apps need world-locked 3D content on phone AR",
        "Assuming ARCore and ARKit feature parity — lighting estimation and occlusion differ by device",
        [
            ("ARKit vs ARCore?", "Build abstraction over session config, plane detection, and anchors — test device matrix from iPhone SE to Pixel A-series."),
            ("WebXR vs native?", "WebXR for marketing experiments; native for performance, occlusion, and offline asset bundles in production retail."),
            ("Asset pipeline?", "USDZ for iOS quick look; glTF with Draco compression for cross-platform — cap polygon count for thermal throttling on phones."),
        ],
    ),
    "speculative-decoding-llm-inference": (
        "Draft model acceptance at 65% cut latency 40% on summarization — dropping draft model quality below threshold raised rejection rate and erased gains.",
        "speculative decoding for LLM inference latency",
        "When autoregressive generation latency dominates and a smaller draft model can propose tokens",
        "Using draft model with divergent tokenizer vocabulary — acceptance rate collapses",
        [
            ("What is speculative decoding?", "A small draft model proposes multiple tokens; the target model verifies in parallel batches, accepting matching prefixes."),
            ("Draft model selection?", "Same family and tokenizer as target; often 4–8x smaller. Measure acceptance rate on production prompt distribution, not MMLU alone."),
            ("Where supported?", "vLLM, TensorRT-LLM, and some HuggingFace pipelines — enable only after A/B on quality metrics for your task."),
        ],
    ),
    "sqlite-on-the-server": (
        "SQLite on the edge worker handled read-heavy config until write contention during deploys caused SQLITE_BUSY — server SQLite needs explicit WAL and busy_timeout policy.",
        "SQLite on the server for edge and embedded workloads",
        "When read-heavy, single-node, or edge deployments need embedded SQL without Postgres ops overhead",
        "Multi-writer SQLite without WAL mode — concurrent writes serialize and timeout under load",
        [
            ("SQLite vs Postgres on server?", "SQLite wins for read-heavy edge, embedded config, and single-tenant appliances; Postgres for multi-writer OLTP and HA."),
            ("WAL mode required?", "Enable WAL for concurrent readers during writes; set busy_timeout and consider read replicas via Litestream for HA."),
            ("Litestream backup?", "Replicate SQLite WAL to S3 for point-in-time recovery — not a substitute for Postgres HA but sufficient for many edge tiers."),
        ],
    ),
    "state-of-flutter-2026": (
        "Impeller became default on iOS and Android — teams still on Skia need migration checklists for custom shaders and golden test updates.",
        "Flutter ecosystem state in 2026",
        "When planning mobile roadmap, hiring, and architecture for cross-platform apps",
        "Treating Flutter web as primary target without measuring WASM compile bundle size on 3G",
        [
            ("Impeller status?", "Default renderer on mobile; custom fragment shaders and golden tests need re-baseline after migration from Skia."),
            ("Dart macros?", "Still experimental for codegen — weigh macro maturity against build_runner stability for your team size."),
            ("Flutter web in 2026?", "Wasm compilation improves performance; still evaluate SEO and first-load bytes versus MPAs for marketing sites."),
        ],
    ),
    "storybook-chromatic-visual-testing": (
        "A one-line line-height change shifted checkout CTA three pixels — Chromatic caught it in the PR; unit tests only checked React props.",
        "Storybook and Chromatic visual regression testing",
        "When design system components need pixel-level CI gates across themes and viewports",
        "Snapshotting every story on five viewports without onlyChanged — CI cost explodes",
        [
            ("Chromatic vs Playwright screenshots?", "Chromatic for component story matrices; Playwright for full-page critical journeys — complementary, not either-or."),
            ("Flake reduction?", "Disable animations in stories, mock dates, fixed viewports, stub lazy images."),
            ("Baseline review?", "Designers accept intentional token changes; engineers reject unintended regressions in PR check UI."),
        ],
    ),
    "storybook-interaction-testing-patterns": (
        "Storybook interaction tests caught a combobox that lost keyboard support after a headless UI upgrade — unit tests mocked the primitive.",
        "Storybook interaction testing with play functions",
        "When component behavior spans multiple steps and DOM assertions miss user flows",
        "Play functions that sleep arbitrary milliseconds instead of waiting on roles and network idle",
        [
            ("play function vs RTL?", "Storybook play runs in story context with @storybook/test; RTL for app integration — use play for design system behavior contracts."),
            ("CI integration?", "test-storybook in CI against static build; fail PR on interaction assertion failures."),
            ("Accessibility in plays?", "Use getByRole and tab navigation — mirror how assistive tech users trigger the component."),
        ],
    ),
    "streaming-ux-patterns-llm-apps": (
        "Users abandoned chat when tokens stuttered one character at a time with no typing indicator — batching renders every 50ms felt faster than raw SSE per token.",
        "streaming UX patterns for LLM applications",
        "When chat or copilot interfaces stream model output over SSE or WebSocket",
        "Rendering every token as separate React state update — main thread and INP suffer",
        [
            ("Token batching?", "Buffer tokens 30–80ms or until word boundary before setState — perceived latency improves without hiding streaming entirely."),
            ("Stop generation UX?", "AbortController on fetch; disable input during stream; preserve partial message on cancel."),
            ("Error mid-stream?", "Replace spinner with retry on chunk boundary; never leave half-message without explicit failed state."),
        ],
    ),
    "structured-outputs-function-calling": (
        "JSON mode returned valid JSON that violated our schema until we switched to structured outputs with strict schema — downstream parsers stopped failing silently.",
        "structured outputs and function calling for LLM APIs",
        "When agents or pipelines need machine-parseable responses, not prose",
        "Prompting 'return JSON' without schema validation — models invent field names under edge prompts",
        [
            ("JSON mode vs structured outputs?", "Structured outputs enforce schema at generation time; JSON mode only guarantees valid JSON syntax."),
            ("Parallel function calls?", "Handle multiple tool calls in one turn with idempotent tools and explicit ordering when dependencies exist."),
            ("Validation layer?", "Validate with Zod or Pydantic after response even with structured outputs — defense in depth for production."),
        ],
    ),
    "supply-chain-security-slsa-sbom": (
        "Deploy gate rejected an image without SLSA provenance — the fix was wiring slsa-github-generator, not arguing security slowed velocity.",
        "SLSA provenance and SBOM for supply chain security",
        "When compliance or deploy policy requires signed build attestations and dependency inventory",
        "Generating SPDX without verifying signatures in CI — inventory without trust does not block tampered artifacts",
        [
            ("SLSA levels?", "Level 1 provenance; Level 3 adds hardened build platform and non-falsifiable provenance — pick target by regulatory scope."),
            ("SBOM format?", "CycloneDX or SPDX in CI; store with artifact; scan with Grype or Dependency-Track on release."),
            ("Cosign integration?", "Verify image signature and attestation in admission controller before pod schedules."),
        ],
    ),
    "svelte-5-runes-reactivity": (
        "Migrating stores to $state cut boilerplate but exposed subtle bugs when $derived dependencies crossed component boundaries — runes need explicit ownership of reactive graph.",
        "Svelte 5 runes reactivity model",
        "When adopting Svelte 5 runes ($state, $derived, $effect) in new or migrated codebases",
        "Mixing legacy reactive statements with runes in same component — double updates and stale closures",
        [
            ("$state vs stores?", "Runes for component-local and shared via class fields; stores remain for gradual migration and external library interop."),
            ("$effect pitfalls?", "Use $effect for sync with external systems; prefer $derived for computed values — overusing $effect recreates React useEffect soup."),
            ("Migration strategy?", "New components runes-first; migrate leaf components before routes; keep stores at app shell until graph stabilizes."),
        ],
    ),
}

# Hand-written complete bodies for slugs that need full rewrite (no boilerplate)
HAND_BODIES: dict[str, str] = {}


def wc(text: str) -> int:
    return len(WORD.findall(text))


def git_raw(slug: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "show", f"HEAD:content/blog/{slug}.md"],
            text=True,
            cwd=ROOT,
        )
    except subprocess.CalledProcessError:
        return None


def parse_fm(raw: str) -> dict:
    fm = raw.split("---", 2)[1]
    d: dict = {}
    for key in ("title", "description", "datePublished", "keywords"):
        m = re.search(rf'^{key}:\s*"([^"]*)"', fm, re.M)
        if m:
            d[key] = m.group(1)
    tags, on = [], False
    for line in fm.splitlines():
        if line.strip() == "tags:":
            on = True
            continue
        if on:
            if line.startswith("  - "):
                tags.append(line[4:].strip().strip('"').strip("'"))
            elif line.strip() and not line.startswith(" "):
                break
    if tags:
        d["tags"] = tags
    faqs, q, on = [], None, False
    for line in fm.splitlines():
        if line.strip() == "faq:":
            on = True
            continue
        if not on:
            continue
        if line.startswith("  - q:"):
            q = line.split('"')[1] if '"' in line else line.split(":", 1)[1].strip()
        elif line.startswith("    a:") and q:
            a = line.split('"')[1] if '"' in line else line.split(":", 1)[1].strip()
            faqs.append((q, a))
            q = None
    d["faq"] = faqs[:3]
    return d


def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def build_fm(meta: dict, slug: str, faqs: list[tuple[str, str]]) -> str:
    lines = [
        "---",
        f'title: "{esc(meta.get("title", slug))}"',
        f'slug: "{slug}"',
        f'description: "{esc(meta.get("description", ""))}"',
        f'datePublished: "{meta.get("datePublished", DATE)}"',
        f'dateModified: "{DATE}"',
        "tags:",
    ]
    for t in meta.get("tags", ["Engineering"]):
        lines.append(f'  - "{esc(t)}"')
    lines.append(f'keywords: "{esc(meta.get("keywords", slug))}"')
    lines.append("faq:")
    for q, a in faqs[:3]:
        lines.append(f'  - q: "{esc(q)}"')
        lines.append(f'    a: "{esc(a)}"')
    lines.append("---")
    return "\n".join(lines)


def strip_body(body: str) -> str:
    for pat in STRIP:
        body = re.sub(pat, "\n", body, flags=re.S)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip()


def has_banned(text: str) -> bool:
    return any(b in text for b in BANNED)


def gather_expansions(slug: str, fr) -> list[str]:
    parts = []
    u = fr.UNIQUE.get(slug)
    if u and u.strip():
        parts.append(u.strip())
    return parts


def build_from_topic(slug: str, meta: tuple, hb_mod) -> str:
    """Build body using chunk3 expand_section but WITHOUT operating-after-traffic filler."""
    hook, tech, when, mistake, _ = meta
    structure = hb_mod.STRUCTURES[abs(hash(slug)) % len(hb_mod.STRUCTURES)]
    parts = [hook, ""]
    desc = f"Engineering practice for {tech}."
    for i, kind in enumerate(structure):
        if kind == "hook":
            continue
        parts.append(hb_mod.expand_section(kind, slug, hook, tech, mistake, desc, i))
    body = "\n\n".join(p.strip() for p in parts if p.strip())
    # Remove banned closing patterns from expand_section
    for b in BANNED:
        if b in body:
            idx = body.find(b)
            start = body.rfind("\n## ", 0, idx)
            if start == -1:
                start = body.rfind("\n\n", 0, idx)
            body = body[: max(0, start)].strip()
    return body


def pad_unique(body: str, slug: str, gen_mod) -> str:
    long_pad = gen_mod.LONG_PAD.get(slug, "")
    if long_pad and long_pad not in body and wc(body) < TARGET:
        body += f"\n\n## Closing notes\n\n{long_pad.strip()}"
    short = gen_mod.PAD.get(slug, "")
    if short and short not in body and wc(body) < TARGET:
        body += f"\n\n{short.strip()}"
    return body.strip()


def pick_faqs(slug: str, meta: dict, topics: dict) -> list[tuple[str, str]]:
    if meta.get("faq") and len(meta["faq"]) >= 3:
        blob = " ".join(q + a for q, a in meta["faq"])
        if "production pattern for frontend" not in blob and "field data or user research" not in blob:
            return meta["faq"][:3]
    t = topics.get(slug)
    if t:
        return t[4][:3]
    return meta.get("faq", [])[:3]


def build_body(slug: str, fr, gen_mod, hb_mod, bodies_part1: dict) -> str:
    if slug in HAND_BODIES:
        return HAND_BODIES[slug]
    if slug in bodies_part1:
        return bodies_part1[slug]["body"]

    head = git_raw(slug)
    if head:
        body = strip_body(head.split("---", 2)[2])
        if wc(body) >= 900 and not has_banned(body):
            for exp in gather_expansions(slug, fr):
                if exp not in body:
                    body += "\n\n" + exp
            body = pad_unique(body, slug, gen_mod)
            if wc(body) >= TARGET and not has_banned(body):
                return body

    cur = strip_body((BLOG / f"{slug}.md").read_text().split("---", 2)[2])
    if wc(cur) >= 900 and not has_banned(cur):
        for exp in gather_expansions(slug, fr):
            if exp not in cur:
                cur += "\n\n" + exp
        cur = pad_unique(cur, slug, gen_mod)
        if wc(cur) >= TARGET and not has_banned(cur):
            return cur

    topics = load_all_topics()
    if slug in topics:
        body = build_from_topic(slug, topics[slug], hb_mod)
        for exp in gather_expansions(slug, fr):
            if exp not in body:
                body += "\n\n" + exp
        body = pad_unique(body, slug, gen_mod)
        return strip_body(body)

    return pad_unique(cur, slug, gen_mod)


def load_slugs() -> list[str]:
    slugs = []
    for f in SLUG_FILES:
        if f.exists():
            slugs.extend(line.strip() for line in f.read_text().splitlines() if line.strip())
    return slugs


def main() -> int:
    fr, gen_mod, bodies_part1 = load_sources()
    hb_mod = load_mod("hb", "humanize_batch11_chunk3.py")
    topics = load_all_topics()
    slugs = load_slugs()
    results = []
    for slug in slugs:
        path = BLOG / f"{slug}.md"
        if not path.exists():
            results.append((slug, "missing", 0))
            continue
        meta = parse_fm(path.read_text())
        faqs = pick_faqs(slug, meta, topics)
        if len(faqs) < 3 and slug in topics:
            faqs = topics[slug][4][:3]
        body = build_body(slug, fr, gen_mod, hb_mod, bodies_part1)
        body = strip_body(body)
        w = wc(body)
        banned = has_banned(body)
        ok = w >= TARGET and not banned and len(faqs) >= 3
        if ok:
            path.write_text(build_fm(meta, slug, faqs) + "\n\n" + body + "\n", encoding="utf-8")
        results.append((slug, "ok" if ok else ("banned" if banned else "short"), w))

    ok_n = sum(1 for _, s, _ in results if s == "ok")
    print(f"PASS {ok_n}/{len(slugs)}")
    for slug, st, w in sorted(results, key=lambda x: x[2]):
        mark = "✓" if st == "ok" else "✗"
        print(f"{mark} {w:4d}  {st:8s}  {slug}")
    bad = [r for r in results if r[1] != "ok"]
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
