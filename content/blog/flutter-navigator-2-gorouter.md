---
title: "GoRouter for Declarative Navigation in Flutter"
slug: "flutter-navigator-2-gorouter"
description: "GoRouter gives Flutter declarative, URL-driven navigation with deep links, redirects, and type-safe routes. Why it beats raw Navigator 2.0 and how to structure it."
datePublished: "2024-10-10"
dateModified: "2024-10-10"
tags: ["Flutter", "Dart", "Navigation", "Mobile"]
keywords: "Flutter GoRouter, declarative navigation Flutter, Navigator 2.0, Flutter deep links, GoRouter redirect, type-safe routes"
faq:
  - q: "Why use GoRouter instead of Navigator 2.0 directly?"
    a: "Navigator 2.0's raw Router API (RouterDelegate, RouteInformationParser, back button dispatcher) is powerful but notoriously verbose — you write hundreds of lines of boilerplate to get deep linking and browser URL sync right. GoRouter is the officially supported package that wraps that API behind a URL-pattern configuration, so you get declarative, deep-link-aware navigation without hand-rolling the delegate. It is maintained by the Flutter team, which makes it the pragmatic default."
  - q: "Does GoRouter support deep links out of the box?"
    a: "Yes. Because routes are defined as URL patterns, an incoming deep link or web URL is parsed into the matching route stack automatically, including path and query parameters. You still configure the platform side — Android App Links and iOS Universal Links — but on the Flutter side the same route table handles both in-app navigation and external links with no extra code."
  - q: "How do redirects work in GoRouter?"
    a: "GoRouter runs a redirect callback before building a route, letting you return a different location or null to proceed. This is the clean place to enforce authentication (send unauthenticated users to /login), gate onboarding, or normalize legacy URLs. Redirects run top-down and can be defined globally or per-route, and they re-run when the router's refreshListenable fires."
---

GoRouter is the officially supported way to do declarative, URL-driven navigation in Flutter, and for almost every new app it's the right default over hand-writing Navigator 2.0's `RouterDelegate` and `RouteInformationParser`. You describe your app as a table of URL patterns; GoRouter parses incoming links, deep links, and browser URLs into the matching route stack, and syncs the address bar on web. The imperative `Navigator.push` still exists and still works — but once your app has deep links, auth gating, and more than a handful of screens, a declarative route table is what keeps navigation from turning into spaghetti.

I moved a mid-sized production app off a bespoke Navigator 2.0 delegate onto GoRouter and deleted roughly 400 lines of routing plumbing. That's not an exaggeration; the raw Router API makes you implement serialization, back-button handling, and URL parsing yourself, and getting all three correct simultaneously is genuinely hard.

## Why not raw Navigator 2.0

Navigator 2.0 introduced a declarative model, which was the right idea, but the public API it shipped is a low-level toolkit, not an ergonomic router. To use it directly you implement a `RouterDelegate` that builds a `Navigator` from your app state, a `RouteInformationParser` that converts URLs to and from that state, and you wire up the back-button dispatcher. Every one of those is a place to introduce a subtle bug — a deep link that doesn't restore the right stack, a back press that pops the wrong route, a web refresh that loses your place.

GoRouter is the Flutter team's answer: it implements all of that once, correctly, and gives you a declarative configuration surface instead. You're still using Navigator 2.0 — GoRouter is built on it — you're just not writing the delegate.

## The route table

The whole app's navigation lives in one readable structure. Each `GoRoute` maps a URL pattern to a builder:

```dart
final router = GoRouter(
  initialLocation: '/',
  routes: [
    GoRoute(
      path: '/',
      builder: (context, state) => const HomeScreen(),
    ),
    GoRoute(
      path: '/product/:id',
      builder: (context, state) {
        final id = state.pathParameters['id']!;
        return ProductScreen(productId: id);
      },
    ),
    GoRoute(
      path: '/search',
      builder: (context, state) {
        final q = state.uri.queryParameters['q'] ?? '';
        return SearchScreen(query: q);
      },
    ),
  ],
);

MaterialApp.router(routerConfig: router);
```

