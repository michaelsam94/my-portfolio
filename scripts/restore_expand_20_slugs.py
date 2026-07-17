#!/usr/bin/env python3
"""Restore 20 blog posts from transcripts + batch expansions; target >=1250 words."""
import json
import re
import glob
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLOG = ROOT / "content/blog"
TRANSCRIPTS = Path.home() / ".cursor/projects/Users-michael-Desktop-my-portfolio/agent-transcripts"
TARGET = 1250

SLUGS = [
    "android-display-cutout-notches",
    "android-broadcast-receiver-exported",
    "android-chromeos-app-optimization",
    "android-desktop-mode-support",
    "android-background-location-policy",
    "android-bluetooth-le-scanning",
    "android-document-provider-files",
    "android-download-manager-resume",
    "android-activity-recognition-api",
    "agent-timeseries-anomaly-alerting",
    "android-assist-structure-extraction",
    "android-automotive-app-design",
    "agent-tax-calculation-vat-gst",
    "agent-webhook-signature-verification",
    "agent-watermarking-outputs",
    "agent-usage-metering-aggregation",
    "agent-storybook-visual-regression",
    "agent-workflow-idempotency-keys",
    "agent-wallet-pass-provisioning",
    "agent-stream-processing-windowing",
]

# Fallback bases for slugs not found in transcripts (from prior humanized drafts)
FALLBACK = {
    "agent-timeseries-anomaly-alerting": ROOT / "content/blog/agent-timeseries-anomaly-alerting.md",
    "agent-tax-calculation-vat-gst": ROOT / "content/blog/agent-tax-calculation-vat-gst.md",
}


def wc(text: str) -> int:
    return len(re.findall(r"\w+", text))


def is_boilerplate(text: str) -> bool:
    return "Design principles that survive production" in text


def best_transcript_base(slug: str) -> str | None:
    best = None
    best_wc = 0
    for tf in glob.glob(str(TRANSCRIPTS / "**/*.jsonl"), recursive=True):
        for line in Path(tf).read_text().splitlines():
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            for part in obj.get("message", {}).get("content", []):
                if part.get("type") != "tool_use" or part.get("name") != "Write":
                    continue
                inp = part.get("input", {})
                path = inp.get("path", "")
                contents = inp.get("contents", "")
                if not path.endswith(f"{slug}.md") or not contents or is_boilerplate(contents):
                    continue
                n = wc(contents)
                if n > best_wc:
                    best_wc = n
                    best = contents
    return best


def load_expansions() -> dict[str, str]:
    merged: dict[str, str] = {}
    for script in sorted((ROOT / "scripts").glob("expand*.py")):
        ns = runpy.run_path(str(script))
        for key in ("EXPANSIONS", "EXTRA", "FINAL"):
            block = ns.get(key)
            if isinstance(block, dict):
                for slug, text in block.items():
                    merged.setdefault(slug, "")
                    if text.strip() and text.strip()[:40] not in merged[slug]:
                        merged[slug] += text
    return merged


