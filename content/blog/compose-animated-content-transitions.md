---
title: "AnimatedContent and Content Transitions in Compose"
slug: "compose-animated-content-transitions"
description: "Master AnimatedContent in Jetpack Compose: transitionSpec, SizeTransform, directional slides, and using content keys to avoid janky state swaps."
datePublished: "2024-09-07"
dateModified: "2024-09-07"
tags: ["Android", "Jetpack Compose", "Animation", "UI"]
keywords: "AnimatedContent, Compose content transition, transitionSpec, SizeTransform, Compose slide transition, contentKey"
faq:
  - q: "What does AnimatedContent do in Jetpack Compose?"
    a: "AnimatedContent animates between two versions of your UI when a target state changes, cross-fading or sliding the old content out while the new content comes in. It is the right choice when the content itself changes — a counter incrementing, a step in a wizard, a loading-to-loaded swap — as opposed to AnimatedVisibility, which only animates a single piece appearing or disappearing."
  - q: "How do I control the direction of an AnimatedContent transition?"
    a: "Use the transitionSpec parameter and compare initialState with targetState to decide direction, returning slideInHorizontally and slideOutHorizontally with opposite signs. Wrap the result with using SizeTransform to control how the container resizes during the swap. This is how you make a counter slide up when incrementing and down when decrementing."
  - q: "Why does AnimatedContent flicker or animate on unrelated changes?"
    a: "AnimatedContent animates whenever the targetState value changes by equality. If your state object is recreated on every recomposition or carries fields you did not intend to animate on, supply a contentKey so the transition only fires when the key you care about changes."
---

`AnimatedContent` is the API you want when the *content itself* changes and you want the change to animate — a counter ticking up, a wizard advancing to the next step, a screen moving from loading to loaded. It cross-fades or slides the outgoing content away while bringing the new content in, all keyed off a target state. Its sibling `AnimatedVisibility` only handles one element appearing or disappearing; `AnimatedContent` handles the *swap* between two states, which is a genuinely different problem.

The defaults give you a reasonable fade, but the reason to learn this API properly is the `transitionSpec` and `SizeTransform` — that's where you turn a generic cross-fade into motion that communicates direction and meaning.

## The basic swap

You give `AnimatedContent` a `targetState` and a lambda that renders the UI for a given state. When the target changes, it animates between the old and new renderings.

```kotlin
AnimatedContent(
    targetState = uiState,
    label = "screenState",
) { state ->
    when (state) {
        is Loading -> LoadingSkeleton()
        is Loaded  -> Content(state.data)
        is Error   -> ErrorPanel(state.message)
    }
}
```

Two rules that trip people up. First, *always render from the lambda's `state` parameter*, never from the outer `uiState`. During the transition both the old and new content are on screen simultaneously; if you read the outer variable, both render the new state and the exit animation shows the wrong thing. Second, the swap fires on value equality, so make your state a proper data class or sealed type with sensible `equals`.

## Directional transitions with transitionSpec

The default is a fade. To make motion mean something — new step slides in from the right, previous step slides back from the left — use `transitionSpec`, where you have access to `initialState` and `targetState` to decide direction:

```kotlin
AnimatedContent(
    targetState = step,
    transitionSpec = {
        if (targetState > initialState) {
            slideInHorizontally { it } + fadeIn() togetherWith
                slideOutHorizontally { -it } + fadeOut()
        } else {
            slideInHorizontally { -it } + fadeIn() togetherWith
                slideOutHorizontally { it } + fadeOut()
        }
    },
    label = "wizardStep",
) { s -> StepContent(s) }
```

`togetherWith` combines the enter transition (for the incoming content) with the exit transition (for the outgoing). The `{ it }` and `{ -it }` lambdas receive the full width and return the pixel offset to start/end at, so `{ it }` slides in from the right edge and `{ -it }` slides out to the left. Comparing `targetState` and `initialState` is what gives you the "forward vs back" feel that makes a wizard or a pager feel spatial rather than random.

