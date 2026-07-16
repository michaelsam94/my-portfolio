---
title: "Drag-and-Drop Reordering in Compose Lists"
slug: "compose-drag-and-drop-reorder"
description: "Implement drag-to-reorder in LazyColumn with Compose drag gestures, item offsets, and stable list state updates for settings and playlist UIs."
datePublished: "2025-03-28"
dateModified: "2025-03-28"
tags: ["Android", "Compose"]
keywords: "Compose drag and drop, LazyColumn reorder, draggable list, item drag gesture, list reorder"
faq:
  - q: "What is the recommended API for reorderable lists in Compose?"
    a: "For Material lists, combine LazyColumn with Modifier.draggable or pointerInput drag detection, tracking dragged index and applying graphicsLayer translation offsets to items. Libraries like reorderable lazy list extensions in androidx or community sh.calvin.reorderable wrap this pattern. Compose 1.7+ improves drag-and-drop APIs for cross-composable drops."
  - q: "How do I avoid LazyColumn item flicker during reorder?"
    a: "Use stable keys on LazyColumn items keyed by item ID, not index. Update the backing list only on drag end or when the dragged item crosses a swap threshold—mid-drag updates should animate offset via graphicsLayer without reordering the list data on every pixel moved. animateItemPlacement() smooths position changes when indices swap."
  - q: "Does drag reorder work with LazyColumn pagination?"
    a: "Reorder within loaded pages works; dragging across unloaded pages needs prefetch or server-side order persistence. Persist order changes to your ViewModel on drag end and sync with backend—optimistic UI with rollback on failure. Do not reorder paginated remote lists without an explicit order field in your data model."
---

Settings screens with "drag handles" and playlist editors with movable tracks are the classic reorderable list. In Compose, there is no single `ReorderableListView` widget—you compose drag detection, visual offset, index tracking, and list mutation yourself or via a small library. The pattern is stable once you internalize it: one dragged index, animated offsets for everyone else, swap on threshold cross, commit on drag end.

## Core state model

```kotlin
data class ReorderState(
    val items: List<Item>,
    val draggedIndex: Int? = null,
    val dragOffsetY: Float = 0f,
)

fun List<Item>.swap(from: Int, to: Int): List<Item> {
    if (from == to) return this
    return toMutableList().apply {
        add(to, removeAt(from))
    }
}
```

Keep `draggedIndex` and `dragOffsetY` in remember or ViewModel. The backing list mutates only when indices swap, not every drag pixel.

## LazyColumn with drag handle

```kotlin
@Composable
fun ReorderableList(
    items: List<Item>,
    onReorder: (List<Item>) -> Unit,
    modifier: Modifier = Modifier,
) {
    var draggedIndex by remember { mutableIntStateOf(-1) }
    var dragOffset by remember { mutableFloatStateOf(0f) }
    val itemHeightPx = with(LocalDensity.current) { 56.dp.toPx() }

    LazyColumn(modifier = modifier) {
        itemsIndexed(items, key = { _, item -> item.id }) { index, item ->
            val offset by animateFloatAsState(
                targetValue = when {
                    index == draggedIndex -> dragOffset
                    draggedIndex >= 0 && index > draggedIndex &&
                        dragOffset > itemHeightPx * (index - draggedIndex) -> -itemHeightPx
                    draggedIndex >= 0 && index < draggedIndex &&
                        dragOffset < itemHeightPx * (index - draggedIndex) -> itemHeightPx
                    else -> 0f
                },
                label = "itemOffset",
            )

            ListItem(
                headlineContent = { Text(item.title) },
                leadingContent = {
                    Icon(
                        Icons.Default.DragHandle,
                        contentDescription = "Reorder",
                        modifier = Modifier.draggableHandle(
                            index = index,
                            itemHeightPx = itemHeightPx,
                            onDragStart = { draggedIndex = index },
                            onDrag = { delta ->
                                dragOffset += delta
                                val target = draggedIndex + (dragOffset / itemHeightPx).roundToInt()
                                    .coerceIn(0, items.lastIndex)
                                if (target != draggedIndex) {
                                    onReorder(items.swap(draggedIndex, target))
                                    draggedIndex = target
                                    dragOffset -= (target - draggedIndex) * itemHeightPx
                                }
                            },
                            onDragEnd = {
                                draggedIndex = -1
                                dragOffset = 0f
                            },
                        ),
                    )
                },
                modifier = Modifier
                    .graphicsLayer { translationY = offset }
                    .animateItem(),
            )
        }
    }
}
```

Extract `draggableHandle` as a `Modifier.pointerInput` block using `detectDragGesturesAfterLongPress` so scrolling still works until long-press activates drag.

## Pointer input for the handle

```kotlin
fun Modifier.draggableHandle(
    index: Int,
    itemHeightPx: Float,
    onDragStart: () -> Unit,
    onDrag: (Float) -> Unit,
    onDragEnd: () -> Unit,
) = pointerInput(index) {
    detectDragGesturesAfterLongPress(
        onDragStart = { onDragStart() },
        onDragEnd = { onDragEnd() },
        onDragCancel = { onDragEnd() },
        onDrag = { change, dragAmount ->
            change.consume()
            onDrag(dragAmount.y)
        },
    )
}
```

Long-press before drag prevents accidental reorders during scroll—a UX expectation from Android settings.

## Haptic and elevation feedback

On drag start:

