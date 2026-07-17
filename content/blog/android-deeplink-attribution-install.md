---
title: "Deferred Deep Links and Attribution"
slug: "android-deeplink-attribution-install"
description: "Implement deferred deep links on Android: Play Install Referrer, App Links verification, attribution SDKs, and routing new installs to the right content."
datePublished: "2026-07-16"
dateModified: "2026-07-16"
tags: ["Android", "Deep Links", "Analytics", "Growth"]
keywords: "deferred deep links Android, install attribution, Android App Links, Play Install Referrer, deep link routing Android"
faq:
  - q: "What is a deferred deep link?"
    a: "A deferred deep link routes a user to specific in-app content after they install the app, even though they clicked the link before installing. The user clicks an ad or shared link, goes to the Play Store, installs, opens the app for the first time, and lands on the intended screen — not the home screen."
  - q: "How does Android pass install attribution data?"
    a: "The Play Install Referrer API provides the referrer URL that led to the Play Store install. Combined with App Links verification and attribution SDKs (Firebase Dynamic Links successor patterns, Branch, Adjust), you can match the install to the original link click and extract routing parameters."
  - q: "What is the difference between deep links and App Links?"
    a: "Deep links use a custom URI scheme (myapp://path) that opens your app if installed. App Links use HTTPS URLs (https://example.com/path) with domain verification, opening your app directly without a disambiguation dialog. App Links are preferred for production — they're more reliable and work for deferred linking with proper attribution setup."
---

A user clicks your ad for 30% off running shoes, installs the app, and lands on the generic home screen. They bounce. That conversion — and the ad spend behind it — is lost because you didn't implement deferred deep linking. Deferred links carry the user's intent through the install gap: click → Play Store → install → open → intended content. Getting this right requires coordination between your web domain, Play Store referrer data, and in-app routing. I've debugged deferred link failures that turned out to be domain verification typos, referrer API timing issues, and routing logic that only handled warm-start deep links, not first-open.

## The deferred link flow

```
User clicks https://example.com/shoes/sale
    ↓
Web page (or direct) → Play Store with referrer param
    ↓
User installs and opens app (first launch)
    ↓
App reads Install Referrer → extracts /shoes/sale
    ↓
NavController routes to SaleScreen
```

The challenge: on first launch, there's no Intent with the deep link URI. You must retrieve the referrer asynchronously and route after.

## App Links setup (prerequisite)

Verify your domain for HTTPS deep links:

```xml
<!-- AndroidManifest.xml -->
<activity android:name=".MainActivity" android:exported="true">
    <intent-filter android:autoVerify="true">
        <action android:name="android.intent.action.VIEW" />
        <category android:name="android.intent.category.DEFAULT" />
        <category android:name="android.intent.category.BROWSABLE" />
        <data android:scheme="https"
              android:host="example.com"
              android:pathPrefix="/shoes" />
    </intent-filter>
</activity>
```

Host `assetlinks.json` at `https://example.com/.well-known/assetlinks.json`:

```json
[{
  "relation": ["delegate_permission/common.handle_all_urls"],
  "target": {
    "namespace": "android_app",
    "package_name": "com.example.app",
    "sha256_cert_fingerprints": ["AB:CD:..."]
  }
}]
```

Verify with:

```bash
adb shell pm verify-app-links --re-verify com.example.app
adb shell pm get-app-links com.example.app
```

Without verified App Links, users see a disambiguation dialog — conversion killer.

## Play Install Referrer

Read the referrer on first launch:

```kotlin
class InstallReferrerReader(private val context: Context) {
    suspend fun getReferrer(): String? = suspendCancellableCoroutine { cont ->
        val client = InstallReferrerClient.newBuilder(context).build()
        client.startConnection(object : InstallReferrerStateListener {
            override fun onInstallReferrerSetupFinished(code: Int) {
                if (code == InstallReferrerClient.InstallReferrerResponse.OK) {
                    val referrer = client.installReferrer.installReferrer
                    client.endConnection()
                    cont.resume(parseReferrerUrl(referrer))
                } else {
                    client.endConnection()
                    cont.resume(null)
                }
            }
            override fun onInstallReferrerServiceDisconnected() {
                cont.resume(null)
            }
        })
    }

    private fun parseReferrerUrl(referrer: String): String? {
        // referrer format: utm_source=...&deep_link=https%3A%2F%2Fexample.com%2Fshoes%2Fsale
        return Uri.parse("?$referrer").getQueryParameter("deep_link")
    }
}
```

Call once on first launch, persist the result, and route:

