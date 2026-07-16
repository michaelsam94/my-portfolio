---
title: "Swipe-to-Dismiss and Row Actions"
slug: "compose-swipe-to-dismiss-actions"
description: "Build swipe-to-dismiss lists and trailing action rows in Compose with SwipeToDismissBox, AnchoredDraggable, and Material3 list patterns."
datePublished: "2025-04-15"
dateModified: "2025-04-15"
tags: ["Android", "Compose"]
keywords: "Compose swipe to dismiss, SwipeToDismissBox, list row actions, AnchoredDraggable, Material3 swipe"
faq:
  - q: "What replaced SwipeToDismiss in Material3 Compose?"
    a: "Material3 provides SwipeToDismissBox with background and dismiss content slots, backed by AnchoredDraggableState. It supports start-to-end and end-to-start swipe directions with positional thresholds for dismiss vs snap-back. Material2 SwipeToDismiss is deprecated in favor of this API."
  - q: "How do I show delete and archive actions on swipe?"
    a: "Use end-to-start swipe revealing a Row of action buttons in the background slot—not full dismiss. Set confirmValueChange to snap to an 'revealed' anchor instead of DismissedValue when the user should tap an action. Full dismiss only when swipe passes dismiss threshold."
  - q: "How do I prevent swipe conflicts with LazyColumn scroll?"
    a: "SwipeToDismissBox consumes horizontal drag after vertical scroll dominance is determined. Use rememberSwipeToDismissBoxState with requireDismissedDirection matching your UX. For rows in LazyColumn, ensure item modifier order places swipe on the row root; avoid nested horizontal scrollables inside swipe rows."
---

Mail clients trained users to swipe left for archive and swipe right to pin. Compose Material3 finally ships first-class swipe primitives—`SwipeToDismissBox` for dismiss-or-reveal patterns and `AnchoredDraggable` underneath for custom anchors. The API changed from Material2's `SwipeToDismiss`, so most Stack Overflow answers are stale. Here is the current pattern.

## SwipeToDismissBox basics

```kotlin
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DismissibleListItem(
    item: TodoItem,
    onDismiss: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val state = rememberSwipeToDismissBoxState(
        confirmValueChange = { value ->
            if (value == SwipeToDismissBoxValue.EndToStart) {
                onDismiss()
                true
            } else false
        },
    )

    SwipeToDismissBox(
        state = state,
        enableDismissFromStartToEnd = false,
        backgroundContent = {
            Box(
                Modifier
                    .fillMaxSize()
                    .background(MaterialTheme.colorScheme.errorContainer)
                    .padding(horizontal = 20.dp),
                contentAlignment = Alignment.CenterEnd,
            ) {
                Icon(Icons.Default.Delete, contentDescription = "Delete")
            }
        },
        modifier = modifier,
    ) {
        ListItem(
            headlineContent = { Text(item.title) },
            supportingContent = { Text(item.subtitle) },
        )
    }
}
```

Background draws under the foreground content; swipe translates foreground revealing background.

## Reveal actions without auto-dismiss

For archive + delete buttons, use anchors instead of immediate dismiss:

```kotlin
enum class SwipeAnchor { Settled, Revealed, Dismissed }

@Composable
fun ActionRow(item: Item, onArchive: () -> Unit, onDelete: () -> Unit) {
    val density = LocalDensity.current
    val anchors = DraggableAnchors {
        SwipeAnchor.Settled at 0f
        SwipeAnchor.Revealed at -160.dp.toPx(density)
        SwipeAnchor.Dismissed at -400.dp.toPx(density)
    }

    val state = rememberAnchoredDraggableState(
        initialValue = SwipeAnchor.Settled,
        anchors = anchors,
    )

    Box(Modifier.anchoredDraggable(state, Orientation.Horizontal)) {
        Row(
            Modifier
                .align(Alignment.CenterEnd)
                .width(160.dp),
            horizontalArrangement = Arrangement.SpaceEvenly,
        ) {
            IconButton(onClick = onArchive) {
                Icon(Icons.Default.Archive, "Archive")
            }
            IconButton(onClick = onDelete) {
                Icon(Icons.Default.Delete, "Delete")
            }
        }
        ListItem(
            headlineContent = { Text(item.title) },
            modifier = Modifier
                .offset { IntOffset(state.requireOffset().roundToInt(), 0) }
                .background(MaterialTheme.colorScheme.surface),
        )
    }
}
```