```kotlin
val haptic = LocalHapticFeedback.current
haptic.performHapticFeedback(HapticFeedbackType.LongPress)
```

Raise dragged item visually:

```kotlin
.graphicsLayer {
    translationY = offset
    shadowElevation = if (index == draggedIndex) 8.dp.toPx() else 0f
    scaleX = if (index == draggedIndex) 1.02f else 1f
    scaleY = if (index == draggedIndex) 1.02f else 1f
}
```

## Persisting order

On drag end, emit final list to ViewModel and persist:

```kotlin
onReorder = { newList ->
    viewModel.updateOrder(newList.map { it.id })
}
```

Backend should store explicit `sort_order` integers, not rely on array index from API responses.

## Compose drag-and-drop framework (cross-composable)

For dragging between lists or into trash zones, use `Modifier.dragAndDropSource` and `dragAndDropTarget` (Compose 1.7+):

```kotlin
Modifier.dragAndDropSource { offset ->
    DragAndDropTransferData(
        clipData = ClipData.newPlainText("itemId", item.id),
    )
}
```

Reorder within one list stays simpler with pointer drag; cross-list moves fit the DnD framework better.

## Accessibility

Announce reorder to TalkBack: update content description on drag end ("Moved to position 3 of 8"). Provide alternative up/down buttons for users who cannot perform drag gestures—Material `IconButton` pairs satisfy accessibility audits.

## Drag gesture implementation with LazyColumn

Full reorder pattern with visual feedback:

```kotlin
@Composable
fun ReorderableList(
    items: List<Item>,
    onReorder: (List<Item>) -> Unit,
) {
    var list by remember { mutableStateOf(items) }
    var draggedIndex by remember { mutableStateOf<Int?>(null) }

    LazyColumn {
        items(list.size, key = { list[it].id }) { index ->
            val offsetY = if (draggedIndex == index) dragOffset else 0f
            Box(
                modifier = Modifier
                    .offset { IntOffset(0, offsetY.roundToInt()) }
                    .zIndex(if (draggedIndex == index) 1f else 0f)
                    .pointerInput(index) {
                        detectDragGesturesAfterLongPress(
                            onDragStart = { draggedIndex = index },
                            onDragEnd = {
                                draggedIndex = null
                                onReorder(list)
                            },
                            onDrag = { change, dragAmount ->
                                change.consume()
                                dragOffset += dragAmount.y
                                // swap logic when drag crosses item midpoint
                            }
                        )
                    }
            ) { ItemRow(list[index]) }
        }
    }
}
```

Use `animateItem()` on LazyColumn items for smooth position transitions when list reorders.

## Haptic feedback on drag

Provide tactile confirmation on drag start and drop:

```kotlin
val haptic = LocalHapticFeedback.current

detectDragGesturesAfterLongPress(
    onDragStart = {
        haptic.performHapticFeedback(HapticFeedbackType.LongPress)
        draggedIndex = index
    },
    onDragEnd = {
        haptic.performHapticFeedback(HapticFeedbackType.ContextClick)
        onReorder(list)
    },
    ...
)
```

Haptic on long-press signals drag mode activated. Context click on drop confirms reorder complete.

## Cross-list drag and drop

For moving items between lists (e.g., todo → done):

```kotlin
Modifier.dragAndDropSource(
    drawDragDecoration = { drawRect(Color.Gray.copy(alpha = 0.3f)) }
) {
    DragAndDropTransferData(ClipData.newPlainText("itemId", item.id))
}

Modifier.dragAndDropTarget(
    shouldStartDragAndDrop = { event ->
        event.mimeTypes().contains(ClipData.MIMETYPE_TEXT_PLAIN)
    }
) { event ->
    val itemId = event.clipData.getItemAt(0).text.toString()
    viewModel.moveToDone(itemId)
    true
}
```

Cross-list DnD uses the Compose 1.7+ drag-and-drop framework. Within-list reorder uses pointer input — simpler and more performant.

## Failure modes

- **No key in LazyColumn items** — recomposition glitches on reorder
- **Drag without haptic feedback** — users unsure if drag mode activated
- **No alternative for accessibility** — TalkBack users can't reorder; need up/down buttons
- **Order not persisted** — reorder lost on configuration change; save to ViewModel immediately
- **Array index as sort order** — API returns different order; use explicit sort_order integers

## Production checklist

- `key` parameter set on all LazyColumn items
- Haptic feedback on drag start and drop
- Up/down button alternative for accessibility
- Order persisted to ViewModel on drag end (not just in local state)
- Explicit `sort_order` field in backend, not array index
- `animateItem()` for smooth reorder transitions

Provide haptic feedback on drag start and drop — TV and tablet users rely on tactile confirmation when pointer precision is limited.

## Resources

- [Compose pointer input](https://developer.android.com/jetpack/compose/touch-input/pointer-input)
- [LazyColumn animateItem](https://developer.android.com/reference/kotlin/androidx/compose/foundation/lazy/LazyItemScope#(androidx.compose.ui.Modifier).animateItem())
- [Compose drag and drop](https://developer.android.com/develop/ui/compose/touch-input/user-interactions/drag-and-drop)
- [detectDragGesturesAfterLongPress](https://developer.android.com/reference/kotlin/androidx/compose/foundation/gestures/package-summary#detectDragGesturesAfterLongPress(kotlin.Function0,kotlin.Function0,kotlin.Function0,kotlin.Function2))
