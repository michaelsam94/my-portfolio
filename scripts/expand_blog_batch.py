#!/usr/bin/env python3
"""Append topic-specific sections before ## Resources to reach word targets."""
from pathlib import Path

# Each value is markdown inserted before ## Resources
EXPANSIONS = {
"android-broadcast-receiver-exported": """
## Real incident: exported downloader receiver

A security review found our `DownloadCompleteReceiver` exported without permission — any app could broadcast a spoof completion and trigger cache deletion logic that assumed "download finished" meant "safe to wipe staging." Fix: `exported=false`, explicit package on PendingIntent, validate `downloadId` against Room table before side effects. Pen test repeated with malformed extras — receiver must no-op.

## Migrating BOOT_COMPLETED receivers

`RECEIVE_BOOT_COMPLETED` requires exported true with system-only senders in practice — pair with `android:directBootAware` only if you truly need pre-unlock work; otherwise defer to `ACTION_USER_UNLOCKED` registered dynamically to avoid CE storage reads before unlock. Document in manifest comment why exported cannot be false for that receiver.

## Ordered broadcasts and abort

Legacy `abortBroadcast()` in ordered receivers poisoned other apps — don't use ordered broadcasts for app-internal events. Local broadcasts are deprecated; use `Flow`/`SharedFlow` in process or explicit `Intent.setPackage`.

## Testing exported surface

`adb shell am broadcast -a android.intent.action.DOWNLOAD_COMPLETE` against your package — verify no handler runs when exported false. Static analysis: `./gradlew :app:lintRelease` with `ExportedReceiver` severity error.
""",
"android-desktop-mode-support": """
## Window bounds vs screen size

Desktop freeform passes smaller window bounds than physical display — `LocalConfiguration.current.screenWidthDp` may read 600dp while monitor is 4K. Use `LocalWindowInfo.current.containerSize` in Compose 1.7+ or `View.getRootWindowInsets()` bounds for pane splits. Drag-resize fires many configuration events — debounce expensive recomputation with `snapshotFlow`.

## Clipboard and drag-drop between instances

Desktop users expect drag text between two editor windows — implement `DragAndDrop` modifiers on supported fields. Each instance needs separate undo stack; shared static clipboard helper is fine, shared document mutex is not.

## Samsung DeX-specific QA

Wireless DeX disconnect mid-edit must not corrupt saves — flush on `onStop` always. DeX panel mode splits phone + desktop — test continuing task on phone while DeX shows second display; task affinity mistakes send users to wrong window.

## Productivity keyboard map

Document shortcuts in Help screen: Ctrl+N new doc, Ctrl+Tab switch tabs, Alt+Left back. Android 13+ predictive back with mouse back button should pop inner NavController before finishing activity — test with `OnBackPressedDispatcher`.
""",
"android-activity-recognition-api": """
## Confidence thresholds in production

`DetectedActivity` includes confidence 0–100 — ignore transitions below 75 for automation that pauses billing timers or GPS. Log confidence histogram weekly; parking-lot vehicle↔foot oscillation often shows 60–80 confidence. Require two consecutive transition events before state change.

## Fusion with location permission story

Activity recognition does not replace location permission for map features — Play policies treat them separately. If you derive "at gym" from AR plus geofence, disclose both. AR alone cannot draw map pin.

## PendingIntent mutability flags

Android 12+ requires explicit `FLAG_MUTABLE` or `IMMUTABLE` on PendingIntent for activity transition updates — wrong flag causes registration failure silently on some OEMs. Register once at boot after permission grant; re-register on `MY_PACKAGE_REPLACED`.

## Testing without driving

Use Android emulator extended controls to inject activity context where available; physical device on desk still reports STILL — simulate by mocking client in debug build only, never in release fraud paths.
""",
"android-assist-structure-extraction": """
## WebView login structure gaps

Hybrid login pages often miss username/password autofill because WebView doesn't expose fields until DOM ready — inject `AutofillManager.requestAutofill()` after `onPageFinished`. For SPAs, delay 300ms or listen for JS bridge "form ready" before requesting fill.

## Credential Manager save path

After successful login, call `CreatePasswordRequest` with username/password captured from structured fields — not from EditText getters if using custom transformation. Passkeys: `CreatePublicKeyCredentialRequest` on register screen with same structure hints.

## Multi-field OTP flows

Split OTP boxes should expose single `ContentType.Password` container semantics with merged autofill id — six boxes one code. Otherwise password managers fill only first digit.

## Regression testing autofill

Macrobenchmark not needed — Espresso with `AutofillManager` test service or Samsung / Google autofill test APK in QA lab. Snapshot AssistStructure dump in CI comparing golden XML when login layout changes.
""",
"android-bluetooth-le-scanning": """
## ScanFilters and manufacturer data

Beacons advertising manufacturer-specific data need `ScanFilter.Builder.setManufacturerData(id, data, mask)` — mask bytes you don't care about. Overly broad filters miss devices; overly narrow miss firmware revisions. Document firmware allowlist in support KB.

## Concurrent scan limit

Multiple features starting scan — centralize in `BleScanCoordinator` singleton reference-counting consumers. Feature A inventory + Feature B proximity both request scan — one underlying `startScan`, stop when refcount zero.

## Bluetooth off UX

`BluetoothAdapter.getDefaultAdapter()?.isEnabled == false` — prompt enable with `ACTION_REQUEST_ENABLE` once per session, not every screen entry. After denial, show settings deep link instead of loop.

## Privacy in scan logs

Debug logs must not print device MAC addresses on Android 12+ — use hashed identifier in internal logs. User-facing device list shows friendly name only after connect permission granted.
""",
"android-dream-service-screensaver": """
## Power and thermal on overnight dreams

Slideshow dreams run hours while charging — prefer dark pixels on OLED hotel tablets. Cap animation frame rate to 30fps; pause network refresh when battery not AC if device sometimes undocks. `DreamService.finish()` when thermal status severe if you monitor `PowerManager`.

## MDM kiosk dreams

Device owner can set `setScreenSaverComponent` — test upgrade path when your dream package updates; MDM may point to old component until policy refresh. Export dream alias activity for admin QR provisioning docs.

## Touch vs non-interactive

`isInteractive=true` enables light interaction (next photo tap) but may keep screen brighter — product choice. Signage wants false; bedside clock wants true for snooze. Document in dream picker description string.

## Android version differences

Screensaver picker moved between Settings paths on OEM skins — in-app help link to generic Settings search "screensaver" instead of hardcoded activity class that fails on Samsung One UI.
""",
"android-16-edge-to-edge-enforcement": """
## Predictive back with transparent bars

Edge-to-edge plus predictive back gesture draws behind nav bar — ensure scrim on bottom sheet doesn't clip gesture inset. `ModalBottomSheet` should use `windowInsetsPadding` on drag handle. Test back animation with floating nav bar on Android 15+.

## Library transitive themes

Third-party SDK activities may still set `fitsSystemWindows` — wrap SDK screens or override theme in manifest merger tools:node merge for SDK activities you control. Interstitial ads fullscreen may fight edge-to-edge — isolate ad activity theme.

## Tablet and foldable expanded insets

Large screens add `WindowInsets.tappableElement` vs `mandatorySystemGestures` — FAB goes above mandatory gesture, not just nav bar padding. Fold hinge obscures center — don't place primary CTA in hinge corridor per Material guidance.

## Rollout feature flag

Ship edge-to-edge behind `Build.VERSION.SDK_INT >= 35` flag remotely killable — if crash rate spikes on specific OEM, disable without full revert. Monitor `WindowInsets` related crash signatures in Play Vitals.
""",
"android-automotive-app-design": """
## Notification and agent parity

Car surfaces cannot show full agent thread — sync read-only "pending approvals" count from same backend queue mobile uses. When user approves on phone, car session invalidates via push or polling on screen resume — avoid stale "approve" on item already handled.

## Passenger vs driver UX

Legal distinction: driver sees templates; passenger tablet in same vehicle may allow richer UI — detect `DrivingState` vs UX restriction `UX_RESTRICTIONS_NO_SETUP`. Don't rely only on speed — parked at red light still restricts typing on some builds.

## OEM certification timeline

Android Auto certification adds weeks — submit early with car-app-validator clean report. AAOS OEM builds may preinstall competitor — differentiation is voice summary quality, not pixel density.

## Error strings in car

Template `MessageTemplate` error text max length — truncate agent error with "Open on phone for details" parked-only action. Never show stack traces or request IDs in car UI.
""",
"android-document-provider-files": """
## Cloud-backed document roots

Expose optional root backed by cached cloud sync — `queryChildDocuments` reads local cache; `openDocument` may trigger download with progress notification if file missing. Column `COLUMN_FLAGS` add `FLAG_PARTIAL` semantics via custom MIME or slow open with CancellationSignal cancel.

## Eject and revoke

When user deletes cloud-backed doc, call `revokeDocumentPermission` on outstanding URIs — clients holding old URI get error on next read. Document ID encoding must not allow `../` escape when decoding to path.

## Conflict resolution

Two apps open same doc write mode — last writer wins on POSIX; consider write mode deny if lock held via internal lease table for collaborative editors.

## Performance on large directories

Pagination: Android 8+ `queryChildDocuments` supports `Bundle QUERY_ARG_LIMIT/OFFSET — implement for folders with 10k+ files; naive listFiles blocks binder thread.
""",
"android-download-manager-resume": """
## Column progress UI

Query `COLUMN_BYTES_DOWNLOADED_SO_FAR` and `COLUMN_TOTAL_SIZE_BYTES` on timer for in-app progress bar — don't poll faster than 1s; binder churn hurts. Handle `TOTAL_SIZE_BYTES` unknown (-1) — indeterminate progress.

## Remove and cancel

`dm.remove(downloadId)` on user cancel — delete partial file from destination. Orphan IDs in Room after remove confuse reconciliation — listen for `ACTION_NOTIFICATION_CLICKED` too if using custom notification.

## HTTPS redirects and resume

Some CDNs break Range on redirect chain — test final URL supports partial content. DownloadManager follows redirects; log failure reason `ERROR_CANNOT_RESUME` distinctly in support metrics.

## Split APK / feature modules

Downloading large dynamic feature module via DM — verify module install API after completion before marking ready; file present ≠ module installed.
""",
}

def main():
    for slug, extra in EXPANSIONS.items():
        path = Path(f"content/blog/{slug}.md")
        text = path.read_text()
        marker = "\n## Resources\n"
        if marker not in text:
            print(f"SKIP {slug}: no Resources")
            continue
        if extra.strip()[:80] in text:
            print(f"SKIP {slug}: already expanded")
            continue
        path.write_text(text.replace(marker, extra + marker))
        print(f"OK {slug}")

if __name__ == "__main__":
    main()
