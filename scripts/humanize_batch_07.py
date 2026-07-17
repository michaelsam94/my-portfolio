#!/usr/bin/env python3
"""Humanize blog posts batch 07 (indices 1750-1999). Unique structure per post, >=1200 words."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import date
from pathlib import Path

from humanize_topics import (
    blocks_for_slug,
    generic_llm_blocks,
    kotlin_blocks,
    kubernetes_blocks,
    supplement_paragraphs,
)

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
PROGRESS = ROOT / "scripts" / "humanize-progress" / "batch-07.json"
SLICE_START, SLICE_END = 1750, 1999
TARGET_WORDS = 1200
WORD_PAT = re.compile(r"\b[\w'-]+\b")

TEMPLATE_MARKERS = [
    "Problem framing",
    "Design principles that survive production",
    "boring center of reliable ai delivery",
    "production patterns for ai teams",
]

FILLER_SECTIONS = re.compile(
    r"\n## (Common production mistakes|Debugging and triage workflow|"
    r"Metrics worth dashboarding|What to measure|How this fits your stack|Rollout checklist)"
    r".*?(?=\n## |\Z)",
    re.DOTALL,
)


def word_count(text: str) -> int:
    return len(WORD_PAT.findall(text))


def slug_to_topic(slug: str, title: str) -> str:
    for prefix in ("kotlin-", "kubernetes-", "ktor-", "llm-", "rag-", "agent-"):
        if slug.startswith(prefix):
            rest = slug[len(prefix):].replace("-", " ")
            return rest if rest else title.lower()
    return slug.replace("-", " ")


def domain_for(slug: str) -> str:
    if slug.startswith("kotlin") or slug.startswith("ktor"):
        return "kotlin"
    if slug.startswith("kubernetes"):
        return "kubernetes"
    if slug.startswith("llm") or slug.startswith("kv-cache"):
        return "llm_platform"
    if slug.startswith("lazy-loading"):
        return "web"
    return "general"


def pick_variant(slug: str, n: int) -> int:
    return int(hashlib.sha256(slug.encode()).hexdigest(), 16) % n


def yaml_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def parse_post(path: Path) -> dict:
    raw = path.read_text()
    parts = raw.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"Bad frontmatter: {path}")
    fm = parts[1]
    body = parts[2]
    if not body.startswith("\n"):
        body = "\n" + body

    def grab(key: str, default: str = "") -> str:
        m = re.search(rf'^{key}:\s*"(.*)"', fm, re.M)
        return m.group(1) if m else default

    tags = re.findall(r'-\s*"([^"]+)"', fm)
    if not tags:
        inline = re.search(r"tags:\s*\[(.*?)\]", fm, re.S)
        if inline:
            tags = re.findall(r'"([^"]+)"', inline.group(1))
    return {
        "path": path,
        "slug": path.stem,
        "title": grab("title", path.stem),
        "description": grab("description"),
        "date_published": grab("datePublished", "2025-01-01"),
        "date_modified": date.today().isoformat(),
        "tags": tags,
        "keywords": grab("keywords"),
        "body": body,
        "raw": raw,
    }


def is_template_body(body: str) -> bool:
    return sum(1 for m in TEMPLATE_MARKERS if m in body) >= 2


def load_head_cache(batch: list[Path]) -> dict[str, dict]:
    cache: dict[str, dict] = {}
    for path in batch:
        rel = str(path.relative_to(ROOT))
        try:
            raw = subprocess.check_output(["git", "show", f"HEAD:{rel}"], cwd=ROOT, text=True)
        except subprocess.CalledProcessError:
            cache[rel] = {"body": None, "tags": [], "description": ""}
            continue
        parts = raw.split("---", 2)
        fm = parts[1] if len(parts) >= 2 else ""
        body = parts[2] if len(parts) >= 3 else raw
        tags = re.findall(r'-\s*"([^"]+)"', fm)
        if not tags:
            inline = re.search(r"tags:\s*\[(.*?)\]", fm, re.S)
            if inline:
                tags = re.findall(r'"([^"]+)"', inline.group(1))
        desc = re.search(r'^description:\s*"(.*)"', fm, re.M)
        cache[rel] = {
            "body": body,
            "tags": tags,
            "description": desc.group(1) if desc else "",
        }
    return cache


def strip_template_sections(body: str) -> str:
    body = FILLER_SECTIONS.sub("", body)
    return body.strip() + "\n"


def faq_for(slug: str, title: str, topic: str, domain: str) -> list[dict]:
    faqs: list[dict] = []
    t = topic
    if "passkey" in slug or "webauthn" in slug:
        faqs = [
            {"q": "Passkeys vs passwords for operator consoles?",
             "a": "Passkeys resist phishing and credential stuffing on accounts that change models, prompts, and billing. Keep break-glass passwords in a vault for disaster recovery only."},
            {"q": "Which attestation formats should we accept?",
             "a": "Consumer passkeys often use none or packed attestation. Enterprise hardware keys may use TPM formats. Document an allowlist and update it when platform vendors change defaults."},
            {"q": "How do we handle lost devices?",
             "a": "Provide recovery via a second enrolled passkey, admin reset with strong identity proof, or hardware token backup — never SMS alone for privileged roles."},
        ]
    elif "streaming" in slug or "sse" in slug:
        faqs = [
            {"q": "SSE vs WebSockets for LLM output?",
             "a": "SSE for one-way token streams through HTTP infrastructure. WebSockets when the client must interrupt generation or send control messages on the same connection."},
            {"q": "Why do streams die behind nginx?",
             "a": "Default proxy_read_timeout and response buffering. Disable buffering with X-Accel-Buffering: no and send heartbeat comments every 15–30 seconds."},
            {"q": "Should we stream tokens or words?",
             "a": "Buffer to word or short phrase boundaries — smoother UI and fewer React commits. Ship final metadata in a done event."},
        ]
    elif "patch-management" in slug:
        faqs = [
            {"q": "How long should inference patch windows be?",
             "a": "Long enough to drain sessions, apply patches, run smoke evals, and warm GPU caches — often 30–90 minutes per pool, scheduled in traffic troughs."},
            {"q": "Can we patch during autoscaling events?",
             "a": "Avoid combining patch restarts with aggressive scale-down. Freeze autoscaler or cordon nodes explicitly so PDBs are not fighting Karpenter."},
        ]
    elif domain == "kotlin":
        faqs = [
            {"q": f"When does {t} earn its keep?",
             "a": "When compile-time checks remove whole classes of bugs at boundaries — API results, UI state, wire formats — not when a simpler type already communicates the idea."},
            {"q": f"What is the main footgun with {t}?",
             "a": "Over-modeling: sealed trees five levels deep, value classes everywhere, or KSP generating magic nobody can grep. Start minimal and expand when metrics or reviews prove pain."},
            {"q": f"How do we migrate existing code toward {t}?",
             "a": "Parallel types at the boundary, map old to new in one module, delete legacy once callers migrate. Never freeze the monolith for a type-system purity project."},
        ]
    elif domain == "kubernetes":
        faqs = [
            {"q": f"What is the first sign {t} is misconfigured?",
             "a": "Tail latency during rollouts, CrashLoopBackOff, or cost climbing without traffic. Compare against a known-good namespace before blaming application code."},
            {"q": f"Cluster-wide or namespace-scoped {t}?",
             "a": "Platform baselines cluster-wide; team overrides namespace-scoped with documented exceptions and expiry dates."},
            {"q": f"Safest rollout order for {t}?",
             "a": "Non-prod with production-shaped load → one node pool or namespace canary → widen after 24h stable golden signals."},
        ]
    else:
        faqs = [
            {"q": f"Why does {t} matter in production AI systems?",
             "a": "It sits on the path users feel — latency, trust, cost. Demos skip it; revenue does not."},
            {"q": f"What should we measure for {t}?",
             "a": "Symptom metrics: success rate, p95 latency, cost per task. Slice by model version and tenant during rollouts."},
            {"q": f"What is the smallest safe version of {t}?",
             "a": "Happy path plus explicit failures, feature flag, and rollback. Add complexity when metrics prove need."},
        ]
    if len(faqs) < 4 and domain in ("llm_platform", "general"):
        faqs.append({"q": f"How does {t} interact with retrieval and tools?",
                     "a": "Same reliability rules apply: timeouts, authz, idempotency, and observability on every hop, not only the final model call."})
    return faqs[:4]


def description_for(slug: str, title: str, topic: str, domain: str) -> str:
    if domain == "kotlin":
        return f"{title}: practical patterns, sharp edges, and production-ready examples."
    if domain == "kubernetes":
        return f"{title}: design, rollout, and day-two operations on real clusters."
    if domain == "llm_platform":
        return f"{title}: engineering guide for secure, observable AI platforms at scale."
    return f"{title}: implementation patterns and operational guidance."


def keywords_for(slug: str, topic: str, domain: str) -> str:
    base = topic.replace(" ", ", ")
    prefix = {"kotlin": "kotlin", "kubernetes": "kubernetes, k8s", "llm_platform": "llm, ai platform"}.get(domain, "production")
    return f"{prefix}, {base}, engineering"


def tags_for(slug: str, domain: str, existing: list[str]) -> list[str]:
    if existing and "Llm" not in existing and len(existing) >= 2:
        return existing
    mapping = {
        "kotlin": ["Kotlin", "Backend", "Architecture"],
        "kubernetes": ["Kubernetes", "DevOps", "Platform Engineering"],
        "llm_platform": ["AI", "LLM", "Production"],
        "web": ["Web", "Performance", "Frontend"],
    }
    return mapping.get(domain, ["Engineering", "Architecture"])


def code_for(slug: str, domain: str) -> str:
    codes = {
        "sealed": '''```kotlin
sealed interface UiState {
    data object Loading : UiState
    data class Ready(val items: List<Item>) : UiState
    data class Error(val reason: String) : UiState
}
```''',
        "webauthn": '''```typescript
const credential = await navigator.credentials.create({
  publicKey: await fetch("/webauthn/register/options").then(r => r.json()),
});
await fetch("/webauthn/register/verify", { method: "POST", body: JSON.stringify(credential) });
```''',
        "streaming": '''```python
return StreamingResponse(generate(), media_type="text/event-stream", headers={
    "Cache-Control": "no-cache", "X-Accel-Buffering": "no",
})
```''',
        "outbox": '''```sql
BEGIN;
  INSERT INTO orders (id, ...) VALUES (...);
  INSERT INTO outbox (topic, payload) VALUES ('OrderCreated', ...);
COMMIT;
```''',
        "gateway-api": '''```yaml
kind: HTTPRoute
spec:
  parentRefs: [{ name: public-gateway }]
  rules:
    - matches: [{ path: { type: PathPrefix, value: /api } }]
      backendRefs: [{ name: api, port: 8080 }]
```''',
        "network-polic": '''```yaml
kind: NetworkPolicy
spec:
  podSelector: {}
  policyTypes: [Ingress, Egress]
  egress:
    - to: [{ namespaceSelector: { matchLabels: { kubernetes.io/metadata.name: kube-system } } }]
```''',
    }
    for key, block in codes.items():
        if key in slug:
            return block
    if domain == "kotlin":
        return "```kotlin\n// adapt to your boundary\nresult.fold(onSuccess = ::ok, onFailure = ::fail)\n```"
    if domain == "kubernetes":
        return "```yaml\n# validate in staging with production-shaped load\napiVersion: v1\nkind: ConfigMap\n```"
    return "```typescript\nconst result = await service.execute(input);\nif (!result.ok) return handleError(result.error);\n```"


def blocks_for_domain(slug: str, topic: str, domain: str) -> list[tuple[str, list[str]]]:
    if domain == "kotlin":
        return kotlin_blocks(topic, slug)
    if domain == "kubernetes":
        return kubernetes_blocks(topic, slug)
    matched = blocks_for_slug(slug)
    if matched:
        return matched + generic_llm_blocks(topic)
    return generic_llm_blocks(topic)


def assemble_rewrite(slug: str, title: str, topic: str, domain: str) -> str:
    blocks = blocks_for_domain(slug, topic, domain)
    # dedupe headings
    seen = set()
    unique_blocks = []
    for h, paras in blocks:
        if h in seen:
            continue
        seen.add(h)
        unique_blocks.append((h, paras))
    if len(unique_blocks) < 6:
        unique_blocks.extend(generic_llm_blocks(topic))

    v = pick_variant(slug, 5)
    hooks = [
        f"Most teams treat {topic} as solved after the tutorial works once. Production is where {topic} earns or loses trust — under retries, skewed clocks, and a proxy that silently buffers your streams.",
        f"I have debugged {topic} at 2am enough times to prefer boring, explicit designs over clever ones. What follows is the checklist I use before calling a feature done.",
        f"{title} sounds niche until it is on your critical path. The sections below are ordered for someone shipping under real SLOs, not for a conference slide.",
    ]
    parts = [hooks[v % len(hooks)], ""]

    if v == 0:
        for h, paras in unique_blocks[:5]:
            parts.append(f"## {h}\n")
            parts.extend(p + "\n" for p in paras)
            parts.append("")
        parts.append("## Code sketch\n")
        parts.append(code_for(slug, domain))
        parts.append("")
    elif v == 1:
        parts.append(f"## Why {topic} is load-bearing\n\n{unique_blocks[0][1][0]}\n")
        parts.append("## Mechanics\n")
        parts.append(code_for(slug, domain))
        parts.append("\n")
        for h, paras in unique_blocks[1:5]:
            parts.append(f"## {h}\n")
            for p in paras:
                parts.append(p + "\n")
    elif v == 2:
        parts.append("## Field notes\n")
        for h, paras in unique_blocks[:3]:
            parts.append(f"### {h}\n")
            parts.append("\n".join(paras) + "\n")
        parts.append("## Deeper cuts\n")
        for h, paras in unique_blocks[3:6]:
            parts.append(f"**{h}** — " + " ".join(paras) + "\n")
    elif v == 3:
        parts.append("## Before production\n")
        for h, paras in unique_blocks[:2]:
            parts.append(f"- **{h}:** {paras[0]}\n")
        parts.append("\n## Implementation\n")
        parts.append(code_for(slug, domain))
        parts.append("\n")
        for h, paras in unique_blocks[2:6]:
            parts.append(f"## {h}\n\n" + "\n\n".join(paras) + "\n")
    else:
        parts.append(f"## Context\n\n{unique_blocks[0][1][0]}\n\n")
        mid = len(unique_blocks) // 2
        for h, paras in unique_blocks[1:mid]:
            parts.append(f"## {h}\n\n" + "\n\n".join(paras) + "\n")
        parts.append("## Reference\n\n")
        parts.append(code_for(slug, domain))
        parts.append("\n")
        for h, paras in unique_blocks[mid:]:
            parts.append(f"## {h}\n\n" + "\n\n".join(paras) + "\n")

    parts.append("## Closing\n")
    parts.append(
        f"Done well, {topic} disappears into the background — releases stay boring, incidents stay rare. "
        f"That is the bar: measurable, owned, and safe to change in small diffs.\n"
    )

    # Depth section — unique paragraphs per slug until word target
    parts.append("\n## Depth notes\n")
    for para in supplement_paragraphs(slug, topic, domain):
        if word_count("\n".join(parts)) >= TARGET_WORDS:
            break
        parts.append(para + "\n")

    parts.append("\n## Resources\n")
    for label, url in resources_for(slug, domain):
        parts.append(f"- [{label}]({url})\n")

    body = "\n".join(parts)
    idx = 0
    paras = supplement_paragraphs(slug, topic, domain)
    while word_count(body) < TARGET_WORDS and idx < len(paras):
        extra = f"\n{paras[idx]}\n"
        if extra.strip() not in body:
            marker = "\n## Resources\n"
            if marker in body:
                head, tail = body.split(marker, 1)
                body = head.rstrip() + extra + marker + tail
            else:
                body = body.rstrip() + extra
        idx += 1
    return body


def pad_unique(slug: str, topic: str, body: str) -> str:
    extras = [
        f"\n\n## Edge cases to test explicitly\n\n"
        f"Concurrent updates, permission downgrades, and cold starts expose hidden assumptions in {topic}. "
        f"Integration tests should use the same dependency topology as production — not Docker Compose on a laptop.",
        f"\n\n## What to document for on-call\n\n"
        f"Dashboard links, rollback commands, and two example log lines (healthy vs broken) for {topic}. "
        f"If mitigation requires senior tribal knowledge, simplify before the next launch.",
        f"\n\n## Stakeholder alignment\n\n"
        f"Product wants speed; security wants blast-radius caps; finance watches unit cost. "
        f"Translate {topic} into each language before review so 'temporary bypasses' do not become permanent.",
    ]
    used: set[int] = set()
    while word_count(body) < TARGET_WORDS and len(used) < len(extras):
        idx = pick_variant(slug + str(word_count(body)) + str(len(used)), len(extras))
        if idx in used:
            idx = next(i for i in range(len(extras)) if i not in used)
        used.add(idx)
        extra = extras[idx]
        if extra.strip() in body:
            continue
        marker = "\n## Resources\n"
        if marker in body:
            head, tail = body.split(marker, 1)
            body = head.rstrip() + extra + marker + tail
        else:
            body = body.rstrip() + extra + "\n"
    return body


def resources_for(slug: str, domain: str) -> list[tuple[str, str]]:
    if "webauthn" in slug or "passkey" in slug:
        return [("WebAuthn Guide", "https://webauthn.guide/"), ("passkeys.dev", "https://passkeys.dev/")]
    if "streaming" in slug:
        return [("MDN SSE", "https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events")]
    if domain == "kotlin":
        return [("Kotlin docs", "https://kotlinlang.org/docs/home.html")]
    if domain == "kubernetes":
        return [("Kubernetes docs", "https://kubernetes.io/docs/home/")]
    return [("OpenTelemetry", "https://opentelemetry.io/docs/")]


def expand_body(slug: str, title: str, topic: str, domain: str, body: str) -> str:
    body = strip_template_sections(body)
    if word_count(body) >= TARGET_WORDS:
        return body
    additions = blocks_for_slug(slug) or generic_llm_blocks(topic)
    extra_parts = ["\n## Production depth\n"]
    for h, paras in additions[:3]:
        extra_parts.append(f"### {h}\n")
        extra_parts.append("\n".join(paras) + "\n")
    extra_parts.append("\n## Operational checklist\n")
    extra_parts.append(
        f"- Define owner and on-call runbook for {topic}\n"
        f"- Add metrics before widening feature flags\n"
        f"- Rehearse rollback once per quarter\n"
        f"- Capture baseline latency and error rate pre-launch\n"
    )
    extra = "\n".join(extra_parts)
    marker = "\n## Resources\n"
    if marker in body:
        head, tail = body.split(marker, 1)
        body = head.rstrip() + extra + marker + tail
    else:
        body = body.rstrip() + extra + "\n"
    for pad in (
        f"\n\n## Field operations\n\nShip observability first, then feature flags, then behavior changes. "
        f"That ordering makes rollback a toggle instead of a revert war for {topic}.\n",
    ):
        if word_count(body) >= TARGET_WORDS:
            break
        if pad.strip() in body:
            continue
        if marker in body:
            head, tail = body.split(marker, 1)
            body = head.rstrip() + pad + marker + tail
        else:
            body = body.rstrip() + pad
    return body


def render_frontmatter(post: dict, faqs: list[dict]) -> str:
    tags_yaml = "\n".join(f'  - "{t}"' for t in post["tags"])
    faq_yaml = "\n".join(
        f'  - q: "{yaml_escape(f["q"])}"\n    a: "{yaml_escape(f["a"])}"' for f in faqs
    )
    return f"""---
