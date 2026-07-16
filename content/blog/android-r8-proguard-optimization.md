---
title: "R8 Optimization: Shrinking Android Apps the Right Way"
slug: "android-r8-proguard-optimization"
description: "How R8 shrinks, optimizes, and obfuscates Android apps: keep rules that actually work, avoid over-keeping, and debug crashes with retrace and mapping files."
datePublished: "2024-06-24"
dateModified: "2024-06-24"
tags: ["Android", "Build", "R8", "Performance"]
keywords: "R8, ProGuard rules, Android code shrinking, keep rules, minifyEnabled, obfuscation, mapping file, retrace"
faq:
  - q: "What is the difference between R8 and ProGuard?"
    a: "R8 is Google's replacement for ProGuard, built into the Android Gradle Plugin. It does shrinking, optimization, obfuscation, and desugaring in a single pass and reads the same ProGuard-format keep rules, so most projects migrate transparently. R8 is generally faster and produces smaller output than legacy ProGuard, and it's the default and recommended tool today."
  - q: "Why does my release build crash but debug works?"
    a: "Almost always because R8 removed or renamed something accessed via reflection, serialization, or JNI that it couldn't see was used. Code that's referenced only by name — Gson field mapping, reflective instantiation, JNI native methods — needs a keep rule, because R8 statically analyzes reachability and can't follow a reflective call. The fix is a targeted -keep rule, not disabling minification."
  - q: "How do I read a stack trace from an obfuscated release build?"
    a: "R8 emits a mapping.txt file that maps obfuscated names back to originals. Keep the mapping file for every release you ship, upload it to your crash reporter, and use the retrace tool to de-obfuscate raw stack traces. Without the mapping file for that exact build, an obfuscated trace is nearly useless, so archiving mappings per release is non-negotiable."
---

R8 is the difference between a 30MB app and a 15MB one, and between a release build that runs 20% less code and one that ships every unused method your dependencies dragged in. It's the tool the Android Gradle Plugin runs when you set `minifyEnabled true` — shrinking unreachable code and resources, optimizing what's left, and obfuscating names, all in one pass. The catch is that R8 works by *static reachability analysis*, and anything your app reaches by name at runtime — reflection, serialization, JNI — is invisible to that analysis. Getting R8 right is mostly about telling it the truth about those blind spots without over-keeping half your app.

## What R8 actually does

Enabling it is one flag per build type:

```kotlin
android {
    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }
}
```

Under the hood R8 performs four jobs:

1. **Shrinking (tree-shaking):** starting from entry points (your manifest components, keep rules), it walks the reachable call graph and deletes everything it can't reach.
2. **Optimization:** inlining, class merging, dead-branch elimination, devirtualization — real bytecode optimization, not just renaming.
3. **Obfuscation:** renaming classes, methods, and fields to short names (`a`, `b`, `c`), which shrinks the DEX and incidentally makes reverse engineering harder.
4. **Desugaring:** rewriting newer language features for older API levels.

The `proguard-android-optimize.txt` default file (note the `-optimize` variant) enables the optimization passes; plenty of projects accidentally use the non-optimize default and leave performance on the table.

## The blind spot: reachability vs reflection

Here's the entire mental model you need. R8 keeps what it can *see* is used. If class `PaymentRequest` is only ever instantiated via `gson.fromJson(json, PaymentRequest::class.java)`, R8's graph walk never sees a constructor call — it sees a `Class<?>` passed to a library — so it may strip fields, rename them, or remove the class. Result: your release build crashes or silently deserializes `null` fields while debug is fine.

The categories that need keep rules:

- **Reflection-based serialization** (Gson, older Moshi setups). Fields matched by name must keep their names.
- **Reflective instantiation** — anything created by `Class.forName(...).newInstance()`.
- **JNI native methods** — the native side looks them up by exact name/signature.
- **Enums used by `valueOf`** in serialization.
- **Classes referenced only from XML/manifest by string** that AGP doesn't auto-detect.

