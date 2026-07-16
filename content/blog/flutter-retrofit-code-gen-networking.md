---
title: "Type-Safe Networking with Retrofit for Dart"
slug: "flutter-retrofit-code-gen-networking"
description: "Retrofit for Dart generates HTTP clients from abstract classes. Annotations for GET, POST, and query params with Dio under the hood."
datePublished: "2025-02-24"
dateModified: "2025-02-24"
tags: ["Flutter", "Dart", "Networking", "Mobile"]
keywords: "Retrofit Dart, Dio code generation, retrofit_generator Flutter, type-safe HTTP Dart, REST client Flutter"
faq:
  - q: "Retrofit vs raw Dio—which should I use?"
    a: "Raw Dio is fine for a handful of endpoints. Retrofit shines at ten-plus endpoints where maintaining path strings and serialization by hand drifts from your OpenAPI spec. Generate once, compile-check URLs and body types."
  - q: "Does Retrofit handle JSON serialization?"
    a: "Retrofit defines method signatures; pair it with json_serializable for request/response models or manual fromJson. The generator wires Dio calls—you still own model classes and converters for dates, enums, etc."
  - q: "How do I add auth headers globally?"
    a: "Configure Dio interceptors before passing Dio to Retrofit factory—same as plain Dio. Retrofit does not replace interceptors for tokens, logging, or retry logic."
---

Hand-written Dio calls across twelve services duplicated query parameter names three different ways. One typo in `'user_id'` vs `'userId'` shipped to production because integration tests mocked HTTP too loosely. Retrofit for Dart generates the client from an abstract class—wrong types fail at compile time, not in QA.

Retrofit.dart wraps Dio with interface definitions annotated by HTTP verb. `retrofit_generator` produces implementation classes at build time.

## Setup

```yaml
dependencies:
  dio: ^5.7.0
  retrofit: ^4.4.0
  json_annotation: ^4.9.0

dev_dependencies:
  build_runner: ^2.4.0
  retrofit_generator: ^9.1.0
  json_serializable: ^6.8.0
```

## API definition

```dart
import 'package:dio/dio.dart';
import 'package:retrofit/retrofit.dart';

part 'user_api.g.dart';

@RestApi(baseUrl: 'https://api.example.com/v1')
abstract class UserApi {
  factory UserApi(Dio dio, {String baseUrl}) = _UserApi;

  @GET('/users/{id}')
  Future<UserDto> getUser(@Path('id') String id);

  @GET('/users')
  Future<List<UserDto>> listUsers({
    @Query('page') int page = 1,
    @Query('limit') int limit = 20,
  });

  @POST('/users')
  Future<UserDto> createUser(@Body() CreateUserRequest body);
}
```

Generate:

```bash
dart run build_runner build --delete-conflicting-outputs
```

## Models with json_serializable

```dart
@JsonSerializable()
class UserDto {
  const UserDto({required this.id, required this.email});

  factory UserDto.fromJson(Map<String, dynamic> json) =>
      _$UserDtoFromJson(json);

  final String id;
  final String email;
}
```

Retrofit deserializes response bodies using `fromJson` when return types are custom classes—configure `Dio` with `JsonConverter` if needed.

## Dio configuration

```dart
Dio createDio() {
  final dio = Dio(BaseOptions(
    connectTimeout: const Duration(seconds: 10),
    receiveTimeout: const Duration(seconds: 30),
  ));

  dio.interceptors.addAll([
    AuthInterceptor(tokenProvider: tokenStore),
    LogInterceptor(requestBody: true, responseBody: true),
  ]);

  return dio;
}

final userApi = UserApi(createDio());
```

Keep cross-cutting concerns in interceptors, not generated code—regenerating would wipe manual edits.

## Error handling

Retrofit surfaces DioException on non-2xx unless you customize:

```dart
try {
  final user = await userApi.getUser('42');
} on DioException catch (e) {
  if (e.response?.statusCode == 404) {
    // handle not found
  }
}
```

Wrap at repository layer with Result types for cleaner UI handling.

## Multipart and file upload

```dart
@POST('/avatar')
@MultiPart()
Future<void> uploadAvatar(
  @Part(name: 'file') File file,
  @Part(name: 'user_id') String userId,
);
```

