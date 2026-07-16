---
title: "Clean Architecture in Flutter"
slug: "flutter-clean-architecture-layers"
description: "Structure Flutter apps with domain, data, and presentation layers: entities, use cases, repositories, and dependency direction that survives real product growth."
datePublished: "2024-10-07"
dateModified: "2024-10-07"
tags: ["Flutter", "Dart"]
keywords: "Flutter clean architecture, domain layer, repository pattern, use case Flutter, feature-first clean architecture"
faq:
  - q: "What is clean architecture in Flutter?"
    a: "Clean architecture separates concerns into layers: domain (business rules, entities, use cases), data (API and database implementations), and presentation (widgets, Bloc/Cubit). Dependencies point inward—presentation depends on domain abstractions, data implements those abstractions. UI never imports HTTP clients or SQL directly."
  - q: "Do I need use cases for every Flutter feature?"
    a: "Not every button needs a use case class. Use cases earn their keep when business logic coordinates multiple repositories, enforces rules, or repeats across presentation entry points. Simple CRUD can go from Cubit to repository directly until complexity justifies extraction."
  - q: "How does clean architecture work with Riverpod or get_it?"
    a: "DI containers wire interfaces to implementations at the composition root—main.dart or an injection module. Presentation receives abstract Repository classes; data layer provides concrete ApiRepository and CacheRepository. Swapping implementations for tests or flavors requires changing DI registration, not business code."
---

Clean architecture gets mocked as "47 folders for a counter app." Fair—but the counter app isn't what breaks your codebase. It's the payment flow that talks to Stripe, checks inventory, applies promo rules, and logs analytics, all while someone adds a GraphQL endpoint beside your REST client. Layer boundaries aren't ceremony; they're how you change one piece without re-reading the entire app.

## The three layers

```
┌─────────────────────────────────────┐
│  Presentation (UI, Bloc, Cubit)   │
├─────────────────────────────────────┤
│  Domain (Entities, UseCases, Repo*) │
├─────────────────────────────────────┤
│  Data (Repo impl, API, Local DB)    │
└─────────────────────────────────────┘
         * Repository interfaces live in domain
```

**Dependency rule:** outer layers depend on inner layers. Domain depends on nothing Flutter-specific—pure Dart.

## Domain layer

**Entities** — plain business objects:

```dart
class Order {
  final String id;
  final List<OrderLine> lines;
  final Money total;

  const Order({required this.id, required this.lines, required this.total});

  bool get isEligibleForRefund => lines.every((l) => l.delivered);
}
```

**Repository interfaces** — contracts, no implementation:

```dart
abstract class OrderRepository {
  Future<Order> getOrder(String id);
  Future<void> submitRefund(String orderId, RefundReason reason);
}
```

**Use cases** — single business operations:

```dart
class SubmitRefundUseCase {
  SubmitRefundUseCase(this._orders, this._analytics);
  final OrderRepository _orders;
  final AnalyticsService _analytics;

  Future<Result<void>> call(String orderId, RefundReason reason) async {
    final order = await _orders.getOrder(orderId);
    if (!order.isEligibleForRefund) {
      return Result.failure(RefundNotAllowedException());
    }
    await _orders.submitRefund(orderId, reason);
    await _analytics.logRefund(orderId);
    return Result.success(null);
  }
}
```

Use cases are optional for trivial flows. Add them when logic exceeds one repository call.

## Data layer

**Models** — serialization, DTO mapping:

```dart
class OrderDto {
  final String id;
  final List<OrderLineDto> lines;

  Order toEntity() => Order(
    id: id,
    lines: lines.map((l) => l.toEntity()).toList(),
    total: _computeTotal(lines),
  );

  factory OrderDto.fromJson(Map<String, dynamic> json) => ...;
}
```

**Repository implementations:**

```dart
class OrderRepositoryImpl implements OrderRepository {
  OrderRepositoryImpl(this._api, this._cache);
  final OrderApi _api;
  final OrderCache _cache;

  @override
  Future<Order> getOrder(String id) async {
    try {
      final dto = await _api.fetchOrder(id);
      await _cache.saveOrder(dto);
      return dto.toEntity();
    } catch (e) {
      final cached = await _cache.getOrder(id);
      if (cached != null) return cached.toEntity();
      rethrow;
    }
  }
}
```

Map exceptions to domain failures here or in use cases—never leak `DioException` to presentation.

## Presentation layer

**State management** calls use cases or repositories:

