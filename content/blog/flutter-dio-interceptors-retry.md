---
title: "Dio Interceptors and Retry Logic"
slug: "flutter-dio-interceptors-retry"
description: "Build resilient HTTP in Flutter with Dio interceptors: auth headers, token refresh, exponential backoff retries, and logging without leaking secrets."
datePublished: "2024-10-25"
dateModified: "2024-10-25"
tags: ["Flutter", "Dart"]
keywords: "Dio Flutter, Dio interceptor, retry logic Flutter, token refresh Dio, HTTP client Flutter"
faq:
  - q: "What are Dio interceptors in Flutter?"
    a: "Interceptors are middleware hooks in the Dio HTTP client wrapping request, response, and error phases. They modify outgoing requests (add auth headers), transform responses, and handle errors globally (retry, refresh tokens). Register them on Dio instance via interceptors.add() in dependency order."
  - q: "How do I retry failed requests with Dio?"
    a: "Implement QueuedInterceptor or Interceptor onError handler checking status codes and retry count. Use dio_smart_retry package or custom logic with exponential backoff delay. Retry only idempotent requests or POST with idempotency keys—blind POST retries cause duplicate side effects."
  - q: "How does token refresh work with Dio interceptors?"
    a: "On 401 response, interceptor pauses pending requests, calls refresh endpoint, updates stored token, clones failed request with new Authorization header, and resolves. Use a lock or queue to prevent multiple simultaneous refresh calls. On refresh failure, clear session and navigate to login."
---

The API returned 401 at 2 AM—not because credentials were wrong, but because the access token expired mid-session and our app showed a generic error instead of refreshing silently. Dio interceptors fixed it in one afternoon: attach tokens on the way out, catch 401 on the way back, refresh once, replay the queue. HTTP resilience belongs in the client layer, not scattered across twenty repository methods.

## Dio setup with interceptors

```dart
final dio = Dio(BaseOptions(
  baseUrl: 'https://api.example.com',
  connectTimeout: const Duration(seconds: 10),
  receiveTimeout: const Duration(seconds: 30),
  headers: {'Accept': 'application/json'},
));

dio.interceptors.addAll([
  AuthInterceptor(tokenStorage),
  RetryInterceptor(dio: dio),
  LogInterceptor(requestBody: true, responseBody: true),
]);
```

Order matters: auth before retry (retry needs fresh token), logging last to capture final request shape.

## Auth interceptor

```dart
class AuthInterceptor extends Interceptor {
  AuthInterceptor(this._storage);
  final TokenStorage _storage;

  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) async {
    final token = await _storage.readAccessToken();
    if (token != null) {
      options.headers['Authorization'] = 'Bearer $token';
    }
    handler.next(options);
  }
}
```

Skip auth for public endpoints:

```dart
if (options.extra['skipAuth'] == true) {
  handler.next(options);
  return;
}
```

Call with: `dio.get('/public', options: Options(extra: {'skipAuth': true}))`.

## Token refresh on 401

```dart
class RefreshTokenInterceptor extends QueuedInterceptor {
  RefreshTokenInterceptor(this._dio, this._storage);
  final Dio _dio;
  final TokenStorage _storage;

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) async {
    if (err.response?.statusCode != 401) {
      handler.next(err);
      return;
    }

    try {
      final newToken = await _refreshToken();
      await _storage.saveAccessToken(newToken);
      err.requestOptions.headers['Authorization'] = 'Bearer $newToken';
      final response = await _dio.fetch(err.requestOptions);
      handler.resolve(response);
    } catch (e) {
      await _storage.clear();
      authEventBus.emit(LoggedOut());
      handler.next(err);
    }
  }

  Future<String> _refreshToken() async {
    final refresh = await _storage.readRefreshToken();
    final response = await Dio().post(
      'https://api.example.com/auth/refresh',
      data: {'refresh_token': refresh},
    );
    return response.data['access_token'] as String;
  }
}
```

`QueuedInterceptor` serializes concurrent 401s—one refresh, many replays. Without queuing, five parallel 401s trigger five refresh calls and race conditions.

## Retry with exponential backoff

Custom retry interceptor:

