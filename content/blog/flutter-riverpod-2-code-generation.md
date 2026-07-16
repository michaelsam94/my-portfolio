---
title: "Riverpod 2 Code Generation Patterns"
slug: "flutter-riverpod-2-code-generation"
description: "riverpod_generator cuts boilerplate for providers with @riverpod annotations. AsyncNotifier, family params, and keepAlive without manual typing."
datePublished: "2025-03-02"
dateModified: "2025-03-02"
tags: ["Flutter", "Dart", "Riverpod", "Mobile"]
keywords: "Riverpod code generation, riverpod_generator, @riverpod annotation, AsyncNotifier generator, Flutter state management"
faq:
  - q: "Do I need code generation for Riverpod?"
    a: "No—manual Provider, NotifierProvider, and AsyncNotifierProvider remain fully supported. Code generation helps when you have many similar providers, want auto-dispose defaults documented in type names, or tired of spelling generic parameters for families."
  - q: "How do generated provider names work?"
    a: "A function userProfileProvider generates userProfileProvider— the annotation strips Provider suffix from function name by convention. Families become userProfileProvider(id) with typed parameters in the function signature."
  - q: "Can I mix manual and generated providers?"
    a: "Yes. Generated and hand-written providers interoperate in the same ProviderScope. Migrate hot spots first—usually repositories and feature notifiers—without rewriting the app."
---

I counted forty-seven `Provider` declarations that differed only by type parameters and a `ref.watch` line. `riverpod_generator` replaced most with a function and an annotation; refactors renamed providers in one place instead of three files. Code generation is optional in Riverpod 2—it is also the path of least resistance once provider count climbs.

## Setup

```yaml
dependencies:
  flutter_riverpod: ^2.6.0
  riverpod_annotation: ^2.6.0

dev_dependencies:
  build_runner: ^2.4.0
  riverpod_generator: ^2.6.0
```

## Simple functional provider

```dart
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'dio_provider.g.dart';

@riverpod
Dio dio(DioRef ref) {
  final dio = Dio();
  ref.onDispose(dio.close);
  return dio;
}
```

Generates `dioProvider`—auto-dispose by default, typed `DioRef` for IDE helpers.

## AsyncNotifier with codegen

```dart
@riverpod
class UserProfile extends _$UserProfile {
  @override
  Future<User> build(String userId) async {
    final api = ref.watch(userApiProvider);
    return api.fetchUser(userId);
  }

  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() => build(userId));
  }
}
```

Usage: `ref.watch(userProfileProvider('42'))`. Family parameter is the function argument.

## keepAlive for app-wide singletons

```dart
@Riverpod(keepAlive: true)
SharedPreferences sharedPreferences(SharedPreferencesRef ref) {
  throw UnimplementedError('override in main');
}
```

Initialize in `main` with override; provider survives while ProviderScope lives.

## Watching dependencies

```dart
@riverpod
Future<OrderSummary> orderSummary(OrderSummaryRef ref, String orderId) async {
  final order = await ref.watch(orderProvider(orderId).future);
  final tax = await ref.watch(taxServiceProvider).calculate(order);
  return OrderSummary(order: order, tax: tax);
}
```

Generator tracks dependencies; invalidates when upstream providers change.

## Class-based vs functional

Use class syntax when notifiers expose methods (`refresh`, `toggle`, `submit`). Use functional `@riverpod` for pure derived state and simple futures.

## Build workflow

```bash
dart run build_runner watch --delete-conflicting-outputs
```

Commit `.g.dart` files or regenerate in CI—team policy choice. Watch mode during feature work prevents stale part files.

## Testing generated providers

```dart
test('userProfile fetches user', () async {
  final container = ProviderContainer(
    overrides: [
      userApiProvider.overrideWithValue(FakeUserApi()),
    ],
  );
  addTearDown(container.dispose);

  final user = await container.read(userProfileProvider('1').future);
  expect(user.id, '1');
});
```

Override syntax identical to manual providers.

## Migration tips

1. Pick one feature folder, convert providers, run tests.
2. Replace `xxxProvider = Provider` with `@riverpod` function returning same type.
3. Rename references only if generated name differs—match function names to old provider stems.
4. Delete hand-written provider generic boilerplate.

