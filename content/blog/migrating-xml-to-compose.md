---
title: "Migrating XML to Compose Without a Rewrite"
slug: "migrating-xml-to-compose"
description: "Incremental XML-to-Compose migration for production Android apps: ComposeView/AndroidView interop, feature flags, and stable ViewModel boundaries — no rewrite."
datePublished: "2026-04-02"
dateModified: "2026-04-05"
tags: ["Android", "Jetpack Compose", "Migration", "Kotlin"]
keywords: "XML to Compose migration, Compose interop, AndroidView, ComposeView, incremental migration, hybrid UI"
faq:
  - q: "Do I have to rewrite my whole app to adopt Jetpack Compose?"
    a: "No. Compose and the View system interoperate in both directions. You can host Compose inside an XML layout with ComposeView and host legacy Views inside Compose with AndroidView, which lets you migrate one screen or component at a time while continuing to ship."
  - q: "Where should I start an XML-to-Compose migration?"
    a: "Start with a new, self-contained screen or a leaf component like an item in a list. Avoid starting with your most complex screen. Getting the theming bridge and one real screen right first de-risks the rest."
  - q: "Can Compose and XML share the same ViewModel?"
    a: "Yes. Both a Fragment rendering XML and a composable can observe the same ViewModel and its StateFlow. Keeping business logic in the ViewModel and out of the UI layer is exactly what makes an incremental migration safe."
---

The question I get most often about Compose isn't "how does recomposition work" — it's "do we have to stop everything and rewrite?" The answer is no, and treating it as a rewrite is how migrations die. Compose was designed to **interoperate with the View system in both directions**, so you can migrate an XML app screen by screen, or even component by component, while continuing to ship features the entire time. I've taken apps with hundreds of thousands of users through this over several releases without a single big-bang merge, and crash-free rates never wobbled because nothing changed wholesale.

The whole strategy rests on two interop bridges: `ComposeView` to put Compose *inside* XML, and `AndroidView` to put existing Views *inside* Compose. Get comfortable with those and the migration becomes a series of small, reviewable, individually shippable steps.

## Compose inside XML: `ComposeView`

The most common first move is embedding a composable into an existing XML-based screen. Add a `ComposeView` to the layout like any other view:

```xml
<androidx.compose.ui.platform.ComposeView
    android:id="@+id/compose_header"
    android:layout_width="match_parent"
    android:layout_height="wrap_content" />
```

Then wire it up in the Fragment or Activity:

```kotlin
binding.composeHeader.apply {
    setViewCompositionStrategy(
        ViewCompositionStrategy.DisposeOnViewTreeLifecycleDestroyed
    )
    setContent {
        AppTheme {
            ProfileHeader(user = viewModel.user.collectAsStateWithLifecycle().value)
        }
    }
}
```

Two things are non-negotiable here. Set a **`ViewCompositionStrategy`** — `DisposeOnViewTreeLifecycleDestroyed` is right for Fragments and prevents the composition from leaking past the view lifecycle. And wrap `setContent` in your app theme, because a `ComposeView` doesn't inherit the XML theme automatically. Forgetting the theme is the number one "why do my colors look wrong" bug in early migrations.

## Views inside Compose: `AndroidView`

Going the other way, when you've moved a screen to Compose but still depend on a custom View — a charting library, a map, a legacy widget nobody wants to rewrite yet — host it with `AndroidView`:

```kotlin
@Composable
fun LegacyChart(dataPoints: List<Point>, modifier: Modifier = Modifier) {
    AndroidView(
        modifier = modifier,
        factory = { context -> ChartView(context) }, // created once
        update = { view -> view.setData(dataPoints) }, // called on recomposition
    )
}
```

The mental split matters: `factory` runs once to create the View, `update` runs whenever the composable recomposes with new data. Put creation in `factory` and data binding in `update`, and the interop behaves. This is how a MapView, a WebView, or an `AdView` survives the transition untouched while everything around it becomes Compose.

## The theming bridge

The trickiest early decision is theming, because you'll have both systems live at once. You don't want to maintain two disconnected sources of truth for colors and typography. The pragmatic path is a **bridge**: derive your Compose `MaterialTheme` values from the same source as your XML theme, or use the `Mdc3Theme` / adapter from `accompanist-themeadapter`-style approaches during the interim so a `ComposeView` picks up the Material Components theme already defined in XML.

Whichever bridge you choose, define it once and reuse it everywhere. The goal is that a button rendered in Compose is visually indistinguishable from the XML button next to it, so users never see a seam mid-migration.

## Sequencing: what to migrate first

Order matters more than speed. A sequence that consistently works:

1. **Stand up the theme bridge and one leaf component.** Migrate a single list item or a header. Small, low-risk, proves the plumbing.
2. **Migrate a whole new screen in Compose.** Anything net-new should be Compose from day one — you're not migrating, you're just not adding to the XML pile.
3. **Convert self-contained existing screens.** Settings, profile, detail screens — leaf screens with few dependencies.
4. **Tackle the hub screens last.** Your main feed or dashboard is usually the most entangled; do it once you've built muscle memory.

Do **not** start with your hardest screen. I've seen teams pick the 2,000-line home screen as screen one, get stuck for a month, and conclude "Compose isn't ready." The framework was ready; the sequencing wasn't.

## What makes it safe: architecture, not luck

Incremental migration only stays safe if the UI layer is thin. If business logic lives in the Fragment, every migration drags logic along with it and each step is risky. When logic lives in a **ViewModel exposing an immutable `UiState` via `StateFlow`**, the XML Fragment and the new composable are just two renderers of the same state — you swap one for the other without touching what the screen *does*. That Clean Architecture boundary is what turns a scary rewrite into a mechanical substitution, and it's the same discipline I described in [Jetpack Compose lessons from 10 years of Android](https://blog.michaelsam94.com/jetpack-compose-lessons-10-years-android/).

Guard each migrated screen behind a feature flag during rollout so you can revert a specific screen without a hotfix if something regresses. Pairing incremental UI migration with [trunk-based development and feature flags](https://blog.michaelsam94.com/feature-flags-trunk-based-development/) is what let me keep merging to main daily throughout a multi-release migration.

## Common traps

- **Missing theme wrap** on a `ComposeView`, producing default Material colors instead of yours.
- **Doing data binding in `factory`** instead of `update`, so the hosted View never refreshes.
- **Nested scrolling conflicts** when a Compose scrollable hosts an `AndroidView` that also scrolls — resolve with nested scroll interop rather than fighting gestures.
- **Two theme sources drifting apart**, causing subtle color mismatches. Bridge once, centrally.
- **Trying to finish in one release.** Migrations that must land all at once never land. Ship continuously.

Compose interop isn't a compromise you tolerate — it's the intended migration path. Bridge the theme, host in both directions, migrate leaf-to-hub behind flags, and keep the logic in the ViewModel. Done that way, "migrating to Compose" stops being a project with a deadline and becomes something your team just does, one green PR at a time.

## Resources

- [Migrating to Jetpack Compose — official guide](https://developer.android.com/develop/ui/compose/migrate)
- [Interoperability APIs](https://developer.android.com/develop/ui/compose/migrate/interoperability-apis)
- [ComposeView reference](https://developer.android.com/reference/androidx/compose/ui/platform/ComposeView)
- [AndroidView in Compose](https://developer.android.com/develop/ui/compose/migrate/interoperability-apis/views-in-compose)
- [Compose and Material theming](https://developer.android.com/develop/ui/compose/designsystems/material3)
- [Migration strategy guidance](https://developer.android.com/develop/ui/compose/migrate/strategy)