## Writing keep rules that don't over-keep

The lazy fix is `-keep class com.myapp.** { *; }`, which keeps everything in your package — and completely defeats shrinking and obfuscation for that package. Don't. Write the *narrowest* rule that covers the actual need:

```proguard
# Keep model fields for Gson (names + fields), but let R8 obfuscate everything else.
-keepclassmembers class com.example.model.** {
    <fields>;
    <init>();
}

# Keep native methods by name/signature; obfuscate the rest of the class.
-keepclasseswithmembernames class * {
    native <methods>;
}

# Keep an enum used via valueOf in serialization.
-keepclassmembers enum com.example.PaymentStatus {
    public static **[] values();
    public static ** valueOf(java.lang.String);
}
```

Note `-keepclassmembers` vs `-keep`. `-keep` protects the class *and* its members from removal and renaming; `-keepclassmembers` only protects members *if the class is otherwise kept*, which lets R8 still remove the class if it's genuinely unused. The distinction is the difference between surgical and sledgehammer.

The best keep rules are the ones you don't write: modern libraries ship `consumer-rules.pro` inside their AARs so their reflection needs travel with them. Prefer libraries that do this, prefer codegen (Moshi's codegen, kotlinx.serialization) over runtime reflection, and your own keep file stays tiny.

## Don't debug crashes by disabling minification

When a release build crashes and debug doesn't, the instinct is to flip `minifyEnabled false` and ship. That's not a fix — it just hides the reachability bug and ships a bloated app. The correct loop:

1. Reproduce with `minifyEnabled true` (obviously).
2. Read the de-obfuscated stack trace to find the class R8 stripped or renamed.
3. Add the *narrowest* keep rule for that specific need.
4. Confirm the fix and confirm shrinking still happened (check the size didn't balloon).

Use `-printusage` and `-printseeds` (or R8's `--pg-conf-output`) to see what R8 removed and what your rules kept — that's how you catch an over-broad rule that silently disabled shrinking.

## Mapping files are not optional

Every obfuscated release produces a `mapping.txt` under `build/outputs/mapping/release/`. It maps `a.b.c()` back to `com.example.CheckoutViewModel.submitOrder()`. Without the mapping file *for that exact build*, a production crash report is a wall of single letters. So:

- **Archive the mapping file per release**, keyed to the version code. Losing it means you can never de-obfuscate that version's crashes.
- **Upload it to your crash reporter** (Crashlytics, Sentry) so traces are de-obfuscated automatically.
- For raw traces, run the **`retrace`** tool with the mapping file to reconstruct the original names.

I've seen teams ship a release, get a crash spike, and have zero readable traces because nobody kept the mapping. Wire the upload into your CI release job so it's impossible to forget — the same "make the right thing automatic" principle behind a solid [CI pipeline](https://blog.michaelsam94.com/fast-cicd-pipelines/).

## What good R8 hygiene looks like

The apps that get the full benefit share a few habits: minification and resource shrinking on for release, the `-optimize` default file in use, a small hand-written keep file (because dependencies bring their own consumer rules and the app avoids runtime reflection), mapping files archived and uploaded per build, and a size check in CI so a dependency bump that breaks shrinking shows up as a regression. Done well, R8 is one of the highest-leverage, lowest-effort wins on Android: smaller downloads, less code executing at runtime, and a modest bump in reverse-engineering resistance — for the cost of one Gradle flag and a disciplined keep file.

## Resources

- [Shrink, obfuscate, and optimize your app (Android)](https://developer.android.com/build/shrink-code)
- [R8 keep rules and configuration](https://developer.android.com/build/shrink-code#keep-code)
- [Retrace obfuscated stack traces](https://developer.android.com/build/shrink-code#retracing)
- [R8 full mode documentation](https://developer.android.com/build/shrink-code#full-mode)
- [ProGuard keep-rule reference (Guardsquare)](https://www.guardsquare.com/manual/configuration/usage)
