---
title: "Shell Routes and Nested Navigation in Flutter"
slug: "flutter-gorouter-shell-routes"
description: "ShellRoute and StatefulShellRoute in GoRouter give you a persistent bottom bar with independent per-tab navigation stacks. How to build nested navigation that keeps state."
datePublished: "2024-10-11"
dateModified: "2024-10-11"
tags: ["Flutter", "Dart", "Navigation", "Mobile"]
keywords: "Flutter ShellRoute, StatefulShellRoute, nested navigation Flutter, persistent bottom navigation, GoRouter tabs, per-tab navigation stack"
faq:
  - q: "What is the difference between ShellRoute and StatefulShellRoute?"
    a: "ShellRoute wraps child routes in shared UI (like a scaffold with a bottom bar) but uses a single nested Navigator, so switching sections does not preserve each section's own stack or scroll position. StatefulShellRoute gives each branch its own Navigator and its own state, so tab A stays exactly where you left it when you jump to tab B and back. For a typical multi-tab app you almost always want StatefulShellRoute."
  - q: "How do I keep scroll position when switching tabs in Flutter?"
    a: "Use StatefulShellRoute.indexedStack, which builds each branch inside an IndexedStack so all branches stay alive and retain their scroll offset, form state, and navigation depth. Switching branches just changes which child is visible rather than rebuilding it. Combine that with restorationId on your scrollables if you also need to survive process death."
  - q: "Can nested routes have their own deep links with ShellRoute?"
    a: "Yes. Each branch is a normal set of GoRoutes with URL patterns, so a deep link into /orders/42 opens the orders branch at the detail screen while keeping the shell chrome. The router resolves the URL to the correct branch and depth automatically, which is one of the main reasons to model tabs as shell branches rather than a manually managed IndexedStack."
---

`StatefulShellRoute` is how you build a Flutter app with a persistent bottom navigation bar where each tab keeps its own navigation stack, scroll position, and state when you switch away and back. It's the piece of GoRouter that turns "a bottom bar that resets everything" into the behavior users actually expect from native apps — jump from a five-screens-deep Orders flow over to Profile, come back, and Orders is still five screens deep, scrolled exactly where you left it.

I've seen more than one team fake this with a hand-managed `IndexedStack` and a pile of `GlobalKey<NavigatorState>` objects. It works until deep links show up, and then it collapses, because now you're manually mapping URLs onto nested navigators. Shell routes solve the whole thing declaratively.

## Two kinds of shell

GoRouter offers two, and picking the wrong one causes the classic "my tab lost its place" complaint.

`ShellRoute` puts shared chrome (an `AppBar`, a bottom bar, a `Scaffold`) around a **single** nested `Navigator`. All child routes share that one navigator, so there's exactly one stack. That's fine for something like a settings section with a shared frame, but it does **not** preserve independent per-tab stacks — switch tabs and you're navigating the same stack.

`StatefulShellRoute` gives each **branch** its own `Navigator` and its own state. Tab A and Tab B are genuinely independent trees. This is what you want for a standard multi-tab app.

## Building a persistent bottom bar

`StatefulShellRoute.indexedStack` is the workhorse. You define branches, each with its own routes, and a builder that renders the shared shell plus the currently active branch:

```dart
final router = GoRouter(
  initialLocation: '/feed',
  routes: [
    StatefulShellRoute.indexedStack(
      builder: (context, state, navigationShell) {
        return ScaffoldWithNavBar(navigationShell: navigationShell);
      },
      branches: [
        StatefulShellBranch(routes: [
          GoRoute(
            path: '/feed',
            builder: (c, s) => const FeedScreen(),
            routes: [
              GoRoute(
                path: 'post/:id',
                builder: (c, s) =>
                    PostScreen(id: s.pathParameters['id']!),
              ),
            ],
          ),
        ]),
        StatefulShellBranch(routes: [
          GoRoute(path: '/orders', builder: (c, s) => const OrdersScreen()),
        ]),
        StatefulShellBranch(routes: [
          GoRoute(path: '/profile', builder: (c, s) => const ProfileScreen()),
        ]),
      ],
    ),
  ],
);
```

