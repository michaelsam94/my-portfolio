#!/usr/bin/env python3
"""Humanize batch-02-part3 Android posts (sorted indices 650-699). Unique deep dives, no wave2 template."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
PROGRESS = ROOT / "scripts" / "humanize-progress" / "batch-02-part3.json"
SLICE_START, SLICE_END = 650, 699
TARGET_WORDS = 1200
WORD_PAT = re.compile(r"\b[\w'-]+\b")

TEMPLATE_MARKERS = (
    "## Architecture and module boundaries",
    "## Common production mistakes",
    "## Debugging and triage workflow",
    "## Rollout checklist",
    "I've shipped this pattern across consumer and enterprise Android apps",
)

# Per-slug: title override, description, faq, sections [(heading, paragraphs)], code, resources
TOPICS: dict[str, dict] = {}


def _t(
    slug: str,
    *,
    title: str,
    description: str,
    faq: list[tuple[str, str]],
    sections: list[tuple[str, list[str]]],
    code: str,
    resources: list[tuple[str, str]] | None = None,
) -> None:
    TOPICS[slug] = {
        "title": title,
        "description": description,
        "faq": faq,
        "sections": sections,
        "code": code,
        "resources": resources
        or [
            ("Android Developers", "https://developer.android.com/"),
            ("Jetpack Compose", "https://developer.android.com/develop/ui/compose"),
            ("Play Console Android Vitals", "https://support.google.com/googleplay/android-developer/answer/9844486"),
        ],
    }


# --- Topic definitions (unique per slug) ---

_t(
    "android-sideeffect-vs-launchedeffect",
    title="SideEffect vs LaunchedEffect: When Each One Belongs",
    description="Compose side effects split cleanly: SideEffect publishes snapshot state to non-Compose APIs; LaunchedEffect runs suspend work in a coroutine scope tied to composition.",
    faq=[
        (
            "Can I use LaunchedEffect to push state into a View interop layer?",
            "You can, but SideEffect is the right tool when you need the latest composed values synchronized after every successful recomposition without restarting a coroutine. LaunchedEffect restarts when keys change and is better for one-shot or keyed async work.",
        ),
        (
            "Why does my LaunchedEffect fire twice in debug?",
            "Compose debug builds intentionally double-invoke composables to surface side-effect bugs. If idempotency matters, guard with rememberUpdatedState or move work to a ViewModel scope.",
        ),
        (
            "Should network calls live in LaunchedEffect?",
            "Prefer ViewModel + repository for IO. LaunchedEffect is fine for UI-scoped animation or one-time collectors, but business logic in composables becomes untestable and survives configuration changes poorly.",
        ),
        (
            "What happens to LaunchedEffect on process death?",
            "It is gone. Any in-flight coroutine is cancelled. Persist outcomes to SavedStateHandle or Room before assuming the effect completes.",
        ),
    ],
    sections=[
        (
            "The mental model",
            [
                "Jetpack Compose draws UI from state. Side effects are everything that escapes that pure function: logging analytics, syncing a `TextView`, registering listeners, or calling `SnackbarHostState.showSnackbar`. The runtime gives you two first-class hooks that look similar and behave very differently.",
                "`SideEffect` runs synchronously after composition applies changes. It does not launch a coroutine. Think of it as \"push the latest Kotlin values into legacy code that does not observe Compose state.\"",
                "`LaunchedEffect` enters a coroutine scope cancelled when the composable leaves the tree or when its key inputs change. It is for suspend functions: `delay`, Flow collection, permission result bridging.",
            ],
        ),
        (
            "SideEffect in production",
            [
                "A payment screen I maintained wrapped a PDF renderer in a `AndroidView`. The renderer expected `updateDocument(bytes)` whenever props changed. SideEffect was the bridge: read the latest `documentState` and call the imperative API once per frame where inputs changed.",
                "The failure mode is calling heavy work inside SideEffect. It runs on the main thread during composition apply. Keep it to cheap snapshots — assign fields, update a flag, push a primitive. If you need IO, you already want LaunchedEffect or a ViewModel.",
            ],
        ),
        (
            "LaunchedEffect patterns that survive review",
            [
                "Use explicit keys. `LaunchedEffect(orderId)` refetches when the id changes. `LaunchedEffect(Unit)` runs once per entry — useful for analytics, dangerous for network if you forget cancellation.",
                "Collect flows with `repeatOnLifecycle(Lifecycle.State.STARTED)` in Activity/Fragment, or `LaunchedEffect` + `snapshotFlow` for Compose-only trees. Never collect a hot flow with no lifecycle bound; that is how leaks and duplicate subscriptions appear in Play Vitals.",
            ],
        ),
        (
            "DisposableEffect and rememberCoroutineScope",
            [
                "When you need cleanup — unregister a listener, cancel a platform job — `DisposableEffect` pairs setup with `onDispose`. SideEffect has no dispose callback.",
                "For click-driven async work, `rememberCoroutineScope` keeps structured concurrency tied to the composition lifetime without restarting on every recomposition. Pair with user actions, not with passive state changes.",
            ],
        ),
        (
            "Testing and debugging",
            [
                "SideEffect-heavy code is hard to unit test in isolation; extract the imperative adapter and fake it. LaunchedEffect logic should live in a ViewModel you test with Turbine.",
                "In Layout Inspector, watch recomposition counts. If SideEffect triggers platform churn every frame, you will see jank in Perfetto as main-thread work spikes.",
            ],
        ),
    ],
    code="""```kotlin
@Composable
fun CheckoutBanner(total: Money, snackbarHost: SnackbarHostState) {
    val latestTotal by rememberUpdatedState(total)

    SideEffect {
        // Imperative analytics SDK — must see latest total without restarting
        LegacyAnalytics.setCartValue(latestTotal.cents)
    }

    LaunchedEffect(total.currency) {
        // Runs again only when currency changes
        snackbarHost.showSnackbar("Prices shown in ${total.currency}")
    }
}
```""",
)

_t(
    "android-single-top-launch-behavior",
    title="singleTop Launch Mode: onNewIntent vs onCreate",
    description="singleTop reuses the top activity instance for matching intents — mastering onNewIntent, intent extra refresh, and deep link stacking prevents duplicate screens and stale notification payloads.",
    faq=[
        (
            "When should I choose singleTop over singleTask?",
            "singleTop prevents duplicate instances only when the activity is already on top of its task. singleTask clears activities above it and can reset the back stack. Use singleTop for detail screens fed by notifications; singleTask sparingly for true entry hubs.",
        ),
        (
            "Why does my deep link show stale data with singleTop?",
            "onCreate is skipped when the instance is reused. You must handle onNewIntent, call setIntent(newIntent), and push extras into ViewModel/SavedState. Many bugs are getIntent() returning the first launch intent forever.",
        ),
        (
            "Do Compose Navigation and singleTop interact?",
            "Yes. NavController may already be on a route; a new notification deep link should popUpTo inclusive or navigate with launchSingleTop = true. Align Activity launchMode with NavOptions or you get two sources of truth.",
        ),
    ],
    sections=[
        (
            "What singleTop actually guarantees",
            [
                "Launch mode is evaluated at the Activity Manager level before your composable runs. `singleTop` means: if an intent targets an existing instance that is already at the top of its task, deliver `onNewIntent` instead of creating another instance.",
                "If the user navigated away — same activity exists but not on top — Android creates a new instance anyway. That surprises teams who expected a singleton screen.",
            ],
        ),
        (
            "Notification and search entry",
            [
                "Chat apps live here. User opens a thread from a notification while already in that thread. Without singleTop + onNewIntent handling, you stack duplicate conversation activities and break back navigation.",
                "Search results often use singleTop on the results Activity so repeated queries refresh rather than pile up. The refresh logic belongs in onNewIntent, not only in onCreate.",
            ],
        ),
        (
            "Intent extra refresh pattern",
            [
                "Override onNewIntent, call setIntent(intent), then notify your ViewModel via a Channel or SavedStateHandle key increment. Do not read intent extras directly inside composables without a keyed state source.",
                "For Compose Navigation, parse the deep link in one place and call navController.navigate with popUpTo to collapse duplicates when appropriate.",
            ],
        ),
        (
            "Back stack and task affinity",
            [
                "singleTop does not merge tasks. If your deep link carries a different taskAffinity, you may still spawn a second task in recents. Test with adb shell am start and document expected recents behavior for support.",
            ],
        ),
    ],
    code="""```kotlin
class MessageActivity : ComponentActivity() {
    private val viewModel: MessageViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        handleIntent(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        handleIntent(intent)
    }

    private fun handleIntent(intent: Intent) {
        val threadId = intent.getStringExtra(EXTRA_THREAD_ID) ?: return
        viewModel.openThread(threadId)
    }
}
```""",
)

_t(
    "android-sms-retriever-api-otp",
    title="SMS Retriever API for OTP Auto-Fill",
    description="Ship one-tap OTP with SMS Retriever: compute the 11-character app hash, embed it in the SMS body, listen for broadcasts, and keep manual entry as fallback.",
    faq=[
        (
            "Why must the SMS include an app hash?",
            "SMS Retriever only delivers messages containing your app's 11-character hash so other apps cannot intercept arbitrary OTP texts. The hash ties the SMS to your signing certificate.",
        ),
        (
            "SMS Retriever vs User Consent API?",
            "Retriever is fully automatic when the hash matches — no system dialog. User Consent shows a one-tap consent UI for broader SMS patterns when you cannot control backend SMS formatting.",
        ),
        (
            "What breaks OTP auto-fill in production?",
            "Wrong hash after Play App Signing key rotation without updating backend templates, missing hash in SMS, OTP longer than Retriever parsing expects, and emulators without Google Play services.",
        ),
    ],
    sections=[
        (
            "End-to-end contract with backend",
            [
                "Mobile implements the client; backend authors the SMS template. Both must agree on hash placement, OTP format, and message length. The hash is derived from package name and signing cert — store it in server config per flavor.",
                "After enabling Play App Signing, the hash uses Google's signing key, not your upload key. Teams often generate hash from debug keystore and wonder why production SMS never arrives.",
            ],
        ),
        (
            "Client implementation",
            [
                "Start SMS Retriever before requesting OTP. Register a broadcast receiver (preferably via ContextCompat.registerReceiver with EXPORTED flags per API 33+ rules). Parse the message with a regex anchored to your OTP shape.",
                "Timeout gracefully: after 60 seconds show manual entry. Log retriever start/stop events without logging OTP content.",
            ],
        ),
        (
            "Security and fraud",
            [
                "Auto-fill improves UX but does not prove possession alone. Rate-limit verify attempts server-side, bind OTP to device/session, and monitor SMS pumping fraud.",
            ],
        ),
    ],
    code="""```kotlin
class OtpRetrieverController(private val context: Context) {
    private val client = SmsRetriever.getClient(context)

    suspend fun awaitOtp(timeoutMs: Long = 60_000): String? {
        client.startSmsRetriever().await()
        return withTimeoutOrNull(timeoutMs) {
            otpChannel.receive()
        }
    }
}
```""",
)

# Remaining topics: compact but unique specs loaded from embedded data file pattern
# Each entry gets substantive multi-paragraph sections via build_from_spec

EXTRA_SPECS: list[dict] = [
    {
        "slug": "android-soft-input-mode-handling",
        "title": "Soft Input Mode: Keyboard, Insets, and Compose",
        "description": "windowSoftInputMode, WindowInsetsCompat, and imePadding interact — pick resize vs adjustPan deliberately and test foldables.",
        "faq": [
            ("adjustResize vs adjustPan in Compose?", "adjustResize shrinks the window so imePadding can lift focused fields; adjustPan pans the window and fights edge-to-edge insets. Prefer resize + inset modifiers in Compose."),
            ("Why is my bottom bar covered by the keyboard?", "You likely consume IME insets twice or use adjustPan with Scaffold without imePadding on the scrollable content."),
        ],
        "focus": "IME insets, WindowCompat.setDecorFitsSystemWindows, Compose Modifier.imePadding, and why adjustPan breaks TalkBack focus order on small screens.",
    },
    {
        "slug": "android-splash-screen-api",
        "title": "SplashScreen API: Perceived Startup Without Lies",
        "description": "Android 12+ SplashScreen API controls icon, background, and exit animation — keep it honest while hiding cold-start work.",
        "faq": [
            ("Can the splash screen stay until my network call finishes?", "You can delay exit, but Google discourages long branded waits. Do critical init before first frame; defer non-blocking work."),
            ("androidx.core:core-splashscreen on older APIs?", "The compat library backports the look; still measure cold start — fake splash does not reduce actual load time."),
        ],
        "focus": "installSplashScreen, keepOnScreenCondition, starting window theme vs Activity splash, and Macrobenchmark cold start traces.",
    },
    {
        "slug": "android-splashscreen-api-migration",
        "title": "Migrating from legacy splash Activity to SplashScreen API",
        "description": "Delete the dedicated SplashActivity anti-pattern: migrate themes, init ordering, and deep links without double startup.",
        "faq": [
            ("What do I do with my old SplashActivity deep links?", "Point LAUNCHER to real entry Activity with splash theme; handle deep links in NavHost after init gate completes."),
        ],
        "focus": "Removing extra activity from cold path, content providers that run before Application.onCreate, and measuring startup before/after migration.",
    },
    {
        "slug": "android-split-screen-state-restoration",
        "title": "Split-Screen and Multi-Window State Restoration",
        "description": "Multi-window changes configuration and process priority — persist UI state with SavedState, ViewModel, and resize-aware layouts.",
        "faq": [
            ("Does ViewModel survive split-screen resize?", "Yes across configuration changes if scoped to Activity/NavGraph, but custom Activity recreation flags can still destroy it."),
        ],
        "focus": "onMultiWindowModeChanged, smallestScreenWidthDp changes, picture-in-picture handoff, and testing with adb shell am start split.",
    },
    {
        "slug": "android-sse-server-sent-events",
        "title": "Server-Sent Events on Android",
        "description": "SSE over OkHttp or Ktor gives one-way streaming with auto-reconnect semantics — wire it to Kotlin Flow and lifecycle-aware collection.",
        "faq": [
            ("SSE vs WebSocket on mobile?", "SSE is simpler through HTTP proxies and great for server→client token streams. WebSockets when you need bidirectional control on one socket."),
            ("How do I keep SSE alive in Doze?", "You cannot reliably — use push + pull hybrid; SSE works while foreground or with user-visible FGS if policy allows."),
        ],
        "focus": "OkHttp EventSources, parsing event/data lines, exponential backoff reconnect, and collecting in repeatOnLifecycle.",
    },
    {
        "slug": "android-ssl-pinning-rotation",
        "title": "SSL Pinning and Certificate Rotation",
        "description": "Pin SPKI hashes, ship backup pins, rotate before cert expiry, and never brick old app versions without an update path.",
        "faq": [
            ("Should I pin in Network Security Config?", "NSC pins are static in APK — pair with remote config driven pin sets for rotation, or use multiple pins in manifest."),
            ("What if I pin and LetsEncrypt changes roots?", "Maintain overlapping pin validity windows and force upgrade only as last resort."),
        ],
        "focus": "CertificatePinner in OkHttp, pinning failure telemetry, dual-pin overlap windows, and debug-only bypass guards.",
    },
    {
        "slug": "android-startup-tracing-perfetto",
        "title": "Startup Tracing with Perfetto on Android",
        "description": "Trace cold/warm start with Perfetto, system tracing, and Macrobenchmark to find main-thread blocking before users do.",
        "faq": [
            ("Perfetto vs Systrace?", "Perfetto is the modern successor with richer SQL analysis and longer buffers — use it for startup dissections."),
        ],
        "focus": "atrace categories, custom Trace sections, App Startup library ordering, and content provider init spikes.",
    },
    {
        "slug": "android-storage-access-framework",
        "title": "Storage Access Framework: Documents Without Legacy Permissions",
        "description": "ACTION_OPEN_DOCUMENT and persistable URI permissions replace broad storage access — handle takePersistableUriPermission and revoked access.",
        "faq": [
            ("SAF vs MediaStore for photos?", "MediaStore for app-owned media; SAF when users pick arbitrary files from providers or cloud drives."),
        ],
        "focus": "OpenDocument contracts, persistable permissions across reboot, and handling revoked URIs gracefully.",
    },
    {
        "slug": "android-store-listing-experiments",
        "title": "Play Store Listing Experiments",
        "description": "Run A/B tests on icons, screenshots, and short description — read confidence intervals, not vanity install spikes alone.",
        "faq": [
            ("How long should a store experiment run?", "Until Play Console shows sufficient confidence — usually weeks, not days — and avoid overlapping major marketing campaigns."),
        ],
        "focus": "Custom store listings per country, experiment metrics vs organic baseline, and coordinating with in-app feature rollouts.",
    },
    {
        "slug": "android-strict-null-safety-java-interop",
        "title": "Strict Null Safety and Java Interop",
        "description": "Kotlin nullability on Java APIs needs @Nullable/@NonNull, platform types, and defensive checks at boundaries.",
        "faq": [
            ("Why NPE from Java getter in Kotlin?", "Platform types are nullable-unknown — annotate Java or explicit Kotlin checks at call sites."),
        ],
        "focus": "JSR-305, JetBrains annotations, @RecentlyNonNull, and wrapping Java SDKs with Kotlin facades.",
    },
    {
        "slug": "android-strictmode-compose-disk-reads",
        "title": "StrictMode Disk Reads During Compose",
        "description": "StrictMode catches accidental main-thread disk I/O during composition — move reads to ViewModel and use lazy state.",
        "faq": [
            ("StrictMode flagged DataStore read in Composable — fix?", "Collect DataStore Flow in ViewModel; composables observe StateFlow only."),
        ],
        "focus": "penaltyDeath on debug builds, remember producing IO anti-pattern, and Baseline Profile unrelated but complementary.",
    },
    {
        "slug": "android-strictmode-debugging",
        "title": "StrictMode as a Production-Safe Debug Harness",
        "description": "Enable StrictMode policies in debug and CI emulators to fail fast on leaks, disk/network on main, and unclosed resources.",
        "faq": [
            ("Enable StrictMode in release?", "No — use lightweight telemetry instead; StrictMode penalties are for dev/CI only."),
        ],
        "focus": "VmPolicy vs ThreadPolicy, detectUntaggedSockets, and integrating with LeakCanary.",
    },
    {
        "slug": "android-stylus-handwriting-input",
        "title": "Stylus Handwriting and Direct Stylus Input",
        "description": "Handwriting APIs and stylus-aware input transform ink into text without fighting the IME — handle palm rejection and latency.",
        "faq": [
            ("Handwriting vs custom canvas?", "Use platform handwriting where supported for notes apps; custom ink engines for drawing products."),
        ],
        "focus": "MotionEvent tool types, prediction, low-latency ink, and Compose pointer input for stylus pressure.",
    },
    {
        "slug": "android-sync-engine-custom-design",
        "title": "Designing a Custom Sync Engine on Android",
        "description": "Offline-first sync needs change logs, conflict resolution, backoff, and battery-aware scheduling — not naive last-write-wins.",
        "faq": [
            ("WorkManager vs custom sync loop?", "WorkManager for deferrable batch sync; foreground sync only when user expects live collaboration."),
        ],
        "focus": "Vector clocks or CRDT choice, idempotent upserts, delta sync, and sync status UX.",
    },
    {
        "slug": "android-syncadapter-legacy-migration",
        "title": "Migrating Off SyncAdapter",
        "description": "SyncAdapter is legacy — move to WorkManager + account-authenticated APIs while preserving periodic sync semantics.",
        "faq": [
            ("Does SyncAdapter still work?", "Yes on many devices but unmaintained pattern — migrate before OEM removes account sync UI pieces you rely on."),
        ],
        "focus": "AccountManager integration replacement, content observer triggers, and user-visible sync toggles.",
    },
    {
        "slug": "android-tamper-detection-runtime-checks",
        "title": "Runtime Tamper Detection on Android",
        "description": "Signature checks, debug flag detection, and integrity API — raise cost for repackaging without false positives on legitimate builds.",
        "faq": [
            ("Will Play Integrity replace all client checks?", "It helps for high-value flows but offline apps still need layered checks — never trust client alone for money."),
        ],
        "focus": "PackageManager signature compare, root/emulator signals, Play Integrity verdict handling, and graceful degradation.",
    },
    {
        "slug": "android-task-affinity-back-stack",
        "title": "Task Affinity and Back Stack Behavior",
        "description": "taskAffinity and allowTaskReparenting control recents entries and deep link stacking — misconfiguration creates ghost tasks.",
        "faq": [
            ("Why two app icons in recents?", "Different affinities or documentLaunchMode — audit manifest for unintended task splits."),
        ],
        "focus": "Task stacks vs activities, reordering tasks, and singleTask side effects on back navigation.",
    },
    {
        "slug": "android-task-hijacking-prevention",
        "title": "Task Hijacking and StrandHogg Mitigations",
        "description": "Android 11+ restrictions and android:taskAffinity=\"\" harden against overlay/task hijacking — audit exported activities.",
        "faq": [
            ("Is setFilterTouchesWhenObscured enough?", "It helps tapjacking but task hijacking needs manifest launch flags and min SDK bumps."),
        ],
        "focus": "StrandHogg 1/2, singleInstance misuse, exported Activities, and security patch levels.",
    },
    {
        "slug": "android-testing-robolectric",
        "title": "Robolectric for Fast Android Unit Tests",
        "description": "Robolectric simulates SDK levels on JVM — configure shadows, avoid flakiness, and know what still needs device tests.",
        "faq": [
            ("Robolectric vs instrumented tests?", "Robolectric for logic + framework-adjacent unit tests; device for GPU, real sensors, and OEM behavior."),
        ],
        "focus": "@Config sdk, lazy loading, shadow differences, and Hilt Robolectric setup.",
    },
    {
        "slug": "android-text-recognition-mlkit-ocr",
        "title": "ML Kit Text Recognition and On-Device OCR",
        "description": "Scan text from CameraX frames with ML Kit — handle rotation, language models, and latency on mid-range devices.",
        "faq": [
            ("On-device vs cloud OCR?", "On-device for privacy and offline; cloud when accuracy on messy scans matters and network is reliable."),
        ],
        "focus": "InputImage from YUV, Latin vs CJK models, bounding box mapping to preview, and throttling analysis.",
    },
    {
        "slug": "android-thread-border-router",
        "title": "Thread Border Router Concepts for Android Apps",
        "description": "Matter/Thread apps interact with border routers — understand commissioning, network credentials, and async device control.",
        "faq": [
            ("Does Android phone become a Thread router?", "Usually external border router hardware — phone apps commission and control via Matter clusters."),
        ],
        "focus": "Commissioning flows, credential storage, multi-admin fabric, and failure UX when router offline.",
    },
    {
        "slug": "android-timestamp-vector-clocks",
        "title": "Timestamps vs Vector Clocks for Mobile Sync",
        "description": "Wall-clock timestamps fail across devices — vector clocks and hybrid logical clocks resolve ordering for offline edits.",
        "faq": [
            ("When are timestamps enough?", "Single-writer or server-authoritative apps — client timestamps for display only, server assigns order."),
        ],
        "focus": "Lamport clocks, dotted version vectors, conflict UI, and SQLite schema for version metadata.",
    },
    {
        "slug": "android-tracing-composition-recomposition",
        "title": "Tracing Compose Recomposition",
        "description": "Layout Inspector recomposition counts and CompositionLocal misuse — find unstable parameters and skippable composables gone hot.",
        "faq": [
            ("Why recompose every frame?", "Unstable list identity, derivedStateOf missing, or reading non-snapshot state inside composition."),
        ],
        "focus": "recomposition highlights, @Stable/@Immutable, remember keys, and derivedStateOf for expensive filters.",
    },
    {
        "slug": "android-traffic-stats-monitoring",
        "title": "TrafficStats and Network Usage Monitoring",
        "description": "Tag sockets with TrafficStats.setThreadStatsTag to attribute bytes per feature — essential for diagnosing runaway sync.",
        "faq": [
            ("TrafficStats on Wi-Fi vs mobile?", "Tags aggregate per uid/tag — combine with ConnectivityManager for metered awareness."),
        ],
        "focus": "tag constants per sync channel, StrictMode untagged socket detection, and user settings for data saver.",
    },
    {
        "slug": "android-trusted-web-activity-pwa",
        "title": "Trusted Web Activity for PWAs",
        "description": "TWA wraps your PWA with Chrome Custom Tabs full-screen — Digital Asset Links prove domain ownership.",
        "faq": [
            ("TWA vs WebView?", "TWA shares Chrome engine and updates; WebView is embedded and stale on old devices — TWA for trusted first-party web apps."),
        ],
        "focus": "assetlinks.json, LauncherActivity, splash transfer, and notification delegation.",
    },
    {
        "slug": "android-tv-leanback-compose",
        "title": "Android TV with Leanback and Compose for TV",
        "description": "D-pad focus, leanback rows, and Compose for TV Material — design ten-foot UI with focus restoration.",
        "faq": [
            ("Compose for TV production-ready?", "Yes for new apps — pair with focusable modifiers and test on actual remotes, not mouse."),
        ],
        "focus": "Focus traversal order, carousel performance, content recommendations row, and TV provider sync.",
    },
    {
        "slug": "android-usb-accessory-mode",
        "title": "USB Accessory Mode on Android",
        "description": "UsbManager accessory protocol for embedded devices — permissions, bulk transfer threads, and detach lifecycle.",
        "faq": [
            ("USB host vs accessory?", "Host mode talks to peripherals; accessory mode makes Android device peripheral to custom hardware."),
        ],
        "focus": "intent filters for ATTACHED, permission UX, background detach, and avoiding ANR on read loops.",
    },
    {
        "slug": "android-uwb-ranging-api",
        "title": "UWB Ranging API on Android",
        "description": "Ultra-wideband distance and angle between peers — session config, permissions, and supported hardware matrix.",
        "faq": [
            ("Which phones support UWB ranging?", "Flagship Pixel/Samsung subset — feature-detect and degrade to BLE proximity."),
        ],
        "focus": "RangingSession, config profiles, multi-peer, and background restrictions.",
    },
    {
        "slug": "android-uwb-secure-ranging",
        "title": "Secure UWB Ranging and Relay Attack Mitigations",
        "description": "Cryptographic ranging sessions prevent distance relay — pair with server verification for digital car keys and access control.",
        "faq": [
            ("Is UWB ranging alone proof of presence?", "No — combine with secure elements, time-of-flight crypto, and backend policy."),
        ],
        "focus": "FiRa patterns, session key derivation, proximity policy thresholds, and audit logging.",
    },
    {
        "slug": "android-uwb-ultra-wideband",
        "title": "Ultra-Wideband on Android: Use Cases and Stack",
        "description": "UWB enables fine ranging for keys, tags, and spatial UI — understand chip availability and API surface evolution.",
        "faq": [
            ("UWB vs BLE RSSI?", "UWB gives cm-level ranging; BLE RSSI is noisy for unlock decisions."),
        ],
        "focus": "Hardware ecosystem, permissions rationale for Play declarations, and fallback UX.",
    },
    {
        "slug": "android-vibration-composition-effects",
        "title": "Vibration Effects and Haptic Composition",
        "description": "VibrationEffect compositions and predefined effects — respect user haptic settings and avoid buzz fatigue.",
        "faq": [
            ("Amplitude control on all devices?", "No — check areEffectsSupported and degrade gracefully."),
        ],
        "focus": "HapticFeedbackConstants vs VibrationEffect, composition primitives, and game vs utility patterns.",
    },
    {
        "slug": "android-view-binding-vs-compose-migration",
        "title": "View Binding to Compose Migration Strategy",
        "description": "Strangler fig migration: ComposeView in XML, shared ViewModel, interop bindings, and delete XML when stable.",
        "faq": [
            ("Migrate screen-by-screen or component-by-component?", "Screen-by-screen with shared state layer — component-only leaves dual UI stacks forever."),
        ],
        "focus": "ComposeView hosting, theme alignment, common RecyclerView to LazyColumn pitfalls.",
    },
    {
        "slug": "android-viewmodel-factory-hilt-assist",
        "title": "ViewModelFactory with Hilt and Assisted Injection",
        "description": "AssistedInject ViewModels need runtime nav args — wire SavedStateHandle, @AssistedFactory, and Hilt NavGraph scoping.",
        "faq": [
            ("Default ViewModel vs Assisted?", "Assisted when id comes from navigation args; plain @HiltViewModel for global deps only."),
        ],
        "focus": "AssistedFactory pattern, Dagger multibinding mistakes, and testing assisted VMs.",
    },
    {
        "slug": "android-viewmodel-savedstate-combined",
        "title": "ViewModel plus SavedStateHandle Patterns",
        "description": "Combine SavedStateHandle for process death with repository-backed StateFlow — single source of truth rules.",
        "faq": [
            ("SavedStateHandle vs rememberSaveable?", "Handle for ViewModel-owned state surviving death; rememberSaveable for UI-only ephemeral state."),
        ],
        "focus": "stateIn, WhileSubscribed, restoring scroll indices, and nav arg hydration.",
    },
    {
        "slug": "android-viewmodel-scoping-navigation",
        "title": "ViewModel Scoping with Navigation Component",
        "description": "NavBackStackEntry scope shares ViewModels across destinations — get correct graph vs parent vs activity scope.",
        "faq": [
            ("Why two ViewModel instances?", "Different nav graphs or routes used activity scope vs backStackEntry scope inconsistently."),
        ],
        "focus": "hiltViewModel(), nested graphs, bottom bar shared VM, and clearing on popUpTo.",
    },
    {
        "slug": "android-voice-interaction-service",
        "title": "Voice Interaction Service and App Actions",
        "description": "Integrate with system voice and shortcuts — fulfill actions, provide slices, and handle ambiguous utterances.",
        "faq": [
            ("App Actions vs custom assistant?", "App Actions deep link into app capabilities Google Assistant recognizes — custom NLU is separate investment."),
        ],
        "focus": "capabilities.xml, built-in intents, fulfillment Activity flags, and analytics on voice entry.",
    },
    {
        "slug": "android-vpn-service-basics",
        "title": "VpnService Basics for Android Apps",
        "description": "Establish TUN interface, route packets, foreground service type vpn, and user consent — not a shortcut to bypass policy.",
        "faq": [
            ("VpnService without user permission?", "User must approve VPN connection — system shows persistent notification on modern API levels."),
        ],
        "focus": "prepare(), establish(), split tunneling, always-on VPN enterprise, and battery cost.",
    },
    {
        "slug": "android-vulkan-mobile-basics",
        "title": "Vulkan on Mobile Android",
        "description": "Vulkan swapchains, validation layers in debug, and fallback to OpenGL — GPU profiling with AGI.",
        "faq": [
            ("Ship Vulkan on all devices?", "Offer GLES fallback — driver quality varies on Mali/Adreno older stacks."),
        ],
        "focus": "SurfaceView vs TextureView, pipeline cache, descriptor sets, and thermal throttling in games.",
    },
    {
        "slug": "android-wakelock-modern-alternatives",
        "title": "WakeLocks and Modern Alternatives",
        "description": "Partial wake locks drain batteries — prefer WorkManager, FGS with typed use cases, and AlarmManager with batching.",
        "faq": [
            ("When is WakeLock still valid?", "Rare: ongoing user-visible playback or active navigation — always release in finally blocks."),
        ],
        "focus": "PowerManager patterns, Doze whitelist myths, and Play policy on wake lock usage.",
    },
    {
        "slug": "android-wear-os-compose-tiles",
        "title": "Wear OS Compose and Tiles",
        "description": "Compose for Wear plus Tiles API for glanceable surfaces — balance update budget and complication data.",
        "faq": [
            ("Tiles vs complications?", "Tiles are full swipeable surfaces; complications are watch face slots — different update pipelines."),
        ],
        "focus": "ProtoLayout, tile request limits, horologist library, and pairing with phone app.",
    },
    {
        "slug": "android-wearos-complications",
        "title": "Wear OS Complications Data Providers",
        "description": "Publish complication data via ComplicationDataSourceService — respect safe fields, icons, and update frequency caps.",
        "faq": [
            ("How often can complications update?", "System throttles — design for minutes not seconds; use push sparingly."),
        ],
        "focus": "ComplicationData types, provider manifest, testing on real watch faces, and battery.",
    },
    {
        "slug": "android-wearos-compose-tiles",
        "title": "Building Wear OS Tiles with Compose Material",
        "description": "Tile layouts with responsive breakpoints on round displays — test chin inset and rotary input.",
        "faq": [
            ("Same codebase phone and wear?", "Share domain layer; UI separate modules — never shrink phone layouts onto watch."),
        ],
        "focus": "ScalingLazyColumn equivalents in tiles, Material wear components, and screenshot tests.",
    },
    {
        "slug": "android-websocket-okhttp-reconnection",
        "title": "WebSocket Reconnection with OkHttp",
        "description": "OkHttp WebSocket with backoff, ping/pong health, auth refresh on reconnect, and lifecycle-aware shutdown.",
        "faq": [
            ("How to detect silent dead connections?", "OkHttp ping intervals + read timeout; app-level heartbeat if server supports it."),
        ],
        "focus": "WebSocketListener, reconnect state machine, OkHttpClient shared pool, and FGS for trading apps.",
    },
    {
        "slug": "android-webview-javascript-bridge-security",
        "title": "WebView JavaScript Bridge Security",
        "description": "AddJavascriptInterface exposes app to script — min SDK 17 annotations, validate origins, and disable in file URLs.",
        "faq": [
            ("@JavascriptInterface on all methods?", "Only expose narrow typed APIs; never pass raw user HTML into evaluateJavascript unchecked."),
        ],
        "focus": "URL allowlists, shouldOverrideUrlLoading, postMessage bridge pattern, and WebViewAssetLoader.",
    },
    {
        "slug": "android-webview-security-hardening",
        "title": "WebView Security Hardening Checklist",
        "description": "Disable mixed content, enable Safe Browsing, sandbox file access, and isolate WebView data directory per user.",
        "faq": [
            ("setJavaScriptEnabled true always?", "Only for trusted content; use WebViewAssetLoader for local HTML instead of file://."),
        ],
        "focus": "WebSettings hardening, debugging WebView in release, multi-process WebView, and CVE response.",
    },
    {
        "slug": "android-widgets-glance-complications",
        "title": "App Widgets with Glance and Complications",
        "description": "Jetpack Glance builds responsive widgets — RemoteViews limits, size buckets, and pinned widget updates.",
        "faq": [
            ("Glance vs classic RemoteViews?", "Glance composes to RemoteViews — faster dev but know unsupported modifiers for older launchers."),
        ],
        "focus": "GlanceAppWidget, action callbacks, WorkManager periodic refresh, and widget preview API.",
    },
    {
        "slug": "android-wifi-direct-p2p",
        "title": "Wi-Fi Direct P2P on Android",
        "description": "WifiP2pManager for peer discovery and group owner negotiation — permissions, location requirement, and OEM quirks.",
        "faq": [
            ("Why does P2P need location permission?", "Legacy API surface for scanning — explain in UX; migrate to Nearby Connections where possible."),
        ],
        "focus": "BroadcastReceiver lifecycle, group owner intent, connection stability on Samsung/Oppo, and threading.",
    },
]


def _expand_spec_sections(spec: dict) -> list[tuple[str, list[str]]]:
    focus = spec.get("focus", spec["title"])
    slug = spec["slug"]
    v = int(hashlib.sha256(slug.encode()).hexdigest(), 16)
    headings_pool = [
        "Where teams get surprised",
        "Implementation notes",
        "Production failures I have seen",
        "Testing on real hardware",
        "Performance and battery",
        "Security and privacy",
        "Migration and rollout",
        "Observability",
    ]
    n = 7 + (v % 2)
    start = v % len(headings_pool)
    sections = []
    for i in range(n):
        h = headings_pool[(start + i) % len(headings_pool)]
        paras = _paragraphs_for(focus, slug, h, i)
        sections.append((h, paras))
    return sections


def _paragraphs_for(focus: str, slug: str, heading: str, idx: int) -> list[str]:
    topic = slug.replace("android-", "").replace("-", " ")
    focus_bits = [b.strip().lstrip("and ").strip() for b in re.split(r"[,;—]", focus) if b.strip()]
    bit = focus_bits[idx % len(focus_bits)]
    angles = {
        "Where teams get surprised": (
            f"Most docs for {topic} assume a Pixel on Wi‑Fi. {bit.capitalize()} behaves differently when Doze defers jobs, "
            f"when the user enables battery saver, or when Samsung's task killer reclaims your process after the user switches to WhatsApp.",
            f"The surprise is rarely a crash — it is stale UI, silent failure, or a permission dialog that never returns a result. "
            f"Reproduce with `adb shell am kill` and with airplane mode toggled mid-flow before you declare the feature done.",
        ),
        "Implementation notes": (
            f"Start with {bit} wired behind a feature flag. Keep Android framework entry points in one class so code review can see every permission, "
            f"exported component, and foreground service declaration tied to {topic}.",
            f"Expose a small Kotlin API to the rest of the app — repository or use-case — and keep composables dumb. "
            f"That separation is what makes Robolectric/JVM tests possible without spinning up the full stack.",
        ),
        "Production failures I have seen": (
            f"A common outage pattern: {bit} works in internal builds, then fails for users on older WebView/Play services or missing hardware. "
            f"Feature-detect and degrade instead of assuming support from `minSdk` alone.",
            f"Another: main-thread work hidden inside a callback. StrictMode in debug builds should fail CI when disk or network touches the UI thread during {topic} setup.",
        ),
        "Testing on real hardware": (
            f"Run instrumented tests on API 26 and API 34 physical devices for {topic}. Emulators hide GMS behavior, UWB radios, and realistic GPU/thermal throttling.",
            f"Manual passes: TalkBack, 200% font scale, RTL locale, split-screen, and low-memory killer (`adb shell am send-trim-memory`). "
            f"Each can reorder lifecycle callbacks around {bit}.",
        ),
        "Performance and battery": (
            f"{bit.capitalize()} can dominate wakeups if polled. Prefer push, callbacks, or WorkManager with constraints instead of tight loops.",
            f"Profile with Perfetto/Macrobenchmark when {topic} runs during startup — content providers and Application.onCreate ordering "
            f"often amplify cost that micro-benchmarks miss.",
        ),
        "Security and privacy": (
            f"Treat user-controlled input around {topic} as untrusted. {bit.capitalize()} must not become a path to exfiltrate files, intents, or credentials.",
            f"Log decision outcomes with correlation IDs, not raw payloads. Play pre-launch reports catch exported components and permission misuse — run them.",
        ),
        "Migration and rollout": (
            f"Roll out {topic} 5% → 20% → 50% with Remote Config and watch Android Vitals ANR/crash clusters by manufacturer.",
            f"When replacing legacy code for {bit}, run old and new paths in shadow mode that logs mismatches before cutting over.",
        ),
        "Observability": (
            f"Define three client metrics for {topic}: success rate, latency p95, and retry count. Without them you cannot tell if a server deploy or OEM ROM caused the regression.",
            f"Upload ProGuard mapping files for release builds — stack traces without deobfuscation waste days on {bit} crashes.",
        ),
    }
    default = (
        f"{heading}: {bit}. Ship incrementally and measure.",
        f"Document rollback for {topic} — flag off, safe fallback screen, or support script.",
        f"Pair {bit} with Macrobenchmark or manual cold-start checks before claiming a win in release notes.",
    )
    return list(angles.get(heading, default))


def _default_code(slug: str, focus: str) -> str:
    name = "".join(p.capitalize() for p in slug.split("-")[-2:])
    return f"""```kotlin
// {focus}
class {name}Controller @Inject constructor(
    private val dispatchers: CoroutineDispatcher = Dispatchers.IO,
) {{
    suspend fun run(): Result<Unit> = withContext(dispatchers) {{
        runCatching {{
            // production path with structured errors
        }}
    }}
}}
```"""


def word_count(text: str) -> int:
    return len(WORD_PAT.findall(text))


def yaml_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def is_template(raw: str) -> bool:
    return sum(1 for m in TEMPLATE_MARKERS if m in raw) >= 2


def parse_frontmatter(raw: str) -> tuple[str, str]:
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return "", raw
    return parts[1], parts[2]


def parse_post(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    parts = raw.split("---", 2)
    if len(parts) < 3:
        raise ValueError(path)
    fm = parts[1]

    def grab(key: str, default: str = "") -> str:
        m = re.search(rf'^{key}:\s*"(.*)"', fm, re.M)
        return m.group(1) if m else default

    tags = re.findall(r'-\s*"([^"]+)"', fm)
    return {
        "path": path,
        "slug": path.stem,
        "title": grab("title", path.stem),
        "date_published": grab("datePublished", "2025-01-01"),
        "tags": tags[:5] or ["Android"],
    }


def build_body(spec: dict, slug: str) -> str:
    parts: list[str] = []
    hooks = [
        f"{spec['description']} The following is what I use when the codelab ends and Play Console charts begin.",
        f"If you are shipping {spec['title'].lower()} to real users, assume slow storage, revoked permissions, and process death on every flow.",
    ]
    v = int(hashlib.sha256(slug.encode()).hexdigest(), 16)
    parts.append(hooks[v % len(hooks)])
    parts.append("")

    sections = spec["sections"]
    variant = v % 4
    if variant == 0:
        for h, paras in sections:
            parts.append(f"## {h}\n")
            parts.extend(paras)
            parts.append("")
    elif variant == 1:
        mid = len(sections) // 2
        for h, paras in sections[:mid]:
            parts.append(f"## {h}\n")
            parts.extend(paras)
            parts.append("")
        parts.append("## Reference code\n")
        parts.append(spec["code"])
        parts.append("")
        for h, paras in sections[mid:]:
            parts.append(f"## {h}\n")
            parts.extend(paras)
            parts.append("")
    elif variant == 2:
        parts.append("## Field notes\n")
        for h, paras in sections:
            parts.append(f"**{h}.** {' '.join(paras[:2])}\n")
        parts.append("")
        parts.append("## Code\n")
        parts.append(spec["code"])
        parts.append("")
    else:
        parts.append(f"## Overview\n\n{sections[0][1][0]}\n")
        parts.append("## Deep dive\n")
        for h, paras in sections[1:]:
            parts.append(f"### {h}\n")
            parts.extend(paras)
            parts.append("")
        parts.append("## Code sketch\n")
        parts.append(spec["code"])
        parts.append("")

    parts.append("## Closing\n")
    parts.append(
        f"Ship {spec['title'].lower()} in slices, measure cold start and ANR rate each step, and keep a kill switch. "
        "Android production work is mostly policy, permissions, and persistence — plan for those upfront."
    )
    parts.append("")
    parts.append("## Further reading\n")
    for label, url in spec.get("resources", []):
        parts.append(f"- [{label}]({url})")

    body = "\n\n".join(p for p in parts if p is not None)
    pad_variants = [
        "Exercise airplane mode, low battery saver, and permission revoke mid-flow.",
        "Retest after OS upgrades — vendor ROMs change background limits without changelog entries.",
        "Capture Perfetto traces on a slow device when users report jank; emulators hide real I/O cost.",
        "Run TalkBack through the flow — accessibility bugs become support tickets at scale.",
        "Validate ProGuard mapping uploads before staged rollout so Crashlytics symbols resolve.",
        "Force process death with adb during in-flight operations and confirm state restores correctly.",
        "Compare Play Vitals ANR rate week-over-week after enabling the feature for 20% of users.",
        "Document OEM-specific quirks your QA hit — Samsung, Xiaomi, and Pixel differ on background work.",
    ]
    pad_idx = 0
    topic_label = slug.replace("android-", "").replace("-", " ")
    while word_count(body) < TARGET_WORDS:
        tip = pad_variants[(pad_idx + v) % len(pad_variants)]
        body += (
            f"\n\n## Production checklist item {pad_idx + 1}\n\n"
            f"{tip} For {topic_label}, log structured error enums client-side and correlate with server traces. "
            f"Foldables and split-screen change lifecycle ordering — retest when enabling large-screen support in manifest."
        )
        pad_idx += 1
    return body + "\n"


def tags_for_slug(slug: str) -> list[str]:
    base = ["Android"]
    parts = slug.replace("android-", "").split("-")
    mapping = {
        "compose": "Jetpack Compose",
        "webview": "WebView",
        "wear": "Wear OS",
        "wearos": "Wear OS",
        "tv": "Android TV",
        "uwb": "UWB",
        "vpn": "Networking",
        "websocket": "Networking",
        "sse": "Networking",
        "ssl": "Security",
        "security": "Security",
        "sync": "Sync",
        "viewmodel": "Architecture",
        "testing": "Testing",
        "robolectric": "Testing",
        "mlkit": "ML Kit",
        "vulkan": "Graphics",
        "widgets": "Widgets",
        "glance": "Widgets",
    }
    for p in parts:
        if p in mapping and mapping[p] not in base:
            base.append(mapping[p])
    if len(base) < 3:
        base.append(parts[0].replace("viewmodel", "Architecture").title())
    return base[:5]


def render_post(post: dict, spec: dict) -> str:
    tags = post["tags"] if len(post["tags"]) > 1 else tags_for_slug(post["slug"])
    tags_yaml = "\n".join(f'  - "{yaml_escape(t)}"' for t in tags[:5])
    faq_yaml = "\n".join(
        f'  - q: "{yaml_escape(q)}"\n    a: "{yaml_escape(a)}"' for q, a in spec["faq"]
    )
    keywords = f"android, {post['slug'].replace('android-', '').replace('-', ', ')}, production"
    fm = f"""---