Snap to `Revealed` on partial swipe; `Dismissed` only past threshold with undo snackbar.

## Undo pattern on dismiss

```kotlin
val scope = rememberCoroutineScope()
val snackbarHostState = remember { SnackbarHostState() }

confirmValueChange = { value ->
    if (value == SwipeToDismissBoxValue.EndToStart) {
        scope.launch {
            val result = snackbarHostState.showSnackbar(
                message = "Item deleted",
                actionLabel = "Undo",
                duration = SnackbarDuration.Short,
            )
            if (result == SnackbarResult.ActionPerformed) {
                state.snapTo(SwipeToDismissBoxValue.Settled)
            } else {
                onDismissConfirmed()
            }
        }
        true
    } else false
}
```

Defer actual deletion until snackbar timeout—standard Material pattern.

## LazyColumn integration

```kotlin
LazyColumn {
    items(items, key = { it.id }) { item ->
        DismissibleListItem(
            item = item,
            onDismiss = { viewModel.delete(item.id) },
            modifier = Modifier.animateItem(),
        )
    }
}
```

Stable keys prevent swipe state leaking between recycled items when list updates.

## Accessibility

Swipe gestures are invisible to TalkBack-only users. Expose actions in overflow menu and set custom actions on semantics:

```kotlin
Modifier.semantics {
    customActions = listOf(
        CustomAccessibilityAction("Delete") {
            onDelete()
            true
        },
    )
}
```

## Material2 migration note

Old API:

```kotlin
// Deprecated pattern
SwipeToDismiss(state, background, dismissContent)
```

Map to `SwipeToDismissBox` with explicit direction flags. `DismissValue` maps to `SwipeToDismissBoxValue`.

## Gesture conflict resolution in lists

Swipe rows inside `LazyColumn` compete with vertical scroll for touch ownership. Compose resolves this with touch slop — the first gesture direction to exceed the slop threshold wins. Horizontal swipe on a row won't trigger until the user moves horizontally enough that vertical scroll is ruled out.

Practical implications:

- **Don't nest horizontal scroll inside swipe rows** — nested `LazyRow` inside a swipeable item fights the parent swipe gesture
- **Keep swipe threshold reasonable** — `positionalThreshold` defaults work for most cases; lower thresholds cause accidental dismiss on diagonal scrolls
- **Test on real devices** — emulators don't reproduce thumb angle and scroll momentum accurately

```kotlin
val state = rememberSwipeToDismissBoxState(
    positionalThreshold = { totalDistance -> totalDistance * 0.5f },
    confirmValueChange = { /* ... */ },
)
```

50% threshold means the user must swipe halfway before dismiss confirms — standard for destructive actions.

## Only one open row pattern

Mail clients close other revealed rows when a new row is swiped. Implement with shared state:

```kotlin
@Composable
fun SwipeableList(items: List<Item>, viewModel: ListViewModel) {
    val openItemId by viewModel.openSwipeItemId.collectAsStateWithLifecycle()

    LazyColumn {
        items(items, key = { it.id }) { item ->
            ActionRow(
                item = item,
                isOpen = openItemId == item.id,
                onOpen = { viewModel.setOpenSwipeItem(item.id) },
                onClose = { viewModel.setOpenSwipeItem(null) },
                onDelete = { viewModel.delete(item.id) },
            )
        }
    }
}
```

When a row opens, animate others closed. Without this, users reveal five rows and forget which actions belong where.

## Haptic and visual feedback

Material3 swipe should provide feedback at threshold crossing:

