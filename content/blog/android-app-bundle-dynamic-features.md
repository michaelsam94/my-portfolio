---
title: "Dynamic Feature Modules with Android App Bundles"
slug: "android-app-bundle-dynamic-features"
description: "Ship smaller Android apps with dynamic feature modules and App Bundles: on-demand delivery, install-time vs conditional modules, and handling install failures."
datePublished: "2024-06-25"
dateModified: "2024-06-25"
tags: ["Android", "App Bundle", "Modularization", "Play Store"]
keywords: "dynamic feature modules, Android App Bundle, on-demand delivery, SplitInstallManager, install-time delivery, deferred install"
faq:
  - q: "What is a dynamic feature module?"
    a: "A dynamic feature module is a Gradle module packaged inside an Android App Bundle but not installed with the base app by default. Google Play delivers it on demand, at install time conditionally, or you can request it at runtime. It lets you keep the initial download small and only ship large or rarely used features to the users who actually need them."
  - q: "When should I use on-demand delivery versus install-time delivery?"
    a: "Use on-demand for features a minority of users need or that are large — a pro editor, an AR mode, a one-time onboarding flow — so the base install stays small. Use install-time (with removable=true optionally) for features most users need but that you still want to be able to uninstall later to reclaim space. Conditional delivery targets device features, countries, or SDK levels at install."
  - q: "How do I handle a dynamic feature that fails to download?"
    a: "Always design the entry point assuming the module might not be present. Request installation through SplitInstallManager, observe the state flow, show progress for large modules, and handle FAILED, canceled, and requires-user-confirmation states. Provide a retry path and never navigate into feature code before confirming the module installed and the split was applied."
---

Dynamic feature modules let you ship an Android app where the base download is small and the heavy, optional, or rarely-used parts arrive only when a user actually needs them. Packaged inside an Android App Bundle, a dynamic feature isn't installed with the base app — Google Play delivers it on demand at runtime, conditionally at install time, or deferred for later. I've used this to cut a base install from 40MB to under 15MB by pushing an AR try-on feature, a document scanner, and a bulky onboarding video flow into modules that only ~20% of users ever downloaded. The engineering cost is that every entry point into a dynamic feature has to assume the code might not be there yet.

## App Bundles are the foundation

None of this works without publishing an `.aab` rather than a monolithic APK. The App Bundle contains your base module plus every feature and configuration split; Play's Dynamic Delivery generates and serves optimized APKs per device — only the density, ABI, and language resources that device needs, plus whichever feature modules are requested. That per-device splitting alone shrinks downloads meaningfully before you add a single dynamic feature. Dynamic features build on that same splitting machinery.

## The three delivery modes

The delivery mode lives in the feature module's manifest and decides *when* the module ships:

- **On-demand** — not installed initially; your app requests it at runtime via the Play Core `SplitInstallManager`. Best for large or minority features.
- **Install-time** — installed with the base app, but as a separate split. Useful when you want modular code organization and the option to later mark it `removable` so users can reclaim space.
- **Conditional** — installed at first install *if* device conditions match (minimum SDK, device feature like a specific sensor, or country). Great for shipping a feature only to hardware that can use it.

```xml
<!-- feature module AndroidManifest.xml -->
<dist:module
    dist:instant="false"
    dist:title="@string/scanner_feature_title">
    <dist:delivery>
        <dist:on-demand />
    </dist:delivery>
    <dist:fusing dist:include="true" />
</dist:module>
```

The `<dist:fusing>` flag matters for legacy: on pre-Lollipop devices that can't do splits, fused modules get merged into the base APK. If you still support very old devices, plan for that.

## Requesting an on-demand module

The runtime flow uses `SplitInstallManager`. The key discipline is treating installation as an async operation with a full set of states, not a fire-and-forget call:

```kotlin
val manager = SplitInstallManagerFactory.create(context)

val request = SplitInstallRequest.newBuilder()
    .addModule("scanner")
    .build()

manager.registerListener { state ->
    when (state.status()) {
        SplitInstallSessionStatus.DOWNLOADING -> {
            val pct = state.bytesDownloaded() * 100 / state.totalBytesToDownload()
            showProgress(pct.toInt())
        }
        SplitInstallSessionStatus.REQUIRES_USER_CONFIRMATION ->
            manager.startConfirmationDialogForResult(state, activity, REQ_CODE)
        SplitInstallSessionStatus.INSTALLED -> launchScanner()
        SplitInstallSessionStatus.FAILED -> showError(state.errorCode())
        SplitInstallSessionStatus.CANCELED -> { /* let user retry */ }
    }
}

manager.startInstall(request)
    .addOnFailureListener { e -> showError(e) }
```

Two states people forget: `REQUIRES_USER_CONFIRMATION` fires when the download exceeds a size threshold on a metered connection, and you *must* forward it to a system confirmation dialog or the install stalls forever. And large modules should show real progress — silently waiting 15 seconds on a big AR module reads as a frozen app.

## The part everyone gets wrong: accessing the code

After `INSTALLED`, the split's code and resources are present but the *current* process may not have them wired into its classloader and resource table until you refresh the context. On many setups you need `SplitCompat` so the newly installed split is usable immediately:

```kotlin
class MyApp : SplitCompatApplication()   // enables SplitCompat app-wide
```

And you never reference feature classes directly from the base — the base can't compile against a module that may be absent. You cross the boundary through reflection-free indirection: define an interface in the base, implement it in the feature, and instantiate it via a `Class.forName` bridge or a navigation deep link that only resolves once the module is installed. Getting this boundary clean is the same modular-architecture discipline as [clean architecture done pragmatically](https://blog.michaelsam94.com/clean-architecture-pragmatically/) — the base defines contracts, features fulfill them.

## Testing is genuinely harder

Dynamic delivery only fully works through Play, which complicates local testing. The tools that make it bearable:

- **`bundletool`** to build APK sets from your `.aab` and install them locally so you exercise the split boundaries.
- **Internal app sharing** on Play, which serves real Dynamic Delivery to test devices without a full release.
- **`FakeSplitInstallManager`** in tests to simulate install, failure, and cancellation states without hitting the network.

Skipping this and testing only the monolithic debug build is how you ship a feature that works in QA and crashes in production the moment the module isn't already present. Always test the "module not installed yet" path explicitly.

## When it's worth it — and when it isn't

Dynamic features are worth the complexity when a feature is genuinely large (tens of MB of native libs, ML models, media) or used by a clear minority. They are *not* worth it to shave a couple hundred KB off a screen everyone uses — the runtime install flow, the failure handling, and the split boundary add real cost and real bug surface. My rule: reach for a dynamic feature when the size saved is measured in double-digit megabytes or the feature is conditional on hardware most devices lack. For everything else, keep it in the base and let App Bundle's per-device configuration splits do the shrinking for free.

The honest trade-off is that you're exchanging a smaller install for a more complex runtime and a harder testing story. When the feature is big enough, that trade is clearly worth it — and Play's per-device splitting means even a monolithic bundle already downloads smaller than the old universal APK it replaces.

## Resources

- [About Android App Bundles](https://developer.android.com/guide/app-bundle)
- [Configure dynamic feature delivery](https://developer.android.com/guide/playcore/feature-delivery)
- [On-demand feature delivery with Play Feature Delivery](https://developer.android.com/guide/playcore/feature-delivery/on-demand)
- [Play Feature Delivery overview](https://developer.android.com/guide/playcore)
- [Build and test with bundletool](https://developer.android.com/tools/bundletool)
