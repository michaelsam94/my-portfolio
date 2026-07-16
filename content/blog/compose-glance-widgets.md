---
title: "Building Home-Screen Widgets with Glance"
slug: "compose-glance-widgets"
description: "Build home-screen Glance widgets on Android: a Compose-style API over RemoteViews, managing Glance state, actions, and the real rendering constraints."
datePublished: "2026-02-20"
dateModified: "2026-02-20"
tags: ["Android", "Jetpack Compose", "Widgets"]
keywords: "Glance widgets, Jetpack Glance, app widgets Compose, home screen widget Android, Glance state"
faq:
  - q: "What is Jetpack Glance?"
    a: "Jetpack Glance is a library that lets you build Android app widgets and other remote surfaces using a Compose-style declarative API. You write composables with Glance's own components, and the library translates them into RemoteViews, the actual mechanism the launcher process uses to render a widget. It gives you Compose ergonomics for widgets without letting you use the full androidx.compose.ui toolkit, which doesn't run in the launcher."
  - q: "Can I use regular Jetpack Compose components in a widget?"
    a: "No. A widget renders inside the launcher's process via RemoteViews, which supports only a limited set of view types, so you can't use androidx.compose.ui composables like Box or Text from the standard UI toolkit. Glance provides its own parallel components — GlanceModifier, Column, Row, Text, Button, Image — that map onto RemoteViews. The mental model is Compose, but the component set is deliberately restricted."
  - q: "How does state work in a Glance widget?"
    a: "Glance widgets are stateless between updates and can't hold in-memory state like an app UI, because the launcher can recreate them at any time. Instead you persist state — commonly via GlanceStateDefinition backed by DataStore — and read it inside provideGlance. When the underlying data changes, you trigger an update so Glance recomposes the widget from the persisted state."
---

Home-screen widgets used to mean hand-assembling `RemoteViews` — a clunky, imperative API where you inflate an XML layout and call `setTextViewText` and `setOnClickPendingIntent` against view IDs. Jetpack Glance replaces that with a Compose-style declarative API: you write composables, and Glance compiles them down to the `RemoteViews` the launcher actually needs. You get familiar ergonomics — `Column`, `Row`, `Text`, `GlanceModifier` — for a surface that historically fought you at every step.

The catch, and the thing every first-timer trips on, is that a widget is *not* your app's UI. It renders in the launcher's process, under tight constraints, with no access to the full Compose toolkit. Glance gives you the syntax of Compose but a deliberately smaller world. Understand that boundary and widgets become pleasant; ignore it and you'll spend an afternoon wondering why `androidx.compose.ui`'s `Box` won't import.

## Glance is Compose-shaped, not Compose

The first thing to internalize: Glance has its *own* component library that mirrors Compose but maps to `RemoteViews` primitives. You import from `androidx.glance`, not `androidx.compose.ui`. A minimal widget looks like this:

```kotlin
class CounterWidget : GlanceAppWidget() {
    override suspend fun provideGlance(context: Context, id: GlanceId) {
        provideContent {
            val count = currentState(key = intPreferencesKey("count")) ?: 0
            Column(
                modifier = GlanceModifier.fillMaxSize().padding(12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(text = "Count: $count")
                Button(
                    text = "Increment",
                    onClick = actionRunCallback<IncrementAction>()
                )
            }
        }
    }
}

class CounterWidgetReceiver : GlanceAppWidgetReceiver() {
    override val glanceAppWidget = CounterWidget()
}
```

Everything here looks like Compose, but `Column`, `Text`, `Button`, and `GlanceModifier` are Glance types. There's no arbitrary drawing, no `Canvas`, no custom layout — you're constrained to what `RemoteViews` can express. That restriction is the whole reason widgets are cheap for the launcher to host, so treat it as a design constraint, not a limitation to fight.

## State: persist it, don't hold it

The single biggest conceptual jump from app UI is state. A Glance widget has **no durable in-memory state** — the launcher can destroy and recreate it whenever it likes. So you never hold state in a variable across updates; you persist it and read it back inside `provideGlance`. Glance ships a `GlanceStateDefinition` backed by DataStore for exactly this:

