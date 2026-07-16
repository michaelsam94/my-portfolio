---
title: "Embedding WebViews in Flutter"
slug: "flutter-webview-inappwebview"
description: "flutter_inappwebview and official webview_flutter embed web content with JS bridges, cookies, and navigation control. Security and performance notes."
datePublished: "2025-04-01"
dateModified: "2025-04-01"
tags: ["Flutter", "Dart", "WebView", "Mobile"]
keywords: "flutter_inappwebview, WebView Flutter, JavaScript channel Flutter, webview_flutter, hybrid app WebView"
faq:
  - q: "webview_flutter vs flutter_inappwebview?"
    a: "webview_flutter is the official minimal plugin—fine for simple URL display. flutter_inappwebview adds JS handlers, cookie managers, interceptors, pull-to-refresh, and desktop support—choose it for production hybrid features."
  - q: "How do I communicate between Flutter and JavaScript?"
    a: "Register JavaScript handlers that Dart listens to, and call evaluateJavascript from Flutter to invoke page functions. Define a narrow JSON message protocol—never pass raw user input into eval strings."
  - q: "Are WebViews a security risk?"
    a: "Yes if they load untrusted URLs or expose JS bridges to arbitrary pages. Allowlist domains, disable file access, validate SSL, and avoid exposing native capabilities to untrusted JS."
---

The payment provider shipped a hosted checkout page faster than we could build native PCI scope. We embedded it in `flutter_inappwebview`, wired a JS handler for `paymentComplete`, and closed the sheet when the bridge fired. The hard parts were cookie persistence, back-button behavior, and stopping the OAuth redirect from opening Safari instead of staying in-app.

## webview_flutter basics

```yaml
dependencies:
  webview_flutter: ^4.10.0
```

```dart
late final WebViewController controller;

@override
void initState() {
  super.initState();
  controller = WebViewController()
    ..setJavaScriptMode(JavaScriptMode.unrestricted)
    ..loadRequest(Uri.parse('https://docs.example.com'));
}

@override
Widget build(BuildContext context) {
  return WebViewWidget(controller: controller);
}
```

Sufficient for read-only docs with no bridge.

## flutter_inappwebview for hybrid apps

```yaml
dependencies:
  flutter_inappwebview: ^6.1.0
```

```dart
InAppWebView(
  initialUrlRequest: URLRequest(url: WebUri('https://app.example.com/checkout')),
  initialSettings: InAppWebViewSettings(
    javaScriptEnabled: true,
    allowsInlineMediaPlayback: true,
  ),
  onWebViewCreated: (webViewController) {
    _controller = webViewController;
    webViewController.addJavaScriptHandler(
      handlerName: 'paymentComplete',
      callback: (args) {
        final orderId = args.first as String;
        Navigator.pop(context, orderId);
      },
    );
  },
  shouldOverrideUrlLoading: (controller, action) async {
    final url = action.request.url;
    if (url?.host == 'evil.com') return NavigationActionPolicy.CANCEL;
    return NavigationActionPolicy.ALLOW;
  },
)
```

Page calls bridge:

```javascript
window.flutter_inappwebview.callHandler('paymentComplete', orderId);
```

## Cookies and auth

Share session cookies between native login and WebView:

```dart
final cookieManager = CookieManager.instance();
await cookieManager.setCookie(
  url: WebUri('https://app.example.com'),
  name: 'session',
  value: token,
  isSecure: true,
);
```

Verify SameSite and HttpOnly flags match server expectations—misconfigured cookies cause infinite login loops.

## Navigation and back button

```dart
PopScope(
  canPop: false,
  onPopInvoked: (didPop) async {
    if (didPop) return;
    if (await _controller.canGoBack()) {
      _controller.goBack();
    } else if (context.mounted) {
      Navigator.pop(context);
    }
  },
  child: InAppWebView(...),
)
```

Android back must pop WebView history before closing route.

## Performance

WebViews are heavy—avoid lists of many simultaneous instances. Prefer one full-screen WebView or load static native UI around it.

Warm up by preloading off-screen if UX requires instant display.

Clear cache on logout if pages cache sensitive data:

```dart
await InAppWebViewController.clearAllCache();
```

## Security checklist

- Allowlist hosts in `shouldOverrideUrlLoading`
- Disable universal file access
- Do not enable JavaScript on untrusted content
- Pin SSL or use HTTPS only
- Sanitize data passed to `evaluateJavascript`