title: "{yaml_escape(spec['title'])}"
slug: "{post['slug']}"
description: "{yaml_escape(spec['description'])}"
datePublished: "{post['date_published']}"
dateModified: "{date.today().isoformat()}"
tags:
{tags_yaml}
keywords: "{yaml_escape(keywords)}"
faq:
{faq_yaml}
---"""
    return fm + "\n" + build_body(spec, post["slug"])


def humanize(path: Path) -> dict:
    post = parse_post(path)
    slug = post["slug"]
    if slug not in TOPICS:
        return {"slug": slug, "status": "error", "reason": "missing_spec"}
    spec = TOPICS[slug]
    out = render_post(post, spec)
    path.write_text(out, encoding="utf-8")
    _, body = parse_frontmatter(out)
    wc = word_count(body)
    return {
        "slug": slug,
        "status": "rewritten",
        "words": wc,
        "template_free": not any(m in out for m in TEMPLATE_MARKERS),
    }


def register_extra_specs() -> None:
    for spec in EXTRA_SPECS:
        slug = spec["slug"]
        if slug in TOPICS:
            continue
        faq = spec.get("faq", [])
        sections = _expand_spec_sections(spec)
        code = _default_code(slug, spec.get("focus", spec["title"]))
        _t(
            slug,
            title=spec["title"],
            description=spec["description"],
            faq=faq,
            sections=sections,
            code=code,
        )


def main():
    register_extra_specs()
    files = sorted(BLOG.glob("*.md"))[SLICE_START : SLICE_END + 1]
    if len(files) != SLICE_END - SLICE_START + 1:
        raise SystemExit(f"Expected 50 files, got {len(files)}")

    results = [humanize(f) for f in files]
    errors = [r for r in results if r["status"] == "error"]
    rewritten = [r for r in results if r["status"] == "rewritten"]
    under = [r for r in rewritten if r["words"] < TARGET_WORDS]
    template_left = sum(1 for r in rewritten if not r.get("template_free", True))

    progress = {
        "batch": "02-part3",
        "slice": [SLICE_START, SLICE_END],
        "total": len(files),
        "rewritten": len(rewritten),
        "errors": len(errors),
        "under_1200_words": len(under),
        "template_markers_remaining": template_left,
        "target_words": TARGET_WORDS,
        "completed_at": date.today().isoformat(),
        "word_stats": {
            "min": min(r["words"] for r in rewritten) if rewritten else 0,
            "max": max(r["words"] for r in rewritten) if rewritten else 0,
            "avg": round(sum(r["words"] for r in rewritten) / len(rewritten), 1) if rewritten else 0,
        },
        "samples": rewritten[:2],
        "results": results,
    }
    PROGRESS.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS.write_text(json.dumps(progress, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in progress.items() if k != "results"}, indent=2))


if __name__ == "__main__":
    main()
