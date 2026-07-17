#!/usr/bin/env python3
"""Rewrite batch11 chunk 3: unique bodies, topic FAQ, no boilerplate."""
from __future__ import annotations

import importlib.util
import json
import re
import textwrap
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
SLUG_FILE = Path("/tmp/batch11_chunk_2.txt")
PROGRESS = ROOT / "scripts/humanize-progress" / "batch-11-chunk2.json"
DATE = "2026-07-17"
TARGET = 1200
WORD = re.compile(r"\b[\w'-]+\b")

BOILER_RE = [
    r"## Common production mistakes\n.*?(?=\n## |\Z)",
    r"## Debugging and triage workflow\n.*?(?=\n## |\Z)",
    r"## Architecture and boundaries\n.*?(?=\n## |\Z)",
    r"## Accessibility requirements\n.*?(?=\n## |\Z)",
    r"## Security and privacy considerations\n.*?(?=\n## |\Z)",
    r"## Testing strategy\n.*?(?=\n## |\Z)",
    r"The gap between reading about .*? — not a conference demo\.\n\n",
    r"I have applied these patterns across product sites where Core Web Vitals.*?\n\n",
    r"Validate in staging with production-like data volumes\..*?\n\n",
    r"Document the timeline during triage\..*?\n\n",
    r"Document trade-offs in the PR description\..*?\n\n",
    r"## Measuring success in production\n.*?(?=\n## |\Z)",
    r"## Additional production considerations\n.*?(?=\n## |\Z)",
    r"## Integration with your stack\n.*?(?=\n## |\Z)",
    r"## Debugging checklist\n.*?(?=\n## |\Z)",
]
GENERIC_FAQ = "is a production pattern for frontend and product engineering"

spec = importlib.util.spec_from_file_location("meta", ROOT / "scripts/humanize_batch11_chunk2_topics.py")
meta_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(meta_mod)
TOPICS = meta_mod.TOPICS


def wc(t: str) -> int:
    return len(WORD.findall(t))


def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def parse(raw: str) -> tuple[str, str]:
    p = raw.split("---", 2)
    return p[1], p[2].lstrip("\n")


def strip_boiler(body: str) -> str:
    for pat in BOILER_RE:
        body = re.sub(pat, "", body, flags=re.S)
    return re.sub(r"\n{3,}", "\n\n", body).strip()


def build_fm(existing_fm: str, slug: str, faqs: list[tuple[str, str]]) -> str:
    fm = re.sub(r"^dateModified:.*$", f'dateModified: "{DATE}"', existing_fm, flags=re.M)
    if "dateModified" not in fm:
        fm = re.sub(r"(datePublished:.*)", rf"\1\ndateModified: \"{DATE}\"", fm, count=1)
    if GENERIC_FAQ in fm or '  - q: "What is' in fm:
        faq_block = "faq:\n" + "\n".join(f'  - q: "{esc(q)}"\n    a: "{esc(a)}"' for q, a in faqs[:3])
        fm = re.sub(r"faq:\n(?:  - q:.*?\n    a: .*?\n)+", faq_block + "\n", fm, flags=re.S)
    return fm.strip()


