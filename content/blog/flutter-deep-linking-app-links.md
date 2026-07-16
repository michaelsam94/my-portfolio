---
title: "Deep Linking and App Links in Flutter"
slug: "flutter-deep-linking-app-links"
description: "Flutter deep linking explained: App Links, Universal Links, and custom schemes, wiring go_router to handle URLs, verifying domains, and platform gotchas."
datePublished: "2026-02-26"
dateModified: "2026-02-26"
tags: ["Flutter", "Navigation", "Mobile"]
keywords: "Flutter deep linking, app links, universal links, go_router deep link, uni_links, navigation deep link"
faq:
  - q: "What is deep linking in Flutter?"
    a: "Deep linking is the ability for a URL to open your Flutter app directly to a specific screen rather than the home screen or a browser. It covers verified HTTPS links — Android App Links and iOS Universal Links — that open your app when a user taps a real web URL, as well as custom URI schemes like myapp://. Flutter surfaces the incoming link so your router can navigate to the matching destination."
  - q: "What's the difference between App Links and a custom URL scheme?"
    a: "A custom scheme like myapp://product/42 is easy to set up but unverified — any app can claim the same scheme, and the links don't work in a browser. Android App Links and iOS Universal Links use real https:// URLs verified against a file you host on your domain, so only your app can handle them and the same URL also works on the web. Verified links are the production-grade choice."
  - q: "Does go_router handle deep links automatically?"
    a: "Largely, yes. go_router integrates with Flutter's platform link handling, so an incoming URL is parsed against your route table and the matching route (including path and query parameters) is navigated to without manual plumbing. You still have to configure the native side — the intent filters, associated domains, and verification files — because that part lives outside Dart."
---

A user taps a link to your product in a WhatsApp message. Does it open a browser, or does it open your app right on that product's screen with the back stack intact? That difference is deep linking, and getting it right is one of those features that's invisible when it works and infuriating when it doesn't. In Flutter, deep linking spans three things: verified HTTPS links (Android App Links and iOS Universal Links), older custom URI schemes (`myapp://`), and the routing layer that turns an incoming URL into the correct screen. The Dart side is the easy part; the native configuration and domain verification are where teams lose a day.

I've wired this up for apps that get most of their traffic from shared links, and the reliability difference between a verified setup and a half-configured one is stark — verified links open instantly and silently, misconfigured ones bounce the user to a browser or a disambiguation dialog.

## Three kinds of links, ranked

Not all deep links are equal, and choosing the right kind up front saves rework:

| Type | Example | Verified? | Works in browser? |
|---|---|---|---|
| Custom scheme | `myapp://product/42` | No | No |
| Android App Links | `https://shop.com/product/42` | Yes (assetlinks.json) | Yes |
| iOS Universal Links | `https://shop.com/product/42` | Yes (AASA file) | Yes |

Custom schemes are trivial to set up and genuinely useful for internal or OAuth-callback flows, but they're unverified — any app can register `myapp://`, and pasting one into a browser does nothing. For anything user-facing in production, App Links and Universal Links are the right answer: they use real `https://` URLs that also render a web fallback, and the OS verifies that *only your app* may handle them. I default to verified links and reserve custom schemes for auth callbacks.

## Routing with go_router

On the Dart side, `go_router` does most of the work because it's URL-first by design. Your route table already describes paths and parameters, so an incoming deep link is just a URL matched against that table:

```dart
final router = GoRouter(
  routes: [
    GoRoute(path: '/', builder: (_, __) => const HomeScreen()),
    GoRoute(
      path: '/product/:id',
      builder: (context, state) =>
          ProductScreen(id: state.pathParameters['id']!),
    ),
    GoRoute(
      path: '/search',
      builder: (context, state) =>
          SearchScreen(query: state.uri.queryParameters['q']),
    ),
  ],
);
```

When `https://shop.com/product/42` arrives, `go_router` matches `/product/:id`, extracts `id = "42"`, and builds `ProductScreen`. Query parameters (`/search?q=shoes`) come through `state.uri.queryParameters`. There's no separate "deep link handler" to write — your routes *are* the handler, which is the whole appeal. This tidiness is why I pair deep linking with `go_router` rather than manual `Navigator` calls; it fits the same declarative philosophy I use for [state management with Riverpod](https://blog.michaelsam94.com/flutter-riverpod-state-management/), where the source of truth drives the UI rather than imperative navigation calls scattered around.

## The Android side: intent filters and assetlinks

This is where Dart stops helping. For App Links, you declare an intent filter in `AndroidManifest.xml` with `autoVerify`:

```xml
<intent-filter android:autoVerify="true">
    <action android:name="android.intent.action.VIEW" />
    <category android:name="android.intent.category.DEFAULT" />
    <category android:name="android.intent.category.BROWSABLE" />
    <data android:scheme="https" android:host="shop.com" />
</intent-filter>
```

Then you host a `assetlinks.json` file at `https://shop.com/.well-known/assetlinks.json` listing your app's package name and signing certificate fingerprint. Android fetches it to verify you own the domain. The trap that gets everyone: the fingerprint must match the certificate that *actually signs the installed build*. If you use Play App Signing, that's Google's key, not your upload key — get this wrong and links silently fall back to the browser with no error message. Verify with the App Links Assistant, not by hoping.

## The iOS side: associated domains and AASA

iOS Universal Links follow the same shape with different names. You add an Associated Domains entitlement (`applinks:shop.com`) in Xcode, and host an `apple-app-site-association` (AASA) file at `https://shop.com/.well-known/apple-app-site-association` — served as JSON with no file extension and no redirects. Apple caches this aggressively at install time, which is the classic iOS gotcha: change the AASA and existing installs may not pick it up until reinstall. Test on a fresh install, and don't trust that a link failing on your dev device means the file is wrong — it might just be cached.

## Cold start, warm start, and the sync trap

A link can arrive in two states, and both must work: the app is already running (warm), or the link launches it from dead (cold). Flutter's platform link handling covers both, and `go_router` navigates correctly either way, but *what you do on arrival* is your responsibility. The mistake I see constantly: deep-linking to `/product/42` and assuming the product data is loaded. On a cold start it isn't — nothing is loaded.

Handle the link as an entry point that must fetch its own data and degrade gracefully if offline:

```dart
GoRoute(
  path: '/product/:id',
  builder: (context, state) => ProductScreen(
    id: state.pathParameters['id']!,
    // ProductScreen fetches by id; shows loading, handles not-found
  ),
),
```

Because deep links routinely land users into screens with no warm cache, they interact directly with your offline strategy. If the device is on a flaky connection when the link opens — which is common, people tap links on the move — you want the graceful loading and cached fallbacks I covered in [offline-first Flutter sync](https://blog.michaelsam94.com/offline-first-flutter-sync/). A deep link into a spinner that never resolves is a worse experience than no deep link at all.

My checklist before shipping deep links: verified links for anything public, `go_router` routes that double as link handlers, native config tested on *fresh installs* on both platforms, and every deep-linkable screen able to load standalone from a cold start. Nail those four and shared links become a reliable growth channel instead of a support-ticket generator.

## Resources

- [Flutter deep linking documentation](https://docs.flutter.dev/ui/navigation/deep-linking)
- [go_router package on pub.dev](https://pub.dev/packages/go_router)
- [Android App Links guide](https://developer.android.com/training/app-links)
- [Apple Universal Links documentation](https://developer.apple.com/documentation/xcode/allowing-apps-and-websites-to-link-to-your-content)
- [Digital Asset Links protocol](https://developers.google.com/digital-asset-links)