```dart
class RefundCubit extends Cubit<RefundState> {
  RefundCubit(this._submitRefund) : super(RefundInitial());
  final SubmitRefundUseCase _submitRefund;

  Future<void> submit(String orderId, RefundReason reason) async {
    emit(RefundLoading());
    final result = await _submitRefund(orderId, reason);
    result.when(
      success: (_) => emit(RefundSuccess()),
      failure: (e) => emit(RefundError(e.message)),
    );
  }
}
```

Widgets know nothing about HTTP status codes or JSON keys.

## Folder structure (feature-first)

```
lib/
  features/
    orders/
      domain/
        entities/order.dart
        repositories/order_repository.dart
        usecases/submit_refund.dart
      data/
        models/order_dto.dart
        datasources/order_api.dart
        repositories/order_repository_impl.dart
      presentation/
        cubit/refund_cubit.dart
        pages/refund_page.dart
        widgets/order_summary.dart
  core/
    error/result.dart
    network/dio_client.dart
  injection.dart
```

Each feature owns its vertical slice. Shared code lives in `core/`.

## Dependency injection at the root

```dart
void configureDependencies() {
  getIt.registerLazySingleton<OrderApi>(() => OrderApi(getIt()));
  getIt.registerLazySingleton<OrderRepository>(
    () => OrderRepositoryImpl(getIt(), getIt()),
  );
  getIt.registerFactory(() => SubmitRefundUseCase(getIt(), getIt()));
  getIt.registerFactory(() => RefundCubit(getIt()));
}
```

Presentation resolves abstractions. Tests swap fakes:

```dart
getIt.registerFactory<OrderRepository>(() => FakeOrderRepository());
```

### Testing benefits

| Layer | Test type | Mock |
|-------|-----------|------|
| Domain use case | Unit | Repository interface |
| Data repository | Unit | API + cache |
| Presentation Cubit | Unit | Use case |
| UI | Widget | Fake Cubit |

Domain tests run without `flutter_test`—pure Dart, fastest feedback.

### Pragmatic compromises

Don't over-architect day one:

- Start with repository interfaces even if one implementation exists.
- Extract use cases when Cubit methods exceed ~15 lines of business logic.
- Colocate small features; split when teams conflict on the same files.

Clean architecture pays off at 20+ features and multiple developers—not at prototype stage. But establishing layers early is cheaper than extracting them later.

### Mapping API errors in the data layer

Centralize HTTP status to Failure mapping:

```dart
Failure mapDioError(DioException e) => switch (e.response?.statusCode) {
  401 => const AuthFailure(),
  404 => const NotFoundFailure(),
  _ => NetworkFailure(e.message ?? 'Unknown'),
};
```

Presentation never switches on status codes. Domain Failures carry enough context for UI copy without leaking transport details to widgets.

Avoid anemic domain models—entities should encapsulate validation rules (isEligibleForDiscount) not just data bags. Use cases orchestrate; entities enforce invariants. Presentation formats dates and currency; domain works in UTC and numeric types without locale awareness.

Production teams should treat this guidance as living documentation: revisit assumptions after major platform upgrades, measure outcomes with real metrics rather than checklist compliance, and pair written standards with automated checks in CI. The patterns here reflect what held up in shipped apps—not theoretical perfection. Adapt thresholds, timeouts, and tooling to your stack, but keep the underlying principles: explicit configuration, testable behavior, and failure modes users can understand.

When onboarding new engineers, walk through one end-to-end example in a debug build before asking them to extend the pattern. Most failures I have seen came from skipped platform setup steps—manifest entries, API keys, code generation, or permission prompts—not from misunderstanding the Dart layer. Keep a troubleshooting section in your team wiki linking official docs and the exact commands that worked for your last upgrade.

Schedule a quarterly review of this implementation against current SDK release notes—Flutter and cloud providers ship breaking changes on six-month cadences, and assumptions that held last year may need adjustment. Capture before-and-after metrics when you change configuration so regressions are obvious in retrospect rather than debated from memory.

## Resources

- [Flutter app architecture guide](https://docs.flutter.dev/app-architecture/guide)
- [Very Good Ventures architecture](https://verygood.ventures/blog/very-good-flutter-architecture)
- [Repository pattern in Flutter](https://docs.flutter.dev/app-architecture/recommendations)
- [Reso Coder clean architecture series (reference)](https://resocoder.com/flutter-clean-architecture-tdd/)
- [get_it package](https://pub.dev/packages/get_it)
