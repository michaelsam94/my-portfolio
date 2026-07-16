---
title: "Service Location with injectable"
slug: "flutter-injectable-service-locator"
description: "Automate Flutter DI with injectable and get_it: annotations, environments, modules, and codegen that scales past manual registration."
datePublished: "2024-11-30"
dateModified: "2024-11-30"
tags: ["Flutter", "Dart"]
keywords: "Flutter injectable, get_it code generation, dependency injection Flutter, injectable module, DI codegen Dart"
faq:
  - q: "What is injectable in Flutter?"
    a: "injectable is a code generator that scans Dart classes for @injectable, @singleton, and @lazySingleton annotations and generates get_it registration code. It eliminates manual registerFactory boilerplate and supports environments, modules for third-party types, and dependency ordering automatically."
  - q: "How does injectable work with get_it?"
    a: "You annotate classes, run build_runner, and call generated configureDependencies() which registers all services on GetIt.instance. injectable generates injection.config.dart mapping types to factories with correct constructor parameter resolution from other registered services."
  - q: "Can injectable handle different environments?"
    a: "Yes—use @Environment('dev') and @Environment('prod') annotations on implementations, then call configureDependencies(environment: Env.dev) at startup. Abstract interfaces can have environment-specific @Injectable(as: Interface) implementations registered conditionally."
---

Manual `get_it` registration in a 2000-line `injection.dart` file was our merge conflict hotspot. Every new repository meant editing the god file and hoping constructor order stayed valid. `injectable` generates registration from annotations—`@injectable` on the class, `build_runner`, call `getIt.init()`. Same get_it runtime, zero manual wiring. The generated file is gitignored or committed per team preference; either way, humans stop editing registration by hand.

## Setup

```yaml
dependencies:
  get_it: ^8.0.0
  injectable: ^2.5.0

dev_dependencies:
  injectable_generator: ^2.6.2
  build_runner: ^2.4.12
```

**lib/injection.dart:**

```dart
import 'package:get_it/get_it.dart';
import 'package:injectable/injectable.dart';
import 'injection.config.dart';

final getIt = GetIt.instance;

@InjectableInit()
Future<void> configureDependencies({String? environment}) async {
  await getIt.init(environment: environment);
}
```

**main.dart:**

```dart
void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await configureDependencies(environment: Environment.dev);
  runApp(MyApp());
}
```

## Annotating services

```dart
@lazySingleton
class AuthRepository {
  AuthRepository(this._api, this._storage);
  final AuthApi _api;
  final TokenStorage _storage;
}

@injectable
class LoginCubit {
  LoginCubit(this._authRepo);
  final AuthRepository _authRepo;
}
```

| Annotation | Registration |
|------------|--------------|
| `@injectable` | Factory (new each time) |
| `@lazySingleton` | Singleton on first access |
| `@singleton` | Singleton immediately |
| `@preResolve` | Async singleton awaited at init |

Generate:

```bash
dart run build_runner build --delete-conflicting-outputs
```

## Interface binding

```dart
@LazySingleton(as: AuthRepository)
class AuthRepositoryImpl implements AuthRepository {
  AuthRepositoryImpl(this._api);
  final AuthApi _api;
}

@injectable
class LoginCubit {
  LoginCubit(this._authRepo);
  final AuthRepository _authRepo; // resolves to Impl
}
```

`as:` registers implementation for abstract type.

## Modules for third-party types

Can't annotate external classes—use `@module`:

```dart
@module
abstract class AppModule {
  @lazySingleton
  Dio dio() => Dio(BaseOptions(baseUrl: Env.apiUrl));

  @preResolve
  Future<SharedPreferences> get prefs => SharedPreferences.getInstance();
}
```

`@preResolve` registers async dependencies; `configureDependencies` awaits them via generated `$initGetIt`.

## Environments

```dart
@LazySingleton(as: AnalyticsService, env: [Environment.dev])
class DebugAnalytics implements AnalyticsService {
  @override
  void logEvent(String name) => debugPrint('Analytics: $name');
}

@LazySingleton(as: AnalyticsService, env: [Environment.prod])
class FirebaseAnalyticsService implements AnalyticsService {
  // real implementation
}
```