def code_for(slug: str) -> str:
    if "webhook" in slug:
        return textwrap.dedent("""
            async function deliverWebhook(delivery, endpoint, secret) {
              const body = JSON.stringify(delivery.payload);
              const ts = Math.floor(Date.now() / 1000).toString();
              const sig = signHmac(secret, ts, body);
              const res = await fetch(endpoint.url, {
                method: "POST",
                headers: {
                  "Content-Type": "application/json",
                  "Webhook-Id": delivery.eventId,
                  "Webhook-Timestamp": ts,
                  "Webhook-Signature": sig,
                },
                body,
                signal: AbortSignal.timeout(30_000),
              });
              if (!res.ok) throw new Error(`HTTP ${res.status}`);
            }
        """).strip()
    if "websocket" in slug:
        return textwrap.dedent("""
            const ws = new WebSocket(url);
            ws.onopen = () => {
              pingTimer = setInterval(() => ws.send(JSON.stringify({ type: "ping" })), 30_000);
            };
            ws.onclose = () => {
              clearInterval(pingTimer);
              setTimeout(reconnect, backoffWithJitter());
            };
        """).strip()
    if "xss" in slug or "sanitize" in slug:
        return textwrap.dedent("""
            import DOMPurify from "dompurify";
            const clean = DOMPurify.sanitize(input, {
              ALLOWED_TAGS: ["b", "i", "em", "strong", "a", "p", "ul", "ol", "li", "code"],
              ALLOWED_ATTR: ["href", "title"],
            });
            el.replaceChildren(document.createRange().createContextualFragment(clean));
        """).strip()
    if "module-preload" in slug or "resource-hints" in slug:
        return textwrap.dedent("""
            <link rel="modulepreload" href="/assets/entry-abc123.js" crossorigin />
            <link rel="preload" href="/hero.avif" as="image" type="image/avif" fetchpriority="high" />
            <link rel="preconnect" href="https://cdn.example.com" crossorigin />
        """).strip()
    if "indexeddb" in slug or "storage" in slug:
        return textwrap.dedent("""
            const db = await openDB("app", 2, {
              upgrade(db, oldVersion) {
                if (oldVersion < 1) db.createObjectStore("drafts", { keyPath: "id" });
                if (oldVersion < 2) db.createObjectStore("outbox", { keyPath: "id", autoIncrement: true });
              },
            });
        """).strip()
    if "webauthn" in slug:
        return textwrap.dedent("""
            const credential = await navigator.credentials.get({
              publicKey: {
                challenge: new Uint8Array(challengeFromServer),
                rpId: "example.com",
                allowCredentials: [{ id: credentialId, type: "public-key" }],
                userVerification: "required",
              },
            });
        """).strip()
    if "worker" in slug:
        return textwrap.dedent("""
            const worker = new Worker(new URL("./compute.worker.ts", import.meta.url), { type: "module" });
            worker.postMessage({ buffer: data.buffer }, [data.buffer]);
            worker.onmessage = (e) => renderResult(e.data);
        """).strip()
    if "workmanager" in slug or "android" in slug:
        return textwrap.dedent("""
            val request = OneTimeWorkRequestBuilder<SyncWorker>()
              .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
              .build()
            WorkManager.getInstance(context).enqueueUniqueWork("sync", ExistingWorkPolicy.KEEP, request)
        """).strip()
    if "migration" in slug:
        return textwrap.dedent("""
            ALTER TABLE orders ADD COLUMN status_v2 text;
            -- batched backfill
            UPDATE orders SET status_v2 = status WHERE status_v2 IS NULL AND id BETWEEN $1 AND $2;
            ALTER TABLE orders ALTER COLUMN status_v2 SET NOT NULL;
        """).strip()
    return textwrap.dedent("""
        performance.mark("start");
        await applyChange();
        performance.mark("end");
        performance.measure("change", "start", "end");
    """).strip()


def lang_for(slug: str) -> str:
    if "workmanager" in slug or "android" in slug:
        return "kotlin"
    if "migration" in slug:
        return "sql"
    if "module-preload" in slug or "resource-hints" in slug or "speculation" in slug:
        return "html"
    return "typescript"


# Import generated unique section content
from batch11_chunk2_sections import SECTIONS  # noqa: E402


def compose_body(slug: str, meta: tuple) -> str:
    hook, tech, when, mistake, faqs = meta
    secs = SECTIONS.get(slug)
    if not secs:
        raise KeyError(f"Missing sections for {slug}")
    parts = [hook]
    for title, paras in secs:
        parts.append(f"## {title}\n\n" + "\n\n".join(paras))
    parts.append(textwrap.dedent(f"""
        ## Reference implementation

        ```{lang_for(slug)}
        {code_for(slug)}
        ```
    """).strip())
    parts.append(f"## When to prioritize\n\n{when.capitalize()}.")
    parts.append(f"## Anti-pattern to avoid\n\n{mistake}")
    return "\n\n".join(parts)


def write_post(slug: str, fm: str, body: str) -> int:
    (BLOG / f"{slug}.md").write_text(f"---\n{fm.strip()}\n---\n\n{body.strip()}\n", encoding="utf-8")
    return wc(body)


def main():
    slugs = [s.strip() for s in SLUG_FILE.read_text().splitlines() if s.strip()]
    done = skipped = 0
    results = []
    for slug in slugs:
        path = BLOG / f"{slug}.md"
        raw = path.read_text(encoding="utf-8")
        fm, old_body = parse(raw)
        meta = TOPICS[slug]
        new_fm = build_fm(fm, slug, meta[4])

        # Keep high-quality existing bodies (webhooks-style) if no template markers and >=1180w after strip
        cleaned = strip_boiler(old_body)
        keep = (
            wc(cleaned) >= 1180
            and GENERIC_FAQ not in raw
            and "## Architecture and boundaries" not in raw
            and "Validate in staging" not in raw
        )
        if keep:
            body = cleaned
            if wc(body) < TARGET:
                body += "\n\n" + SECTIONS.get(slug, [[("", [])]])[-1][1][0] if slug in SECTIONS else ""
            count = write_post(slug, new_fm, body)
            skipped += 1
        else:
            body = compose_body(slug, meta)
            count = write_post(slug, new_fm, body)
            done += 1
        results.append({"slug": slug, "words": count, "status": "skipped" if keep else "done"})

    under = [r for r in results if r["words"] < TARGET]
    report = {"done": done, "skipped": skipped, "under_1200": len(under), "results": results}
    PROGRESS.write_text(json.dumps(report, indent=2), encoding="utf-8")
    samples = sorted(results, key=lambda x: -x["words"])[:3]
    print(json.dumps({"done": done, "skipped": skipped, "samples": samples}, indent=2))


if __name__ == "__main__":
    main()
