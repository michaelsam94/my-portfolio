---
title: "Stateful Glance App Widgets"
slug: "android-jetpack-glance-appwidgets-state"
description: "Build stateful Android app widgets with Jetpack Glance: how state and updates work, using GlanceStateDefinition, and updating widgets from work reliably."
datePublished: "2024-09-28"
dateModified: "2024-09-28"
tags: ["Android", "Jetpack Compose", "Glance", "App Widgets"]
keywords: "Glance app widget, Jetpack Glance state, GlanceStateDefinition, updateAppWidget, Android widget Compose, glance appwidget update"
faq:
  - q: "How does state work in a Glance app widget?"
    a: "Glance widgets don't hold live in-memory state like a running Compose screen; they render a snapshot that RemoteViews displays in the launcher process. You persist state (commonly via a GlanceStateDefinition backed by DataStore) and trigger a re-composition with updateAppWidget or update() when it changes. The widget reads the persisted state each time it recomposes, so durable storage is the source of truth, not a ViewModel."
  - q: "Why isn't my Glance widget updating?"
    a: "The most common cause is mutating state without telling Glance to recompose. After changing the backing state you must call the widget's update() (or updateAppWidget) so the framework re-renders and pushes new RemoteViews. Also remember widget updates are subject to system throttling, so rapid successive updates may be coalesced by the launcher."
  - q: "Can I use a ViewModel with a Glance widget?"
    a: "Not the usual Activity/Fragment ViewModel — a widget has no lifecycle owner in your process and renders in the launcher. Instead, back the widget with persisted state (DataStore via GlanceStateDefinition) and update it from a coroutine, WorkManager job, or broadcast. Treat the persisted store as the model and the widget as a pure render of it."
---

Jetpack Glance lets you build Android app widgets with a Compose-style API instead of hand-authoring `RemoteViews` XML, and that's a genuine relief — anyone who's built widgets the old way remembers the pain. But Glance is not "Compose on the home screen," and the place that trips people up is **state**. A widget doesn't run like an Activity: there's no live composition sitting in memory, no ViewModel, no recomposition loop reacting to a `mutableStateOf`. It renders a *snapshot* into the launcher process. Get that model right and stateful widgets are straightforward; miss it and you'll wonder why your widget never updates.

## The mental model: render a snapshot, don't run a UI

When your Glance widget composes, Glance translates the composition into `RemoteViews` and hands them to the launcher, which displays them in *its* process. Your code isn't running while the widget sits on the home screen. So "state" can't live in memory the way it does on a screen — it has to be **persisted** somewhere durable, and the widget reads it fresh each time it recomposes.

This flips the usual Compose intuition. On a screen, state is in memory and the UI reacts to it. In a widget, storage is the source of truth, and you *ask* Glance to recompose when that storage changes.

## GlanceStateDefinition: durable state, wired in

Glance formalizes this with `GlanceStateDefinition`, most commonly backed by DataStore (Preferences or Proto). You declare where the widget's state lives, read it inside the composable via `currentState`, and Glance handles loading it before composition.

```kotlin
class CounterWidget : GlanceAppWidget() {
    override val stateDefinition = PreferencesGlanceStateDefinition

    override suspend fun provideGlance(context: Context, id: GlanceId) {
        provideContent {
            val count = currentState(key = intPreferencesKey("count")) ?: 0
            Column {
                Text("Count: $count")
                Button(text = "Add", onClick = actionRunCallback<IncrementAction>())
            }
        }
    }
}
```

The widget reads `count` from persisted preferences on each composition. There's no `remember { mutableStateOf }` here that survives — the durable store is the state. This is the single most important shift from screen Compose: **your model is on disk, not in memory.**

## Mutating state and forcing a re-render

Changing state is two steps that people frequently collapse into one and then wonder why nothing happens: (1) update the persisted value, (2) tell Glance to recompose.

```kotlin
class IncrementAction : ActionCallback {
    override suspend fun onAction(context: Context, glanceId: GlanceId, params: ActionParameters) {
        updateAppWidgetState(context, glanceId) { prefs ->
            val key = intPreferencesKey("count")
            prefs[key] = (prefs[key] ?: 0) + 1
        }
        CounterWidget().update(context, glanceId)   // trigger recomposition
    }
}
```

`updateAppWidgetState` persists the change; `update()` (or `updateAppWidget` from the manager) tells the framework to re-render and push new `RemoteViews`. Skip the second call and your data changes silently while the widget shows the stale snapshot. This is the "why isn't my widget updating" bug in nearly every case I've debugged.

## Updating from the background

Widgets rarely update only from taps — they show data that changes elsewhere: sync status, a step count, the next calendar event. The right pattern is to update the persisted state from a background job and then trigger the widget. WorkManager is the natural fit for periodic or event-driven updates:

```kotlin
class RefreshWidgetWorker(ctx: Context, params: WorkerParameters) : CoroutineWorker(ctx, params) {
    override suspend fun doWork(): Result {
        val fresh = repository.fetchLatest()
        val manager = GlanceAppWidgetManager(applicationContext)
        manager.getGlanceIds(CounterWidget::class.java).forEach { id ->
            updateAppWidgetState(applicationContext, id) { it[intPreferencesKey("count")] = fresh.count }
            CounterWidget().update(applicationContext, id)
        }
        return Result.success()
    }
}
```

Two things to internalize. First, a widget can have **multiple instances** (the user placed it twice), so iterate all `GlanceId`s. Second, updates are subject to **system throttling** — the launcher coalesces rapid updates, so don't design around sub-second refreshes. For anything time-sensitive, update on real events, not a tight timer, and respect that the platform will batch you.

## Practical guidance from shipping widgets

- **Keep the composition cheap.** It runs to produce `RemoteViews`; heavy work belongs in the worker that prepares state, not in `provideContent`.
- **Model state explicitly.** A small Proto DataStore schema for the widget beats scattering preference keys — it makes the "widget = render of this model" contract obvious.
- **Handle the empty/loading state.** The first render may have no data yet; design a sensible placeholder rather than a blank widget.
- **Test the update path, not just the layout.** The layout is the easy part; the bugs live in "did I persist and *then* call update."

Glance's declarative API is the same ergonomic win Compose brought to screens — the state-hoisting instinct from [ten years of Compose lessons](https://blog.michaelsam94.com/jetpack-compose-lessons-10-years-android/) still applies, you're just hoisting all the way out to durable storage. And because the update work often runs off the main thread, injectable dispatchers and the [coroutine patterns](https://blog.michaelsam94.com/kotlin-coroutines-flow-patterns/) you'd use anywhere keep those workers testable.

## What I'd take away

A Glance widget renders a persisted snapshot into the launcher, not a live composition in your process. So state must be durable — typically DataStore via `GlanceStateDefinition` — read fresh on each recomposition, and every change is two steps: persist it, then call `update()` to force a re-render. Update from WorkManager or event callbacks for background data, iterate all instances, and design around system throttling instead of fighting it. Hold that model in your head and stateful Glance widgets stop being mysterious: storage is the truth, and the widget is a pure render of it.

## Resources

- [Jetpack Glance overview](https://developer.android.com/develop/ui/compose/glance)
- [Manage and update Glance widget state](https://developer.android.com/develop/ui/compose/glance/glance-app-widget)
- [App widgets overview](https://developer.android.com/develop/ui/views/appwidgets/overview)
- [WorkManager — schedule background work](https://developer.android.com/develop/background-work/background-tasks/persistent/getting-started)
- [DataStore](https://developer.android.com/topic/libraries/architecture/datastore)
