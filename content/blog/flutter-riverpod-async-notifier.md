---
title: "AsyncNotifier: Riverpod's Async Workhorse"
slug: "flutter-riverpod-async-notifier"
description: "AsyncNotifier replaces FutureProvider for mutable async state. Loading, error, data transitions with refresh, optimistic updates, and pagination."
datePublished: "2025-03-05"
dateModified: "2025-03-05"
tags: ["Flutter", "Dart", "Riverpod", "Mobile"]
keywords: "AsyncNotifier Riverpod, AsyncValue Flutter, Riverpod async state, FutureProvider vs AsyncNotifier, pull to refresh Riverpod"
faq:
  - q: "AsyncNotifier vs FutureProvider?"
    a: "FutureProvider is read-mostly—great for one-shot fetches. AsyncNotifier adds methods to mutate async state: refresh, loadMore, optimistic updates. Choose AsyncNotifier when users trigger reloads or you paginate."
  - q: "How do I show previous data while refreshing?"
    a: "Set state = const AsyncLoading<User>().copyWithPrevious(state) or use AsyncValue.guard while keeping prior value visible in UI with switch on AsyncValue when loading && hasValue."
  - q: "Can AsyncNotifier depend on other providers?"
    a: "Yes. Watch dependencies in build() with ref.watch. When authProvider changes, rebuild invalidates and re-runs async build—ideal for user-scoped data."
---

`FutureProvider` worked until product asked for pull-to-refresh that kept the old list visible, optimistic toggles on star ratings, and pagination that appended without a full-screen spinner. `AsyncNotifier` is Riverpod 2's answer: one class owns `AsyncValue<T>` lifecycle and exposes imperative methods UI calls.

## Basic AsyncNotifier

```dart
@riverpod
class TodoList extends _$TodoList {
  @override
  Future<List<Todo>> build() async {
    final api = ref.watch(todoApiProvider);
    return api.fetchTodos();
  }

  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() async {
      final api = ref.read(todoApiProvider);
      return api.fetchTodos();
    });
  }
}
```

UI:

```dart
final todos = ref.watch(todoListProvider);

return todos.when(
  loading: () => const CircularProgressIndicator(),
  error: (e, st) => ErrorView(error: e, onRetry: () => ref.read(todoListProvider.notifier).refresh()),
  data: (items) => TodoListView(items: items),
);
```

## Preserving previous data on refresh

```dart
Future<void> refresh() async {
  state = const AsyncLoading<List<Todo>>().copyWithPrevious(state, isRefresh: true);
  state = await AsyncValue.guard(() => _fetch());
}
```

UI pattern:

```dart
switch (todos) {
  case AsyncData(:final value):
    return TodoListView(items: value);
  case AsyncLoading(:final value?) when value.isNotEmpty:
    return Stack(
      children: [
        TodoListView(items: value),
        const LinearProgressIndicator(),
      ],
    );
  ...
}
```

Users see stale-while-revalidate instead of blank flash.

## Optimistic updates

```dart
Future<void> toggle(String id) async {
  final previous = state;
  if (previous case AsyncData(value: final list)) {
    state = AsyncData([
      for (final t in list)
        if (t.id == id) t.copyWith(done: !t.done) else t,
    ]);
  }

  try {
    await ref.read(todoApiProvider).toggle(id);
  } catch (e, st) {
    state = previous;
    rethrow;
  }
}
```

Rollback on failure keeps trust in the UI.

## Pagination

```dart
@riverpod
class Feed extends _$Feed {
  @override
  Future<List<Post>> build() => _fetchPage(1);

  Future<void> loadMore() async {
    final current = state.valueOrNull ?? [];
    final nextPage = (current.length / pageSize).ceil() + 1;

    state = await AsyncValue.guard(() async {
      final more = await _fetchPage(nextPage);
      return [...current, ...more];
    });
  }
}
```

Guard against duplicate `loadMore` calls with a boolean latch in the notifier.

## Parameterized AsyncNotifier (family)

```dart
@riverpod
class UserPosts extends _$UserPosts {
  @override
  Future<List<Post>> build(String userId) async {
    ref.watch(authProvider); // rebuild on logout
    return ref.read(postApiProvider).forUser(userId);
  }
}
```

`ref.watch(userPostsProvider('ada'))` scopes cache per user.

## Testing

