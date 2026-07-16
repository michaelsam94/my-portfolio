---
title: "Managing a Flutter Monorepo with Melos"
slug: "flutter-monorepo-melos"
description: "How to run a multi-package Flutter monorepo with Melos: bootstrapping, scripts, versioning, and CI — plus where Dart workspaces fit and the mistakes to avoid."
datePublished: "2026-05-17"
dateModified: "2026-05-17"
tags: ["Flutter", "Melos", "Monorepo", "Dart"]
keywords: "Melos, Flutter monorepo, Dart monorepo, package management, multi-package Flutter, workspaces"
faq:
  - q: "What is Melos in Flutter?"
    a: "Melos is a CLI tool for managing Dart and Flutter monorepos with multiple packages in one repository. It handles linking local packages together, running commands across all of them, and coordinating versioning and publishing."
  - q: "Do I still need Melos now that Dart has workspaces?"
    a: "Dart's pub workspaces (Dart 3.6+) handle shared dependency resolution and a single lockfile, which removes part of what Melos did. Melos still adds value for running scripts across packages, filtering by changed packages, and versioning with conventional commits, and it integrates with workspaces."
  - q: "When should I split a Flutter app into multiple packages?"
    a: "Split when you have code shared across apps, clear feature or layer boundaries you want to enforce, or build-time concerns you want isolated. Do not split prematurely — a handful of packages with real boundaries beats twenty micro-packages that just add import friction."
---

If you have more than one Flutter app sharing code, or a single app you want to carve into enforceable feature and layer packages, you end up wanting a monorepo. Melos is the tool that makes a Dart/Flutter monorepo pleasant: it links your local packages together, runs commands across all of them at once, and coordinates versioning and publishing. In 2026 it also plays nicely with Dart's native pub workspaces, so the setup is cleaner than it used to be.

I have run this layout on real projects, including a mobile platform where a shared design system and data layer fed several app flavors. Here is a setup that scales without turning into a maintenance tax.

## Why a monorepo, and why Melos

A monorepo is not the goal — enforceable boundaries and shared code are. Once you split an app into packages like `core`, `data`, `design_system`, and `feature_charging`, the dependency arrows become real: `feature_charging` can depend on `core`, but `core` can never depend on a feature. That is the kind of rule you want the build system to enforce, not code review to police.

Melos handles the mechanics that otherwise become tedious:

- **Bootstrapping**: linking every local package so they resolve each other during development.
- **Running scripts everywhere**: one command to analyze, test, or format all packages.
- **Filtering**: run tasks only on packages that changed, which is the difference between a 2-minute and a 20-minute CI run.
- **Versioning and publishing**: bump versions and generate changelogs from conventional commits.

## A layout that holds up

```
my_platform/
  melos.yaml
  pubspec.yaml          # workspace root
  packages/
    core/               # pure Dart: models, utils, no Flutter
    data/               # repositories, API clients, drift DB
    design_system/      # shared widgets, theme, tokens
    feature_charging/   # a feature module
    feature_wallet/
  apps/
    driver_app/         # Flutter app
    operator_app/       # Flutter app
```

Keep `core` as **pure Dart** with no Flutter dependency — it is testable in milliseconds and reusable on a backend. Put Flutter-specific shared UI in `design_system`. Feature packages depend downward only. Apps compose features.

## Melos plus Dart workspaces

Since Dart 3.6, pub has native **workspaces**: you declare member packages in the root `pubspec.yaml`, get one shared `pubspec.lock`, and a single `.dart_tool`. That subsumes the dependency-linking part of what Melos historically did. The modern pattern is to use *both* — workspaces for resolution, Melos for orchestration.

```yaml
# pubspec.yaml (workspace root)
name: my_platform_workspace
environment:
  sdk: ^3.6.0
workspace:
  - packages/core
  - packages/data
  - packages/design_system
  - packages/feature_charging
  - packages/feature_wallet
  - apps/driver_app
  - apps/operator_app
```

```yaml
# melos.yaml
name: my_platform
scripts:
  analyze:
    exec: dart analyze .
  test:
    run: melos exec --dir-exists=test -- flutter test
    description: Run tests in every package that has them
  test:changed:
    run: melos exec --dir-exists=test -- flutter test
    packageFilters:
      diff: origin/main
  format:
    exec: dart format --set-exit-if-changed .
```

Then day-to-day:

```bash
dart pub get                 # workspace resolves everything at once
melos run analyze            # lint all packages
melos run test:changed       # only packages touched vs main
```

## Versioning without hand-editing changelogs

Melos reads conventional commits (`feat:`, `fix:`, `feat!:`) and computes version bumps per package, updating each `CHANGELOG.md` and cross-package version constraints in one shot:

```bash
melos version --no-private   # bump changed packages, write changelogs
melos publish --dry-run      # verify before pushing to pub.dev
```

For internal-only packages you rarely publish, versioning still matters for traceability — you want to know which `data` version an app shipped with.

## CI: filter aggressively

The single biggest win in a monorepo CI is **only building what changed**. Melos `packageFilters` with `diff` scopes tasks to affected packages and their dependents, so a one-line fix in `feature_wallet` does not retest the whole tree.

```yaml
# GitHub Actions step
- run: dart pub get
- run: dart pub global activate melos
- run: melos run analyze
- run: melos run test:changed
```

Pair that with build caching and you keep PR feedback fast even as the repo grows to dozens of packages.

## Mistakes I have watched teams make

- **Over-splitting.** Twenty micro-packages where five would do just adds import ceremony and version churn. Split on *real* boundaries — shared code, layer rules, independent release cadence — not on aesthetics.
- **Letting `core` depend on Flutter.** The moment your domain layer imports `package:flutter`, you have lost fast pure-Dart tests and backend reuse. Guard it.
- **Circular feature dependencies.** If `feature_a` needs `feature_b`, the shared thing belongs in `core` or `data`, not in a feature. This is the same [Clean Architecture](https://blog.michaelsam94.com/clean-architecture-pragmatically/) dependency rule applied to package layout.
- **Skipping `test:changed`.** Running the full suite on every PR feels safe and quietly makes everyone dread opening PRs.

A Flutter monorepo with Melos and workspaces gives you the thing that actually scales a codebase: boundaries the tooling enforces and a build that only does the work a change requires. Set it up early, keep the package graph honest, and it stays an asset instead of becoming the thing everyone complains about. Want a review of your package boundaries? [Reach out](/#contact).

## Resources

- [Melos documentation](https://melos.invertase.dev/)
- [Dart pub workspaces](https://dart.dev/tools/pub/workspaces)
- [Flutter: developing packages and plugins](https://docs.flutter.dev/packages-and-plugins/developing-packages)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [Dart package layout conventions](https://dart.dev/tools/pub/package-layout)
- [Trunk-based development](https://trunkbaseddevelopment.com/)
