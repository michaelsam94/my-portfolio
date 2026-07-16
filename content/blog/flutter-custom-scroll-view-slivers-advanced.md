---
title: "Advanced Sliver Compositions"
slug: "flutter-custom-scroll-view-slivers-advanced"
description: "Master nested CustomScrollView slivers: SliverPersistentHeader, SliverAnimatedList, overlap absorption, and collapsing app bar patterns that scroll correctly."
datePublished: "2024-10-13"
dateModified: "2024-10-13"
tags: ["Flutter", "Dart"]
keywords: "Flutter slivers, CustomScrollView, SliverPersistentHeader, NestedScrollView, collapsing toolbar Flutter"
faq:
  - q: "When should I use slivers instead of ListView in Flutter?"
    a: "Use slivers when one scroll view combines heterogeneous scrolling sections—a collapsing app bar, sticky headers, and a list—or when you need scroll-linked animations between sections. ListView is a single sliver under the hood; CustomScrollView exposes the full sliver protocol for composition."
  - q: "What is SliverPersistentHeader used for?"
    a: "SliverPersistentHeader pins or shrinks a header as the user scrolls. delegate minExtent and maxExtent control collapse range. Use pinned: true for sticky section headers, floating: true for headers that reappear on scroll up. Common for filter bars and tab bars below collapsing toolbars."
  - q: "How do I fix NestedScrollView overlap issues?"
    a: "NestedScrollView coordinates an outer header sliver with an inner body scroll view via SliverOverlapAbsorber and SliverOverlapInjector. Without these, inner lists start under the header with incorrect padding. Match the inner scroll view's headerSliverBuilder with absorber/injector pairs from the Flutter documentation pattern."
---

The product screen needed a collapsing hero image, pinned category tabs, a pull-to-refresh list, and a floating action button that hides on scroll down. `Column` + `ListView` fought each other with nested scroll conflicts and janky overscroll. One `CustomScrollView` with the right slivers fixed it—and taught me that sliver composition is less about API memorization and more about understanding how scroll extents chain together.

## Sliver fundamentals

A **Sliver** is a scrollable segment with its own layout protocol. `CustomScrollView` stitches slivers into one scrollable:

```dart
CustomScrollView(
  slivers: [
    SliverAppBar(
      expandedHeight: 200,
      pinned: true,
      flexibleSpace: FlexibleSpaceBar(
        title: Text('Products'),
        background: Image.network(heroUrl, fit: BoxFit.cover),
      ),
    ),
    SliverToBoxAdapter(child: PromoBanner()),
    SliverList.builder(
      itemCount: products.length,
      itemBuilder: (_, i) => ProductTile(products[i]),
    ),
  ],
)
```

Each sliver reports geometry to the viewport. Total scroll extent = sum of sliver extents minus overlaps.

## SliverPersistentHeader patterns

Sticky section headers:

```dart
SliverPersistentHeader(
  pinned: true,
  delegate: _StickyTabDelegate(tabs: categories),
)

class _StickyTabDelegate extends SliverPersistentHeaderDelegate {
  _StickyTabDelegate({required this.tabs});
  final List<String> tabs;

  @override
  double get minExtent => 48;
  @override
  double get maxExtent => 48;

  @override
  Widget build(context, shrinkOffset, overlapsContent) {
    return Material(
      color: Theme.of(context).colorScheme.surface,
      child: TabBar(tabs: tabs.map((t) => Tab(text: t)).toList()),
    );
  }

  @override
  bool shouldRebuild(covariant _StickyTabDelegate old) =>
      old.tabs != tabs;
}
```

For collapsing headers, `minExtent < maxExtent` and use `shrinkOffset` to animate:

```dart
@override
Widget build(context, shrinkOffset, overlapsContent) {
  final progress = shrinkOffset / (maxExtent - minExtent);
  return Opacity(
    opacity: 1 - progress.clamp(0, 1),
    child: LargeHeader(),
  );
}
```

## NestedScrollView for tabbed content

TabBarView with independent scroll positions per tab:

```dart
NestedScrollView(
  headerSliverBuilder: (context, innerScrolled) => [
    SliverAppBar(
      title: Text('Store'),
      pinned: true,
      forceElevated: innerScrolled,
    ),
    SliverPersistentHeader(
      pinned: true,
      delegate: TabBarDelegate(tabController),
    ),
  ],
  body: TabBarView(
    controller: tabController,
    children: [
      _ProductList(category: 'all'),
      _ProductList(category: 'sale'),
    ],
  ),
)
```

Each tab body uses `CustomScrollView` with overlap handling:

```dart
CustomScrollView(
  slivers: [
    SliverOverlapInjector(
      handle: NestedScrollView.sliverOverlapAbsorberHandleFor(context),
    ),
    SliverList.builder(...),
  ],
)
```

The outer `NestedScrollView` wraps with `SliverOverlapAbsorber` in `headerSliverBuilder`. Skip this pair and content hides under the pinned header.