```dart
test('refresh replaces data', () async {
  final container = ProviderContainer(
    overrides: [todoApiProvider.overrideWithValue(FakeTodoApi())],
  );

  await container.read(todoListProvider.future);
  await container.read(todoListProvider.notifier).refresh();

  expect(container.read(todoListProvider).value, hasLength(3));
});
```

Use `AsyncValue.guard` in tests to mirror production error paths.

## When to stay with FutureProvider

Static config loaded once, feature flags, rarely changing reference data with no user-triggered reload—FutureProvider is less code.

## Pagination edge cases

Guard `loadMore` when already loading:

```dart
bool _loadingMore = false;

Future<void> loadMore() async {
  if (_loadingMore || state is AsyncLoading) return;
  _loadingMore = true;
  try {
    // append logic
  } finally {
    _loadingMore = false;
  }
}
```

Expose `hasMore` flag from API cursor to hide footer spinner when exhausted.

## Error retry UX

```dart
error: (e, st) => ErrorView(
  onRetry: () => ref.invalidate(feedProvider),
),
```

`invalidate` re-runs `build` fresh—prefer over manual state assignment unless preserving partial data with `copyWithPrevious`.

## Combining with pull-to-refresh

```dart
RefreshIndicator(
  onRefresh: () => ref.read(todoListProvider.notifier).refresh(),
  child: list,
)
```

Ensure refresh sets loading state that keeps list visible—users hate empty flash on pull.


## Sealed UI state alternative

Some teams model UI with sealed class `ViewState<T>` parallel to AsyncValue—AsyncNotifier still backs it via mapping in listener. Choose one pattern per app; mixing confuses onboarding.

## Cancellation

When user navigates away, autoDispose cancels pending futures if provider configured—verify API client respects `CancelToken` tied to ref.onDispose to avoid setting state on disposed notifier.

## Pagination with cursor API

Prefer cursor over offset pagination in notifier—store `nextCursor` in notifier private field, append on loadMore, set `hasMore` from API `links.next` presence.

## Testing loading states

```dart
expect(container.read(feedProvider), isA<AsyncLoading>());
await container.read(feedProvider.future);
expect(container.read(feedProvider), isA<AsyncData>());
```

Assert intermediate states explicitly—regressions often skip loading UI entirely.

## ref.mounted check

After await in notifier method, if using manual state assignment verify ref still mounted (Riverpod 2.6+) before setState equivalent—avoid updating disposed notifier after slow network.

## Rollout guidance

AsyncNotifier refresh UX pattern library internal package three variants: skeleton reload, pull refresh, silent background refresh—product picks per screen consistency doc prevents eleven different loading behaviors same app confuses users.

## Team practices

Shipping Flutter Riverpod Async Notifier in production taught our team that documentation beats hero demos. We wrote runbooks covering failure modes, on-call steps, and rollback triggers before the second release, not after the first outage.

When reviewing PRs touching Flutter Riverpod Async Notifier, we ask for measurable outcomes: latency, crash rate, or support ticket volume—not subjective feels faster. If metrics are unavailable, the PR includes a DevTools trace or load test snippet proving the change.

Onboarding engineers paste a checklist into their first Flutter Riverpod Async Notifier PR description: environment setup verified, tests added or updated, accessibility spot-checked, and release notes drafted for user-visible changes.

We keep a living FAQ in the repo wiki for Flutter Riverpod Async Notifier questions repeated in Slack more than twice. FAQ entries link to source files and Slack threads, reducing tribal knowledge and repeated explanations in code review.

Cross-functional review includes design for UX-facing work, security for auth or storage, and platform for native bridges. Flutter Riverpod Async Notifier spans layers; skipping reviewers recreated bugs we fixed months ago.

Staging soaks 24 hours for risky changes while dashboards watch error rates.canary cohorts internal staff first, then five percent production, then full rollout if crash-free sessions hold within baseline tolerance.

## Resources

- [AsyncNotifier documentation](https://riverpod.dev/docs/concepts2/async_notifier)
- [AsyncValue API](https://pub.dev/documentation/riverpod/latest/riverpod/AsyncValue-class.html)
- [Riverpod pull-to-refresh example](https://riverpod.dev/docs/essentials/first_request)
- [flutter_riverpod package](https://pub.dev/packages/flutter_riverpod)
- [Riverpod migration guide 2.0](https://riverpod.dev/docs/migration/from_state_notifier)