## SizeTransform: handling the resize

When the two states are different sizes — an error message longer than a loading spinner — the container has to resize during the transition, and by default that resize is abrupt. `SizeTransform` controls it. Attach it with `using`:

```kotlin
transitionSpec = {
    (fadeIn() togetherWith fadeOut())
        .using(SizeTransform(clip = false) { initial, target ->
            keyframes {
                durationMillis = 300
                // grow width first, then height
                IntSize(target.width, initial.height) at 150
            }
        })
}
```

`clip = false` lets content overflow during the animation instead of being cut off, which usually looks better for text. The keyframe here grows one dimension before the other, so an expanding card unfolds rather than inflating uniformly. Even without the keyframes, just wrapping in a default `SizeTransform` smooths the container resize — a small touch that removes a surprising amount of jank.

## contentKey: animate only on what matters

Here's the subtle bug. `AnimatedContent` animates whenever `targetState` changes by equality. If your state object carries fields you *don't* want to trigger a transition — a timestamp, a scroll position, a loading sub-flag — every unrelated change kicks off a full content animation, and the UI flickers.

The fix is `contentKey`: tell `AnimatedContent` which property actually defines a distinct content version.

```kotlin
AnimatedContent(
    targetState = uiState,
    contentKey = { it.screenId },   // only animate when the screen changes
    label = "content",
) { state -> ScreenFor(state) }
```

Now a change to `uiState.scrollOffset` recomposes without triggering the transition, because the `screenId` key is unchanged. This one parameter fixes most "why is it animating for no reason" reports I've debugged.

## When AnimatedContent is the wrong tool

| Situation | Right tool |
| --- | --- |
| Content changes between states | `AnimatedContent` |
| One element appears/disappears | `AnimatedVisibility` |
| Container just resizes, content same | `Modifier.animateContentSize` |
| Swiping between many pages | `HorizontalPager` |

Don't force a pager-like experience out of `AnimatedContent`; for a real swipeable pager, `HorizontalPager` gives you gesture control and offscreen page management that `AnimatedContent` isn't built for. Use `AnimatedContent` for programmatic, state-driven swaps.

## Performance notes from production

During a transition both content versions are composed and drawn, so the swap momentarily doubles the work for that subtree. For heavy content — an image grid, a chart — that spike can drop frames on the swap. Two mitigations I use: keep transitions short (200–300ms) so the overlap window is brief, and avoid triggering `AnimatedContent` swaps for content that's expensive to compose from scratch every time. The general Compose rule of keeping composables cheap and stable, covered in [ten years of Compose lessons](https://blog.michaelsam94.com/jetpack-compose-lessons-10-years-android/), matters double here because you're paying for two subtrees at once.

## What I'd take away

`AnimatedContent` is for swapping between states, and the difference between a bland fade and motion that *means* something is entirely in the `transitionSpec`. Compare `initialState` and `targetState` to give transitions direction, wrap them with `SizeTransform` so container resizes stay smooth, and — the part everyone misses — supply a `contentKey` so you animate only on the property that defines a real content change. Render exclusively from the lambda's state parameter, keep durations short, and reach for `HorizontalPager` when you actually want a pager. Get those right and content swaps feel intentional instead of accidental.

## Resources

- [AnimatedContent guide (Android developers)](https://developer.android.com/develop/ui/compose/animation/composables-modifiers#animatedcontent)
- [AnimatedContent API reference](https://developer.android.com/reference/kotlin/androidx/compose/animation/package-summary#AnimatedContent(kotlin.Any,androidx.compose.ui.Modifier,kotlin.Function1,androidx.compose.ui.Alignment,kotlin.String,kotlin.Function1,kotlin.Function2))
- [Enter and exit transitions](https://developer.android.com/develop/ui/compose/animation/composables-modifiers)
- [Compose animation quick guide](https://developer.android.com/develop/ui/compose/animation/quick-guide)