## SliverAnimatedList for dynamic items

Insert/remove with animation:

```dart
SliverAnimatedList(
  key: _listKey,
  initialItemCount: items.length,
  itemBuilder: (context, index, animation) {
    return SizeTransition(
      sizeFactor: animation,
      child: ItemTile(items[index]),
    );
  },
)

void _insert(int index, Item item) {
  items.insert(index, item);
  _listKey.currentState!.insertItem(index);
}
```

Works inside `CustomScrollView` unlike `AnimatedList` which needs bounded height in sliver context via `SliverFillRemaining` or explicit extent.

## Performance considerations

**Use builders:** `SliverList.builder`, `SliverGrid.builder` for long lists—lazy build.

**RepaintBoundary** on complex sliver children (images, charts).

**Avoid shrinkWrap: true** on inner ListViews inside slivers—forces full layout, kills laziness. Convert to `SliverList`.

**Cache extent:** tune for smoother scroll at memory cost:

```dart
CustomScrollView(cacheExtent: 500, slivers: [...])
```

## Pull-to-refresh with slivers

Material 3:

```dart
CustomScrollView(
  slivers: [
    SliverAppBar(...),
    SliverToBoxAdapter(child: ...),
    SliverFillRemaining(
      hasScrollBody: false,
      child: Center(child: Text('Empty')),
    ),
  ],
)
```

Or wrap with `RefreshIndicator` + `CustomScrollView` using `ScrollPhysics` that supports refresh. For sliver-native refresh, use `CupertinoSliverRefreshControl` on iOS-style apps.

### Debugging scroll issues

Enable debug painting:

```dart
debugPaintSizeEnabled = true; // layout boxes
```

Common bugs:

- **Gap at top of inner list** — missing `SliverOverlapInjector`.
- **Double scrollbars** — nested scrollables both scrollable; use one `CustomScrollView`.
- **Header jumps** — `shouldRebuild` returning true every frame on delegate.
- **FAB overlap** — use `Scaffold.extendBody` and pad list bottom by FAB height.

ScrollController listener on the outer view for hide/show FAB:

```dart
_scrollController.addListener(() {
  if (_scrollController.offset > _lastOffset && _scrollController.offset > 100) {
    setState(() => _showFab = false);
  } else if (_scrollController.offset < _lastOffset) {
    setState(() => _showFab = true);
  }
  _lastOffset = _scrollController.offset;
});
```

### CustomScrollView with SliverFillRemaining

Empty states and loading indicators often misuse unbounded shrinkWrap ListViews:

```dart
CustomScrollView(
  slivers: [
    SliverAppBar(title: Text('Orders')),
    SliverFillRemaining(
      hasScrollBody: false,
      child: Center(child: Text('No orders yet')),
    ),
  ],
)
```

`hasScrollBody: false` centers content in remaining viewport—better UX than zero-item SliverList for empty states.

SliverMainAxisGroup and SliverCrossAxisGroup (newer APIs) organize complex scroll sections with less manual extent math—evaluate against your Flutter SDK minimum. Stick to well-supported slivers when min SDK lags channel releases.

Production teams should treat this guidance as living documentation: revisit assumptions after major platform upgrades, measure outcomes with real metrics rather than checklist compliance, and pair written standards with automated checks in CI. The patterns here reflect what held up in shipped apps—not theoretical perfection. Adapt thresholds, timeouts, and tooling to your stack, but keep the underlying principles: explicit configuration, testable behavior, and failure modes users can understand.

When onboarding new engineers, walk through one end-to-end example in a debug build before asking them to extend the pattern. Most failures I have seen came from skipped platform setup steps—manifest entries, API keys, code generation, or permission prompts—not from misunderstanding the Dart layer. Keep a troubleshooting section in your team wiki linking official docs and the exact commands that worked for your last upgrade.

Schedule a quarterly review of this implementation against current SDK release notes—Flutter and cloud providers ship breaking changes on six-month cadences, and assumptions that held last year may need adjustment. Capture before-and-after metrics when you change configuration so regressions are obvious in retrospect rather than debated from memory.

Version-pin dependencies mentioned here in your pubspec.lock or infrastructure modules, and note the Flutter/Dart SDK constraint your team validated. Upgrading without re-running the verification steps in this article is the most common source of regressions. If something fails after an upgrade, compare release notes first, then your git history for the last known-good configuration.

## Resources

- [CustomScrollView API](https://api.flutter.dev/flutter/widgets/CustomScrollView-class.html)
- [Slivers overview (Flutter docs)](https://docs.flutter.dev/ui/layout/scrolling/slivers)
- [NestedScrollView API](https://api.flutter.dev/flutter/widgets/NestedScrollView-class.html)
- [SliverPersistentHeaderDelegate](https://api.flutter.dev/flutter/widgets/SliverPersistentHeaderDelegate-class.html)
- [SliverAnimatedList API](https://api.flutter.dev/flutter/widgets/SliverAnimatedList-class.html)