```dart
class RetryInterceptor extends Interceptor {
  RetryInterceptor({required this.dio, this.maxRetries = 3});
  final Dio dio;
  final int maxRetries;

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) async {
    final retryCount = err.requestOptions.extra['retryCount'] as int? ?? 0;

    if (!_shouldRetry(err) || retryCount >= maxRetries) {
      handler.next(err);
      return;
    }

    final delay = Duration(milliseconds: 500 * pow(2, retryCount).toInt());
    await Future.delayed(delay);

    err.requestOptions.extra['retryCount'] = retryCount + 1;
    try {
      final response = await dio.fetch(err.requestOptions);
      handler.resolve(response);
    } catch (e) {
      handler.next(e is DioException ? e : err);
    }
  }

  bool _shouldRetry(DioException err) {
    if (err.type == DioExceptionType.connectionTimeout ||
        err.type == DioExceptionType.receiveTimeout) return true;
    final code = err.response?.statusCode;
    return code == 502 || code == 503 || code == 504;
  }
}
```

Or use `dio_smart_retry`:

```dart
dio.interceptors.add(RetryInterceptor(
  dio: dio,
  retries: 3,
  retryDelays: [
    Duration(seconds: 1),
    Duration(seconds: 2),
    Duration(seconds: 4),
  ],
));
```

Never retry 401 here—that's refresh interceptor's job. Never retry non-idempotent POST without idempotency keys.

## Logging safely

```dart
dio.interceptors.add(LogInterceptor(
  requestHeader: true,
  requestBody: true,
  responseHeader: false,
  responseBody: kDebugMode,
  logPrint: (obj) => debugPrint(obj.toString()),
));
```

Redact tokens in custom logger:

```dart
class SafeLogInterceptor extends Interceptor {
  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    final headers = Map.of(options.headers);
    if (headers.containsKey('Authorization')) {
      headers['Authorization'] = 'Bearer [REDACTED]';
    }
    debugPrint('→ ${options.method} ${options.uri} headers=$headers');
    handler.next(options);
  }
}
```

Disable verbose body logging in release builds—PII in logs is a compliance incident.

## Error mapping

Centralize in error interceptor or repository base:

```dart
DioException _ mapDioError(DioException err) {
  switch (err.type) {
    case DioExceptionType.connectionTimeout:
      return err.copyWith(message: 'Connection timed out');
    case DioExceptionType.badResponse:
      final data = err.response?.data;
      if (data is Map && data['message'] != null) {
        return err.copyWith(message: data['message'] as String);
      }
    default:
      return err;
  }
}
```

Presentation layer receives domain `NetworkFailure`, not raw `DioException`.

### Testing interceptors

Use `MockAdapter` from `http_mock_adapter`:

```dart
final dio = Dio();
final adapter = MockAdapter(dio);

adapter.onGet('/users', (server) => server.reply(200, {'id': 1}));

adapter.onGet('/protected', (server) => server.reply(401, {}), headers: {});
// Test refresh replay separately
```

Verify retry count and token refresh with sequential mock responses.

### CancelToken for disposed widgets

Pass CancelToken from widget dispose to Dio requests:

```dart
final cancelToken = CancelToken();
try {
  await dio.get('/data', cancelToken: cancelToken);
} on DioException catch (e) {
  if (CancelToken.isCancel(e)) return;
  rethrow;
}
// dispose: cancelToken.cancel()
```

Retry interceptors should respect cancellation—don't retry if token already cancelled. Prevents setState after dispose when user navigates away mid-request.

Log request IDs from server response headers in interceptors—support tickets correlate client logs with backend traces. Interceptor order documented in code comment: Auth → Retry → Log → Cache (if any). Changing order breaks refresh-retry interaction silently.

Production teams should treat this guidance as living documentation: revisit assumptions after major platform upgrades, measure outcomes with real metrics rather than checklist compliance, and pair written standards with automated checks in CI. The patterns here reflect what held up in shipped apps—not theoretical perfection. Adapt thresholds, timeouts, and tooling to your stack, but keep the underlying principles: explicit configuration, testable behavior, and failure modes users can understand.

When onboarding new engineers, walk through one end-to-end example in a debug build before asking them to extend the pattern. Most failures I have seen came from skipped platform setup steps—manifest entries, API keys, code generation, or permission prompts—not from misunderstanding the Dart layer. Keep a troubleshooting section in your team wiki linking official docs and the exact commands that worked for your last upgrade.

## Resources

- [Dio package](https://pub.dev/packages/dio)
- [Dio interceptors documentation](https://pub.dev/documentation/dio/latest/dio/Interceptor-class.html)
- [dio_smart_retry package](https://pub.dev/packages/dio_smart_retry)
- [QueuedInterceptor API](https://pub.dev/documentation/dio/latest/dio/QueuedInterceptor-class.html)
- [http_mock_adapter](https://pub.dev/packages/http_mock_adapter)