## Pitfalls

- Forgetting `part 'file.g.dart';` — analyzer errors everywhere.
- Circular imports between generated parts—keep API definitions in leaf files.
- `@Riverpod(keepAlive: true)` on everything defeats auto-dispose benefits for screen-scoped state.

## Family providers and cache

Generated family providers cache per argument identity—`userProfileProvider('42')` distinct from `userProfileProvider('99')`. Invalidate one:

```dart
ref.invalidate(userProfileProvider(userId));
```

Auto-dispose families remove cache when last listener gone—watch in list items carefully; scrolling may recreate providers frequently. Use `keepAlive` link when appropriate:

```dart
@Riverpod(keepAlive: true)
```

## Ref types and IDE support

`UserProfileRef` extends `AutoDisposeAsyncNotifierProviderRef`—use ref.watch/ref.read with compile-time checks. Renaming provider function regenerates ref typedef.

## build_runner in monorepos

Melos script:

```yaml
generate:
  run: melos exec --depends-on=riverpod_generator -- dart run build_runner build --delete-conflicting-outputs
```

Run generate before analyze in CI for packages using codegen.


## Part files and visibility

Generated `.g.dart` exposes private providers—do not import part files from other libraries. Public API remains annotated source file exports.

## Refactoring generated names

Renaming `@riverpod` function renames provider—use IDE rename symbol across project. Grep old provider name after refactor before merge.

## Disabling code generation temporarily

Emergency hotfix on branch without build_runner: use manual provider equivalent, merge codegen follow-up immediately—do not leave dual patterns long.

## Analyzer excludes

Do not exclude `.g.dart` from analysis—generated code should analyze clean. If not, generator version mismatch; align `riverpod_generator` with `riverpod_annotation` per pub constraint solve.

## Custom provider naming

@Riverpod(name: 'legacyName') preserves provider name during migration from hand-written Provider—grep consumers unchanged while implementation moves to codegen.

## Rollout guidance

Codegen adoption milestone: 80% new providers codegen six weeks after workshop—tech lead reviews exempt requests case-by-case documenting why manual provider required.

## Team practices

Shipping Flutter Riverpod 2 Code Generation in production taught our team that documentation beats hero demos. We wrote runbooks covering failure modes, on-call steps, and rollback triggers before the second release, not after the first outage.

When reviewing PRs touching Flutter Riverpod 2 Code Generation, we ask for measurable outcomes: latency, crash rate, or support ticket volume—not subjective feels faster. If metrics are unavailable, the PR includes a DevTools trace or load test snippet proving the change.

Onboarding engineers paste a checklist into their first Flutter Riverpod 2 Code Generation PR description: environment setup verified, tests added or updated, accessibility spot-checked, and release notes drafted for user-visible changes.

We keep a living FAQ in the repo wiki for Flutter Riverpod 2 Code Generation questions repeated in Slack more than twice. FAQ entries link to source files and Slack threads, reducing tribal knowledge and repeated explanations in code review.

Cross-functional review includes design for UX-facing work, security for auth or storage, and platform for native bridges. Flutter Riverpod 2 Code Generation spans layers; skipping reviewers recreated bugs we fixed months ago.

Staging soaks 24 hours for risky changes while dashboards watch error rates.canary cohorts internal staff first, then five percent production, then full rollout if crash-free sessions hold within baseline tolerance.

Post-release we schedule a short retro even on smooth launches—what signal caught issues early, what was noise. Flutter Riverpod 2 Code Generation improvements compound when feedback loops stay short and blameless.

## Resources

- [Riverpod code generation docs](https://riverpod.dev/docs/concepts/about_code_generation)
- [riverpod_generator package](https://pub.dev/packages/riverpod_generator)
- [riverpod_annotation](https://pub.dev/packages/riverpod_annotation)
- [Riverpod AsyncNotifier guide](https://riverpod.dev/docs/concepts2/async_notifier)
- [Flutter Riverpod package](https://pub.dev/packages/flutter_riverpod)
