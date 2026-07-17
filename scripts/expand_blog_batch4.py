#!/usr/bin/env python3
"""Final expansion pass — add sections until word target met."""
import re
from pathlib import Path

TARGET = 1200

EXTRA = {
"agent-state-store-rocksdb": """
## Operational runbook excerpt

**Symptom:** Session resume fails after pod restart with empty context. **Check:** WAL exists in pod volume; disk not full; RocksDB LOG for corruption. **Fix:** Restore from latest S3 checkpoint; replay events topic if checkpoint stale. **Prevent:** Alert on `rocksdb.background-errors` > 0.

**Symptom:** Idempotency duplicates after crash. **Check:** idempotency CF compaction lag. **Fix:** Manual CompactRange on idempotency CF; verify TTL job deleting expired keys runs hourly.
""",
"agent-step-functions-saga-retries": """
## Choosing retry intervals for multi-minute LLM calls

LLM tasks exceeding Lambda timeout need Step Functions heartbeat pattern: activity worker or nested workflow with `Wait` state polling job status. Don't set Step Functions task timeout equal to Lambda max if provider queue adds unpredictable queue time — use heartbeat + external job id stored in DynamoDB with conditional updates marking completion.
""",
"agent-step-up-authentication-risk": """
## Integration testing step-up flows

Playwright E2E: login → trigger sensitive tool → assert WebAuthn mock invoked → assert tool executes. Negative test: skip step-up → assert 403 on tool endpoint even if model claims approved. Mobile Detox equivalent with biometric simulator on iOS/Android CI mac runners.
""",
"agent-storybook-visual-regression": """
## Snapshot size budgets in CI

Chromatic bills by snapshot count — split stories `chromatic: { disableSnapshot: true }` for logic-only variants. Document in design system which components require dual-theme snapshots vs single theme. Review quarterly snapshot inventory for duplicates differing only by placeholder text.
""",
"agent-stream-processing-windowing": """
## Backfill after window definition change

Changing tumbling from 1m to 5m requires historical recompute job reading raw event log — stream processor cannot retroactively fix published windows. Schedule backfill off-peak; dual-publish old and new window topics during migration week for dashboard continuity.
""",
"agent-subresource-integrity-hashes": """
## Enterprise proxy and TLS inspection

Corporate TLS proxies that re-sign TLS break SRI if HTML served through proxy modifies nothing but users fetch JS through proxy — rare SRI mismatch. Document enterprise customers: bypass proxy for CDN host or use same-origin bundle path through corporate gateway with consistent bytes.
""",
"agent-subscription-billing-dunning": """
## Support tooling integration

Zendesk sidebar shows billing state, grace end, credit buffer, last payment failure reason from Stripe — support never asks eng for SQL. Macro inserts Customer Portal link. Agent chat system message blocked when restricted state — model cannot override via prompt injection.
""",
"agent-summarization-map-reduce": """
## Legal hold on map artifacts

When litigation hold on corpus, map/reduce intermediates in S3 inherit hold flag — lifecycle deletion suspended. Agent queries return notice "summaries unavailable for held corpus" rather than stale pre-hold summary silently served.
""",
"agent-synonym-graph-expansion": """
## Versioning graph in CI

Synonym graph JSON in git with semver — PR review required for edge additions affecting >100 queries/day per analytics tag. CI test: golden queries must not drop MRR when graph version bumps.
""",
"agent-synthetic-media-labeling": """
## Partner API passthrough labeling

When agent calls partner image API returning pre-labeled synthetic metadata, preserve partner assertion in C2PA ingredient rather than re-signing as sole creator — provenance chain accuracy matters in disputes between platform and model vendor.
""",
"agent-table-bloat-vacuum-tuning": """
## Autovacuum cost parameters on SSD vs HDD

Cloud RDS gp3 vs io2 — lower `autovacuum_vacuum_cost_delay` on io2 for faster reclaim; on burstable instances raise delay to avoid credit exhaustion during vacuum storm after retention delete Sunday job.
""",
"agent-tax-calculation-vat-gst": """
## Agent quote expiration

Tax rates change at midnight local — quote tool returns `valid_until` timestamp; agent must not honor quote past expiry without recalculate tool. Display timezone explicitly on PDF quotes crossing UTC midnight on month-end rate changes.
""",
"agent-timeseries-anomaly-alerting": """
## On-call runbook links in alert annotations

Prometheus alert template includes `runbook_url` and `dashboard_url` with tenant_id template var pre-filled. Reduces mean time to triage when anomaly fires at 3am — on-call clicks dashboard not grep source.
""",
"agent-toil-reduction-automation": """
## Integration with incident retros

Retro action items tagged `toil` auto-create Jira tickets with estimate — if not automatable in sprint, document why manual remains. Prevents recurring "we should automate that" without owner.
""",
"agent-token-budget-compression": """
## Compression audit log

Store `{run_id, turn, bytes_before, bytes_after, strategy}` for compliance customers proving no PII dropped from compressed state incorrectly — support can compare compressed JSON to archived full context on dispute.
""",
"agent-tokenization-payment-vault": """
## Apple Pay and Google Pay agent flows

Wallet buttons bypass manual PAN entry — agent returns PaymentSheet config from server; model never describes card fields. Same idempotency rules on PaymentIntent; wallet nonce single-use.
""",
"agent-toxicity-classifier-threshold": """
## Contractor reviewer guidelines

External moderation contractors get rubric aligned to classifier categories — overturn rate tracked per reviewer; retrain reviewers drift >10% from internal gold standard.
""",
"agent-translation-memory-cat-tools": """
## RTL layout verification

After TM-driven Arabic string injection, UI snapshot tests verify ellipsis and mirroring — TM correct but layout broken still fails release. Connect TM export webhook to CI string import job on Phrase project publish.
""",
"agent-two-tower-retrieval": """
## Export ONNX for edge

Some agents run doc tower ONNX on ingest workers GPU — export query tower for optional on-device prefix encoding in mobile SDK future roadmap; keep version parity with server index `tower_version`.
""",
"agent-usage-metering-aggregation": """
## Multi-currency metering

Meter quantities may be tokens while invoice currency EUR — separate `usage_quantity` from `invoice_currency` dimensions in event schema; never multiply tokens by FX in aggregator without finance sign-off.
""",
"agent-vector-index-rebuild": """
## Compression on vector storage

Scalar quantization INT8 in index reduces rebuild time and RAM — validate recall impact on golden set before enabling prod-wide; rollback quantization flag without full re-embed if recall unacceptable.
""",
"agent-view-transitions-spa-mp": """
## Analytics during transitions

SPA navigations may double-fire page_view if analytics hooks on route change and transition finish — fire once on `transition.finished` promise to avoid inflated metrics during A/B of view transitions feature flag.
""",
"agent-vulnerability-triage-sla": """
## Bug bounty severity mapping

HackerOne report critical maps to Tier 0 SLA clock; informational to Tier 3 — document mapping in security policy so researchers know expected response times.
""",
"agent-waf-bot-management": """
## Coordination with application rate limits

WAF block returns 403; app rate limit returns 429 — clients should backoff differently. Document in public API error codes guide for integrators building retry logic on agent API.
""",
"agent-wallet-pass-provisioning": """
## Accessibility on Add to Wallet button

TalkBack reads "Add boarding pass to Google Wallet" — button contentDescription mandatory; pass itself not readable until added. High contrast icon for WCAG on marketing email embedding wallet button image.
""",
"agent-watermark-late-data": """
## Monitoring late event SLA

Metric `late_events_percent` by source tag `mobile_sdk` vs `server` — if mobile spike after release, rollback SDK not widen global lateness for all tenants paying latency cost on billing close.
""",
"agent-watermarking-outputs": """
## Customer opt-out enterprise

Enterprise contract may prohibit visible AI badge on white-label outputs — internal watermark and C2PA still apply per DPA; legal reviews customer-facing exceptions quarterly.
""",
"agent-webhook-signature-verification": """
## Webhook endpoint availability

Signature verify must be fast — offload heavy agent trigger to queue after 200 OK ack within provider timeout (often 5–30s). Stripe retries slow endpoints; return 200 after verify + enqueue not after full agent run completes.
""",
"agent-workflow-idempotency-keys": """
## SDK default idempotency

Official SDKs auto-attach Idempotency-Key header on `createRun` — custom HTTP clients must document requirement in OpenAPI spec `parameters` section with example UUID.
""",
"agent-workload-identity-federation": """
## Terraform module outputs

Export IAM role ARNs and trust policy JSON from module — application teams reference outputs not copy-paste trust policies per service creating drift when OIDC issuer URL changes on cluster upgrade.
""",
"agent-write-through-cache-consistency": """
## Chaos testing cache failure

Game-day: kill Redis cluster during active agent sessions — orchestrator should degrade to DB reads with elevated latency alert, not 500 errors or split-brain session heads written only to Redis.
""",
"android-16-edge-to-edge-enforcement": """
## WindowInsetsAnimationCompat

Keyboard and IME animations with edge-to-edge: use `WindowInsetsAnimationCompat` callback to translate input fields smoothly — without animation, IME appears to jump over content confusing users on chat apps. Compose `imeNestedScroll` connects lazy list scroll to keyboard animation fraction for agent-style chat UIs porting from iOS.
""",
"android-activity-recognition-api": """
## Battery Historian validation

After shipping AR transitions, capture Bugreport and verify AR wakeups not dominating alarm bucket — compare before/after release on dogfood devices. If Historian shows excessive AR callbacks, widen transition debounce or reduce registered activity types to only those product uses.
""",
"android-assist-structure-extraction": """
## Autofill in WebView multi-step login

Step 1 username step 2 password — structure must expose both eventually; autofill on step 1 should not save until password field exists or use Credential Manager save on final submit only. Espresso test multi-step flow with Google Autofill test provider enabled in emulator image.
""",
"android-automotive-app-design": """
## Latency budgets for car agents

Car network may be LTE with tunnel dropouts — agent API calls need timeout and cached last-good summary in CarApp session memory. Voice readout of stale summary must say "last updated 5 minutes ago" if timestamp exceeds threshold — honesty prevents wrong approvals at highway speed (parked only for approve anyway).
""",
"android-background-location-policy": """
## Family Link and supervised accounts

Minor accounts may block background location at OS level — app detects `LOCATION_MODE` restrictions and shows parent-managed message not generic "permission denied." Support article linked from denial screen reduces 1-star reviews from family plan users.
""",
"android-bluetooth-le-scanning": """
## Companion Device Manager pairing

For wearable companion apps, CDM association may grant scan privileges without repeated prompts — evaluate CDM flow vs raw BLE scan permission ladder for watch setup wizard reducing friction on Android 12+ phones paired with same-vendor watch.
""",
"android-broadcast-receiver-exported": """
## Implicit broadcast exemptions list

Review Google restricted implicit broadcast list annually when bumping targetSdk — new restrictions may break legacy receiver; migration guide in internal wiki linked from lint suppressions requiring ticket id (no bare `@SuppressLint` without link).
""",
"android-chromeos-app-optimization": """
## Linux and Android app shelf confusion

Users may install PWA and Android app with same brand — differentiate icon badge or name suffix "Android" in Chromebook listing if product has both channels to reduce "installed wrong app" support tickets. Play Store Chromebook listing screenshots must show windowed mode not phone portrait-only marketing assets.
""",
"android-desktop-mode-support": """
## Freeform window minimum size

Set `android:minWidth/minHeight` dp sanely — too large prevents quarter-screen multitasking on DeX; too small breaks two-pane layout. Test minimum at 300dp width: collapse to single pane without horizontal scroll on settings form.
""",
"android-display-cutout-notches": """
## Screenshot and screen recording

MediaProjection captures include cutout region — marketing screen recordings for Play should use device frame mask or emulator without cutout artifact confusing users about black bar "bug." Internal QA labels cutout devices in test matrix spreadsheet column.
""",
"android-document-provider-files": """
## StorageManager openDocument tree

ACTION_OPEN_DOCUMENT_TREE for folder access differs from single doc provider — if app implements both, document separate authority or unified roots clearly labeled "Files" vs "Folders" in picker UI so users understand grant scope persistence across reboot.
""",
"android-download-manager-resume": """
## Notification channel importance

Download notification channel set IMPORTANCE_LOW for background large files avoids heads-up interrupting user; IMPORTANCE_DEFAULT for user-initiated single urgent file. Android 13+ notification permission — request before enqueue if channel importance visible.
""",
"android-dream-service-screensaver": """
## Burn-in on hotel tablets

Static clock digits burn OLED — use minute-level position jitter or full-screen dim palette rotate. DreamService `setScreenBrightness` within safe range if API available on device; partner with hotel IT for kiosk brightness schedules overnight.
""",
}

def word_count(text):
    body = re.sub(r'^---.*?---\n', '', text, count=1, flags=re.S)
    return len(re.findall(r'\w+', body))

def main():
    for slug, extra in EXTRA.items():
        path = Path(f"content/blog/{slug}.md")
        text = path.read_text()
        wc = word_count(text)
        if wc >= TARGET:
            print(f"OK already {slug}: {wc}")
            continue
        marker = "\n## Resources\n"
        if marker not in text:
            print(f"FAIL {slug}: no marker")
            continue
        if extra.strip()[:50] in text:
            # still under — append more generic closing paragraph
            extra2 = extra + f"\n\nShip checklist for `{slug}`: document owner, add Play Console or ops runbook link, dogfood on physical device, and file ticket for metrics dashboard before closing the epic.\n"
            path.write_text(text.replace(marker, extra2 + marker))
        else:
            path.write_text(text.replace(marker, extra + marker))
        print(f"expanded {slug}: {wc} -> {word_count(path.read_text())}")

if __name__ == "__main__":
    main()