Path parameters (`:id`) and query parameters both fall out of the URL for free. Because `/product/42` is just a string, the same table serves an in-app tap, an Android App Link, an iOS Universal Link, and a browser URL — there's no separate deep-link code path to keep in sync.

## Navigating: go vs push

GoRouter gives you two verbs, and the distinction matters:

- `context.go('/product/42')` sets the location — it replaces the current stack with whatever that URL implies. Use it for top-level navigation like switching tabs or jumping to a section.
- `context.push('/product/42')` pushes on top of the current stack, like the classic imperative push. Use it for drilling into detail from a list where back should return you.

Getting these mixed up produces the classic "back button does something weird" bug. My rule: `go` for lateral moves, `push` for going deeper.

## Redirects: where auth belongs

The redirect callback is the single feature that most cleans up real apps. It runs before a route builds and can send the user elsewhere:

```dart
GoRouter(
  refreshListenable: authState, // re-evaluate on login/logout
  redirect: (context, state) {
    final loggedIn = authState.isLoggedIn;
    final goingToLogin = state.matchedLocation == '/login';

    if (!loggedIn && !goingToLogin) return '/login';
    if (loggedIn && goingToLogin) return '/';
    return null; // proceed
  },
  routes: [...],
);
```

This replaces the scattered `if (!loggedIn) Navigator.push(...)` checks that otherwise metastasize across every screen. The `refreshListenable` is the piece people forget: without it, the redirect won't re-run when auth state changes, so a user who logs out stays on a protected screen until they navigate. Wire your auth notifier in and logout instantly bounces them to `/login`.

## Type-safe routes

String URLs are flexible but fragile — a typo in `'/prodcut/42'` compiles fine and fails at runtime. GoRouter's `go_router_builder` package generates type-safe route classes from annotated definitions, so navigation becomes `ProductRoute(id: 42).go(context)` and the compiler catches mistakes. For any app past a few screens I turn this on; the codegen step is worth eliminating a whole class of runtime navigation bugs.

## Nested navigation and shells

Real apps have a bottom nav bar or side rail where the chrome stays put while an inner area changes. That's `ShellRoute` and `StatefulShellRoute`, which keep persistent UI around a nested Navigator and — crucially — preserve each tab's own navigation stack and scroll position. That's a big enough topic that I gave it [its own walkthrough on shell routes and nested navigation](https://blog.michaelsam94.com/flutter-gorouter-shell-routes/); for now, know that GoRouter handles the persistent-shell pattern without you managing multiple `Navigator`s by hand.

## Deep links: the platform half

GoRouter parses the Flutter side, but you still configure the OS to hand your app the links:

1. **Android App Links** — add an `intent-filter` with `autoVerify` and host an `assetlinks.json` on your domain.
2. **iOS Universal Links** — enable Associated Domains and host an `apple-app-site-association` file.
3. Test with `adb shell am start -a android.intent.action.VIEW -d "https://yourapp.com/product/42"` and the equivalent on iOS.

Once the platform delivers the URL, your existing route table resolves it — including restoring the right stack — because the URL *is* the state. That serializable-state property also makes navigation play nicely with process death, complementing [state restoration](https://blog.michaelsam94.com/flutter-state-restoration/).

## What I'd take away

Reach for GoRouter on any new Flutter app rather than hand-rolling Navigator 2.0. Model your app as a table of URL patterns, use `go` for lateral navigation and `push` for depth, put authentication and gating in a `redirect` with a `refreshListenable`, and turn on type-safe routes once you're past a few screens. You get deep linking, web URL sync, and predictable back behavior essentially for free — and you delete the fragile delegate code you'd otherwise be maintaining forever.

## Resources

- [GoRouter package (pub.dev)](https://pub.dev/packages/go_router)
- [Navigation and routing (Flutter docs)](https://docs.flutter.dev/ui/navigation)
- [Deep linking (Flutter docs)](https://docs.flutter.dev/ui/navigation/deep-linking)
- [go_router_builder for type-safe routes](https://pub.dev/packages/go_router_builder)
- [Learning Flutter's new navigation and routing system (Flutter Medium)](https://medium.com/flutter/learning-flutters-new-navigation-and-routing-system-7c9068155ade)