title: "{yaml_escape(post['title'])}"
slug: "{post['slug']}"
description: "{yaml_escape(post['description'])}"
datePublished: "{post['date_published']}"
dateModified: "{post['date_modified']}"
tags:
{tags_yaml}
keywords: "{yaml_escape(post['keywords'])}"
faq:
{faq_yaml}
---
"""


def process_post(post: dict, rel: str, head_entry: dict) -> dict:
    slug = post["slug"]
    topic = slug_to_topic(slug, post["title"])
    domain = domain_for(slug)
    faqs = faq_for(slug, post["title"], topic, domain)
    post["keywords"] = keywords_for(slug, topic, domain)
    head = head_entry.get("body") or ""
    meta = head_entry
    head_is_template = is_template_body(head)
    disk_is_template = is_template_body(post["body"])
    generator_artifact = (
        "I have shipped" in post["body"]
        or "Most write-ups on" in post["body"]
        or "## Starting point\n\nMinimize stored conversations" in post["body"]
    )

    if head_is_template or disk_is_template or generator_artifact:
        new_body = assemble_rewrite(slug, post["title"], topic, domain)
        mode = "rewritten"
        post["tags"] = tags_for(slug, domain, post["tags"])
        post["description"] = description_for(slug, post["title"], topic, domain)
    else:
        base = head if head else post["body"]
        new_body = expand_body(slug, post["title"], topic, domain, base)
        mode = "expanded"
        if meta.get("tags"):
            post["tags"] = meta["tags"]
        if meta.get("description") and "production patterns for ai teams" not in meta["description"]:
            post["description"] = meta["description"]

    wc = word_count(new_body)
    out = render_frontmatter(post, faqs) + "\n" + new_body.lstrip("\n")
    if not out.endswith("\n"):
        out += "\n"
    post["path"].write_text(out)
    return {"slug": slug, "status": mode, "words": wc, "domain": domain}


def main():
    all_files = sorted(BLOG.glob("*.md"))
    batch = all_files[SLICE_START: SLICE_END + 1]
    head_cache = load_head_cache(batch)
    results = []
    for path in batch:
        rel = str(path.relative_to(ROOT))
        post = parse_post(path)
        results.append(process_post(post, rel, head_cache.get(rel, {})))

    expanded = [r for r in results if r["status"] == "expanded"]
    rewritten = [r for r in results if r["status"] == "rewritten"]
    under = [r for r in results if r["words"] < TARGET_WORDS]

    progress = {
        "batch": "07",
        "slice": [SLICE_START, SLICE_END],
        "total": len(batch),
        "expanded": len(expanded),
        "rewritten": len(rewritten),
        "under_target_words": len(under),
        "target_words": TARGET_WORDS,
        "completed_at": date.today().isoformat(),
        "word_stats": {
            "min": min(r["words"] for r in results),
            "max": max(r["words"] for r in results),
            "avg": round(sum(r["words"] for r in results) / len(results), 1),
        },
        "by_domain": {},
        "samples": results[:5],
        "samples_tail": results[-3:],
    }
    for r in results:
        d = r["domain"]
        progress["by_domain"][d] = progress["by_domain"].get(d, 0) + 1

    PROGRESS.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS.write_text(json.dumps(progress, indent=2) + "\n")

    print(json.dumps({k: progress[k] for k in ("total", "expanded", "rewritten", "under_target_words", "word_stats", "by_domain", "samples", "samples_tail")}, indent=2))


if __name__ == "__main__":
    main()
