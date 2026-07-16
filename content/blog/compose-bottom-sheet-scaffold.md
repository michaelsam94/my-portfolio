---
title: "BottomSheetScaffold Patterns That Hold Up in Production"
slug: "compose-bottom-sheet-scaffold"
description: "Practical BottomSheetScaffold patterns in Jetpack Compose: persistent vs modal sheets, controlling sheet state, peek height, and handling back and config changes."
datePublished: "2024-09-04"
dateModified: "2024-09-04"
tags: ["Android", "Jetpack Compose", "Material 3", "UI"]
keywords: "BottomSheetScaffold, Compose bottom sheet, ModalBottomSheet, SheetState, persistent bottom sheet, peek height"
faq:
  - q: "What is the difference between BottomSheetScaffold and ModalBottomSheet?"
    a: "BottomSheetScaffold is for persistent sheets that stay attached to the screen and can be partially expanded via a peek height, like a map details panel. ModalBottomSheet is a transient overlay that dims the background and is dismissed by tapping the scrim or swiping down, like a share menu. Choose based on whether the sheet is part of the screen or an interruption on top of it."
  - q: "How do I programmatically expand or collapse a BottomSheetScaffold?"
    a: "Hold a BottomSheetScaffoldState from rememberBottomSheetScaffoldState, then call bottomSheetState.expand() or partialExpand() inside a coroutine scope. These are suspend functions because they animate, so launch them from rememberCoroutineScope in response to a click or event."
  - q: "How do I handle the back button with a bottom sheet in Compose?"
    a: "ModalBottomSheet handles back dismissal for you. For BottomSheetScaffold you add a BackHandler that is enabled only when the sheet is expanded, and collapse the sheet inside it, so the system back gesture collapses the sheet before navigating away."
---

`BottomSheetScaffold` is the right tool when a sheet is *part of* the screen — a persistent panel that peeks above the content and expands on demand, like the details drawer on a map. If the sheet is instead a transient interruption that should dim everything behind it, you want `ModalBottomSheet`. Getting this distinction right up front saves you from fighting the wrong component, which is the single most common mistake I see with Compose sheets.

Both live in Material 3 now, both are stateful, and both have sharp edges around back handling and configuration changes. I'll walk through the patterns I actually reach for, starting with the persistent case.

## Persistent sheets: the peek-height pattern

The defining feature of `BottomSheetScaffold` is `sheetPeekHeight` — the amount of the sheet visible when collapsed. This is what makes it a persistent panel rather than a modal. A ride-share app shows the trip summary at peek height and expands to full detail on drag.

```kotlin
val scaffoldState = rememberBottomSheetScaffoldState()

BottomSheetScaffold(
    scaffoldState = scaffoldState,
    sheetPeekHeight = 120.dp,
    sheetContent = {
        TripDetails(
            modifier = Modifier
                .fillMaxWidth()
                .navigationBarsPadding(),
        )
    },
) { innerPadding ->
    MapView(Modifier.padding(innerPadding))
}
```

Two things people forget here. First, apply `navigationBarsPadding()` inside the sheet content — otherwise your expanded controls sit under the gesture navigation bar. Second, the `innerPadding` the scaffold hands your main content already accounts for the peek height at the bottom, so respect it or your map's zoom controls hide behind the collapsed sheet.

## Driving the sheet programmatically

The sheet state is a first-class object you can command. `SheetState` exposes `expand()`, `partialExpand()`, and `hide()` (for skippable/hideable sheets). They're suspend functions because they animate, so you fire them from a coroutine scope:

```kotlin
val scope = rememberCoroutineScope()

Button(onClick = {
    scope.launch { scaffoldState.bottomSheetState.expand() }
}) {
    Text("Show full trip")
}
```

Read the current state with `scaffoldState.bottomSheetState.currentValue`, which is a `SheetValue` (`PartiallyExpanded`, `Expanded`, or `Hidden`). I use this to swap the FAB icon or toggle a header. Resist the urge to keep a *separate* boolean mirroring the sheet's openness; the `SheetState` is the source of truth, and duplicating it is how you end up with a header that says "expand" while the sheet is already expanded.

## Back handling that feels native

