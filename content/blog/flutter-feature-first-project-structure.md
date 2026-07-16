---
title: "Feature-First Project Structure"
slug: "flutter-feature-first-project-structure"
description: "Organize Flutter apps by feature instead of layer: folder layout, shared core module, cross-feature imports, and scaling from one developer to a team."
datePublished: "2024-11-03"
dateModified: "2024-11-03"
tags: ["Flutter", "Dart"]
keywords: "Flutter project structure, feature-first architecture, Flutter folder organization, modular Flutter app"
faq:
  - q: "What is feature-first structure in Flutter?"
    a: "Feature-first organizes code by business capability—auth, cart, profile—each containing its own data, domain, and presentation subfolders. Alternative layer-first groups all repositories together, all screens together. Feature-first keeps related code colocated so changes to checkout touch one directory, not six scattered layers."
  - q: "How is feature-first different from clean architecture?"
    a: "They complement each other. Clean architecture defines layer boundaries within a feature; feature-first defines top-level folder boundaries between capabilities. A feature-first app often has lib/features/cart/domain, lib/features/cart/data, lib/features/cart/presentation inside each feature folder."
  - q: "When should I split features into separate packages?"
    a: "Extract to packages when features have independent release cycles, different teams own them, or build times suffer from monolithic analysis. Start with folder-based features in one repo; promote to melos monorepo packages when import boundaries need enforcement or CI can skip unchanged packages."
---

Our layer-first layout had `lib/repositories/cart_repository.dart` three folders away from `lib/screens/cart_page.dart` and `lib/widgets/cart_badge.dart`. Every checkout tweak meant grep-ing the codebase. Moving to feature-first—everything cart-related under `lib/features/cart/`—cut PR review time because diffs stayed in one subtree. Structure doesn't solve architecture problems, but wrong structure guarantees navigation pain.

## Layer-first vs feature-first

**Layer-first (traditional):**

```
lib/
  models/
  repositories/
  screens/
  widgets/
  services/
```

**Feature-first:**

```
lib/
  features/
    auth/
    cart/
    profile/
  core/
  app.dart
```

Feature-first wins when the app has distinct business domains. Layer-first survives tiny apps with five screens.

## Standard feature folder anatomy

```
lib/features/cart/
  data/
    datasources/cart_api.dart
    models/cart_item_dto.dart
    repositories/cart_repository_impl.dart
  domain/
    entities/cart_item.dart
    repositories/cart_repository.dart
    usecases/add_to_cart.dart
  presentation/
    bloc/cart_bloc.dart
    pages/cart_page.dart
    widgets/cart_item_tile.dart
  cart.dart              # barrel export (optional)
```

Each feature is a vertical slice. `presentation` imports `domain`; `data` implements `domain`; `domain` imports nothing from sibling layers.

## The core module

Shared infrastructure lives outside features:

```
lib/core/
  error/failures.dart
  network/dio_client.dart
  theme/app_theme.dart
  utils/date_formatters.dart
  widgets/loading_indicator.dart
```

Rules:

- `core/` must not import from `features/`.
- Features may import from `core/`.
- Features should not import from other features directly.

## Cross-feature communication

When cart needs auth state, avoid `import '../auth/...'`:

**Option 1 — Shared domain interfaces in core:**

```dart
// core/auth/auth_state.dart
abstract class AuthStateProvider {
  Stream<User?> get currentUser;
}
```

Auth feature implements; cart feature depends on interface registered in DI.

**Option 2 — Navigation with parameters:**

Cart doesn't know auth internals—router passes `userId` as route param.

**Option 3 — Event bus (use sparingly):**

```dart
eventBus.on<UserLoggedOut>().listen((_) => cartBloc.add(ClearCart()));
```

Prefer explicit interfaces over global events.

## Barrel exports

Optional `cart.dart` re-exports public API:

```dart
// features/cart/cart.dart
export 'presentation/pages/cart_page.dart';
export 'domain/repositories/cart_repository.dart';
```

External code imports `package:app/features/cart/cart.dart`—internal files stay private by convention.

## Routing per feature

With go_router, colocate route definitions:

