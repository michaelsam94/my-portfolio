---
title: "Focus Management in Compose"
slug: "compose-focus-management-tv"
description: "Manage D-pad and keyboard focus in Jetpack Compose for TV and large-screen apps: FocusRequester, focus order, and focusRestorer patterns."
datePublished: "2025-03-31"
dateModified: "2025-03-31"
tags: ["Android", "Compose"]
keywords: "Compose TV focus, FocusRequester, D-pad navigation, focus order, Android TV Compose"
faq:
  - q: "How does focus work differently on Android TV vs phone?"
    a: "TV apps have no touch input—every interactive element must be reachable via D-pad directional navigation. Compose assigns focus to one focused composable at a time, drawing a focus highlight. You must define logical focus traversal order; the system cannot infer grid layout intent from visual placement alone without focus properties or custom focus search."
  - q: "What is FocusRequester used for?"
    a: "FocusRequester programmatically moves focus to a composable—on screen entry, after closing a dialog, or when a row expands. Call requestFocus() from LaunchedEffect or a callback, not during composition. Each focusable composable needs exactly one FocusRequester attached via Modifier.focusRequester."
  - q: "How do I restore focus after navigating back?"
    a: "Use Modifier.focusRestorer() or save the focused item key in rememberSaveable and request focus on that item when the screen recomposes. Without restoration, back navigation often lands focus on the first focusable element, disorienting TV users who expect focus where they left off."
---

Building a Compose app for Android TV without explicit focus management ships a UI that looks correct on your monitor and feels broken on a couch. D-pad users tab through focusable elements in traversal order—not visual order—and when that order jumps from the sidebar to row seventeen of a grid, users leave. Focus on TV is not an accessibility add-on; it is the primary navigation model.

## Focusable modifiers

Make composables focusable with `Modifier.focusable()` or clickable variants that include focus:

```kotlin
Box(
    modifier = Modifier
        .focusable()
        .onFocusChanged { state ->
            isFocused = state.isFocused
        }
        .border(
            width = if (isFocused) 2.dp else 0.dp,
            color = MaterialTheme.colorScheme.primary,
        )
        .clickable { onSelect() },
) {
    Text(title)
}
```

TV Material components (`androidx.tv.material3`) provide `Card` and `Button` with built-in focus scaling and glow—prefer them over phone Material on leanback.

## FocusRequester for initial and restored focus

```kotlin
@Composable
fun DetailScreen(initialFocusId: String?) {
    val focusRequesters = remember { mutableMapOf<String, FocusRequester>() }

    LaunchedEffect(initialFocusId) {
        initialFocusId?.let { id ->
            focusRequesters[id]?.requestFocus()
        }
    }

    LazyRow {
        items(categories, key = { it.id }) { category ->
            val requester = remember { FocusRequester() }
            focusRequesters[category.id] = requester

            CategoryChip(
                category = category,
                modifier = Modifier.focusRequester(requester),
            )
        }
    }
}
```

Request focus after layout—`LaunchedEffect` or `onGloballyPositioned` first frame, not in composable body.

## Custom focus traversal

Override default search with focus properties:

```kotlin
Modifier.focusProperties {
    // When pressing RIGHT from this item, focus this specific target
    right = nextItemRequester
    up = sidebarRequester
    // Prevent focus from leaving grid at edges
    canFocus = isEnabled
}
```

For grids, broken row-major order is the top complaint. Align traversal with visual rows:

```kotlin
Modifier.focusProperties {
    next = { direction ->
        when (direction) {
            FocusDirection.Right -> itemAt(row, col + 1)?.focusTarget
            FocusDirection.Down -> itemAt(row + 1, col)?.focusTarget
            else -> FocusDirection.Next
        }
    }
}
```

## focusRestorer on back stack

Navigation Compose back stack loses focus by default. Save and restore:

```kotlin
@Composable
fun CatalogScreen() {
    var lastFocusedIndex by rememberSaveable { mutableIntStateOf(0) }
    val rowFocusRequester = remember { FocusRequester() }

    LazyColumn(
        modifier = Modifier.focusRestorer {
            rowFocusRequester.saveFocusedChild()
        },
    ) {
        itemsIndexed(items) { index, item ->
            ItemRow(
                item = item,
                modifier = Modifier
                    .focusRequester(if (index == lastFocusedIndex) rowFocusRequester else FocusRequester())
                    .onFocusChanged {
                        if (it.isFocused) lastFocusedIndex = index
                    },
            )
        }
    }
}
```

`focusRestorer` (Compose 1.7+) replays saved focus when returning to a composable subtree.