`ModalBottomSheet` intercepts back for you. `BottomSheetScaffold` does not — so a user who expands the sheet and hits back navigates *away from the screen* instead of collapsing the sheet, which feels wrong. Add a conditional `BackHandler`:

```kotlin
val expanded = scaffoldState.bottomSheetState.currentValue == SheetValue.Expanded

BackHandler(enabled = expanded) {
    scope.launch { scaffoldState.bottomSheetState.partialExpand() }
}
```

The `enabled` flag matters: when the sheet is at peek height, the handler is off and back navigates normally. Only when expanded does back collapse the sheet first. This two-step back behavior is exactly what users expect from Google Maps and Spotify's now-playing panel.

## Modal sheets: the transient case

When the sheet is an interruption — a filter menu, a share sheet, an action list — use `ModalBottomSheet`. It dims the background with a scrim, handles back and scrim-tap dismissal, and animates out when you set your visibility flag to false.

```kotlin
var showSheet by remember { mutableStateOf(false) }
val sheetState = rememberModalBottomSheetState()

if (showSheet) {
    ModalBottomSheet(
        onDismissRequest = { showSheet = false },
        sheetState = sheetState,
    ) {
        ShareOptions(onPicked = { option ->
            scope.launch { sheetState.hide() }
                .invokeOnCompletion { showSheet = false }
        })
    }
}
```

The subtlety: when you dismiss *programmatically* after an action, animate `hide()` first, then flip the boolean in `invokeOnCompletion`. If you just set `showSheet = false`, the sheet vanishes with no exit animation because the composable leaves the tree instantly. That two-phase dismissal is the polish difference between a sheet that snaps away and one that glides.

## Choosing between the two

| Question | Persistent (`BottomSheetScaffold`) | Modal (`ModalBottomSheet`) |
| --- | --- | --- |
| Is the sheet part of the screen? | Yes | No |
| Should the background be dimmed? | No | Yes |
| Peek height / partial visible? | Yes | Rarely |
| Back handling | You add `BackHandler` | Built in |
| Typical use | Map panel, player | Filters, share, actions |

## Surviving configuration changes

Sheet state survives recomposition because `rememberBottomSheetScaffoldState` uses a saver — but only the sheet's *open/closed* position. The *data* you show inside the sheet is your responsibility. If a user expands a details sheet for item 42 and rotates the device, you need item 42's identity in your state holder, not just in the composable. Keep the "which item is selected" in the ViewModel and let the sheet render from that, so rotation restores both the sheet position and its content. This is the same state-hoisting discipline that keeps [adaptive Compose layouts](https://blog.michaelsam94.com/adaptive-layouts-compose-grid-flexbox/) predictable across configuration changes.

## Nested scrolling inside the sheet

A long list inside an expanded sheet should scroll independently, and the sheet should only start dragging once the list is scrolled to the top. Material 3 wires this nested-scroll relationship automatically when your sheet content is a `LazyColumn` — you get it for free. The bug appears when you wrap the list in a fixed-height `Column` with `verticalScroll`; the handoff breaks and the whole sheet drags when you meant to scroll the list. Use lazy lists inside sheets and let the framework broker the scroll.

## What I'd take away

Pick the component by intent: persistent panel that belongs to the screen means `BottomSheetScaffold` with a peek height and a conditional `BackHandler`; transient overlay means `ModalBottomSheet` with two-phase dismissal for a clean exit animation. Treat `SheetState` as the single source of truth instead of mirroring it in a boolean, keep the sheet's *content identity* in your ViewModel so rotation restores it, and use lazy lists inside sheets so nested scrolling works. Those choices are what separate a sheet that feels engineered from one that feels bolted on.

## Resources

- [Bottom sheets in Compose (Android developers)](https://developer.android.com/develop/ui/compose/components/bottom-sheets)
- [BottomSheetScaffold API reference](https://developer.android.com/reference/kotlin/androidx/compose/material3/package-summary)
- [Material 3 bottom sheet guidance](https://m3.material.io/components/bottom-sheets/overview)
- [Handling back gestures in Compose](https://developer.android.com/develop/ui/compose/system/predictive-back)
