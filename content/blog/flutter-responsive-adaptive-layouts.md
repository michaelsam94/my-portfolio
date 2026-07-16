---
title: "Responsive and Adaptive Flutter Layouts"
slug: "flutter-responsive-adaptive-layouts"
description: "Breakpoints, LayoutBuilder, and adaptive navigation patterns for phones, tablets, and desktop. One codebase without squashed phone UI on iPad."
datePublished: "2025-02-18"
dateModified: "2025-02-18"
tags: ["Flutter", "Dart", "Layout", "Mobile"]
keywords: "Flutter responsive layout, adaptive navigation Flutter, LayoutBuilder breakpoints, Material 3 adaptive, Flutter tablet layout"
faq:
  - q: "What is the difference between responsive and adaptive in Flutter?"
    a: "Responsive usually means fluid layouts that reflow with available width—columns become rows, grids add tiles. Adaptive means platform-appropriate patterns—NavigationRail on wide windows, bottom bar on phone, perhaps Cupertino widgets on iOS. Most production apps need both."
  - q: "Should I use MediaQuery or LayoutBuilder for breakpoints?"
    a: "LayoutBuilder gives the constraints of the parent, which is correct inside split views or resizable windows. MediaQuery.sizeOf(context) reflects full screen—misleading in master-detail panes. Prefer LayoutBuilder for component-level breakpoints."
  - q: "Does Flutter support foldables and dual-screen devices?"
    a: "Yes via MediaQuery.displayFeatures and the two_pane or adaptive scaffold patterns. Detect hinges and avoid placing critical controls in the fold gutter. Test on Surface Duo emulator or Samsung Remote Test Lab."
---

Shipping phone layouts to tablet users produces giant stretched lists and wasted horizontal space. Shipping separate tablet apps doubles maintenance. Flutter's layout system—constraints down, sizes up—handles responsive design well if you choose breakpoints deliberately and adapt navigation chrome, not just column counts.

## Breakpoints that match content

Material 3 suggests approximate widths:

| Window | Width | Pattern |
|--------|-------|---------|
| Compact | < 600 dp | Single pane, bottom navigation |
| Medium | 600–840 dp | Optional side nav, two-column grids |
| Expanded | > 840 dp | NavigationRail or permanent drawer, master-detail |

Define constants once:

```dart
enum WindowSize { compact, medium, expanded }

WindowSize windowSizeFor(double width) {
  if (width < 600) return WindowSize.compact;
  if (width < 840) return WindowSize.medium;
  return WindowSize.expanded;
}
```

## LayoutBuilder at the root shell

```dart
class AppShell extends StatelessWidget {
  const AppShell({super.key});

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final size = windowSizeFor(constraints.maxWidth);

        return switch (size) {
          WindowSize.compact => const CompactScaffold(),
          WindowSize.medium => const MediumScaffold(),
          WindowSize.expanded => const ExpandedScaffold(),
        };
      },
    );
  }
}
```

Switch navigation pattern at the shell, not deep inside every screen—otherwise you chase inconsistent back behavior.

## Adaptive navigation with NavigationRail

```dart
class ExpandedScaffold extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Row(
        children: [
          NavigationRail(
            selectedIndex: _index,
            onDestinationSelected: (i) => setState(() => _index = i),
            destinations: _destinations,
          ),
          const VerticalDivider(width: 1),
          Expanded(child: _pages[_index]),
        ],
      ),
    );
  }
}
```

On compact, same routes render inside `NavigationBar`. `StatefulShellRoute` in GoRouter preserves stacks per destination across size class changes if you key navigators correctly—test rotation and window resize on desktop.

## Master-detail on wide screens

```dart
Widget buildOrders(BuildContext context, BoxConstraints constraints) {
  if (constraints.maxWidth >= 840) {
    return Row(
      children: [
        SizedBox(width: 360, child: OrderList(onSelect: _select)),
        const VerticalDivider(width: 1),
        Expanded(child: OrderDetail(id: _selectedId)),
      ],
    );
  }
  return OrderList(onSelect: (id) => context.push('/orders/$id'));
}
```

List-detail avoids duplicate routes on phone (push detail) vs tablet (selection state).

## Flexible grids with SliverGrid

```dart
SliverGrid(
  gridDelegate: SliverGridDelegateWithMaxCrossAxisExtent(
    maxCrossAxisExtent: 280,
    mainAxisSpacing: 16,
    crossAxisSpacing: 16,
    childAspectRatio: 1.2,
  ),
  delegate: SliverChildBuilderDelegate(...),
)
```

`maxCrossAxisExtent` adapts column count automatically—cleaner than hardcoding crossAxisCount per breakpoint for product grids.

## Text scale and accessibility