```dart
await configureDependencies(environment: Environment.prod);
```

Pass environment matching `@InjectableInit(preferRelativeImports: false)` config.

## Named instances

```dart
@Named('authenticated')
@lazySingleton
Dio authenticatedDio(AuthInterceptor interceptor) {
  final dio = Dio();
  dio.interceptors.add(interceptor);
  return dio;
}

@injectable
class ProfileApi {
  ProfileApi(@Named('authenticated') this._dio);
  final Dio _dio;
}
```

### Testing with injectable

Reset and register mocks:

```dart
setUp(() async {
  await getIt.reset();
  getIt.registerFactory<AuthRepository>(() => MockAuthRepository());
  getIt.registerFactory(() => LoginCubit(getIt()));
});
```

Or use `@Environment('test')` mock implementations toggled in test `main`.

Alternative: don't use get_it in unit tests—pass mocks to constructors directly. Reserve generated DI for integration and widget tests.

### injectable vs manual get_it

| Aspect | Manual | injectable |
|--------|--------|------------|
| New service | Edit injection.dart | Add annotation |
| Constructor changes | Fix registration order | Regenerate |
| Large apps | Error-prone | Scales |
| Learning curve | Lower initial | Codegen setup |

### Common issues

1. **Missing `@InjectableInit()`** — no config generated.
2. **Circular deps** — refactor or use `@lazySingleton` to defer.
3. **Forgot build_runner** — stale injection.config.dart causes runtime missing registration.
4. **Abstract class without `as:`** — generator can't instantiate.

Commit `injection.config.dart` if CI shouldn't run codegen; gitignore if CI always builds fresh.

### Order of initialization

Async singletons like SharedPreferences and Isar must complete before runApp:

```dart
void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await configureDependencies();
  await getIt.allReady();
  runApp(App());
}
```

Missing allReady causes race where splash screen accesses uninitialized prefs—intermittent startup crashes hardest to reproduce.

MicroPackage injectable modules per feature register via external package init—call AuthPackageModule.init(getIt) from root configureDependencies keeping feature packages self-contained for monorepo extraction later without rewriting global injection.dart.

Production teams should treat this guidance as living documentation: revisit assumptions after major platform upgrades, measure outcomes with real metrics rather than checklist compliance, and pair written standards with automated checks in CI. The patterns here reflect what held up in shipped apps—not theoretical perfection. Adapt thresholds, timeouts, and tooling to your stack, but keep the underlying principles: explicit configuration, testable behavior, and failure modes users can understand.

When onboarding new engineers, walk through one end-to-end example in a debug build before asking them to extend the pattern. Most failures I have seen came from skipped platform setup steps—manifest entries, API keys, code generation, or permission prompts—not from misunderstanding the Dart layer. Keep a troubleshooting section in your team wiki linking official docs and the exact commands that worked for your last upgrade.

Schedule a quarterly review of this implementation against current SDK release notes—Flutter and cloud providers ship breaking changes on six-month cadences, and assumptions that held last year may need adjustment. Capture before-and-after metrics when you change configuration so regressions are obvious in retrospect rather than debated from memory.

Version-pin dependencies mentioned here in your pubspec.lock or infrastructure modules, and note the Flutter/Dart SDK constraint your team validated. Upgrading without re-running the verification steps in this article is the most common source of regressions. If something fails after an upgrade, compare release notes first, then your git history for the last known-good configuration.

Pair this setup with logging sufficient to diagnose field failures: request identifiers, cache keys, and user-visible error codes. Support teams need traceability from a screenshot to the underlying state without redeploying debug builds.

Add a smoke test that resolves each registered singleton at startup in debug builds—fail fast in development when injection.config.dart drifts from actual constructors after refactor.

Generate injectable config in CI to catch missing registrations — runtime `GetIt` errors on first navigation are hard to reproduce in tests.

## Resources

- [injectable package](https://pub.dev/packages/injectable)
- [injectable_generator](https://pub.dev/packages/injectable_generator)
- [get_it package](https://pub.dev/packages/get_it)
- [injectable documentation](https://pub.dev/packages/injectable/example)
- [Flutter dependency injection guide](https://docs.flutter.dev/app-architecture/recommendations#dependency-injection)