```kotlin
class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Handle direct deep link (app already installed)
        intent?.data?.let { uri -> handleDeepLink(uri); return }

        // Handle deferred deep link (first install)
        if (isFirstLaunch()) {
            lifecycleScope.launch {
                val deferredUri = InstallReferrerReader(this@MainActivity).getReferrer()
                deferredUri?.let { handleDeepLink(it.toUri()) }
            }
        }
    }
}
```

## Unified routing

One function handles both direct and deferred links:

```kotlin
fun handleDeepLink(uri: Uri) {
    when (uri.pathSegments.firstOrNull()) {
        "shoes" -> navController.navigate("shoes/${uri.lastPathSegment}")
        "promo" -> navController.navigate("promo?code=${uri.getQueryParameter("code")}")
        else -> navController.navigate("home")
    }
}
```

Test both paths: click link with app installed (direct), and click link → install → open (deferred).

## Attribution SDKs

For marketing campaigns requiring cross-platform attribution, SDKs like Branch, Adjust, or AppsFlyer handle:
- Link generation with campaign parameters
- Deferred deep linking across platforms
- Install attribution analytics
- Fraud detection

Firebase Dynamic Links was deprecated; Google's recommended path is using App Links + Install Referrer directly, or a third-party attribution SDK for marketing use cases.

If you use an SDK, still implement App Links verification — the SDK relies on the same underlying mechanisms.

## Testing deferred links

```bash
# Simulate install referrer via adb (requires debug build)
adb shell am broadcast -a com.android.vending.INSTALL_REFERRER \
  -n com.example.app/com.example.app.InstallReferrerReceiver \
  --es "referrer" "deep_link=https%3A%2F%2Fexample.com%2Fshoes%2Fsale"
```

Test matrix:
- App installed → click link → correct screen
- App not installed → install → first open → correct screen
- App installed → click link → app in background → correct screen (warm)
- Invalid/broken link → graceful fallback to home

## Common failures

**Referrer read too late.** If your splash screen navigates to home before the referrer callback returns, the user sees a flash of home then jumps — or never jumps. Show a loading state until referrer resolution completes on first launch.

**Missing assetlinks.json.** App Links verification fails silently. Check Play Console → App Links verification status.

**Routing only in onCreate.** Deep links from notifications and [app shortcuts](https://blog.michaelsam94.com/android-app-shortcuts-dynamic/) arrive via `onNewIntent()`. Handle both:

```kotlin
override fun onNewIntent(intent: Intent) {
    super.onNewIntent(intent)
    intent.data?.let { handleDeepLink(it) }
}
```

## Common production mistakes

Teams get deeplink attribution install wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Shipping deeplink attribution install on Android fails quietly when you test only on flagship devices, skip process-death scenarios, or assume `minSdk` behavior matches latest API docs. Emulator-only validation misses OEM-specific battery optimizations and background execution limits.

## Debugging and triage workflow

When deeplink attribution install misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Play Install Referrer latency

Referrer available seconds after first open — defer attribution callback until `InstallReferrerClient` success or timeout. Deferred deep link without referrer still routes via Firebase Dynamic Links successor APIs — verify 2025+ Play Install Referrer migration path.

## Intent filter priority collisions

Multiple activities handling same https host — disambiguation dialog kills conversion. Use single entry Activity dispatching internally; `android:autoVerify` per host once.

## Deeplink Attribution Install Supplement 0 on Samsung and Pixel divergence

Exercise deeplink attribution install supplement 0 on Galaxy A-series and Pixel a-series — emulators hide OEM battery and storage quirks. Capture Macrobenchmark or Firebase trace for the critical path touching deeplink; regressions above 8% block release for `android-deeplink-attribution-install-supplement-0`.

Document permission and background behavior in internal runbook: what breaks under Doze, what requires foreground service, and what Play policy declarations apply. Support tickets referencing "Deeplink Attribution Install Supplement 0" should map to a single runbook section with known workarounds.

## Install regression gates for Play Vitals

Before promoting `android-deeplink-attribution-install-supplement-0` changes past 20% rollout, compare ANR rate, slow cold start, and excessive wakeups against seven-day baseline. Fail rollback review if 0 path shows >5% increase in `slow frames` without documented trade-off approval.

## Resources

- [Android App Links documentation](https://developer.android.com/training/app-links)
- [Play Install Referrer Library](https://developer.android.com/google/play/installreferrer)
- [Verify App Links](https://developer.android.com/training/app-links/verify-android-applinks)
- [Digital Asset Links specification](https://developers.google.com/digital-asset-links/v1/getting-started)
- [Dynamic and pinned app shortcuts](https://blog.michaelsam94.com/android-app-shortcuts-dynamic/)
