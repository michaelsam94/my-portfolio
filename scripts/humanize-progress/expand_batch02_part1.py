#!/usr/bin/env python3
"""Expand batch 02 part 1 posts under 1200 words with unique sections."""
import re
from pathlib import Path

BLOG = Path(__file__).resolve().parents[2] / "content" / "blog"
FILES = sorted(BLOG.glob("*.md"))[550:600]

EXPANSIONS = {
    "android-nearby-share-api": """

## Share sheet UX details users notice

The chooser title matters more than teams expect. Generic "Share" feels lazy; "Share receipt with accountant" sets context and reduces wrong taps. If your flow returns to the same screen after share, preserve scroll state — users often share mid-review and expect to land where they left off.

For PDFs and large exports, copy to cache with a human-readable filename before building the URI. Receivers display filenames in their import UI; `export.pdf` collisions confuse Gmail and Drive.

## Enterprise and work profile boundaries

Work profile apps may not expose Nearby Share targets the same way personal profile does. QA on managed devices prevents "works on my phone" surprises for IT-deployed builds. Document that share-to-personal-only flows may need explicit copy when corporate policy blocks cross-profile share.

## Analytics without leaking content

Log share *intent* opened, not URI contents. `"share_sheet_opened"` with `{mime_type, item_count}` is enough product signal. Logging full URLs or file paths creates privacy incidents in analytics warehouses.

## Edge cases worth explicit tests

- Share while rotation mid-chooser — activity recreate should not double-open sheet.
- Share immediately after capture before MediaStore IS_PENDING clears — receiver may see zero-byte file; gate share button until pending cleared.
- Share from process death restored state — URI grant may expire; regenerate from persisted file id.
""",
    "android-nearby-connections-api": """

## Bandwidth upgrade and topology

After connection, Nearby may upgrade from Bluetooth to Wi-Fi Direct for throughput. UI should not disconnect when radio switches — `onBandwidthChanged` callbacks (when available) explain "Transfer speeding up" for impatient users moving multi-GB zips.

## Encryption and trust model

Payloads are encrypted in transit by Play services implementation — do not roll custom XOR "for speed." If you need authenticated pairing, show numeric compare codes derived from connection handshake out-of-band (user reads code aloud) before accepting sensitive exports.

## Version skew between app versions

Field teams run mixed app versions during rollout. Protocol version byte in first control payload prevents older clients mis-parsing new manifest format. Refuse unsupported versions with actionable upgrade prompt rather than silent corruption.

## Comparison with Bluetooth OBEX legacy

OBEX file push still exists on some industrial devices. Nearby Connections is easier for Android-to-Android; keep OBEX adapter branch if your user base includes rugged devices without Play services.
""",
    "android-multi-window-drag-drop": """

## Foldable inner/outer display gotchas

Same activity spanning displays may report drag coordinates in window space that jumps when folding. Reset drag state on `CONFIGURATION_CHANGED` rather than assuming continuous gesture.

## Drag shadow customization

Default shadow is semi-transparent screenshot of view — expensive for large images. Provide lightweight `DragShadowBuilder` drawing icon only for list rows to reduce jank at drag start.

## Accessibility services interaction

TalkBack users need non-drag path — always duplicate with overflow menu actions. Announce drag start/end with `ViewCompat.performAccessibilityAction` when programmatic moves complete.

## Desktop mode and ChromeOS

Freeform windows on ChromeOS treat drag-drop similarly to split-screen — test with ARC++ if you ship to Chromebook users. URI permissions persist across window focus changes but not indefinitely — revalidate on drop.
""",
    "android-mvi-unidirectional-data-flow": """

## Time-travel and debugging

Logging `(intent, stateBefore, stateAfter)` triples to structured logs enables replay debugging without full time-travel library. Keep logs sampling in production — 1% sessions enough for anomaly detection.

## Compose Navigation integration

Effects channel should not call `navController` directly from ViewModel — keep navigation as effect consumed in UI layer to preserve testability and avoid Android framework in domain tests.

## SavedStateHandle interplay

Process death restores `@SavedStateHandle` fields — do not duplicate entire state tree if SavedState already holds ids. Merge: SavedState for ids, MVI state for derived UI fields.

## Performance on high-frequency intents

Search-as-you-type sending `QueryChanged` intents every keystroke can choke reducer. Debounce in UI or coalesce in ViewModel with `distinctUntilChanged` before reduce for text fields.
""",
    "android-ndk-jni-basics-kotlin": """

## 16 KB page size readiness

Google Play device requirements moving toward 16 KB memory page sizes affect native linker flags — follow NDK release notes for `-Wl,-z,max-page-size=16384` when packaging `.so` for future devices. Test on 16 KB emulator image when available.

## Sanitizers in debug native builds

AddressSanitizer native builds catch buffer overruns before production SIGSEGV. Wire optional CMake argument for internal CI nightly — not consumer APK size.

## Kotlin suspend wrapping JNI

Pattern: `suspendCancellableCoroutine` with native callback on background thread posting result. Cancel propagation must abort long native computation if possible to avoid wasted CPU after user navigates away.

## Vendor SDK integration

Third-party `.aar` with bundled `.so` may duplicate STL — watch for duplicate symbol link errors. Align on shared c++_shared or static STL per vendor doc.
""",
    "android-metered-connection-optimization": """

## User education copy that works

Instead of "Sync paused," prefer "Waiting for Wi-Fi to back up 120 photos (~340 MB)." Numbers increase trust; vague pauses feel like bugs.

## Roaming agreements

Enterprise travelers on corporate plans may have NOT_ROAMING even internationally — do not assume roaming equals foreign country only; carriers differ.

## ExoPlayer track selection tie-in

Combine metered flag with `trackSelector` max bitrate cap — separate from disabling prefetch. Users on unlimited mobile still appreciate default SD on cellular with HD toggle per session.
""",
    "android-microbenchmark-inline-methods": """

## Baseline comparison across commits

Store benchmark JSON in `benchmark/baseline-prof.json` or dedicated metrics repo. PR comment bot posting delta table keeps perf visible without reading raw logcat.

## Kotlin inline vs value classes

Value classes wrapping IDs may eliminate boxing — microbenchmark before/after for hot collections. Results vary by ART version; ship measurement not intuition.

## Multithreaded microbenchmarks

Default MicrobenchmarkRule is single-threaded. Contended locks need JMH-style multithread setup outside AndroidX microbenchmark or custom harness — do not infer lock perf from single-thread loop.
""",
    "android-modularization-strategy": """

## Feature flag per module extraction

Ship extracted module behind flag while old code path remains until parity proven — reduces big-bang risk. Flag at repository boundary, not every composable.

## Build cache and remote build

Modularization shines with Gradle remote cache — without it, developers may not feel compile win. Invest in cache hit rate monitoring when splitting modules.

## Ownership and CODEOWNERS

Map `:feature:checkout` to team in GitHub CODEOWNERS — modularization social contract as important as Gradle graph.
""",
    "android-multi-module-navigation-compose": """

## Public navigation API surface

Publish `-navigation` artifact with interfaces only for other teams consuming routes without depending on UI module — enables contract tests that feature UI does not leak into wrong modules.

## Animation shared elements across modules

Shared element transitions require knowing both endpoints — place shared transition spec in `core:ui` or navigation contract, not duplicated in each feature.

## Versioned routes for deep links

Server deep links may outlive app versions — support route version in URI path `/v2/product/` while app registers both during migration window.
""",
    "android-media-playback-foreground-service": """

## Bluetooth metadata lag

Some car units cache old title until AVRCP pause/play cycle — force metadata refresh on track change with session metadata update even if playback continuous.

## Audio becoming noisy on speaker

Product decision document: continue on speaker after unplug vs pause — user setting persisted in DataStore.

## Cast and local playback handoff

When user casts, local ExoPlayer may pause — service should not stopSelf until cast session ends if notification still represents active session.
""",
    "android-media-session-controls": """

## Metadata art cache

Implement disk cache for album art URLs to avoid re-fetch on every skip — lock screen flicker otherwise. Size cap LRU 50 MB typical.

## Android Auto search

If supporting search, debounce query to server — driving safety and ANR prevention on head unit.

## Session inactive timeout

Media3 may stop service after inactivity — document for QA expected stop delay after pause to distinguish bug vs policy.
""",
    "android-media-store-scoped": """

## EXIF location stripping

Publishing photos may leak GPS — strip EXIF location on export if not product intent. Use ExifInterface on background thread before insert.

## MediaStore vs Photo Picker return

Picker returns URI without broad permission — persist takePersistableUriPermission when flag offered. Missing persist breaks upload next day.

## Scoped storage on API 29 legacy flag

`requestLegacyExternalStorage` deprecated — remove from manifest; any remaining flag gives false confidence during migration audit.
""",
    "android-media3-exoplayer-migration": """

## Cronet extension module

If using ExoPlayer Cronet extension, migrate to Media3 Cronet artifact separately — easy to miss in script-only migration.

## Custom Extractors

Apps with niche formats (TS, custom containers) verify ExtractorsFactory registration after package move — silent playback failure if not registered.

## Regression snapshot tests

Golden frame grab at 5s playback timestamp compared pixel diff tolerance in androidTest — catches renderer regressions unit tests miss.
""",
    "android-media3-media-session": """

## Controller connection race in Compose

`rememberMediaController` should handle `ControllerFuture` failure with fallback UI — Play services missing on custom ROMs rare but support tickets exist.

## Queue replacement vs append

`addMediaItems` vs `setMediaItems` semantics differ for shuffle mode — document which API playlist screen uses to avoid duplicate tracks after refresh.

## Sleep timer feature

If product includes sleep timer, use coroutine delay in service scope canceling on user extend — do not AlarmManager unless process must survive killed app.
""",
    "android-memory-leaks-leakcanary": """

## ViewModel leak via callback

Third-party SDK registering callback with Activity in init — wrap with Application context or unregister in `onDestroy`. LeakCanary trace showing SDK class is smoking gun for vendor ticket.

## Compose remember without keys

`remember(apiResponse)` capturing large objects — prefer remember with keys or ViewModel. Not always leak but retained memory grows.

## Heap dump on CI

Optional: fail build if LeakCanary detected leak in instrumentation run — aggressive but useful for regression-sensitive releases.
""",
    "android-mlkit-on-device-vision": """

## Rotation and mirroring front camera

Selfie preview mirrored but ML Kit InputImage rotation must match sensor — mismatch causes false negatives on face bounds.

## GPU acceleration flags

Some detectors offer GPU mode — test thermal throttling on 10-minute continuous scan scenarios warehouse apps use.

## Model download UX

Unbundled model first launch — progress bar honest about download size on cellular before starting.
""",
    "android-material3-adaptive-navigation": """

## Window size class insets

Display cutout and system bars affect perceived width — use WindowInsets and adaptive info together, not raw screen widthDp alone.

## Legacy three-pane XML migration

Teams migrating XML layouts should map existing `slidingPaneLayout` to `ListDetailPaneScaffold` incrementally — do not rewrite navigation and pane on same sprint.

## Desktop windowing resize

ChromeOS freeform resize triggers rapid size class changes — debounce navigation chrome switch 150ms to avoid flicker bar↔rail.
""",
    "android-matter-commissioning": """

## Multi-admin fabric joins

Second user joining home scans different QR — document UX separate from first-device commissioning to avoid "already commissioned" dead ends without explanation.

## Firmware update during commission

Device OTA mid-commission fails session — advise plug power and retry with factory reset only as last resort copy.

## Thread border router offline

Explicit screen when no OTBR found linking to compatible hub SKUs reduces support calls vs generic timeout.
""",
    "android-network-capabilities-detection": """

## Dual SIM active data

Default data SIM switch mid-session fires capabilities callback — re-evaluate prefetch policy without requiring app restart.

## VPN split tunnel metrics

Some bytes route outside VPN — do not assume all app traffic encrypted because TRANSPORT_VPN true if split tunnel.

## Logging redaction

NetSnapshot logs safe; never log SSID or BSSID in production — location sensitive.
""",
    "android-network-security-config": """

## Certificate transparency

NSC pinning does not replace CT log verification on server — client pins only help client-side MITM after trust establishment.

## Multi-flavor pinning

Staging pins in `src/staging/res/xml` overlay release pins — prevent staging cert in production artifact via variant merge verification task in CI.

## WebView mixed content

After NSC strict, audit internal WebView marketing pages for http:// asset references — fix CMS not client workaround.
""",
    "android-new-task-document-launch": """

## Launcher vs non-launcher entry

Deep link from browser vs launcher icon may need different flags — centralize DeepLinkRouter interpreting source.

## Task reparenting

`allowTaskReparenting` rarely needed — enable breaks predictable back; document if used for widget entry.

## Predictive back with document tasks

Android 13+ predictive back animation with multiple document tasks — test Recents swipe consistency.
""",
    "android-notification-channels-best-practices": """

## OEM channel batching

Some OEMs merge channels visually — still create logical separation for users on stock Android and policy clarity.

## Channel sound URIs

Custom sound per channel requires raw resource URI — verify copyright on bundled sounds.

## Upgrade migration comms

In-app message when migrating channels explains why users should re-check settings — reduces "app broken" reviews after channel split release.
""",
    "android-offline-first-sync-strategy": """

## Tombstones vs hard delete

Server delete should tombstone locally with `deletedAt` for sync propagation — hard delete breaks other device convergence.

## Sync status in app icon badge

Optional badge count of pending outbox — power users trust app when they see pending count drop after connectivity returns.

## Schema migration with outbox

Room migration must not drop outbox table — data loss unacceptable. Version outbox schema separately if needed.
""",
    "android-pending-intent-immutable-patterns": """

## Widget click request codes

AppWidgetProvider update ids should incorporate appWidgetId in requestCode hash — multiple widgets same layout need distinct PendingIntents.

## Task stack builder

`TaskStackBuilder` PendingIntents for back stack parent — each level immutable with unique requestCode per depth.

## PendingIntent.cancel

Cancel obsolete notifications' PendingIntents when conversation deleted — prevents stale tap opening wrong thread after id reuse mistake.
""",
    "android-pending-intent-mutability-flags": """

## Android 13+ backported behavior

Test minSdk 24 device with targetSdk 34 — flags enforced at runtime on older devices when targeting modern SDK.

## Slice and template remnants

If legacy Slice providers remain, audit their PendingIntents — easy miss during migration.

## Lint suppressions

Avoid `@SuppressLint` on PendingIntent without comment linking to security review ticket.
""",
    "android-notification-trampoline-restrictions": """

## ActivityOptions mode

`MODE_BACKGROUND_ACTIVITY_START_ALLOWED` for eligible cases — rarely app-set; understand system grants on notification tap vs explicit start.

## Wear companion notification taps

Watch may use different trampoline path — test phone+watch pair for same notification builder.

## Custom heads-up full screen abuse history

Apps banned for fake incoming call full screen — do not replicate patterns Play now rejects.
""",
    "android-picture-in-picture-compose": """

## Seamless resize disabled

`setSeamlessResizeEnabled(false)` when aspect ratio must hold during PiP transition — video letterbox vs cropped product choice.

## PiP auto-enter denied

User can disable auto-PiP per app in settings — detect and show in-app hint to re-enable for video app category.

## DRM content

Widevine L1 content may disable PiP — handle ExoPlayer error callback with user message not silent failure.
""",
    "android-overlay-permission-security": """

## Accessibility overlay confusion

Malware abuses accessibility over overlays — high-security flows may warn on enabled accessibility services list with care not to stigmatize legitimate users.

## Screen recording overlap

FLAG_SECURE blocks recording but not all overlay classes — combine defenses for high-value flows.

## Play Protect overlay scanners

Some enterprise MDM block overlay globally — app behavior when Settings.canDrawOverlays false for all apps.
""",
    "android-notification-bubbles-api": """

## Bubble dismiss persistence

User dismissing bubble should not re-post bubble on next message without user opt-in — respect bubble suppressed state per conversation.

## Shortcuts sync

ShortcutManager dynamic shortcuts must stay in sync with conversations or bubble metadata stale.

## Launcher differences

Third-party launchers vary bubble support — degrade to standard notification without error.
""",
    "android-notification-inline-replies": """

## Draft reply persistence

Optional: save unsent RemoteInput draft to local store if send fails — user can retry from app.

## End-to-end encryption

Ciphertext in MessagingStyle preview may leak metadata policy — E2E apps often disable inline reply on lock screen.

## Smart reply ML

On-device smart reply suggestions separate feature — do not confuse with RemoteInput path.
""",
    "android-notification-grouping-summary": """

## Badging interaction

Notification dot count may aggregate group — verify OEM launcher behavior for grouped messages badge.

## FCM collapse key alignment

Server collapse key should match client group key namespace — mismatched collapse shows duplicate groups.

## Silent group updates

Marketing batch silent delivery still updates summary without sound — use setSilent true on children.
""",
    "android-notification-wearable-extender": """

## Wear OS version fragmentation

Older watches ignore pages beyond two — cap pages defensively.

## Bridged voice reply

Wear may use voice to fill RemoteInput — same mutable PendingIntent path as phone inline reply.

## Battery impact

Large background images in extender increase bridge transfer cost — compress JPEG quality 80 sufficient for map preview.
""",
    "android-notification-runtime-permission": """

## Exact alarm notification exemption

Do not confuse POST_NOTIFICATIONS with SCHEDULE_EXACT_ALARM — separate permissions separate UX.

## Kids / supervised accounts

Family Link may restrict notifications — parental settings override grant.

## Permission rationale localization

Pre-permission screen strings must localize — grant rates vary by locale when English-only rationale shown to non-English users.
""",
    "android-nfc-hce-payment": """

## Terminal kernel configuration

Some POS kernels require specific PDOL responses — certification lab captures before field pilot.

## Offline payment limits

Network offline stored transactions caps — exceed triggers decline until sync; surface in wallet UI.

## NFC off state

Detect `NfcAdapter.isEnabled` false — deep link to wireless settings before showing tap UI.
""",
    "android-nfc-host-card-emulation": """

## Foreground requirement

Some OEMs require app foreground for HCE non-payment — test Huawei/Samsung background tap behavior.

## Multiple AID routing

Priority order in apduservice.xml when overlapping filters — first match wins.

## Power saving

Battery saver may disable NFC — listener for adapter state disabled with user prompt.
""",
    "android-opengl-es-basics-compose": """

## Context loss recovery

On context loss, reload textures in onSurfaceCreated — keep asset path map in controller to rebuild GPU resources.

## HDR and wide gamut

Display P3 surface optional — match color space to content or colors look washed out on flagship panels.

## Profiling GPU overdraw

Developer option overdraw on mixed Compose+GL screen — Compose overdraw separate from GL clear pass; optimize each layer.
""",
    "android-phone-number-hint-api": """

## eSIM only devices

Hint may list eSIM profile number — validate E.164 normalization before API submit.

## Fraud considerations

Hint number not verified until OTP — rate limit OTP requests per hinted number to prevent enumeration abuse paired with SMS pumping.

## Kids accounts

Family supervised accounts may block Hint — manual entry only path tested.
""",
    "android-play-asset-delivery": """

## Offline-first asset cache

After pack download, copy critical assets to app private storage if you need offline guarantee when Play revokes pack access on uninstall edge cases during development.

## Asset pack size limits

Monitor Play Console size reports — exceeding limits blocks releases; plan split across multiple on-demand packs by level band.

## Delta updates QA

Verify binary patch applies on upgrade from N-2 version — patch bugs show corrupt assets mid-level load.
""",
}


def extract_frontmatter(text: str):
    m = re.match(r"^---\n(.*?)\n---\n\n?(.*)", text, re.DOTALL)
    if not m:
        return None, text
    return m.group(1), m.group(2)


def word_count(text: str) -> int:
    body = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.DOTALL)
    return len(body.split())


def main():
    results = {}
    for path in FILES:
        slug = path.stem
        text = path.read_text()
        fm, body = extract_frontmatter(text)
        if fm is None:
            continue
        wc = word_count(text)
        if wc < 1200 and slug in EXPANSIONS:
            body = body.rstrip() + EXPANSIONS[slug]
            path.write_text(f"---\n{fm}\n---\n\n{body.strip()}\n")
            wc = word_count(path.read_text())
        results[slug] = wc
    for slug, wc in sorted(results.items()):
        flag = "OK" if wc >= 1200 else "SHORT"
        print(f"{wc:5d} {flag} {slug}")


if __name__ == "__main__":
    main()
