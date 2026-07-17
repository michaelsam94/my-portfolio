---
title: "Navigation 3 in Jetpack Compose: Back Stack as State"
slug: "navigation-3-jetpack-compose"
description: "Navigation 3 (Nav3) makes the back stack ordinary Compose state you own. How it differs from Navigation Compose, deep links, and adaptive multi-pane navigation."
datePublished: "2026-03-18"
dateModified: "2026-07-17"
tags:
keywords: "Navigation 3, Compose navigation, Nav3, back stack as state, Compose navigation library, deep links"
faq:
  - q: "What is Navigation 3 for Jetpack Compose?"
    a: "Navigation 3 (Nav3) is a rethink of Android navigation where the back stack is an ordinary observable list you own in your own state, rather than being hidden inside a framework controller. You mutate the list to navigate, and the library renders the top entries as UI."
  - q: "How is Navigation 3 different from Navigation Compose?"
    a: "In Navigation Compose the NavController owns and hides the back stack behind an imperative API. In Navigation 3 the back stack is a plain list in your state that you read and mutate directly, which makes navigation state testable, serializable, and adaptive-friendly."
  - q: "Does Navigation 3 support deep links and multi-pane layouts?"
    a: "Yes. Because the back stack is just a list, a deep link becomes 'construct this list of destinations,' and multi-pane layouts become 'render the top N entries side by side.' Both are far more natural than in controller-based navigation."
---
For years, Android navigation meant handing your back stack to a controller and poking it through an imperative API — `navigate("route")`, `popBackStack()` — while the actual stack stayed hidden inside the framework. It worked, but it fought Compose's core idea that UI is a function of state you own. Navigation 3 flips this: **the back stack is just a list you hold in your own state**, and the library renders it. Navigate by adding to the list; go back by removing from it. That's the whole model, and it's a much better fit for how Compose actually thinks.

I've shipped apps on Navigation Compose and its predecessors, and the recurring pain was always that navigation state lived somewhere I couldn't easily read, test, or restore. Nav3 puts it back in my hands. Here's what changes and why it matters.

## The back stack is ordinary state

In Nav3 you keep the back stack as an observable list of keys — plain data describing where the user is:

```kotlin
val backStack = rememberNavBackStack(HomeKey)

NavDisplay(
    backStack = backStack,
    onBack = { backStack.removeLastOrNull() },
    entryProvider = entryProvider {
        entry<HomeKey> { HomeScreen(onOpen = { backStack.add(DetailKey(it)) }) }
        entry<DetailKey> { key -> DetailScreen(id = key.id) }
    },
)
```

Look at what navigation *is* here: `backStack.add(DetailKey(id))` to go forward, `removeLastOrNull()` to go back. No controller, no string routes to parse, no separate navigation graph DSL. The keys are your own typed classes, so a destination carries its arguments directly — `DetailKey(id)` instead of building and parsing `"detail/$id"`. Type-safe by construction, and the compiler catches a missing argument instead of a runtime crash.

## Why "state you own" is the whole point

Because the back stack is a normal list, everything Compose is good at applies to navigation for free:

- **Testable.** You assert on a list. "After tapping the item, the stack should end with `DetailKey(42)`" is a plain equality check — no Espresso, no controller test harness.
- **Restorable.** The stack is serializable data, so surviving process death is just saving and restoring a list, not wrestling with the framework's opaque saved state.
- **Inspectable.** You can log, snapshot, or debug the entire nav state at any moment because it's right there in your state, not buried in a controller.

This is the same philosophy as [state hoisting in Compose](https://blog.michaelsam94.com/jetpack-compose-lessons-10-years-android/), extended to navigation. Once navigation state is hoisted into ordinary observable state, it stops being a special case.

## Deep links become "build a list"

Deep linking in controller-based navigation was always fiddly — you'd declare intent filters, map URIs to routes, and hope the synthesized back stack was right. In Nav3, a deep link is just a function that produces the initial list:

```kotlin
fun backStackFor(uri: Uri): List<NavKey> = when {
    uri.pathSegments.firstOrNull() == "product" ->
        listOf(HomeKey, CatalogKey, DetailKey(uri.lastPathSegment!!))
    else -> listOf(HomeKey)
}
```

You're literally constructing the stack you want the user to land on, with a sensible parent chain so "back" behaves. Because it's plain code producing plain data, it's trivial to unit test that a given URL yields the right stack — something that was genuinely painful before.

## Multi-pane and adaptive navigation fall out naturally

Here's where the model really earns its keep. On a tablet or foldable you often want list and detail side by side. With a hidden back stack that's awkward; with a list you own, it's obvious — **render the top N entries as panes instead of just the top one**.

Nav3 provides scenes/strategies to do exactly this: a strategy can decide "if the window is expanded and the top two entries are list + detail, show them together." Combine it with the [adaptive layout](https://blog.michaelsam94.com/adaptive-layouts-compose-grid-flexbox/) tools — window size classes — and the same back stack drives a single-pane phone experience and a two-pane tablet experience with no duplicate navigation logic. The back-stack-as-list model is what makes that clean; you're just choosing how many entries to display.

## Migrating from Navigation Compose

A few honest notes if you're considering the move:

| Aspect | Navigation Compose | Navigation 3 |
|---|---|---|
| Back stack | Hidden in `NavController` | A list you own |
| Destinations | String routes / typed routes | Your own key data classes |
| Navigate | `navController.navigate(...)` | `backStack.add(...)` |
| Deep links | URI-to-route mapping | Function returning a list |
| Multi-pane | Manual / awkward | Render top-N entries |

Migration is real work — the mental model and the API both change — so don't rip out a working Navigation Compose setup for its own sake. Where Nav3 pays off is greenfield apps, apps targeting foldables and large screens seriously, or apps where navigation state has become hard to test and restore. Nav3 also composes well with scoped ViewModels and lifecycle: each entry can own its own lifecycle and scoped state, so per-screen ViewModels still work as you'd expect.

## The gotchas

- **You own correctness now.** With freedom comes responsibility: it's on you not to leave the stack empty or push duplicate keys where you didn't mean to. Wrap common operations (push, replace, pop-to) in small helpers rather than mutating the list ad hoc all over the app.
- **Keys should be stable, serializable data.** Since the stack gets saved and restored, keep keys as simple `@Serializable` data classes without heavy or non-serializable payloads — pass IDs, fetch data in the destination.
- **Animations and predictable back.** Nav3 integrates with [predictive back gestures](https://blog.michaelsam94.com/predictive-back-gestures-android/); wire `onBack` through the provided handlers so the system back animation stays smooth rather than fighting your manual list mutation.

## The takeaway

Navigation 3's one big idea — the back stack is state you own — resolves the longstanding friction between Android navigation and Compose. Typed keys instead of string routes, a list you can test and restore instead of a hidden controller, deep links as list construction, and multi-pane layouts as "render more entries." It's more explicit, which means slightly more responsibility, but for large-screen and testability-focused apps it's the model I'd start new work on. Navigation finally works the way the rest of Compose does.

## Resources

- [Navigation 3 documentation](https://developer.android.com/guide/navigation/navigation-3)
- [Navigation Compose reference](https://developer.android.com/develop/ui/compose/navigation)
- [Android Developers Blog](https://android-developers.googleblog.com/)
- [Adaptive navigation for large screens](https://developer.android.com/develop/ui/compose/layouts/adaptive)
- [Predictive back gesture guide](https://developer.android.com/guide/navigation/custom-back/predictive-back-gesture)