```kotlin
val haptic = LocalHapticFeedback.current

LaunchedEffect(state.currentValue) {
    if (state.currentValue != SwipeToDismissBoxValue.Settled) {
        haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
    }
}
```

Background color should intensify as swipe progresses — use `state.progress` (if available) or calculate from offset to interpolate alpha between surface and error container colors.

## Testing swipe interactions

```kotlin
@Test
fun swipeToDismiss_triggersDelete() {
    composeTestRule.setContent {
        DismissibleListItem(item = testItem, onDismiss = { deleted = true })
    }

    composeTestRule.onNodeWithText(testItem.title)
        .performTouchInput { swipeLeft(endX = -500f) }

    assertTrue(deleted)
}
```

Test undo flow separately — swipe, wait for snackbar, click Undo, verify item restored. Test accessibility custom actions for TalkBack users who can't swipe.

## Common failure modes

- **Swipe state leaks between items** — missing stable `key` in LazyColumn causes recycled composables to retain swipe offset
- **Immediate delete without undo** — destructive actions need snackbar confirmation for accidental swipes
- **No alternative for accessibility** — swipe-only delete excludes motor-impaired users; overflow menu required
- **Full dismiss when reveal intended** — wrong `confirmValueChange` logic triggers delete on partial swipe
- **Animation jank on dismiss** — removing item from list without `animateItem()` causes visible pop

## Production checklist

- Stable keys on LazyColumn items for swipe state isolation
- Undo snackbar for destructive dismiss actions
- Custom accessibility actions mirroring swipe actions
- Only one revealed row at a time in action-reveal pattern
- Swipe threshold tested on physical devices with varied scroll speeds
- Background actions visible at partial swipe (color/icon feedback)
- Material2 migration complete — no deprecated `SwipeToDismiss` usage

## SwipeToDismissBox state management

Manage dismiss state across recompositions:

```kotlin
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DismissibleItem(
    item: Item,
    onDismiss: (Item) -> Unit,
) {
    var showUndo by remember { mutableStateOf(false) }
    val dismissState = rememberSwipeToDismissBoxState(
        confirmValueChange = { value ->
            if (value == SwipeToDismissBoxValue.EndToStart) {
                showUndo = true
                false  // don't dismiss yet — wait for undo window
            } else true
        }
    )

    SwipeToDismissBox(
        state = dismissState,
        backgroundContent = { DismissBackground(dismissState) },
        enableDismissFromStartToEnd = false,
    ) {
        ItemRow(item)
    }

    if (showUndo) {
        LaunchedEffect(item.id) {
            delay(5000)
            onDismiss(item)
            showUndo = false
        }
        Snackbar(action = { TextButton(onClick = { showUndo = false }) { Text("Undo") } }) {
            Text("Item deleted")
        }
    }
}
```

`confirmValueChange` returning false prevents immediate dismiss — gives undo window. Reset dismiss state after undo.

## Testing swipe interactions

```kotlin
@Test
fun swipeToDismiss_triggersDeleteAction() {
    composeTestRule.setContent { DismissibleList(items = testItems, onDismiss = { deleted = it }) }
    composeTestRule.onNodeWithTag("item-${testItems[0].id}")
        .performTouchInput { swipeLeft(startX = right, endX = left) }
    composeTestRule.onNodeWithText("Item deleted").assertIsDisplayed()
}
```

Test swipe threshold, undo action, and background reveal at partial swipe. Use `performTouchInput` for precise swipe simulation.

## Resources

- [SwipeToDismissBox Material3](https://developer.android.com/reference/kotlin/androidx/compose/material3/SwipeToDismissBox)
- [AnchoredDraggableState](https://developer.android.com/reference/kotlin/androidx/compose/foundation/gestures/AnchoredDraggableState)
- [Compose gestures overview](https://developer.android.com/jetpack/compose/touch-input)
- [Material motion — swipe to dismiss](https://m3.material.io/foundations/interaction/gestures)