Responsive is not only width. Respect `MediaQuery.textScalerOf(context)`—fixed-height cards clip when users enable large text. Use `FittedBox` sparingly; prefer flexible layouts and max lines with ellipsis.

## Desktop and web considerations

Mouse hover states, keyboard shortcuts, and scroll wheel on nested scrollables matter on desktop targets. `ScrollConfiguration` with `PointerScrollDeviceKind` fixes trackpad vs mouse feel.

Minimum window sizes: set in macOS/Windows runner config so users cannot squash UI below usable breakpoints.

## Testing responsive layouts

```dart
testWidgets('shows rail on wide width', (tester) async {
  tester.view.physicalSize = const Size(1200, 800);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);

  await tester.pumpWidget(const MyApp());
  expect(find.byType(NavigationRail), findsOneWidget);
});
```

Golden tests at multiple sizes catch accidental regressions.

## Window resize on desktop and web

Flutter web and desktop apps resize live—users drag window across breakpoints. `LayoutBuilder` rebuilds on constraint change; preserve navigation state with `StatefulShellRoute` rather than resetting selected tab on resize.

```dart
final width = MediaQuery.sizeOf(context).width;
// Prefer constraints.maxWidth from LayoutBuilder inside split panes
```

## Canonical breakpoints vs content breakpoints

Material window size classes are starting points. A data-dense table may need expanded layout at 960dp while marketing hero stays compact until 600dp. Define **content breakpoints** per screen in design specs—not one global constant for entire app.

## Foldables and dual-pane

```dart
final displayFeatures = MediaQuery.displayFeaturesOf(context);
final hinge = displayFeatures.whereType<HingeDisplayFeature>().firstOrNull;
```

Avoid placing primary actions in hinge occlusion region. Span mode lists may use two columns automatically when `MediaQuery.sizeOf(context).width` exceeds threshold after unfold.

## Testing rotation and resize

Widget tests should cover compact → expanded transition:

```dart
tester.view.physicalSize = Size(400, 800);
await tester.pumpWidget(app);
expect(find.byType(NavigationBar), findsOneWidget);

tester.view.physicalSize = Size(1200, 800);
await tester.pumpAndSettle();
expect(find.byType(NavigationRail), findsOneWidget);
```

Golden both orientations for regression-sensitive marketing screens.


## Input modality

Desktop adds hover, keyboard focus rings, and context menus—`MouseRegion` on custom widgets; ensure focus traversal order logical on expanded NavigationRail layouts.

## Picture-in-picture and multi-window

Tablet multi-window splits width suddenly—LayoutBuilder responds; save selection state in ViewModel not local widget state lost on constraint jump.

## Design handoff

Figma frames for compact/medium/expanded per screen—not one mobile frame scaled. Engineers implement breakpoint behavior matching spec tables.

## Performance

Adaptive layouts with multiple navigators heavy—lazy-build off-screen branches where StatefulShellRoute allows.

## TV and large screen

Android TV and Apple TV need D-pad focus navigation—adaptive layout includes focus order on ten-foot UI not only touch targets; test with keyboard on desktop web same focus code paths.

## Additional measurement notes

Analytics event `layout_breakpoint` sampled 0.1% production reports compact/medium/expanded distribution informing design priority when resources constrained—data beats guessing which breakpoint neglected in QA.

## Team practices

Shipping Flutter Responsive Adaptive Layouts in production taught our team that documentation beats hero demos. We wrote runbooks covering failure modes, on-call steps, and rollback triggers before the second release, not after the first outage.

When reviewing PRs touching Flutter Responsive Adaptive Layouts, we ask for measurable outcomes: latency, crash rate, or support ticket volume—not subjective feels faster. If metrics are unavailable, the PR includes a DevTools trace or load test snippet proving the change.

Onboarding engineers paste a checklist into their first Flutter Responsive Adaptive Layouts PR description: environment setup verified, tests added or updated, accessibility spot-checked, and release notes drafted for user-visible changes.

We keep a living FAQ in the repo wiki for Flutter Responsive Adaptive Layouts questions repeated in Slack more than twice. FAQ entries link to source files and Slack threads, reducing tribal knowledge and repeated explanations in code review.

## Resources

- [Adaptive design (Flutter docs)](https://docs.flutter.dev/ui/adaptive-responsive)
- [Material 3 layout guidelines](https://m3.material.io/foundations/layout/applying-layout/window-size-classes)
- [LayoutBuilder API](https://api.flutter.dev/flutter/widgets/LayoutBuilder-class.html)
- [NavigationRail widget](https://api.flutter.dev/flutter/material/NavigationRail-class.html)
- [flutter_adaptive_scaffold package](https://pub.dev/packages/flutter_adaptive_scaffold)
