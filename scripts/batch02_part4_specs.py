# Unique topic specs for batch-02-part4 (slice 701-750)
SLUG_SPECS: dict[str, dict] = {
    "android-wifi-scanning-privacy": {
        "title": "Wi-Fi Scanning and Privacy on Android",
        "description": "How Android throttled Wi-Fi scanning for privacy, which APIs work on each API level, and how to build location-adjacent features without Play policy violations.",
        "focus": "NEARBY_WIFI_DEVICES permission, scan throttling, BSSID privacy, startScan debouncing, ConnectivityManager vs WifiManager, background scan limits",
        "faq": [
            ("Why does Wi-Fi scanning need location permission on older Android?", "Before Android 13, scan results expose BSSIDs usable for location fingerprinting. Android 13+ offers NEARBY_WIFI_DEVICES with neverForLocation for non-location Wi-Fi features."),
            ("How often can apps scan in background?", "Background apps are throttled to roughly four scans per two minutes on Android 9+. Debounce scans and handle EXTRA_RESULTS_UPDATED false."),
            ("Can I read connected SSID without location?", "Often returns unknown ssid without permission. Prefer NetworkCapabilities for connectivity UX without neighbor scans."),
            ("What triggers Play rejection for Wi-Fi?", "Declaring fine location solely for SSID display when NEARBY_WIFI_DEVICES suffices; uploading raw scan lists to analytics without consent."),
        ],
    },
    "android-window-insets-handling": {
        "title": "Window Insets Handling on Modern Android",
        "description": "Edge-to-edge rendering, WindowInsetsCompat, IME animations, and cutout-safe layouts on Android 15 without breaking keyboard behavior.",
        "focus": "enableEdgeToEdge, systemBarsPadding, imePadding, display cutout, setDecorFitsSystemWindows false, SDK 35 enforcement, ModalBottomSheet IME",
        "faq": [
            ("What are window insets?", "Regions occupied by status bar, navigation bar, notch, and IME. Content drawing edge-to-edge must apply inset padding at the correct hierarchy node."),
            ("fitsSystemWindows vs WindowInsetsCompat?", "Avoid fitsSystemWindows for new code. Use WindowInsetsCompat listeners or Compose windowInsetsPadding modifiers."),
            ("Keyboard covers TextField in Compose?", "Use imePadding on scroll container, enableEdgeToEdge in Activity, avoid adjustPan-only setups."),
            ("Why break after targeting SDK 35?", "Android 15 enforces edge-to-edge; opaque system bars no longer assumed. Handle insets or content clips under notch."),
        ],
    },
    "android-window-manager-embedding-activities": {
        "title": "Activity Embedding for Large Screens",
        "description": "Split list-detail activities on tablets and foldables with WindowManager Jetpack rules without fragment rewrites.",
        "focus": "SplitPairRule XML, placeholder activity, fold posture, finishSecondaryWithPrimary, FLAG_ACTIVITY_NEW_TASK pitfalls, three-pane 840dp",
        "faq": [
            ("What is activity embedding?", "Two activities side-by-side in one task on large screens via SplitPairRule declarations."),
            ("Need fragments for tablets?", "No — embedding works with existing multi-activity apps."),
            ("Fold behavior?", "Collapses to single pane below width threshold; persist selection in ViewModel across fold."),
            ("Play large-screen badge?", "Embedding qualifies if activities are resizable and orientation locks removed."),
        ],
    },
    "android-workmanager-coroutine-worker": {
        "title": "CoroutineWorker Best Practices",
        "description": "Suspend doWork, setForeground, setProgress, cancellation, and testing CoroutineWorker in production Android apps.",
        "focus": "CancellationException rethrow, ForegroundInfo dataSync, setProgress throttling, coroutineScope async, TestListenableWorkerBuilder, HiltWorker",
        "faq": [
            ("CoroutineWorker vs Worker?", "CoroutineWorker for suspend IO; Worker blocks thread pool; ListenableWorker for callback APIs."),
            ("setProgress from CoroutineWorker?", "Yes — throttle updates; each write hits WorkManager DB."),
            ("Force-stop during doWork?", "Work cancelled; restart from scratch unless partial state persisted."),
            ("Testing without sleep?", "WorkManagerTestInitHelper, TestListenableWorkerBuilder, injected TestDispatcher."),
        ],
    },
    "android-workmanager-expedited-work": {
        "title": "WorkManager Expedited Work",
        "description": "Expedited jobs for user-initiated tasks — quota limits, OutOfQuotaPolicy fallback, pairing with foreground promotion.",
        "focus": "setExpedited RUN_AS_NON_EXPEDITED, quota scarcity, user-initiated litmus test, DROP_WORK danger, FGS inside worker",
        "faq": [
            ("What is expedited work?", "Priority scheduling bypassing normal JobScheduler batching for user-initiated tasks within quota."),
            ("OutOfQuotaPolicy?", "RUN_AS_NON_EXPEDITED degrades gracefully; DROP_WORK loses job silently."),
            ("Replace ForegroundService?", "Not for long runs — expedited starts faster; FGS keeps upload alive mid-run."),
            ("Quota amount?", "Not fixed publicly — treat as scarce; reserve for explicit user actions."),
        ],
    },
    "android-workmanager-hilt-integration": {
        "title": "WorkManager Hilt Integration",
        "description": "HiltWorkerFactory, AssistedInject workers, and safe repository injection into background jobs.",
        "focus": "Configuration.Provider, @HiltWorker @AssistedInject, cancel on logout, ProGuard WorkerFactory, SyncWorkScheduler",
        "faq": [
            ("Why not @Inject constructor on Worker?", "WorkManager passes Context and WorkerParameters — requires AssistedInject split."),
            ("Register HiltWorkerFactory where?", "Configuration.Provider on Application returning setWorkerFactory."),
            ("Singleton repos in workers?", "Yes — fail fast if session invalid; cancel work on logout."),
            ("ProGuard rules?", "Keep @HiltWorker and generated AssistedFactory classes."),
        ],
    },
    "android-workmanager-test-driver": {
        "title": "Testing WorkManager with TestDriver",
        "description": "Deterministic WorkManager tests with TestInitHelper and TestDriver — constraints, chains, periodic work without Thread.sleep.",
        "focus": "setAllConstraintsMet, setPeriodDelayMet, SynchronousExecutor, chain order asserts, closeWorkDatabase tearDown",
        "faq": [
            ("What is TestDriver?", "Test API to satisfy constraints and advance periodic delays instantly."),
            ("JVM or instrumented?", "TestDriver needs instrumented tests; JVM uses TestListenableWorkerBuilder for doWork."),
            ("Test hangs on SUCCEEDED?", "Constraints not met — call setAllConstraintsMet on enqueued id."),
            ("Test backoff?", "Unit test retry in doWork; integration uses TestDriver after failure."),
        ],
    },
    "android-workmanager-unique-work-chains": {
        "title": "WorkManager Unique Work and Chains",
        "description": "enqueueUniqueWork policies, beginWith chains, output merging, and naming for reliable sync pipelines.",
        "focus": "KEEP vs REPLACE semantics, WorkNames per tenant, beginWith then, parallel beginWith list, cancelUniqueWork logout",
        "faq": [
            ("What is unique work?", "Named logical job — only one pending/running instance per name depending on policy."),
            ("REPLACE vs KEEP?", "REPLACE cancels in-flight for latest user refresh; KEEP drops duplicate enqueue."),
            ("Chain data passing?", "Result.success outputData merges into next worker inputData."),
            ("Unique work with tags?", "Yes — name dedupes; tags group observation and bulk cancel."),
        ],
    },
    "android-workmanager-vs-jobscheduler": {
        "title": "WorkManager vs JobScheduler in 2026",
        "description": "Why WorkManager is the default for deferrable background work and when raw JobScheduler still fits.",
        "focus": "WorkDatabase reboot survival, chaining, expedited work, migration from JobService, category mistakes coroutine vs WM",
        "faq": [
            ("WorkManager or JobScheduler in 2026?", "WorkManager for almost all deferrable guaranteed work."),
            ("Just a wrapper?", "Uses JobScheduler on modern APIs plus persistence, chains, observation, retries."),
            ("Wrong tool?", "User-waiting work → coroutine; continuous visible → FGS; deferrable → WorkManager."),
            ("Migrate JobScheduler?", "Wrap JobService in Worker, dual-run behind flag, remove boot receiver when zero traffic."),
        ],
    },
    "android-xr-headset-development": {
        "title": "Android XR Headset Development Basics",
        "description": "Jetpack XR SDK, spatial Compose panels, emulator setup, and incremental path from flat Android to mixed reality.",
        "focus": "Subspace SpatialPanel, input modalities, passthrough MR comfort, thermal throttling, Compose reuse with larger touch targets",
        "faq": [
            ("What is Android XR?", "Extended-reality Android for headsets/glasses with Jetpack XR spatial APIs."),
            ("Existing app without changes?", "Runs windowed; spatial product needs Jetpack XR investment."),
            ("Dev hardware?", "XR emulator plus physical kit for passthrough and hand tracking latency."),
            ("Unity vs Jetpack XR?", "Unity for heavy 3D; Compose XR for integrated Android shell and productivity UIs."),
        ],
    },
    "android-xr-vs-visionos": {
        "title": "Building for Android XR vs visionOS",
        "description": "Comparing spatial SDKs, input models, tooling, and cross-platform strategy for mobile developers.",
        "focus": "Kotlin Compose vs SwiftUI RealityKit, gaze-pinch vs multi-modal input, share domain fork presentation, floating panel trap",
        "faq": [
            ("Difference Android XR vs visionOS?", "Android XR on Android/Kotlin; visionOS on Swift/SwiftUI — same category, different ecosystems."),
            ("Reuse mobile app?", "2D window mode yes; spatial APIs do not port automatically."),
            ("Shorter learning curve?", "Match your existing mobile stack — Android team → XR; iOS team → visionOS."),
            ("One spatial UI codebase?", "Not realistic today — input paradigms differ too much for native feel."),
        ],
    },
}