## OAuth and redirect handling

Identity providers love redirect chains. When Google OAuth returns to `https://app.example.com/callback?code=...`, the WebView must stay in-app—not hand off to Chrome. Intercept custom schemes and app links:

```dart
shouldOverrideUrlLoading: (controller, action) async {
  final uri = action.request.url;
  if (uri == null) return NavigationActionPolicy.CANCEL;

  if (uri.scheme == 'myapp') {
    ref.read(authNotifierProvider.notifier).handleCallback(uri);
    return NavigationActionPolicy.CANCEL;
  }

  if (!_allowedHosts.contains(uri.host)) {
    return NavigationActionPolicy.CANCEL;
  }
  return NavigationActionPolicy.ALLOW;
},
```

Register the same callback URL in your native deep link config so cold-start OAuth still works if the user leaves mid-flow. Test with provider sandbox accounts; staging OAuth client IDs often differ from production.

Injecting cookies before load helps SSO: set session cookie, then `loadUrl` to `/dashboard` instead of forcing another login screen inside the WebView.

## User agent and desktop mode

Some sites serve broken mobile layouts inside WebView. Override user agent sparingly—payment gateways may reject non-standard agents:

```dart
initialSettings: InAppWebViewSettings(
  userAgent: 'MyApp/2.1 (Flutter; Android) AppleWebKit/537.36',
),
```

Document the UA string with vendors before production. iOS WKWebView and Android WebView differ in JavaScript engine features; feature-detect in JS rather than assuming Chrome desktop APIs.

## Testing hybrid flows

Widget tests struggle with real WebView—use integration tests on device for bridge contracts. Unit-test message parsing separately:

```dart
test('parses paymentComplete payload', () {
  final orderId = parsePaymentArgs(['ord_123']);
  expect(orderId, 'ord_123');
});
```

Maintain a stub HTML page in `assets/test/` that fires handlers on button click for QA builds. Log bridge traffic in debug only; redact tokens before crash reports.

## Platform differences worth planning for

Android allows multiple WebView implementations (Chrome WebView vs legacy). InAppWebView abstracts most differences, but file upload (`<input type="file">`) and geolocation permission prompts need platform-specific permission grants in `AndroidManifest.xml` and `Info.plist`.

iOS requires `NSAppTransportSecurity` exceptions only when absolutely necessary—prefer fixing server TLS. Android cleartext traffic blocked by default on newer API levels; do not load `http://` in production WebViews.

Memory: dispose controllers when routes pop. iOS WKWebView processes can linger if pages hold large media buffers—call `stopLoading()` before dispose on checkout completion.

## File upload and geolocation

Handle `onPermissionRequest` for camera/microphone inside WebView flows—delegate to app permission state:

```dart
onPermissionRequest: (controller, request) async {
  return PermissionResponse(
    resources: request.resources,
    action: PermissionResponseAction.GRANT,
  );
},
```

Grant only after app-level permission granted—do not auto-grant sensitive resources.

## Desktop WebView

flutter_inappwebview supports desktop targets—test Windows/macOS if shipping hybrid desktop; cookie isolation differs from mobile.


## SSL pinning interaction

If app pins SSL for native HTTP client, WebView may use separate trust store—configure WebView to respect pinning or exempt hosted pages consistently with security review.

## incognito mode

Some flows require no cookie persistence—use separate WebView profile or clear all storage on close for guest checkout.

## Print and PDF

Users may expect print from WebView content—platform print APIs differ; test share/print menu if contract requires.

## Zoom and text scaling

Respect system font scale inside WebView where possible—some CSS fixes font-size preventing accessibility zoom; coordinate with web team.

## Desktop cookie jar

Desktop WebView cookie persistence path differs—test login persistence on Windows/macOS targets if shipping Flutter desktop hybrid app to enterprise.

## Resources

- [flutter_inappwebview documentation](https://inappwebview.dev/docs/)
- [webview_flutter package](https://pub.dev/packages/webview_flutter)
- [flutter_inappwebview pub.dev](https://pub.dev/packages/flutter_inappwebview)
- [Android WebView security best practices](https://developer.android.com/privacy-and-security/risks/insecure-webview-usage)
- [Apple WKWebView documentation](https://developer.apple.com/documentation/webkit/wkwebview)