```kotlin
class IncrementAction : ActionCallback {
    override suspend fun onAction(
        context: Context, glanceId: GlanceId, parameters: ActionParameters
    ) {
        updateAppWidgetState(context, glanceId) { prefs ->
            val key = intPreferencesKey("count")
            prefs[key] = (prefs[key] ?: 0) + 1
        }
        CounterWidget().update(context, glanceId)  // trigger recomposition
    }
}
```

The pattern is always the same loop: an action mutates persisted state, then calls `update` to make Glance recompose from that state. If you come from app-side Compose and reach for `remember { mutableStateOf(...) }`, stop — it won't survive, and the widget will silently reset. Think of a widget as a pure function of persisted data, re-rendered on demand.

## Updating widgets: the timing reality

Widgets don't update on a whim, and they *shouldn't* — the system throttles them to protect battery. You have a few triggers:

- **Direct `update()`** after a user action or a data change you're already reacting to.
- **`updateAll()`** to refresh every instance of a widget when app data changes.
- **Periodic refresh** via the widget's `updatePeriodMillis`, which the system clamps to a minimum (historically 30 minutes) — do not expect a ticking clock.

For anything time-based or data-fetching, the right tool is scheduled background work, not the widget's own refresh knob. I wire widget refreshes to the same job that syncs the data, using [WorkManager for reliable background work](https://blog.michaelsam94.com/workmanager-reliable-background-work/) — when the sync completes, it calls `updateAll()`. That keeps the widget consistent with the app's data and respects the system's constraints instead of hammering a refresh that the OS will throttle anyway. Trying to make a widget feel "live" by polling aggressively is a battery complaint waiting to happen.

## Composition and performance still matter

It's tempting to think performance is irrelevant for something as small as a widget. It isn't — `provideGlance` runs to produce `RemoteViews`, and the translation has a cost, especially with images and complex layouts. The same discipline that keeps app UI smooth applies: keep the composition lean, avoid doing heavy work inside `provideContent`, and load data *before* you compose rather than blocking during it. The habits I describe in [Compose performance and recomposition stability](https://blog.michaelsam94.com/compose-performance-stability-recomposition/) carry over — do expensive work outside the composition and feed it in as already-computed state.

One concrete rule: fetch and prepare everything (from DataStore, from a repository) at the top of `provideGlance`, then let the composable be a straightforward render of that data. A widget that does I/O mid-composition is both slow to appear and fragile.

## Sizing and the responsive gotcha

Widgets get resized by the user, and Glance handles this through `SizeMode`. Three options:

| SizeMode | Behavior | Use when |
| --- | --- | --- |
| `Single` | One layout regardless of size | Fixed, simple widgets |
| `Responsive` | You define layouts for a set of size buckets | Widgets that should adapt |
| `Exact` | Recomposes for the actual reported size | Fine-grained control, more work |

`Responsive` is the sensible default for anything non-trivial — you declare a small set of supported sizes, and Glance picks the best fit, which avoids the recomposition churn of `Exact` while still adapting between, say, a 2x1 and a 4x2 placement. Design your layout to degrade gracefully: show a compact view when small, more detail when large.

Glance is a genuine quality-of-life upgrade over raw `RemoteViews`, and I reach for it now on every widget. Just hold the two hard truths in mind: it's Compose-*shaped* but not Compose, and a widget is a stateless render of persisted data, refreshed on the system's terms rather than yours. Build within those constraints and you get widgets that are clean to write, cheap for the launcher, and kind to the battery — which is exactly what a good widget should be.

## Resources

- [Jetpack Glance — official documentation](https://developer.android.com/develop/ui/compose/glance)
- [Create a widget with Glance](https://developer.android.com/develop/ui/compose/glance/create-app-widget)
- [Glance state and actions](https://developer.android.com/develop/ui/compose/glance/glance-state)
- [App widgets overview](https://developer.android.com/develop/ui/views/appwidgets/overview)
- [Glance on GitHub (source)](https://github.com/androidx/androidx/tree/androidx-main/glance)