# Extra unique sections not in batch scripts (no shared skeleton)
CUSTOM = {
    "android-display-cutout-notches": """
## Waterfall insets and curved display edges

Samsung and other OEMs expose `DisplayCutout.getWaterfallInsets()` separately from punch-hole bounds. Toolbar padding that only reads status bar height leaves icons in the curved glass zone where contrast fails and touches miss. Union insets before applying padding:

```kotlin
val topInset = WindowInsets.displayCutout
    .union(WindowInsets.statusBars)
    .union(WindowInsets.waterfall)
```

On devices without waterfall, the inset is zero — one code path covers all SKUs.

## Modal surfaces and IME interaction with cutouts

Bottom sheets and full-screen dialogs have their own decor views. Material3 `ModalBottomSheet` should set `contentWindowInsets = WindowInsets.safeDrawing` so drag handles are not under gesture bars or bottom cutouts on foldables. When the IME opens, re-measure composer padding — cached cutout values from `onCreate` are stale after rotation. Agent chat composers that ignore this place the send button under the camera island when users rotate to landscape mid-thread.
""",
    "android-chromeos-app-optimization": """
## ARCVM memory pressure on education Chromebooks

ARC shares RAM with Chrome tabs. Agent apps retaining full thread history should paginate lists and respond to `onTrimMemory(TRIM_MEMORY_RUNNING_LOW)` by evicting bitmap caches. Cold-start profiling on 4GB Celeron-class hardware is mandatory before claiming Chromebook support — integrated GPUs also struggle with heavy blur and overdraw compared to flagship phones.

## Drag-and-drop from Files app into agent composers

ChromeOS users expect to drag PDFs and images from the Files app into chat. Implement `Modifier.dragAndDropTarget` or `View.OnDragListener` for `text/plain`, `image/*`, and `application/pdf`. Route through the same sanitization pipeline as the attachment button — never pass Linux filesystem paths to the model, upload to your backend and return signed URLs.
""",
    "agent-timeseries-anomaly-alerting": """
## Deploy markers as anomaly covariates

Spikes after intentional model routing changes should not page as unknown anomalies. Ingest deploy events into Prometheus as external labels or Grafana annotations; suppress or retune seasonal detectors for a soak window after each production model switch. On-call learns to ignore "mystery spikes" when change management is visible on the same dashboard panel.

## Composite burn: latency × volume

Success rate alone misses latency-only regressions users feel before errors register. Alert when p95 latency doubles versus same-hour-last-week **and** traffic exceeds a floor — tune multipliers per product SLO. Agent chat tolerates higher latency than realtime tool gateways; split alert rules by `service_tier` label rather than one global threshold.
""",
    "agent-tax-calculation-vat-gst": """
## OSS registration vs merchant-of-record for agent platforms

EU B2C digital services require correct OSS or MoR configuration before agents quote tax-inclusive prices. Stripe Tax and Paddle abstract registration for early-stage teams; Avalara fits multi-entity structures later. Agent tools call a stable `TaxService` interface — swapping adapters never changes LLM tool schemas. Shadow-compare line totals for one billing cycle before decommissioning the old engine.

## Quote `valid_until` and January rate changes

Persist full tax breakdown JSON on every quote with `tax_engine_version` and expiry timestamp. Re-run calculation on acceptance if expired — VAT and US sales tax rates change on calendar boundaries. The agent narrates updated totals from server numbers; it never recomputes percentages from memory.
""",
    "agent-webhook-signature-verification": """
## Svix-style standard headers for partner tool callbacks

Standardize partner integrations on timestamp + signature + event id headers documented in your developer portal. Issue per-tenant rotatable secrets stored in KMS. Reject requests older than five minutes even with valid HMAC — signature proves integrity, not freshness. Queue verified payloads only; never trust unverified bodies inside workers unless the gateway attestation is signed.

## Load testing webhook endpoints

Providers retry 5xx responses with exponential backoff — a signature bug returning 500 can amplify traffic tenfold. Load-test with duplicated valid events; p95 handler latency should stay under 200ms through verify + enqueue only. Store raw bodies to WORM storage after verification when regulations require immutable audit trails.
""",
    "agent-watermarking-outputs": """
## Zero-width characters break code-generation agents

Never embed zero-width Unicode in code tool outputs — IDEs, compilers, and diff tools break silently. Attach provenance as sidecar JSON or signed export metadata for code; reserve statistical text watermarks for natural language and C2PA for raster media. Policy engine evaluates modality before post-processing so code paths skip text watermark embedders entirely.

## Quarterly paraphrase red-team on text watermarks

Run automated paraphrase attacks against watermarked agent prose; if detection rate falls below policy threshold, increase embed strength or rotate keys. False positives in DMCA workflows are as costly as false negatives — tune confidence thresholds per channel (public web vs enterprise API).
""",
}


def insert_before_resources(text: str, extra: str) -> str:
    marker = "\n## Resources\n"
    if marker not in text:
        text = text.rstrip() + "\n"
        return text + extra + marker
    chunk = extra.strip()
    if chunk and chunk[:60] in text:
        return text
    return text.replace(marker, "\n" + chunk + "\n" + marker, 1)


def main():
    expansions = load_expansions()
    results = []

    for slug in SLUGS:
        base = best_transcript_base(slug)
        if not base or wc(base) < 400:
            # use current file if it's good, else skip with error
            path = BLOG / f"{slug}.md"
            cur = path.read_text()
            if not is_boilerplate(cur) and wc(cur) >= 400:
                base = cur
            else:
                print(f"ERROR: no base for {slug}")
                continue

        text = base
        if "dateModified:" in text:
            text = re.sub(r'dateModified: "[^"]*"', 'dateModified: "2026-07-17"', text, count=1)

        extras = expansions.get(slug, "") + CUSTOM.get(slug, "")
        text = insert_before_resources(text, extras)

        # Append batch expansions piecemeal until target met (avoid duplicate headings)
        for script in sorted((ROOT / "scripts").glob("expand*.py")):
            if wc(text) >= TARGET:
                break
            ns = runpy.run_path(str(script))
            for key in ("EXPANSIONS", "EXTRA", "FINAL"):
                block = ns.get(key, {})
                part = block.get(slug, "")
                if part.strip():
                    text = insert_before_resources(text, part)

        path = BLOG / f"{slug}.md"
        path.write_text(text)
        n = wc(text)
        results.append((slug, n, "OK" if n >= 1200 else "LOW"))

    for slug, n, status in sorted(results, key=lambda x: len(x[0])):
        print(f"{slug}: {n} {status}")


if __name__ == "__main__":
    main()