```dart
// features/cart/routes.dart
List<RouteBase> get cartRoutes => [
  GoRoute(
    path: '/cart',
    builder: (_, __) => const CartPage(),
  ),
];

// app/router.dart
final router = GoRouter(routes: [
  ...authRoutes,
  ...cartRoutes,
  ...profileRoutes,
]);
```

### Scaling to monorepo packages

When `lib/features/payments/` grows to 40 files and a dedicated team:

```
packages/
  payments/
    lib/
      src/...
    pubspec.yaml
  cart/
  core/
apps/
  mobile/
    pubspec.yaml  # depends on payments, cart, core
```

Melos manages versions and local path dependencies:

```yaml
# melos.yaml
packages:
  - packages/**
  - apps/**
```

CI runs `melos exec --scope=payments -- flutter test` on affected packages only.

### Naming and conventions

- Feature folders: lowercase, singular or plural consistently (`orders` not `order` + `orders`).
- Pages suffix: `_page.dart`. Widgets: descriptive nouns. Blocs: `_bloc.dart` / `_cubit.dart`.
- Keep feature-specific assets colocated: `features/cart/assets/` or root `assets/cart/` with matching prefix.

Document import rules in `ARCHITECTURE.md`—lint with `import_lint` or custom `analysis_options` import restrictions if needed.

### Migration from layer-first

Don't big-bang rewrite:

1. Create `features/` and `core/`.
2. Move one feature (smallest first) entirely.
3. Fix imports; run tests.
4. Repeat per sprint until layer folders empty.
5. Delete old structure.

`git mv` preserves history. Update CI paths if tests mirror old structure.

### When feature-first hurts

- **Tiny prototypes** — folder overhead exceeds benefit.
- **Highly shared UI kits** — design system may deserve top-level `design_system/` parallel to features.
- **Single CRUD app** — one `features/app/` is fine; don't force artificial splits.

Structure serves the team. Revisit at 10, 30, and 100 screens.

### Enforcing boundaries with custom lint

Add import restrictions in analysis_options or dependency_validator ensuring features don't cross-import:

```yaml
# conceptually - use import_lint or custom analyzer plugin
# features/cart must not import features/auth/presentation
```

Code review checklist: "Does this PR import another feature's data layer?" Shared abstractions belong in core, not cross-feature presentation imports.

Shared widgets used by three or more features move to core/widgets or packages/ui—not copied across features. Conversely, resist premature extraction—duplicate once, abstract on third identical usage per rule of three.

Production teams should treat this guidance as living documentation: revisit assumptions after major platform upgrades, measure outcomes with real metrics rather than checklist compliance, and pair written standards with automated checks in CI. The patterns here reflect what held up in shipped apps—not theoretical perfection. Adapt thresholds, timeouts, and tooling to your stack, but keep the underlying principles: explicit configuration, testable behavior, and failure modes users can understand.

When onboarding new engineers, walk through one end-to-end example in a debug build before asking them to extend the pattern. Most failures I have seen came from skipped platform setup steps—manifest entries, API keys, code generation, or permission prompts—not from misunderstanding the Dart layer. Keep a troubleshooting section in your team wiki linking official docs and the exact commands that worked for your last upgrade.

Schedule a quarterly review of this implementation against current SDK release notes—Flutter and cloud providers ship breaking changes on six-month cadences, and assumptions that held last year may need adjustment. Capture before-and-after metrics when you change configuration so regressions are obvious in retrospect rather than debated from memory.

## Common production mistakes

Teams get feature first project structure wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Flutter teams implementing feature first project structure often regress performance by rebuilding entire subtrees on every frame, ignoring platform channel latency, or testing only on iOS simulators. Profile on mid-range Android hardware before calling the work done.

## Resources

- [Flutter app architecture guide](https://docs.flutter.dev/app-architecture/guide)
- [Very Good Core template structure](https://github.com/VeryGoodOpenSource/very_good_core)
- [Melos monorepo tool](https://melos.invertase.dev/)
- [Flutter recommended project structure](https://docs.flutter.dev/app-architecture/recommendations)
- [import_lint package](https://pub.dev/packages/import_lint)
