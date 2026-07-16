---
title: "Edge-to-Edge Is Mandatory: Handling Insets in Android 16"
slug: "edge-to-edge-android-16"
description: "Android 16 makes edge-to-edge non-optional. A practical guide to window insets in Jetpack Compose — system bars, cutouts, IME — without content hiding behind bars."
datePublished: "2026-04-01"
dateModified: "2026-04-01"
tags: ["Android", "Jetpack Compose", "Android 16", "UI"]
keywords: "edge-to-edge Android, window insets, Android 16, edge to edge Compose, system bars, WindowInsets, IME insets"
faq:
  - q: "Is edge-to-edge mandatory in Android 16?"
    a: "Yes. For apps targeting SDK 36 (Android 16), the framework no longer honors the deprecated APIs that opted out of edge-to-edge, so your app draws behind the system bars by default. You must handle insets yourself or content will sit under the status and navigation bars."
  - q: "How do I handle window insets in Jetpack Compose?"
    a: "Use the WindowInsets APIs — Modifier.windowInsetsPadding, Modifier.safeDrawingPadding, or consume specific insets like WindowInsets.systemBars and WindowInsets.ime. Apply them at the right level so backgrounds still draw edge-to-edge while content stays clear of the bars."
  - q: "What's the difference between safeDrawing, systemBars, and ime insets?"
    a: "systemBars covers the status and navigation bars. ime is the on-screen keyboard. safeDrawing is the union of everything content should avoid — system bars, display cutouts, and the IME — so it's the safest default for interactive content."
---

Android 16 removed the escape hatch. If your app targets SDK 36, the framework ignores the old `setDecorFitsSystemWindows` and the `statusBarColor` / `navigationBarColor` opt-outs, so your app draws edge-to-edge whether you planned for it or not. That means content behind the status bar, buttons under the gesture bar, and text fields hidden by the keyboard — unless you handle **window insets** deliberately. Edge-to-edge on Android 16 isn't a design nicety anymore; it's a correctness requirement.

I've retrofitted edge-to-edge into apps that predate Compose and built it in from scratch on new ones. The good news: in Compose, once you understand the inset model, it's a handful of modifiers applied at the right layers. The bad news: apply them at the wrong layer and you either lose the edge-to-edge look or clip your content.

## What "edge-to-edge" actually means

Edge-to-edge means your app draws under the system bars — the status bar at the top, the navigation/gesture bar at the bottom, and around display cutouts (notches, punch-holes). The system bars become translucent overlays on your content. The *point* is a more immersive, modern look where your background color or image extends to the physical edges of the screen.

The complication is that some of your UI must **not** sit under those bars: a top app bar's title, a bottom button, a text field the keyboard would cover. Insets are the measurements the system gives you — "the status bar is 48dp tall here, the gesture bar is 24dp" — so you can pad interactive content inward while backgrounds stay full-bleed.

## Enable it, then handle it

In an Activity you enable edge-to-edge once. On Android 16 targeting SDK 36 this is effectively the default, but calling it explicitly keeps behavior consistent on older OS versions:

```kotlin
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        setContent { App() }
    }
}
```

From there it's all about applying insets in Compose. The three tools you'll reach for constantly:

```kotlin
// Pad content clear of ALL system UI (bars + cutout + IME). Safe default.
Modifier.safeDrawingPadding()

// Pad only for a specific inset — e.g. keep a bottom bar above the gesture area.
Modifier.windowInsetsPadding(WindowInsets.navigationBars)

// Consume an inset so children don't double-apply it.
Box(Modifier.consumeWindowInsets(WindowInsets.statusBars)) { /* ... */ }
```

## The layering rule that prevents 90% of bugs

Here's the principle I wish someone had drilled into me earlier: **backgrounds go edge-to-edge, content gets padded, and you consume insets exactly once.** Concretely:

- Put your `Surface`/background at the root with **no** inset padding — it should fill the whole window, under the bars.
- Apply `safeDrawingPadding()` (or specific insets) to the **content** inside, so text and controls stay clear.
- If a parent already padded for an inset, `consumeWindowInsets` so children don't add it a second time — double insets are the classic "why is there a huge gap" bug.

Material 3's `Scaffold` does a lot of this for you. It reads insets and passes them through `contentPadding`, and its `TopAppBar` and `BottomBar` handle their own inset padding. The mistake is ignoring the `innerPadding` it hands you:

```kotlin
Scaffold(
    topBar = { TopAppBar(title = { Text("Chargers") }) }
) { innerPadding ->
    LazyColumn(
        contentPadding = innerPadding, // don't drop this
        modifier = Modifier.fillMaxSize()
    ) { /* items */ }
}
```

Passing `innerPadding` to `contentPadding` (not `Modifier.padding`) is what lets the list scroll *under* the bars while the first and last items stay visible — the ideal edge-to-edge scroll feel.

## The keyboard (IME) is an inset too

The on-screen keyboard is `WindowInsets.ime`, and it's animated. For a screen with a text field near the bottom, you want the content to move up as the keyboard appears:

```kotlin
Column(
    Modifier
        .fillMaxSize()
        .imePadding()          // pushes content above the keyboard
        .verticalScroll(rememberScrollState())
) {
    // form fields
}
```

Combine `imePadding()` with a scrollable container and the field stays visible as the keyboard animates in. Skip it, and users type blind behind the keyboard — one of the most common complaints in edge-to-edge migrations.

## Testing across the shapes that break things

Insets vary wildly across devices, so test on the shapes that expose bugs:

| Scenario | What to check |
| --- | --- |
| Gesture nav vs 3-button nav | Bottom bar spacing differs; 3-button is taller |
| Landscape with cutout | Content must avoid the side cutout |
| Keyboard open on a form | Fields stay visible, no clipping |
| Foldable unfolded | Insets recompute on configuration change |
| RTL locale | Left/right insets swap correctly |

A tactic that saved me hours: temporarily give inset-padded containers a debug background tint so you can *see* whether padding lands where you expect. Once it's right, remove the tint.

Edge-to-edge fits neatly into the broader Android UI modernization story — it pairs with [predictive back gestures](https://blog.michaelsam94.com/predictive-back-gestures-android/) and the Compose migration work I've written about in [ten years of Jetpack Compose lessons](https://blog.michaelsam94.com/jetpack-compose-lessons-10-years-android/). Get the inset model right once, build it into your design-system components, and every new screen inherits correct behavior for free. That's the real win: it stops being a per-screen chore and becomes a property of your scaffolding.

## Resources

- [Display content edge-to-edge](https://developer.android.com/develop/ui/views/layout/edge-to-edge)
- [Edge-to-edge in Compose](https://developer.android.com/develop/ui/compose/system/insets)
- [WindowInsets reference](https://developer.android.com/reference/kotlin/androidx/compose/foundation/layout/WindowInsets)
- [Android 16 behavior changes](https://developer.android.com/about/versions/16/behavior-changes-16)
- [Material 3 Scaffold](https://developer.android.com/jetpack/compose)
- [Android developers blog](https://android-developers.googleblog.com/)

*Retrofitting edge-to-edge across an app and hitting inset gremlins? [Let's talk](/#contact).*