## Lazy lists and focus

`LazyRow`/`LazyColumn` recycle items—FocusRequester instances must be keyed to stable item IDs, not index:

```kotlin
items(items, key = { it.id }) { item ->
    val requester = remember(item.id) { FocusRequester() }
    // ...
}
```

Bringing focused item into view when focus moves programmatically:

```kotlin
LaunchedEffect(focusedIndex) {
    listState.animateScrollToItem(focusedIndex)
    focusRequesters[focusedIndex]?.requestFocus()
}
```

## Dialogs and overlays

When a modal opens, trap focus inside and return on dismiss:

```kotlin
Dialog(onDismissRequest = onDismiss) {
    Box(
        modifier = Modifier
            .focusGroup()
            .onPreviewKeyEvent { event ->
                if (event.key == Key.Back) {
                    onDismiss()
                    true
                } else false
            },
    ) {
        val firstButton = remember { FocusRequester() }
        LaunchedEffect(Unit) { firstButton.requestFocus() }
        // dialog content
    }
}
```

`focusGroup()` keeps D-pad traversal within the dialog boundary.

## Testing focus

Compose UI tests with `performKeyPress(Key.DirectionRight)` and assert `onNodeWithTag("item-2").assertIsFocused()`. For TV, run on Android TV emulator with hardware keyboard mapped to D-pad.

## Phone and tablet crossover

Large-screen and foldable apps benefit from the same focus patterns when users attach keyboard or use stylus hover. `Modifier.hoverable()` pairs with focus for desktop-mode Chromebooks running Android apps.

## Focus order customization

Override default focus traversal order for non-linear layouts:

```kotlin
Row(modifier = Modifier.focusGroup()) {
    Box(
        modifier = Modifier
            .focusRequester(item3Focus)
            .focusProperties { next = item1Focus }
    ) { Item3() }
    Box(modifier = Modifier.focusRequester(item1Focus)) { Item1() }
    Box(modifier = Modifier.focusRequester(item2Focus)) { Item2() }
}
```

Use `focusProperties { next = ...; previous = ... }` to define custom traversal. Essential for TV grids where visual layout doesn't match logical reading order.

## FocusRestorer for temporary focus loss

When a dialog closes or a snackbar dismisses, restore focus to the previously focused element:

```kotlin
var focusedElement by remember { mutableStateOf<FocusRequester?>(null) }

Box(modifier = Modifier.onFocusChanged { state ->
    if (state.isFocused) focusedElement = currentFocusRequester
}) { /* content */ }

// On dialog dismiss:
LaunchedEffect(dialogVisible) {
    if (!dialogVisible) focusedElement?.requestFocus()
}
```

Without focus restoration, D-pad users land on an unexpected element after dialog close — disorienting on TV.

## Leanback vs Compose TV

Android TV Leanback library (XML-based) is legacy — Compose TV is the forward path:

| | Leanback | Compose TV |
|---|---|---|
| UI framework | XML Views | Compose |
| Focus handling | Built-in browse/ details | Manual FocusRequester |
| Maintenance | Maintenance mode | Active development |
| Custom layouts | Difficult | Full Compose flexibility |

New TV apps should use Compose TV. Existing Leanback apps migrate screen-by-screen to Compose.

## Failure modes

- **No initial focus on screen load** — D-pad user can't interact until they press a direction
- **Focus escapes dialog boundary** — user navigates behind modal; use `focusGroup()`
- **Focus not restored after dialog** — user lands on wrong element after dismiss
- **Touch-only design on TV** — no focus indicators; unusable with D-pad
- **Custom focus order not tested** — traversal breaks on edge cases

## Production checklist

- Initial focus set via `LaunchedEffect` on every screen
- Dialogs use `focusGroup()` to trap D-pad traversal
- Focus restored to previous element on dialog dismiss
- Custom focus order tested with `performKeyPress` in UI tests
- TV emulator or hardware tested with D-pad (not just touch)
- Compose TV used for new TV app development

## Common production mistakes

Teams get focus management tv wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Compose UI work on focus management tv janks when recomposition scope is too wide, `remember` keys omit stable inputs, and semantics for TalkBack are added only after QA finds focus traps.

## Resources

- [Compose focus guide](https://developer.android.com/jetpack/compose/touch-input/focus)
- [Android TV Compose libraries](https://developer.android.com/training/tv/playback/compose)
- [FocusRequester reference](https://developer.android.com/reference/kotlin/androidx/compose/ui/focus/FocusRequester)
- [focusProperties modifier](https://developer.android.com/reference/kotlin/androidx/compose/ui/focus/FocusProperties)
