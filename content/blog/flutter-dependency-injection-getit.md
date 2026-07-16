---
title: "Dependency Injection with get_it"
slug: "flutter-dependency-injection-getit"
description: "Wire Flutter apps with get_it: singletons, factories, async registration, testing fakes, and scoping patterns that don't become a service locator mess."
datePublished: "2024-10-19"
dateModified: "2024-10-19"
tags: ["Flutter", "Dart"]
keywords: "Flutter get_it, service locator, dependency injection Dart, get_it singleton, Flutter DI testing"
faq:
  - q: "What is get_it in Flutter?"
    a: "get_it is a pure Dart service locator providing global or scoped registration of dependencies by type. Register implementations at app startup with registerSingleton, registerLazySingleton, or registerFactory; resolve anywhere via getIt<Type>() without passing dependencies through every constructor manually."
  - q: "Is get_it the same as dependency injection?"
    a: "get_it implements service locator pattern—a form of DI. Constructor injection purists prefer passing dependencies explicitly; get_it trades some explicitness for ergonomics in large Flutter apps. Combining both—constructor injection resolved from get_it at the composition root—is a common compromise."
  - q: "How do I reset get_it for Flutter tests?"
    a: "Call await getIt.reset() in tearDown to unregister all instances and dispose singletons implementing Disposable. Register mock implementations before each test group. Never share get_it state across tests without reset—order-dependent failures will follow."
---

Constructor injection through twelve layers of widgets is honest but exhausting. `get_it` gives you a composition root: register everything once in `setupDependencies()`, resolve with `getIt<AuthRepository>()` where needed. I've used it on four production Flutter apps. The pattern works until someone calls `getIt` inside domain entities—then you've built a global singleton soup. Rules matter more than the library choice.

## Setup and registration types

```dart
final getIt = GetIt.instance;

Future<void> setupDependencies() async {
  // Singleton — created immediately
  getIt.registerSingleton<AppConfig>(AppConfig.fromEnv());

  // Lazy singleton — created on first access
  getIt.registerLazySingleton<Dio>(() => Dio(BaseOptions(
    baseUrl: getIt<AppConfig>().apiUrl,
  )));

  // Factory — new instance every resolve
  getIt.registerFactory<LoginCubit>(
    () => LoginCubit(getIt<AuthRepository>()),
  );

  // Async singleton — await before app start
  getIt.registerSingletonAsync<Database>(() async {
    return Database.connect();
  });
}
```

Bootstrap in `main()`:

```dart
void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await setupDependencies();
  await getIt.allReady(); // wait for async registrations
  runApp(MyApp());
}
```

## Registration patterns

**Interface to implementation:**

```dart
getIt.registerLazySingleton<AuthRepository>(
  () => AuthRepositoryImpl(getIt<AuthApi>(), getIt<TokenStorage>()),
);
```

Presentation and domain depend on `AuthRepository`, not `AuthRepositoryImpl`.

**Named instances** when multiple of same type:

```dart
getIt.registerLazySingleton<Dio>(
  () => createDio(baseUrl: prodUrl),
  instanceName: 'prod',
);

final dio = getIt<Dio>(instanceName: 'prod');
```

**Environment-specific modules:**

```dart
void setupDependencies({required Environment env}) {
  if (env == Environment.dev) {
    getIt.registerLazySingleton<AuthRepository>(() => FakeAuthRepository());
  } else {
    getIt.registerLazySingleton<AuthRepository>(() => AuthRepositoryImpl(...));
  }
}
```

## Constructor injection + get_it

Best of both worlds—explicit dependencies in classes, resolution at edge:

```dart
class ProfilePage extends StatelessWidget {
  const ProfilePage({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) => getIt<ProfileCubit>()..load(),
      child: ProfileView(),
    );
  }
}

class ProfileCubit extends Cubit<ProfileState> {
  ProfileCubit(this._repo) : super(ProfileInitial());
  final ProfileRepository _repo;
  // ...
}
```

Register factory for Cubit; never call `getIt` inside Cubit methods.

## Scoping with GetIt scopes

User session scope—logout disposes user-specific services:

```dart
getIt.pushNewScope(scopeName: 'authenticated');

getIt.registerLazySingleton<UserRepository>(() => UserRepositoryImpl());

// On logout:
await getIt.popScope(); // disposes scope registrations
```

