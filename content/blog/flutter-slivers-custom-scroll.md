---
title: "Building Custom Scroll Effects with Slivers in Flutter"
slug: "flutter-slivers-custom-scroll"
description: "Slivers power Flutter's custom scroll effects: collapsing headers, pinned bars, and mixed content in one scroll view. How CustomScrollView and sliver widgets fit together."
datePublished: "2024-10-12"
dateModified: "2024-10-12"
tags: ["Flutter", "Dart", "UI", "Performance"]
keywords: "Flutter slivers, CustomScrollView, SliverAppBar, collapsing header Flutter, SliverList, SliverPersistentHeader, custom scroll"
faq:
  - q: "What is a sliver in Flutter?"
    a: "A sliver is a portion of a scrollable area that knows how to render itself lazily based on the current scroll viewport. Widgets like SliverList, SliverGrid, and SliverAppBar are slivers, and they compose inside a CustomScrollView so that a single scroll view can mix lists, grids, and collapsing headers. The name refers to the thin slice of content that is actually visible and being laid out at any moment."
  - q: "When should I use CustomScrollView instead of ListView?"
    a: "Use CustomScrollView when you need multiple scrollable sections or effects to scroll together as one — for example a collapsing header above a list above a grid. ListView is a convenience wrapper around a single sliver and is perfect for a plain list, but the moment you want a SliverAppBar, mixed section types, or a pinned header, you drop down to CustomScrollView and compose slivers directly."
  - q: "How do I make a collapsing app bar in Flutter?"
    a: "Put a SliverAppBar as the first sliver in a CustomScrollView and configure floating, pinned, and snap plus a FlexibleSpaceBar for the expanding content. Set expandedHeight for the tall state; pinned keeps a bar visible when collapsed, floating brings it back on any upward scroll. For fully custom collapse behavior, use SliverPersistentHeader with your own delegate."
---

Slivers are how Flutter builds scroll effects that a plain `ListView` can't touch: a collapsing hero header that shrinks into a toolbar, a section header that pins to the top, a list and a grid that scroll together as one surface. A sliver is a scrollable region that lays itself out lazily against the current viewport, and `CustomScrollView` is the container that stitches several of them into a single, coordinated scroll. If you've ever wanted the header to shrink while the list keeps scrolling underneath it, slivers are the answer.

Most Flutter developers meet slivers only through `SliverAppBar`, copy a snippet, and never learn the model underneath. That's a shame, because once the mental model clicks, an entire category of "how do I even build that" scroll UIs becomes routine.

## The mental model

Everyday scrollables — `ListView`, `GridView` — are thin conveniences wrapping a single sliver inside a viewport. `CustomScrollView` removes the wrapper and hands you the raw composition surface: a `slivers:` list where each entry is a self-contained scrollable region. The viewport asks each sliver, in order, "given the current scroll offset, how much space do you occupy and what should I paint?" That protocol is what lets a header, a list, and a grid negotiate one shared scroll position.

```dart
CustomScrollView(
  slivers: [
    SliverAppBar(
      expandedHeight: 240,
      pinned: true,
      flexibleSpace: FlexibleSpaceBar(
        title: const Text('Trail Guide'),
        background: Image.network(headerUrl, fit: BoxFit.cover),
      ),
    ),
    const SliverToBoxAdapter(child: IntroCard()),
    SliverList.builder(
      itemCount: sections.length,
      itemBuilder: (context, i) => SectionTile(sections[i]),
    ),
    SliverGrid.count(
      crossAxisCount: 2,
      children: gallery.map(PhotoTile.new).toList(),
    ),
  ],
);
```

That single scroll view collapses a header, shows a one-off card, then a list, then a grid — all sharing one scrollbar and one fling. You can't express that with nested `ListView`s without fighting nested scrolling.

## The core sliver vocabulary

A handful of slivers cover almost everything:

- **`SliverAppBar`** — the collapsing/pinning/floating toolbar.
- **`SliverList` / `SliverList.builder`** — lazily built lists (the sliver form of `ListView.builder`).
- **`SliverGrid`** — lazily built grids.
- **`SliverToBoxAdapter`** — wraps a single ordinary (box) widget so it can live among slivers. Great for a one-off banner; bad for a long list, because it builds everything at once.
- **`SliverPersistentHeader`** — a header that can pin or float with fully custom collapse logic.
- **`SliverFillRemaining`** — fills whatever viewport space is left, handy for empty states.
- **`SliverPadding`** — because you can't wrap a sliver in an ordinary `Padding`; padding itself must be a sliver.

