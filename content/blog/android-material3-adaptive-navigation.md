---
title: "Material 3 Adaptive Navigation Suite: One Nav for Every Form Factor"
slug: "android-material3-adaptive-navigation"
description: "Use the Material 3 adaptive navigation suite in Compose to switch between bottom bar, navigation rail, and drawer based on window size class across phones, foldables, tablets."
datePublished: "2024-07-31"
dateModified: "2024-07-31"
tags: ["Android", "Jetpack Compose", "Material 3", "Adaptive UI"]
keywords: "Material 3 adaptive navigation, NavigationSuiteScaffold, navigation rail Compose, adaptive navigation Android, window size class navigation"
faq:
  - q: "What is NavigationSuiteScaffold in Material 3?"
    a: "NavigationSuiteScaffold is a Compose component that automatically chooses the right navigation container — bottom navigation bar, navigation rail, or navigation drawer — based on the current window size class. You declare your destinations once and the scaffold swaps the presentation as the window grows or shrinks, so you don't hand-roll form-factor branching."
  - q: "When does the navigation suite show a rail versus a bottom bar?"
    a: "By default it shows a bottom navigation bar in compact width (phones in portrait) and a navigation rail in medium and expanded width (foldables, tablets, and large windows). You can override the selected type with a custom NavigationSuiteType if your design needs a drawer or a rail earlier, but the defaults follow Material guidance."
  - q: "Does the adaptive navigation suite handle foldables and split-screen?"
    a: "Yes, because it reacts to the window size class rather than the physical device. When a user unfolds a device or drags your app into split-screen, the window size class recomputes and the scaffold reflows from bottom bar to rail or back, preserving your selected destination through the change."
---

The Material 3 adaptive navigation suite exists so you stop writing `if (isTablet) NavigationRail() else BottomBar()`. `NavigationSuiteScaffold` takes one declaration of your top-level destinations and automatically renders a bottom navigation bar, a navigation rail, or a drawer depending on the current window size class — reflowing live as the user unfolds, rotates, or enters split-screen. I've replaced a hand-rolled adaptive nav layer with it and deleted roughly a third of the navigation code, along with the whole class of bugs that came from device sniffing.

## The problem it solves

Cross-form-factor navigation used to mean maintaining parallel component trees: a `NavigationBar` for phones, a `NavigationRail` for medium widths, a `ModalNavigationDrawer` for large ones — each wired to the same destinations, each a place for the wiring to drift out of sync. Add a destination and you edited three components. Miss one and the rail silently lacked a tab.

The adaptive suite collapses that into a single source of truth. You describe *what* the destinations are; the scaffold decides *how* to present them for the current window. That's the same principle behind all good [adaptive layout work in Compose](https://blog.michaelsam94.com/adaptive-layouts-compose-grid-flexbox/): decide on semantics once, high up, and let a component resolve presentation from window metrics.

## Minimal setup

The API is deliberately small. You give it items and the content:

```kotlin
@Composable
fun AppScaffold(currentDestination: Dest, onNavigate: (Dest) -> Unit) {
    NavigationSuiteScaffold(
        navigationSuiteItems = {
            Dest.entries.forEach { dest ->
                item(
                    selected = dest == currentDestination,
                    onClick = { onNavigate(dest) },
                    icon = { Icon(dest.icon, contentDescription = dest.label) },
                    label = { Text(dest.label) },
                )
            }
        }
    ) {
        // Your current screen content goes here.
        DestinationContent(currentDestination)
    }
}
```

No form-factor branch anywhere. On a compact phone this renders a bottom bar; on a foldable or tablet it becomes a rail; when the window is wide enough (and you opt in) it can present a drawer. Add a destination by adding an enum value — every layout updates at once.

## How it decides, and how to override

The scaffold reads `WindowAdaptiveInfo` (derived from the current window size class) and maps it to a `NavigationSuiteType`:

