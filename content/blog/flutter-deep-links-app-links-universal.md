---
title: "Deep Links and Universal Links"
slug: "flutter-deep-links-universal-links-universal"
description: "Configure Android App Links and iOS Universal Links in Flutter: go_router, app_links package, assetlinks.json, and debugging the failures that send users to Safari."
datePublished: "2024-10-16"
dateModified: "2024-10-16"
tags: ["Flutter", "Dart"]
keywords: "Flutter deep links, Universal Links iOS, Android App Links, go_router deep linking, app_links package"
faq:
  - q: "What is the difference between deep links and Universal Links?"
    a: "Deep links are URL schemes like myapp://product/123 that open your app if installed. Universal Links (iOS) and App Links (Android) use HTTPS URLs verified via hosted association files—links open the app directly without browser chooser when verification succeeds. HTTPS links are preferred for email, SMS, and web marketing because they degrade gracefully to your website."
  - q: "How do I handle deep links in Flutter with go_router?"
    a: "Define routes matching your URL paths in GoRouter configuration. Pass initial deep link via platform getInitialLink on cold start and listen to uriLinkStream for warm starts. go_router's redirect and path parameters map URL segments to screen arguments automatically when configured with correct path templates."
  - q: "Why do Universal Links open Safari instead of my Flutter app?"
    a: "Common causes: apple-app-site-association file missing or wrong content-type, Team ID or bundle ID mismatch, link clicked from same domain in Safari (iOS won't reopen app), or user long-pressed and chose Open in Safari which iOS remembers. Verify AASA with Apple's CDN cache and test from Notes app or Messages, not Safari address bar."
---

Marketing sent an email blast with `https://shop.example.com/products/42`. Tapping it opened Safari—not our Flutter app. The `apple-app-site-association` file was valid JSON but served as `application/octet-stream` instead of `application/json`. Two hours of debugging later, Universal Links worked. Deep linking is three problems: platform verification, Flutter routing, and cold-start vs warm-start handling. Miss any one and links fall through to the browser.

## Choose your linking strategy

| Type | URL example | Pros | Cons |
|------|-------------|------|------|
| Custom scheme | `myapp://item/5` | Easy setup | No web fallback, chooser dialogs |
| App Links / Universal | `https://example.com/item/5` | Verified, no chooser | Hosting AASA/assetlinks |
| Deferred deep links | Branch, Firebase Dynamic Links | Install attribution | Third-party dependency |

For production, implement HTTPS App Links + Universal Links. Keep custom scheme as fallback for dev testing.

## Flutter routing with go_router

```dart
final router = GoRouter(
  routes: [
    GoRoute(
      path: '/',
      builder: (_, __) => HomePage(),
      routes: [
        GoRoute(
          path: 'products/:id',
          builder: (_, state) => ProductPage(
            id: state.pathParameters['id']!,
          ),
        ),
      ],
    ),
  ],
);
```

Handle platform links with `app_links`:

```dart
final _appLinks = AppLinks();

Future<void> initDeepLinks() async {
  final initial = await _appLinks.getInitialLink();
  if (initial != null) _handleUri(initial);

  _appLinks.uriLinkStream.listen(_handleUri);
}

void _handleUri(Uri uri) {
  // https://shop.example.com/products/42 → /products/42
  router.go(uri.path);
}
```

Call `initDeepLinks()` after `GoRouter` is mounted—typically in app initState or bootstrap.

## Android App Links

**AndroidManifest.xml** intent filter with `autoVerify`:

```xml
<intent-filter android:autoVerify="true">
  <action android:name="android.intent.action.VIEW"/>
  <category android:name="android.intent.category.DEFAULT"/>
  <category android:name="android.intent.category.BROWSABLE"/>
  <data android:scheme="https"
        android:host="shop.example.com"
        android:pathPrefix="/products"/>
</intent-filter>
```

**assetlinks.json** at `https://shop.example.com/.well-known/assetlinks.json`:

```json
[{
  "relation": ["delegate_permission/common.handle_all_urls"],
  "target": {
    "namespace": "android_app",
    "package_name": "com.example.shop",
    "sha256_cert_fingerprints": ["AB:CD:..."]
  }
}]
```

Get fingerprint:

```bash
keytool -list -v -keystore upload-keystore.jks -alias upload
```

Verify:

```bash
adb shell pm get-app-links com.example.shop
```