Useful for multi-tenant or authenticated-only dependencies without polluting global scope.

## Testing with get_it

```dart
void main() {
  setUp(() async {
    await getIt.reset();
    getIt.registerLazySingleton<CartRepository>(() => MockCartRepository());
    getIt.registerFactory(() => CartCubit(getIt()));
  });

  test('loads cart', () {
    final cubit = getIt<CartCubit>();
    // ...
  });
}
```

Or pass mocks directly in unit tests without get_it—reserve get_it for widget/integration tests needing full graph.

Implement `Disposable` for cleanup:

```dart
class Database implements Disposable {
  @override
  Future<void> onDispose() async => close();
}
```

## Anti-patterns

1. **`getIt` inside business logic** — domain layer shouldn't know about service locator.
2. **Over-using singletons** — stateful objects tied to screen lifecycle should be factories.
3. **Circular dependencies** — A needs B needs A; refactor or use lazy registration carefully.
4. **God module** — split registration across feature modules:

```dart
Future<void> setupDependencies() async {
  await _registerCore();
  _registerAuth();
  _registerCart();
}
```

5. **Forgetting `allReady()`** — async singletons unresolved cause null errors at first access.

### get_it vs Riverpod vs injectable

| Tool | Style | Best for |
|------|-------|----------|
| get_it | Service locator | Imperative registration, non-Widget DI |
| Riverpod | Declarative providers | Widget tree integration, rebuild on change |
| injectable | Codegen on get_it | Large graphs, less boilerplate |

`injectable` generates registration from annotations—pairs well with get_it at scale. Riverpod replaces both DI and state for teams all-in on that ecosystem.

Pick one primary DI strategy per app. Mixing get_it and Riverpod providers for the same dependencies confuses everyone.

### Factory vs singleton decision guide

Register repositories as lazySingleton—one cache, one connection pool. Register Cubits/Blocs as factory—fresh state per screen. Register ViewModels tied to routes as factoryParam when you need route arguments:

```dart
getIt.registerFactoryParam<OrderCubit, String, void>(
  (orderId, _) => OrderCubit(getIt(), orderId),
);
```

Mis-scoping Cubits as singleton causes state bleed between navigations—the classic "previous user's cart visible" bug.

Document service lifetimes in injection.dart header comment—new engineers onboarding faster when singleton vs factory rationale is explicit. Periodic audit for unused registrations; dead bindings confuse debugging when getIt throws on missing vs duplicate registration.

Production teams should treat this guidance as living documentation: revisit assumptions after major platform upgrades, measure outcomes with real metrics rather than checklist compliance, and pair written standards with automated checks in CI. The patterns here reflect what held up in shipped apps—not theoretical perfection. Adapt thresholds, timeouts, and tooling to your stack, but keep the underlying principles: explicit configuration, testable behavior, and failure modes users can understand.

When onboarding new engineers, walk through one end-to-end example in a debug build before asking them to extend the pattern. Most failures I have seen came from skipped platform setup steps—manifest entries, API keys, code generation, or permission prompts—not from misunderstanding the Dart layer. Keep a troubleshooting section in your team wiki linking official docs and the exact commands that worked for your last upgrade.

Schedule a quarterly review of this implementation against current SDK release notes—Flutter and cloud providers ship breaking changes on six-month cadences, and assumptions that held last year may need adjustment. Capture before-and-after metrics when you change configuration so regressions are obvious in retrospect rather than debated from memory.

Version-pin dependencies mentioned here in your pubspec.lock or infrastructure modules, and note the Flutter/Dart SDK constraint your team validated. Upgrading without re-running the verification steps in this article is the most common source of regressions. If something fails after an upgrade, compare release notes first, then your git history for the last known-good configuration.

Register lazy singletons for services with heavy init — eager registration at startup adds seconds to cold launch on low-end devices.

## Resources

- [get_it package](https://pub.dev/packages/get_it)
- [get_it API documentation](https://pub.dev/documentation/get_it/latest/)
- [injectable package](https://pub.dev/packages/injectable)
- [Flutter dependency injection recommendations](https://docs.flutter.dev/app-architecture/recommendations#dependency-injection)
- [GetIt scopes documentation](https://pub.dev/documentation/get_it/latest/get_it/GetIt/popScope.html)
