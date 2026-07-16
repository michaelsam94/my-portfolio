---
title: "Shared Resources in Compose Multiplatform"
slug: "kotlin-multiplatform-compose-resources"
description: "Manage shared strings, images, and fonts in Compose Multiplatform with the compose-resources library: generation, qualifiers, and platform overrides."
datePublished: "2025-12-15"
dateModified: "2025-12-15"
tags: ["Android", "Kotlin"]
keywords: "Compose Multiplatform resources, compose-resources, shared strings, Res.string, KMP assets, localization"
faq:
  - q: "How does compose-resources differ from Android res/ folders?"
    a: "compose-resources lives in commonMain composeResources/ and generates type-safe accessors usable on Android, iOS, Desktop, and Web. Android res/ remains platform-specific. KMP shared code uses generated Res.drawable and Res.string instead of R.string."
  - q: "Can I localize strings per language in KMP?"
    a: "Yes. Place strings in composeResources/values/strings.xml for default and composeResources/values-fr/strings.xml for French. The generator produces accessors that resolve locale at runtime using Compose Multiplatform locale APIs."
  - q: "Do vector drawables work on all targets?"
    a: "XML vectors work on Android and Desktop; iOS and Web may require PNG or SVG depending on version. Check target-specific docs—provide expect/actual assets when vector support differs."
---

Hardcoding `"Sign in"` in shared Composables worked until marketing added Finnish. Someone duplicated strings in androidMain and iosMain; they drifted within a sprint. **Compose Multiplatform Resources** centralizes assets in `commonMain`, generates typed `Res` accessors, and keeps one source of truth for strings, images, and fonts across targets.

The `compose-resources` Gradle plugin (org.jetbrains.compose) replaces manual `expect/actual` resource loaders for most cases.

## Project setup

```kotlin
// shared/build.gradle.kts
plugins {
    id("org.jetbrains.compose")
    id("org.jetbrains.kotlin.multiplatform")
    id("org.jetbrains.compose.resources") version "1.7.3"
}

kotlin {
    sourceSets {
        commonMain.dependencies {
            implementation(compose.components.resources)
        }
    }
}
```

Directory layout:

```
shared/src/commonMain/composeResources/
  drawable/
    logo.xml
  font/
    Inter-Regular.ttf
  values/
    strings.xml
  values-es/
    strings.xml
```

## Strings and usage

`values/strings.xml`:

```xml
<resources>
    <string name="sign_in">Sign in</string>
    <string name="welcome">Welcome, %s</string>
</resources>
```

Generated usage:

```kotlin
@Composable
fun SignInScreen() {
    Text(stringResource(Res.string.sign_in))
    Text(stringResource(Res.string.welcome, userName))
}
```

Import `org.jetbrains.compose.resources.stringResource` and generated `Res`.

## Images and vectors

```kotlin
Image(
    painter = painterResource(Res.drawable.logo),
    contentDescription = stringResource(Res.string.app_name)
)
```

Place PNGs in `drawable/` for universal support; XML vectors where supported.

## Fonts

```kotlin
@Composable
fun BrandedText() {
    val font = FontFamily(Font(Res.font.Inter-Regular))
    Text("Hello", fontFamily = font)
}
```

Load once per theme, not per Text composable, to avoid repeated IO.

## Qualifiers and density

Use drawable directories for density-specific bitmaps:

```
composeResources/drawable-mdpi/icon.png
composeResources/drawable-xhdpi/icon.png
```

The resource system picks appropriate variant similar to Android qualifiers.

## Platform-specific overrides

When one target needs different assets, use target source sets:

```
iosMain/composeResources/drawable/  // override or addition
```

Or keep platform-specific splash screens in native projects while sharing in-app icons from common.

## Build and IDE support

Generated `Res` class lives under `build/generated/compose/resourceGenerator`. Sync Gradle after adding resources. CI must run resource generation before compile—standard with Compose plugin.

Version compose-resources with Compose Multiplatform BOM to avoid mismatches.

## Migration from expect/actual

Replace:

```kotlin
// old
expect fun appName(): String
```