Use `MultipartFile.fromFile` on Dio 5.x as generator expects.

## Testing

Mock the abstract class or use Dio adapter:

```dart
dio.httpClientAdapter = MockAdapter()
  ..onGet('/users/1', (server) => server.reply(200, {'id': '1', 'email': 'a@b.c'}));
```

For unit tests without HTTP, mock `UserApi` with Mocktail.

## OpenAPI alignment

If backend publishes OpenAPI, tools can scaffold Retrofit interfaces—reduces drift. Manual Retrofit still beats string paths when spec changes trigger compile errors in return types.

## Base URL per environment

```dart
final dio = createDio();
final api = UserApi(dio, baseUrl: flavor.apiBaseUrl);
```

Avoid hardcoding `@RestApi(baseUrl: ...)` when staging and production differ—pass at factory time.

## Cancel tokens and long downloads

Dio `CancelToken` tied to widget dispose or Riverpod ref.onDispose:

```dart
@riverpod
Future<Report> report(ReportRef ref) async {
  final cancelToken = CancelToken();
  ref.onDispose(cancelToken.cancel);
  return ref.read(reportApiProvider).download(cancelToken);
}
```

Retrofit methods accept `@CancelRequest() CancelToken? cancel` when added to signature.

## Mock server testing

Use `http_mock_adapter` or custom `InterceptorsWrapper` returning fixture JSON—validate Retrofit parsing without hitting network in unit tests.

## OpenAPI sync

If backend ships OpenAPI, diff on CI when spec changes—regenerate or manually update Retrofit interfaces so new required fields fail compile instead of null at runtime.


## Enum and custom converters

Retrofit does not auto-convert all types—register `JsonConverter` on Dio for `DateTime`, enums, and loose-typed API quirks:

```dart
class IsoDateConverter implements JsonConverter<DateTime, String> {
  const IsoDateConverter();
  @override
  DateTime fromJson(String json) => DateTime.parse(json);
  @override
  String toJson(DateTime object) => object.toIso8601String();
}
```

## Logging sensitive endpoints

Disable `LogInterceptor` body logging for auth and payment endpoints in production builds—use `kDebugMode` guard or tree-shake via flavor.

## Retry policy

Implement retry in Dio interceptor for idempotent GETs only—POST retries risk duplicate side effects unless server supports idempotency keys.

## Version pinning

Lock `retrofit_generator` version in CI—generator output shifts between minor versions; unexpected `.g.dart` diffs block PRs until team reviews generator upgrade deliberately.

## Dynamic base URL interceptor

Interceptor reads flavor header to rewrite base URL for white-label apps—single Retrofit interface multi-tenant without codegen per tenant.

## Rollout guidance

API client major version synchronized mobile app semver major—consumers know major app bump may require backend deployment order documented runbook same page Retrofit interface changelog.

## Team practices

Shipping Flutter Retrofit Code Gen Networking in production taught our team that documentation beats hero demos. We wrote runbooks covering failure modes, on-call steps, and rollback triggers before the second release, not after the first outage.

When reviewing PRs touching Flutter Retrofit Code Gen Networking, we ask for measurable outcomes: latency, crash rate, or support ticket volume—not subjective feels faster. If metrics are unavailable, the PR includes a DevTools trace or load test snippet proving the change.

Onboarding engineers paste a checklist into their first Flutter Retrofit Code Gen Networking PR description: environment setup verified, tests added or updated, accessibility spot-checked, and release notes drafted for user-visible changes.

We keep a living FAQ in the repo wiki for Flutter Retrofit Code Gen Networking questions repeated in Slack more than twice. FAQ entries link to source files and Slack threads, reducing tribal knowledge and repeated explanations in code review.

Cross-functional review includes design for UX-facing work, security for auth or storage, and platform for native bridges. Flutter Retrofit Code Gen Networking spans layers; skipping reviewers recreated bugs we fixed months ago.

## Resources

- [retrofit.dart package](https://pub.dev/packages/retrofit)
- [retrofit_generator](https://pub.dev/packages/retrofit_generator)
- [Dio documentation](https://pub.dev/documentation/dio/latest/)
- [json_serializable](https://pub.dev/packages/json_serializable)
- [Retrofit GitHub (Dart)](https://github.com/trevorwang/retrofit.dart)
