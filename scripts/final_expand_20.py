#!/usr/bin/env python3
"""Append final unique sections to 20 slugs until >=1250 words."""
import re
from pathlib import Path

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

UNIQUE = {
    "android-display-cutout-notches": """
## Foldable inner versus outer display cutouts

Foldables expose different cutout geometry on cover versus inner displays. Cache `DisplayCutout` per `WindowMetrics` instance — storing the first cutout in an Application singleton breaks when the user opens the device. Hinge-aware layouts may shift the cutout from top to side when spanning displays. Dynamic Island-style OEM overlays sometimes omit bounds from `DisplayCutout`; maintain an internal OEM workaround table linked from layout bug tickets rather than guessing padding.

## Game and immersive cutout policy

Games using `LAYOUT_IN_DISPLAY_CUTOUT_MODE_ALWAYS` for full-bleed rendering should document acceptable overlap regions in the UX spec. Productivity agent UIs should prefer `shortEdges` with padded chrome so connection indicators and typing carets never sit under the camera housing — a frequent Play review complaint on chat apps.
""",
    "android-broadcast-receiver-exported": """
## WorkManager versus broadcast for deferred agent sync

Replace implicit `CONNECTIVITY_CHANGE` manifest receivers with `NetworkRequest` callbacks or WorkManager constraints. Agent sync that only needs eventual consistency should enqueue `OneTimeWorkRequest` with `NetworkType.CONNECTED` rather than registering exported receivers. If you must receive `BOOT_COMPLETED`, keep exported true with `RECEIVE_BOOT_COMPLETED` permission and defer heavy work to WorkManager inside the receiver within the ANR budget.

## Pen-test replay commands

Document expected no-op behavior for security reviewers:

```bash
adb shell am broadcast -a com.example.app.action.DOWNLOAD_COMPLETE --es downloadId 99999
```

When exported is false, no handler runs and no agent job enqueues. Pair with lint `ExportedReceiver` severity error in CI.
""",
    "android-chromeos-app-optimization": """
## Play listing assets for Chromebook discovery

Upload windowed-mode screenshots and declare keyboard support in Play Console. Apps flagged "not optimized for Chrome OS" show a warning badge that reduces edu-market installs. Monitor Crashlytics with filters for ARC device patterns (`cheets`, `chrome`) to isolate Chromebook-specific stack traces from phone noise.

## Managed edu network constraints

School Chromebooks may TLS-intercept outbound HTTPS. Certificate pinning on agent API clients fails on managed networks unless IT allowlists your endpoints. Document optional pin-disable for enterprise builds and test agent streaming through a proxy during QA.
""",
    "android-desktop-mode-support": """
## Taskbar focus and agent streaming pause policy

Losing window focus in DeX does not equal user abandonment — define whether agent token streaming pauses when the window is inactive. Persist scroll state across resize events; debounce expensive layout work during drag-resize with `snapshotFlow`. Set meaningful activity labels — users pick apps from the taskbar by name when multitasking.

## Third-column agent layout above 1200dp

At wide widths, use list | thread | citations panel. Below 600dp freeform width, collapse to single-pane navigation. Persist column weights in `DataStore` keyed by width bucket, not absolute pixels.
""",
    "android-background-location-policy": """
## Geofencing as lower-privilege alternative

Evaluate `GeofencingClient` for "arrived at job site" features before requesting `ACCESS_BACKGROUND_LOCATION`. Combined with Wi-Fi fused location, geofence transitions may suffice without continuous GPS. When user revokes background permission in Settings, stop FGS within seconds and surface "tracking off" in UI — silent failure breaks dispatch agent workflows.

## Analytics SDK audit for hidden location readers

Play rejection often traces to a third-party SDK sampling location in background without disclosure. Quarterly audit SDK network traffic with `adb shell dumpsys package` permission flags and remove non-essential location calls from analytics vendors.
""",
    "android-bluetooth-le-scanning": """
## Scan duty cycle budgeting

Target scan duty cycle under 5% in background unless FGS owns the UX. Log `(scan_ms / wall_ms)` in debug builds. Centralize scan requests in a coordinator with reference counting — inventory and proximity features must not each call `startScan` independently.

## Android 12 permission UX copy

Request `BLUETOOTH_SCAN` and `BLUETOOTH_CONNECT` with rationale tied to the agent tool — never pre-prompt on cold start before the user invokes a BLE feature. After denial, deep-link to Settings instead of looping prompts every screen entry.
""",
    "android-document-provider-files": """
## QUERY_ARG_LIMIT pagination for large trees

Folders with 10k+ files must paginate `queryChildDocuments` using `QUERY_ARG_LIMIT` and `QUERY_ARG_OFFSET` — naive `listFiles` on the binder thread causes ANRs in the system Files app. Document ID encoding must reject `../` path escape when mapping to internal storage.

## Revoke outstanding URI permissions on delete

When deleting cloud-backed documents, revoke permissions on outstanding URIs so clients holding stale grants fail read on next access rather than reading deleted content from cache.
""",
    "android-activity-recognition-api": """
## GMS-less device degradation

When `ActivityRecognition.getClient` fails on Huawei or other GMS-less devices, disable auto-pause features with an explanatory settings toggle rather than crash-looping registration. Remote-config blocklist incompatible models from Play device catalog analytics.

## Transition debouncing for drive mode

Require two consecutive `IN_VEHICLE` enter events above confidence 75 before enabling drive mode — parking-lot foot↔vehicle oscillation often shows 60–80 confidence. Log weekly confidence histograms to tune thresholds.
""",
    "android-assist-structure-extraction": """
## Compose semantics for assist visibility

Naked Compose `Text` without semantics may be invisible to assist extraction. Set `contentDescription` on order totals, status chips, and agent tool labels. WebView login pages need JS bridge "form ready" before `AutofillManager.requestAutofill()` — SPAs often miss fields on first assist snapshot.

## On-device redaction before any network call

Run PII regex and password-field heuristics on extracted JSON in debug and release. Never upload full `AssistStructure` on background timers — only after explicit user "help with this screen" consent.
""",
    "android-automotive-app-design": """
## Car App Library version alignment

Host head units lag `androidx.car.app` releases — set `minCarApiLevel` meta-data to match partner compatibility matrices before adopting breaking template APIs. Run car-app-validator in CI on every release candidate.

## Voice-first agent summaries on driver display

Driver templates cannot show full agent threads — sync pending-approval counts from the same backend queue as mobile. Invalidate car session on phone approval via push so stale "Approve" actions do not appear after the user already handled the item on their phone.
""",
    "agent-webhook-signature-verification": """
## Next.js App Router raw body capture

Disable default body parsing on webhook routes or read `request.text()` before JSON parse. Re-serialized JSON breaks HMAC — buffer raw bytes in middleware, verify, then parse. Return 200 within provider timeout after verify + enqueue; never run full agent workflows synchronously in the handler.

## Multi-region secret routing

EU endpoints must reject webhooks signed with US-only secrets unless product explicitly supports cross-region routing — misconfigured active-active setups create data residency incidents even when signatures verify cryptographically.
""",
    "agent-watermarking-outputs": """
## PDF and DOCX export pipelines

C2PA covers PNG well; PDF exports need metadata plus visible footer watermarks. DOCX requires a separate pipeline — do not assume one post-processor covers all agent export tools. Code modality stores provenance in sidecar JSON only; zero-width text watermarks break compilers.

## GDPR erasure versus in-the-wild watermarks

Honor erasure by anonymizing generation records in your database — you cannot reverse statistical watermarks already copied by users. Detection API returns generation hints for routing takedowns, not for undoing embeds in third-party documents.
""",
    "agent-usage-metering-aggregation": """
## Stripe exporter idempotency

Stripe Meter `identifier` must be unique per hour-tenant-meter — reuse causes silent dedupe (usually desired). On API 500, retry with backoff and dead-letter failed exports for finance reconciliation; never double-submit without idempotency keys on the exporter job.

## Enterprise committed-spend dashboards

Branch the same event stream in the warehouse for product-led growth views — duplicate ingestion pipelines drift. Show 5-minute delayed dashboards with footnote "subject to hourly reconciliation" to set finance expectations.
""",
    "agent-storybook-visual-regression": """
## Font loading flake fix

Await `document.fonts.ready` before Chromatic capture. Local fixture avatars at `/fixtures/avatar.png` instead of remote URLs. Quarantine stories with >2% flake until fixed — do not mute forever.

## Percy/Chromatic review SLAs

Require designer approval on intentional diffs for `components/chat/**` CODEOWNERS paths. Bulk-accept after dependency bumps without scanning is how overlapping tool chips ship to production.
""",
    "agent-workflow-idempotency-keys": """
## Partial 202 replay semantics

Long-running runs return 202 + `run_id` on first POST; idempotent replay must return the same 202 body, not a duplicate 201. Document client SDK auto-generation of UUID v4 keys — timestamp keys collide on double-click same millisecond.

## Redis cluster hash tags

Colocate tenant idempotency keys with `{tenant_id}:idem:{key}` in Redis Cluster to avoid CROSSSLOT errors. TTL must exceed max retry horizon including DLQ replay windows.
""",
    "agent-wallet-pass-provisioning": """
## Pass revocation on booking cancel

Cancel flows must void passes — stale boarding passes on lock screens confuse travelers. Apple web service returns 410; Google objects set `EXPIRED`. Agent narrates "pass will update when online" if push is pending while device is offline.

## HSM signing throughput tests

Load-test pass signing before peak travel events — Black Friday surges hit HSM rate limits before API rate limits. Never embed signing certificates in agent runtime; wallet microservice owns crypto exclusively.
""",
}


def wc(text: str) -> int:
    return len(re.findall(r"\w+", text))


def insert(text: str, extra: str) -> str:
    marker = "\n## Resources\n"
    chunk = extra.strip()
    if not chunk or chunk[:40] in text:
        return text
    return text.replace(marker, "\n" + chunk + "\n" + marker, 1)


def main():
    for slug in SLUGS:
        path = Path(f"content/blog/{slug}.md")
        text = path.read_text()
        before = wc(text)
        if before >= TARGET:
            print(f"OK {slug}: {before}")
            continue
        extra = UNIQUE.get(slug, "")
        text = insert(text, extra)
        path.write_text(text)
        after = wc(text)
        print(f"{slug}: {before} -> {after} {'OK' if after >= 1200 else 'LOW'}")


if __name__ == "__main__":
    main()