With `stringResource(Res.string.app_name)` in Composables, or `getString(Res.string.app_name)` in non-Composable code via `Res.getUri()` patterns documented for each release.

## Plurals and accessibility strings

Android-style plurals work in `composeResources/values/strings.xml`:

```xml
<plurals name="items_in_cart">
    <item quantity="one">%d item</item>
    <item quantity="other">%d items</item>
</plurals>
```

```kotlin
Text(pluralStringResource(Res.plurals.items_in_cart, count, count))
```

Keep `contentDescription` strings in resources alongside visible text—TalkBack reads the same `composeResources` tree on Android, and iOS accessibility labels can reference shared keys through platform wrappers where needed.

## CI and cache invalidation

Resource changes invalidate incremental builds correctly when files live under `composeResources/`. In CI, do not cache `build/generated/compose/resourceGenerator` across different branches without also caching the source XML—stale generated `Res` classes cause compile errors that look like missing imports. A clean `./gradlew :shared:compileKotlinIosArm64` after resource edits catches cross-target issues early.

When renaming a string key, grep the repo for the old generated accessor—IDE refactor sometimes misses `Res.string.old_key` in commonTest.

## What to measure after rollout

Track error rates, tail latency, and resource utilization for two weeks after changes land—most regressions appear under real traffic mixes, not in staging smoke tests. Keep a rollback path documented: feature flags, Helm revision, or Git revert with known good digest. Review on-call pages tied to the topic quarterly; delete alerts that never fire and add thresholds that would have caught your last incident.

Run a short blameless postmortem if production surprised you, even for minor issues. The goal is updating this runbook section with one concrete lesson per quarter so the next engineer inherits context, not just configuration snippets.


## Documentation your team should maintain

Maintain a one-page runbook link from your main service README: prerequisites, owner rotation, last drill date, and known sharp edges. Link to vendor docs in the Resources section below but capture org-specific decisions (CIDR ranges, cluster names, approval gates) in internal docs that stay current. New hires should deploy a safe canary within a week using only that runbook—if they cannot, the doc is incomplete.


## Pre-production checklist

Before promoting to production, walk through this list with someone who was not the primary author—fresh eyes catch assumptions.

- **Staging parity**: The staging environment exercises the same code paths as production, including failure modes you expect to handle (timeouts, retries, partial outages).
- **Observability**: Dashboards and alerts exist for the metrics and log patterns discussed above; on-call knows where to look first.
- **Rollback**: You can revert to the previous known-good state in one documented step without improvising.
- **Access control**: Only the principals that need access have it; audit logs are enabled where the topic touches secrets or infrastructure APIs.
- **Load test**: You have evidence—not intuition—about behavior at expected peak plus headroom.

If any item is "we will do that later," treat it as a release blocker for tier-1 services.


## Common questions from reviewers

Reviewers and auditors often ask whether this approach scales with team growth and whether it fails safely. Answer explicitly in your design doc: what happens when dependencies are down, when credentials expire, and when traffic doubles overnight. Prefer defaults that deny or degrade gracefully over defaults that fail open. Document known limits (throughput ceilings, supported versions, regions) in the same place operators look during incidents—avoid scattering critical constraints across Slack threads.


## Version and compatibility notes

Pin library and control-plane versions in production manifests; track upstream release notes quarterly. Run upgrade drills in non-production before bumping minor versions that touch serialization, auth, or CRD schemas. Keep a compatibility matrix in your internal wiki listing supported Kubernetes, broker, and SDK versions validated together.

## Resources

- [Compose Multiplatform resources docs](https://www.jetbrains.com/help/kotlin-multiplatform-dev/compose-images-resources.html) — official setup guide
- [compose-resources GitHub](https://github.com/JetBrains/compose-multiplatform-core/tree/master/components/resources) — source and issue tracker
- [Localization in KMP](https://kotlinlang.org/docs/multiplatform-localization.html) — broader i18n strategies
- [Compose Multiplatform changelog](https://github.com/JetBrains/compose-multiplatform/releases) — breaking changes per version