Status should show `verified` for your domain.

## iOS Universal Links

**Runner.entitlements:**

```xml
<key>com.apple.developer.associated-domains</key>
<array>
  <string>applinks:shop.example.com</string>
</array>
```

**apple-app-site-association** at `https://shop.example.com/.well-known/apple-app-site-association` (no extension):

```json
{
  "applinks": {
    "apps": [],
    "details": [{
      "appID": "TEAMID.com.example.shop",
      "paths": ["/products/*", "/checkout/*"]
    }]
  }
}
```

Requirements:

- Served over HTTPS without redirects.
- Content-Type: `application/json` (Apple accepts `application/pkcs7-mime` too).
- No `.json` extension in URL.

Test with [Branch AASA validator](https://branch.io/resources/aasa-validator/) or `curl -I` the URL.

## Cold start vs warm start

**Cold start** — app killed, user taps link. OS launches app with link payload. Read via `getInitialLink()` / `getInitialUri()` once at startup.

**Warm start** — app backgrounded. Listen to `uriLinkStream`.

Handle both or first navigation after install-from-link breaks:

```dart
@override
void initState() {
  super.initState();
  _initDeepLinks();
}

Future<void> _initDeepLinks() async {
  try {
    final uri = await _appLinks.getInitialLink();
    if (uri != null && mounted) router.go(uri.path);
  } finally {
    _sub = _appLinks.uriLinkStream.listen((uri) {
      router.go(uri.path);
    });
  }
}
```

## Authentication and deep links

Links to protected routes need auth guards in go_router:

```dart
redirect: (context, state) {
  final loggedIn = authService.isLoggedIn;
  final goingToLogin = state.matchedLocation == '/login';
  if (!loggedIn && !goingToLogin) {
    return '/login?redirect=${Uri.encodeComponent(state.uri.toString())}';
  }
  return null;
},
```

After login, navigate to decoded redirect param.

### Debugging checklist

1. **Custom scheme works?** — If yes, Flutter routing is fine; platform config is the issue.
2. **AASA/assetlinks reachable?** — curl from external network, not localhost.
3. **Correct signing cert?** — Play App Signing uses Google's cert; upload that fingerprint to assetlinks.
4. **iOS clicked from same domain?** — Universal Links won't fire from Safari on same site; test from Messages.
5. **Flutter engine ready?** — defer navigation until after first frame if router throws.

Log every incoming URI during development:

```dart
void _handleUri(Uri uri) {
  debugPrint('Deep link: $uri');
  router.go(uri.path);
}
```

### Deferred deep linking note

Firebase Dynamic Links deprecation pushed teams toward custom deferred deep linking or third-party (Branch, Adjust). Universal Links handle post-install only if user tapped link before install and you implement native attribution storage—Flutter receives link on first open via same app_links stream. Test install attribution on both platforms; iOS clipboard-based deferred linking has privacy restrictions post-iOS 15.

Marketing UTM parameters on Universal Links pass through to Flutter Uri—strip analytics params in router redirect before matching routes. Store campaign metadata separately from path matching logic to prevent route-not-found on legitimate links with query strings.

Production teams should treat this guidance as living documentation: revisit assumptions after major platform upgrades, measure outcomes with real metrics rather than checklist compliance, and pair written standards with automated checks in CI. The patterns here reflect what held up in shipped apps—not theoretical perfection. Adapt thresholds, timeouts, and tooling to your stack, but keep the underlying principles: explicit configuration, testable behavior, and failure modes users can understand.

When onboarding new engineers, walk through one end-to-end example in a debug build before asking them to extend the pattern. Most failures I have seen came from skipped platform setup steps—manifest entries, API keys, code generation, or permission prompts—not from misunderstanding the Dart layer. Keep a troubleshooting section in your team wiki linking official docs and the exact commands that worked for your last upgrade.

Verify Android App Links assetlinks.json from production domain, not staging — Play Store review checks live domain verification.

## Resources

- [app_links package](https://pub.dev/packages/app_links)
- [go_router deep linking](https://pub.dev/documentation/go_router/latest/topics/Deep%20linking-topic.html)
- [Android App Links documentation](https://developer.android.com/training/app-links)
- [Apple Universal Links documentation](https://developer.apple.com/documentation/xcode/supporting-universal-links-in-your-app)
- [Flutter deep linking overview](https://docs.flutter.dev/ui/navigation/deep-linking)