Note the nested `routes:` under `/feed` — `post/:id` resolves to `/feed/post/42`, which lives *inside* the feed branch. That nesting is what makes deep links land in the right tab at the right depth.

## The shell widget

The `navigationShell` handed to your builder is a `StatefulNavigationShell`. It knows the current branch index and how to switch branches while preserving state:

```dart
class ScaffoldWithNavBar extends StatelessWidget {
  const ScaffoldWithNavBar({required this.navigationShell, super.key});
  final StatefulNavigationShell navigationShell;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: navigationShell,
      bottomNavigationBar: NavigationBar(
        selectedIndex: navigationShell.currentIndex,
        onDestinationSelected: (i) => navigationShell.goBranch(
          i,
          // tapping the active tab pops it to its root
          initialLocation: i == navigationShell.currentIndex,
        ),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.home), label: 'Feed'),
          NavigationDestination(icon: Icon(Icons.receipt), label: 'Orders'),
          NavigationDestination(icon: Icon(Icons.person), label: 'Profile'),
        ],
      ),
    );
  }
}
```

Two details worth internalizing. `navigationShell.goBranch(index)` is how you switch tabs — not `context.go`, which would treat it as a location change and not necessarily preserve the branch. And the `initialLocation: i == currentIndex` trick implements the native pattern where tapping the tab you're already on pops that branch back to its root — a small touch users unconsciously expect.

## Why indexedStack matters for state

`StatefulShellRoute.indexedStack` builds all branches inside an `IndexedStack`, meaning every branch stays mounted and only visibility changes when you switch. That's precisely why scroll offsets, half-filled forms, and animation state survive a tab switch — nothing is rebuilt or disposed. The trade-off is that all branches are alive in memory at once. For three to five tabs that's a non-issue; if you had dozens of heavy branches you'd reconsider, but that's not a real bottom-bar shape.

If you want laziness instead, there's a non-indexed constructor, but you'll give up the keep-alive behavior that makes this pattern worth using in the first place.

## Deep links land in the right branch

Because each branch is just URL patterns, an external link to `/feed/post/42` opens the feed branch at the post detail, with the shell chrome intact and the correct tab highlighted — no manual routing logic. This is the payoff over a hand-rolled `IndexedStack`: you don't write code to translate incoming URLs into "select tab 0, then push post 42." The route table already expresses it. This is the same declarative-navigation philosophy I covered in [GoRouter for declarative navigation](https://blog.michaelsam94.com/flutter-navigator-2-gorouter/).

## Gotchas I've hit

- **Nested vs top-level paths.** Child routes under a branch should generally use relative paths (`post/:id`, not `/post/:id`). A leading slash makes it a top-level path and it won't nest into the branch.
- **A shared root scaffold key.** If you show snackbars or dialogs from within branches, be deliberate about which `ScaffoldMessenger`/`Navigator` context you use, since there are now multiple navigators in play.
- **Back button on Android.** The system back pops within the active branch's navigator first, which is usually what you want; verify it against your product's expectations for what "back" does at a branch root.
- **Restoration.** Shell routes preserve state within a live process; to also survive an OS kill, pair scrollables with `restorationId` as covered in [Flutter state restoration](https://blog.michaelsam94.com/flutter-state-restoration/).

## What I'd take away

For any app with a persistent bottom bar or side rail, reach for `StatefulShellRoute.indexedStack`. Give each tab its own branch of routes, render the shared chrome around `navigationShell`, switch tabs with `goBranch`, and let the `IndexedStack` keep every branch's stack and scroll alive. You'll get native-feeling tab persistence and correct deep linking for free — and you'll never again wire up a fragile web of `GlobalKey<NavigatorState>` to fake it.

## Resources

- [StatefulShellRoute API reference](https://pub.dev/documentation/go_router/latest/go_router/StatefulShellRoute-class.html)
- [GoRouter package (pub.dev)](https://pub.dev/packages/go_router)
- [Navigation and routing (Flutter docs)](https://docs.flutter.dev/ui/navigation)
- [IndexedStack API reference](https://api.flutter.dev/flutter/widgets/IndexedStack-class.html)
- [Material NavigationBar reference](https://api.flutter.dev/flutter/material/NavigationBar-class.html)