That last point trips everyone up once: box widgets and slivers don't mix directly. You adapt a box into sliver-space with `SliverToBoxAdapter`, and you use sliver-specific versions of things like padding.

## SliverAppBar: the flags that matter

The collapsing header's behavior is entirely in three booleans, and their combinations define the feel:

| pinned | floating | snap | Behavior |
|---|---|---|---|
| true | false | — | Bar collapses to a persistent toolbar that stays on screen |
| false | true | false | Bar hides on scroll down, reappears on any scroll up |
| false | true | true | Same, but snaps fully open/closed instead of tracking finger |
| true | true | true | Toolbar always visible; expanded area snaps back on scroll up |

I reach for `pinned: true` for content where the title must always be reachable, and `floating: true, snap: true` for feeds where I want to reclaim vertical space but let the user summon the bar with a flick. `expandedHeight` plus a `FlexibleSpaceBar` gives you the tall hero state and the interpolation down to the collapsed bar automatically.

## SliverPersistentHeader for custom collapse

When you need a header that isn't an app bar — a pinned filter row, a stats strip that shrinks — `SliverPersistentHeader` with a `SliverPersistentHeaderDelegate` gives you frame-by-frame control:

```dart
class _StatsHeaderDelegate extends SliverPersistentHeaderDelegate {
  @override
  double get minExtent => 56;
  @override
  double get maxExtent => 140;

  @override
  Widget build(BuildContext context, double shrinkOffset, bool overlapsContent) {
    final t = (shrinkOffset / (maxExtent - minExtent)).clamp(0.0, 1.0);
    return StatsStrip(collapse: t); // interpolate opacity/size on t
  }

  @override
  bool shouldRebuild(covariant _StatsHeaderDelegate old) => false;
}
```

The `shrinkOffset` is how far the header has collapsed; you normalize it to a 0–1 progress `t` and drive any interpolation you like — fade a subtitle, shrink an avatar, slide a search bar in. This is the escape hatch when the built-in app bar animations aren't enough.

## Performance: laziness is the whole point

The reason slivers exist is lazy building. `SliverList.builder` and `SliverGrid.builder` only build the items near the viewport, so a 10,000-row list costs the same as a 20-row one. The anti-pattern I flag most in reviews is stuffing a big list into a `SliverToBoxAdapter(child: Column(children: [...]))` — that builds every child eagerly and throws away the entire benefit. If it scrolls and it's long, it must be a builder-based sliver.

Two more habits: pass stable `key`s to items so reordering doesn't recompose the wrong widgets, and keep item widgets `const` where possible. These are the same fundamentals that make any Flutter list smooth, and they compound in a `CustomScrollView` with multiple sections.

## When the physics need to change too

Slivers control *what* scrolls; `ScrollPhysics` controls *how* it feels — the friction, the bounce, the snap. If your custom scroll effect also needs unusual momentum or paging behavior, that's a separate lever I cover in [custom scroll physics in Flutter](https://blog.michaelsam94.com/flutter-custom-scroll-physics/). And if a header effect needs to paint something the standard slivers can't express, you can drop to a [CustomPainter](https://blog.michaelsam94.com/flutter-canvas-custom-painter/) inside a sliver.

## What I'd take away

Reach for `CustomScrollView` the moment a screen needs more than one scrolling behavior in a single surface — a collapsing header over a list over a grid. Learn the small sliver vocabulary, remember that box widgets need `SliverToBoxAdapter` to join the party, and drive custom collapse effects through `SliverPersistentHeader`'s `shrinkOffset`. Above all, keep long content in builder-based slivers so laziness does its job. Once the composition model clicks, the fancy scroll screens stop feeling like magic and start feeling like plumbing.

## Resources

- [Slivers (Flutter docs)](https://docs.flutter.dev/ui/layout/scrolling/slivers)
- [Using slivers to achieve fancy scrolling (Flutter cookbook)](https://docs.flutter.dev/cookbook/lists/floating-app-bar)
- [SliverAppBar API reference](https://api.flutter.dev/flutter/material/SliverAppBar-class.html)
- [SliverPersistentHeader API reference](https://api.flutter.dev/flutter/widgets/SliverPersistentHeader-class.html)
- [CustomScrollView API reference](https://api.flutter.dev/flutter/widgets/CustomScrollView-class.html)