| Window width class | Default navigation type |
|---|---|
| Compact (phone portrait) | Bottom navigation bar |
| Medium (foldable, small tablet) | Navigation rail |
| Expanded (tablet, desktop window) | Navigation rail (or drawer if you opt in) |

When the defaults don't match your design, compute the type yourself and pass it in:

```kotlin
val adaptiveInfo = currentWindowAdaptiveInfo()
val customType = with(adaptiveInfo) {
    if (windowSizeClass.windowWidthSizeClass == WindowWidthSizeClass.EXPANDED)
        NavigationSuiteType.NavigationDrawer
    else NavigationSuiteScaffoldDefaults.calculateFromAdaptiveInfo(adaptiveInfo)
}

NavigationSuiteScaffold(
    layoutType = customType,
    navigationSuiteItems = { /* items */ },
) { /* content */ }
```

Reach for the override sparingly. The defaults encode Material guidance, and every override is a rule you now own and must re-check as new form factors appear.

## Pair it with list-detail, don't reinvent it

The navigation suite handles the *outer* chrome — which top-level section you're in. It does not, by itself, turn a list screen into a two-pane list-detail on a tablet. That's a separate adaptive concern handled by `NavigableListDetailPaneScaffold` from the same `material3-adaptive` family. The clean architecture is layered:

- **Outer:** `NavigationSuiteScaffold` picks bottom bar vs rail vs drawer.
- **Inner:** for sections that benefit, a list-detail pane scaffold splits content into two panes on wide windows and collapses to single-pane navigation on narrow ones.

Keeping these two concerns separate is what stops the classic mess where one component tries to own both the app-level nav and the per-screen pane logic and becomes unmaintainable.

## State, back handling, and continuity

A few things I learned the hard way integrating this with a `NavController`:

1. **Selection is your state, not the scaffold's.** The suite is presentational; you own "which destination is current" and hoist it. Drive `selected` from your nav back stack so bottom bar and rail always agree.
2. **Preserve selection across window changes.** Because an unfold or split-screen entry is effectively a configuration change, back your selected destination with `rememberSaveable` (or your nav state) so reflowing from bottom bar to rail doesn't drop the user's place.
3. **Mind back behavior per form factor.** With a drawer on large screens, users expect different back semantics than a bottom bar. Let your `NavController` own the back stack and keep the suite purely a view of it.

## Accessibility and touch targets come free-ish

Because you're using the real Material components under the hood, you inherit correct semantics: each item is announced with its label and selected state, touch targets meet the minimum size, and the rail/bar transitions don't strand focus. The one thing you must supply is a meaningful `contentDescription` (or label) per item — never ship an icon-only rail item with no accessible name. TalkBack users navigate by those names.

## What I'd take away

If you support anything beyond a phone, adopt `NavigationSuiteScaffold` and delete your device-sniffing navigation branches. Declare destinations once, let the scaffold map window size class to bottom bar, rail, or drawer, override only when your design truly requires it, and pair it with a list-detail pane scaffold for per-screen adaptivity. Hoist the selected destination so every presentation stays in sync, back it with saveable state so unfolds and split-screen preserve context, and give every item an accessible label. It's one of the highest-leverage adaptive components Compose has shipped — a lot of correctness for very little code.

## Resources

- [Build adaptive navigation (Android)](https://developer.android.com/develop/ui/compose/layouts/adaptive/build-adaptive-navigation)
- [NavigationSuiteScaffold reference](https://developer.android.com/reference/kotlin/androidx/compose/material3/adaptive/navigationsuite/package-summary)
- [Material 3 navigation guidance](https://m3.material.io/components/navigation-bar/overview)
- [androidx.compose.material3.adaptive releases](https://developer.android.com/jetpack/androidx/releases/compose-material3-adaptive)
- [Window size classes](https://developer.android.com/develop/ui/compose/layouts/adaptive/use-window-size-classes)
