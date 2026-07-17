#!/usr/bin/env python3
"""Rewrite mission 46 slugs using humanize_batch_s quality generator."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

spec = importlib.util.spec_from_file_location("hb_s", ROOT / "scripts" / "humanize_batch_s.py")
hb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hb)

BLOG = ROOT / "content" / "blog"
TARGET = 1200

AGENT_SLUGS = [
    "agent-state-store-rocksdb", "agent-status-page-communication", "agent-step-functions-saga-retries",
    "agent-step-up-authentication-risk", "agent-storybook-visual-regression", "agent-stream-processing-windowing",
    "agent-subresource-integrity-hashes", "agent-subscription-billing-dunning", "agent-summarization-map-reduce",
    "agent-synonym-graph-expansion", "agent-synthetic-media-labeling", "agent-table-bloat-vacuum-tuning",
    "agent-tax-calculation-vat-gst", "agent-timeseries-anomaly-alerting", "agent-tls-certificate-pinning-mobile",
    "agent-toil-reduction-automation", "agent-token-budget-compression", "agent-tokenization-payment-vault",
    "agent-toxicity-classifier-threshold", "agent-translation-memory-cat-tools", "agent-two-tower-retrieval",
    "agent-usage-metering-aggregation", "agent-vector-index-rebuild", "agent-view-transitions-spa-mp",
    "agent-vulnerability-triage-sla", "agent-waf-bot-management", "agent-wallet-pass-provisioning",
    "agent-watermark-late-data", "agent-watermarking-outputs", "agent-webhook-signature-verification",
    "agent-workflow-idempotency-keys", "agent-workload-identity-federation", "agent-write-through-cache-consistency",
]

ANDROID_SLUGS = [
    "android-16-edge-to-edge-enforcement", "android-activity-recognition-api", "android-assist-structure-extraction",
    "android-automotive-app-design", "android-background-location-policy", "android-bluetooth-le-scanning",
    "android-broadcast-receiver-exported", "android-chromeos-app-optimization", "android-desktop-mode-support",
    "android-display-cutout-notches", "android-document-provider-files", "android-download-manager-resume",
    "android-dream-service-screensaver",
]

ANDROID_TOPICS = {
    "android-16-edge-to-edge-enforcement": (
        "Platform", "16-edge-to-edge-enforcement", "Android 16 Edge-to-Edge Enforcement",
        "Mandatory edge-to-edge on Android 16 targets: enableEdgeToEdge, WindowInsets in Compose, IME, and cutout handling.",
        "Android|UI|Compose|Platform", "android 16 edge to edge, WindowInsets Compose, enableEdgeToEdge",
        "After targeting SDK 36, the toolbar drew under the status bar and the FAB sat in the gesture inset — Play pre-launch flagged inset misuse on twelve devices.",
        "edge-to-edge enforcement", "Before shipping targetSdk 36 without inset refactors.",
        "Calling enableEdgeToEdge() without padding LazyColumn, topBar, and IME — fixed dp padding is not a strategy.",
    ),
    "android-activity-recognition-api": (
        "Sensors", "activity-recognition-api", "Activity Recognition API on Android",
        "Detect walking, driving, and still states with Activity Transition API, battery-aware sampling, and Play policy disclosures.",
        "Android|Sensors|Location|Privacy", "activity recognition API, ActivityTransition, ACTIVITY_RECOGNITION permission",
        "Auto-pausing workouts when users drove home worked — until parking-lot oscillation toggled vehicle/foot ten times in five minutes.",
        "Activity Transition API", "When automation depends on semantic activity not raw accelerometer.",
        "Polling activity updates every few seconds instead of transition callbacks.",
    ),
    "android-assist-structure-extraction": (
        "Autofill", "assist-structure-extraction", "Assist Structure Extraction for Android Autofill",
        "Publish AssistStructure from Compose and custom views so password managers and Credential Manager can map login fields.",
        "Android|Autofill|Accessibility|Compose", "AssistStructure autofill, Compose contentType, onProvideAutofillStructure",
        "Bitwarden would not offer save on our Compose login — AssistStructure showed anonymous nodes with no username hint.",
        "AssistStructure and autofill hints", "When custom login UI blocks credential managers.",
        "Relying on visual TextField without semantics contentType or autofill hints.",
    ),
    "android-automotive-app-design": (
        "Automotive", "automotive-app-design", "Android Automotive App Design Patterns",
        "Car App Library templates, driving-state UX restrictions, and voice-first agent summaries for AAOS and Android Auto.",
        "Android|Automotive|UX|Car App Library", "android automotive app, Car App Library, driving state UX",
        "Porting phone chat UI to Android Auto failed review — free-form text input while driving is not negotiable.",
        "Car App Library templates", "Before shipping agent UIs to projected or embedded automotive.",
        "RecyclerView chat threads instead of ListTemplate and MessageTemplate surfaces.",
    ),
    "android-background-location-policy": (
        "Location", "background-location-policy", "Android Background Location Policy Compliance",
        "ACCESS_BACKGROUND_LOCATION ladder, foreground service types, Play declarations, and prominent disclosure UX.",
        "Android|Location|Privacy|Policy", "background location policy, ACCESS_BACKGROUND_LOCATION Play, FGS location type",
        "Play rejected v2.3 for requesting background location before users understood why — the video showed a map, not background behavior.",
        "background location compliance", "Before any feature needs location when UI is not visible.",
        "Requesting background location on first launch alongside fine location.",
    ),
    "android-bluetooth-le-scanning": (
        "Bluetooth", "bluetooth-le-scanning", "Bluetooth LE Scanning on Android",
        "ScanSettings batching, BLUETOOTH_SCAN permissions, PendingIntent scans, and background throttle limits.",
        "Android|Bluetooth|BLE|Hardware", "BLE scanning Android, ScanFilter, BLUETOOTH_SCAN neverForLocation",
        "Warehouse app scanned beacons every second in LOW_LATENCY mode in background — battery reports killed adoption.",
        "BLE scan lifecycle", "When discovering peripherals without burning radio budget.",
        "Broad scans without filters and without stopping on onStop.",
    ),
    "android-broadcast-receiver-exported": (
        "Security", "broadcast-receiver-exported", "Exported BroadcastReceivers on Android 12+",
        "android:exported requirements, RECEIVER_NOT_EXPORTED, and replacing implicit CONNECTIVITY_CHANGE receivers.",
        "Android|Security|BroadcastReceiver|Manifest", "exported broadcast receiver Android 12, RECEIVER_NOT_EXPORTED",
        "Manifest merger failed on API 31 — three receivers lacked exported; one exported receiver wiped cache on any broadcast.",
        "explicit exported flags", "When targeting API 31+ with manifest receivers.",
        "exported=true on internal-only receivers without permission protection.",
    ),
    "android-chromeos-app-optimization": (
        "ChromeOS", "chromeos-app-optimization", "ChromeOS Android App Optimization",
        "Resizable windows, keyboard and mouse hover, WindowSizeClass layouts, and ARC++ performance tuning.",
        "Android|ChromeOS|Large Screens|Optimization", "ChromeOS android optimization, resizable activity, ARC++",
        "Our app letterboxed to phone width on a 14-inch Chromebook — users assumed it was broken.",
        "ChromeOS windowing and input", "Before enabling Chromebook distribution on Play.",
        "Portrait lock and touch-only gestures without keyboard alternatives.",
    ),
    "android-desktop-mode-support": (
        "Desktop", "desktop-mode-support", "Desktop Mode Support on Android",
        "Freeform windows, multi-instance documents, DeX and Android 15 desktop mode lifecycle and input expectations.",
        "Android|Desktop|Large Screens|Productivity", "android desktop mode, DeX multi instance, freeform window",
        "Two side-by-side note instances crashed because Repository.currentDocument was a singleton.",
        "multi-instance and resize", "When users run productivity apps in desktop/freeform mode.",
        "Static singletons shared across multiple task instances.",
    ),
    "android-display-cutout-notches": (
        "UI", "display-cutout-notches", "Display Cutout and Notch Handling on Android",
        "LAYOUT_IN_DISPLAY_CUTOUT_MODE, WindowInsets.displayCutout, and keeping controls out of punch-hole overlap.",
        "Android|UI|Display|Compose", "display cutout notches, WindowInsets displayCutout, shortEdges",
        "Exit from fullscreen video left the toolbar under the punch-hole because we hardcoded 24dp top padding.",
        "displayCutout insets", "On notched devices with edge-to-edge content.",
        "fitsSystemWindows and magic statusBarHeight dp from Stack Overflow.",
    ),
    "android-document-provider-files": (
        "Storage", "document-provider-files", "DocumentProvider for Files on Android",
        "DocumentsProvider SAF integration, stable document IDs, openDocument modes, and scoped storage compliance.",
        "Android|Storage|SAF|Files", "DocumentsProvider Android, Storage Access Framework, openDocument",
        "Users could not attach app files in Gmail — FileProvider URIs broke after cache clear; DocumentsProvider fixes picker persistence.",
        "DocumentsProvider implementation", "When app files should appear in system document pickers.",
        "Unstable document IDs and path traversal in createDocument handlers.",
    ),
    "android-download-manager-resume": (
        "Networking", "download-manager-resume", "DownloadManager Resume and Reliable Downloads on Android",
        "DownloadManager enqueue, Range resume, completion receivers, and Doze-aware scheduling.",
        "Android|Networking|Downloads|Storage", "DownloadManager resume, ACTION_DOWNLOAD_COMPLETE, Range requests",
        "Home-grown OkHttp download died in Doze at 87% — no resume, users re-downloaded 2GB.",
        "DownloadManager with Range support", "For large user-visible downloads and offline packs.",
        "Ignoring ERROR_CANNOT_RESUME when CDN drops Range support.",
    ),
    "android-dream-service-screensaver": (
        "Automotive", "dream-service-screensaver", "DreamService Screensavers on Android",
        "DreamService for docked tablets and signage: isInteractive, burn-in mitigation, and Compose in dreams.",
        "Android|DreamService|TV|Kiosk", "DreamService screensaver, Daydream API, dock mode",
        "Hotel tablets needed ambient slideshow when docked — Activity back stack was the wrong tool.",
        "DreamService lifecycle", "For kiosk and bedside docked experiences.",
        "Always-on animations without OLED burn-in mitigation.",
    ),
}


def meta_from_tuple(t):
    cat, suffix, title, description, tags, keywords, hook, tech, when, mistake = t
    return {
        "category": cat, "title": title, "description": description,
        "tags": tags, "keywords": keywords, "hook": hook, "tech": tech,
        "when": when, "mistake": mistake,
    }


def write_agent(slug: str) -> int:
    llm_slug = "llm-" + slug[len("agent-") :]
    meta_tuple = hb.TOPIC_MAP.get(llm_slug)
    if not meta_tuple:
        raise SystemExit(f"missing llm topic for {slug}")
    meta = meta_from_tuple(meta_tuple)
    path = BLOG / f"{slug}.md"
    old_pub = None
    if path.exists():
        _, _, old_pub = hb.parse_frontmatter(path.read_text())
    content = hb.build_frontmatter(slug, meta, old_pub) + "\n" + hb.build_body(llm_slug, meta)
    path.write_text(content)
    return hb.wc(content)


def write_android(slug: str) -> int:
    meta_tuple = ANDROID_TOPICS[slug]
    meta = meta_from_tuple(meta_tuple)
    path = BLOG / f"{slug}.md"
    old_pub = None
    if path.exists():
        _, _, old_pub = hb.parse_frontmatter(path.read_text())
    # build_body uses slug for generic depth when no dedicated block
    content = hb.build_frontmatter(slug, meta, old_pub) + "\n" + hb.build_body(slug, meta)
    path.write_text(content)
    return hb.wc(content)


def main():
    under = []
    for slug in AGENT_SLUGS:
        w = write_agent(slug)
        print(f"agent {slug}: {w}")
        if w < TARGET:
            under.append((slug, w))
    for slug in ANDROID_SLUGS:
        w = write_android(slug)
        print(f"android {slug}: {w}")
        if w < TARGET:
            under.append((slug, w))
    print(f"TOTAL {len(AGENT_SLUGS)+len(ANDROID_SLUGS)} under {TARGET}: {len(under)}")
    for s, w in under:
        print(f"  {s}:{w}")


if __name__ == "__main__":
    main()