# Auto-generate remaining API/auth specs from slug tokens
_API_FAQ = [
    ("When should teams adopt this pattern?", "When production incidents, client complaints, or scale tests show the ad-hoc approach breaks — not before you have a measurable pain point."),
    ("What is the most common mistake?", "Copying a tutorial without matching your auth model, retry semantics, or observability stack — and skipping idempotency on retriable paths."),
    ("How do I debug issues in production?", "Start from correlation IDs and structured logs filtered by route and tenant; reproduce minimally with the same headers and payload shape."),
]

def _api_spec(slug: str) -> dict:
    topic = slug.replace("api-", "").replace("auth-", "").replace("-", " ")
    title = " ".join(w.capitalize() for w in topic.split())
    if slug.startswith("auth-"):
        title = "Auth: " + title
    else:
        title = "API " + title if not title.startswith("API") else title
    return {
        "title": title,
        "description": f"Production guide to {topic} — design, implementation, failure modes, and operational checklist for backend teams.",
        "focus": f"{topic}, HTTP semantics, idempotency, observability, client contracts, rate limits, security boundaries, rollout strategy",
        "faq": list(_API_FAQ),
    }

_REMAINING = [
    "api-authentication-jwt-vs-sessions", "api-bulk-operations-batch-endpoints",
    "api-conditional-requests-etag", "api-content-negotiation-accept",
    "api-contract-testing-pact-provider", "api-correlation-id-propagation",
    "api-cors-preflight-production", "api-cursor-pagination-stable-sort",
    "api-deprecation-sunset-headers", "api-documentation-openapi",
    "api-error-envelope-consistency", "api-field-selection-sparse-fieldsets",
    "api-gateway-auth-offload-patterns", "api-gateway-patterns",
    "api-graceful-shutdown-drain", "api-health-check-deep-shallow",
    "api-hypermedia-hateoas-pragmatic", "api-idempotency-key-header-standard",
    "api-json-patch-merge-patch", "api-long-running-async-jobs",
    "api-multi-tenant-header-isolation", "api-openapi-codegen-tradeoffs",
    "api-pagination-keyset-vs-offset", "api-problem-details-rfc7807",
    "api-rate-limit-response-headers", "api-rate-limiting-algorithms",
    "api-request-size-limits-dos", "api-request-validation-zod-joi",
    "api-response-compression-brotli", "api-security-owasp-api-top-10",
    "api-server-sent-events-streaming", "api-versioning-strategies",
    "astro-content-collections",
    "auth-api-key-hashing-storage", "auth-break-glass-emergency-access",
    "auth-mtls-client-certificates", "auth-rbac-vs-abac-decision",
    "auth-session-hardening-cookies", "auth-spiffe-spire-workload-identity",
]

for s in _REMAINING:
    if s not in SLUG_SPECS:
        if s == "astro-content-collections":
            SLUG_SPECS[s] = {
                "title": "Content Collections in Astro",
                "description": "Type-safe Markdown with Zod schemas, getCollection queries, and build-time validation for blogs and docs.",
                "focus": "content.config.ts loaders, Zod schema, reference(), draft filtering, astro check CI, slug stability, RSS sitemap shared filter",
                "faq": [
                    ("What problem do collections solve?", "Validated frontmatter at build time instead of runtime typos in production."),
                    ("Non-Markdown collections?", "JSON/YAML for authors, products — reference across collections."),
                    ("Query posts?", "getCollection with filter/sort; getEntry for single slug."),
                    ("Astro 5 migration?", "content.config.ts loaders replace legacy config module — pin version in CI."),
                ],
            }
        else:
            SLUG_SPECS[s] = _api_spec(s)

ALL_SLUGS = list(SLUG_SPECS.keys())
