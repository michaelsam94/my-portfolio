---
title: "Managing Monorepos with Melos"
slug: "flutter-melos-monorepo-management"
description: "Melos coordinates versioning, dependency linking, and scripted workflows across multiple Dart and Flutter packages in one repo. A practical setup guide."
datePublished: "2025-01-16"
dateModified: "2025-01-16"
tags: ["Flutter", "Dart", "Monorepo", "Mobile"]
keywords: "Melos Flutter monorepo, Dart workspace management, multi-package Flutter, Melos bootstrap, pub workspace"
faq:
  - q: "When should I use Melos instead of a single Flutter app?"
    a: "Reach for Melos when you have two or more publishable or reusable packages—shared UI kits, API clients, feature modules—that need to stay in sync without copy-pasting code. A lone app with a lib/ folder does not need it. The tipping point is usually the second package that must version and test together with the first."
  - q: "Does Melos replace pub workspaces?"
    a: "No. Melos orchestrates scripts, versioning, and changelogs on top of Dart's native workspace support in pubspec.yaml. You still declare a workspace: block listing package paths; Melos adds bootstrap, exec, and publish automation that raw pub workspaces do not provide."
  - q: "How do I run tests across all packages at once?"
    a: "Define a melos script like test: melos exec -- flutter test, then run melos run test. Melos fans out the command to every package that matches your filter, failing the whole run if any package fails—exactly what CI needs."
---

The third time I copied a shared `ApiClient` into two Flutter apps, I stopped pretending a folder symlink was a strategy. We had a design system, a networking layer, and two product flavors that all needed the same bug fix within hours of each other. Melos is the tool that turned that sprawl into a repo where one `melos bootstrap` links local packages, one script runs every test, and releases stay coordinated.

Melos is a CLI for Dart and Flutter monorepos. It sits above `pub` workspaces and gives you dependency bootstrapping, cross-package script execution, conventional versioning, and changelog generation. If you have ever watched a CI job fail because package B still pointed at pub.dev while package A expected a local path override, Melos is the fix.

## Workspace layout that scales

A typical Melos repo looks like this:

```
my_workspace/
  melos.yaml
  pubspec.yaml          # workspace root
  packages/
    app/
    design_system/
    api_client/
```

The root `pubspec.yaml` declares the workspace:

```yaml
name: my_workspace
publish_to: none

workspace:
  - packages/app
  - packages/design_system
  - packages/api_client
```

Each package keeps its own `pubspec.yaml` with normal dependencies. Internal packages reference each other by name and version constraint; Melos resolves them locally during bootstrap.

## melos.yaml essentials

Create `melos.yaml` at the repo root:

```yaml
name: my_workspace

packages:
  - packages/**

scripts:
  analyze:
    run: melos exec -- dart analyze .
    description: Run analyzer in all packages

  test:
    run: melos exec -- flutter test
    description: Run tests in all packages

  format:
    run: melos exec -- dart format . --set-exit-if-changed
```

Run `dart pub global activate melos`, then `melos bootstrap` from the root. Bootstrap installs dependencies for every package and wires path dependencies between workspace members automatically.

## Linking packages without manual overrides

Before workspaces, teams hand-edited `dependency_overrides` or ran brittle scripts. Melos bootstrap reads your workspace graph and ensures `design_system` resolves to `packages/design_system` when `app` depends on it. That means a change in the design system is immediately visible in the app on the next hot reload—no `pub publish` to a private registry just to iterate.

For packages you intend to publish, keep version constraints honest (`^1.2.0` on internal deps). Melos version commands bump those constraints when you cut a release.

## Scripting CI-friendly workflows

The real payoff is `melos exec` and `melos run`. Filters narrow scope:

```bash
melos exec --scope=app -- flutter build apk
melos exec --depends-on=design_system -- flutter test
```

In GitHub Actions, a minimal pipeline:

```yaml
- run: dart pub global activate melos
- run: melos bootstrap
- run: melos run analyze
- run: melos run test
```

One job, every package. Failed tests report which package broke, not a mystery stack trace three directories deep.

## Versioning and changelogs

When internal packages ship to pub.dev or a private registry, Melos can bump versions across dependents:

```bash
melos version --all
```

It applies conventional commit messages to decide semver bumps, updates inter-package constraints, and writes CHANGELOG entries. That beats manually grep-ing for `"design_system":` in six pubspec files.

## Gotchas worth knowing early

**Circular dependencies.** Melos will bootstrap them if pub allows it, but your architecture should not. Keep shared code in leaf packages, apps at the top.

**Flutter vs pure Dart packages.** Mixing is fine; use `melos exec -- flutter test` only in Flutter packages or filter with `--flutter`.

**IDE analysis.** Open the repo root, not individual packages, so the analyzer sees the full workspace graph. VS Code and Android Studio both respect Dart workspaces when the root is the project folder.

**melos clean.** When dependency state gets weird after a major refactor, `melos clean` followed by `melos bootstrap` resets symlinks and `.dart_tool` directories cleanly.

## When Melos is overkill

A single app with feature folders does not need a monorepo tool. Neither does one app plus one tiny plugin unless you plan to reuse that plugin elsewhere. Melos earns its keep when package count, shared release cadence, or CI matrix complexity crosses the threshold where manual path overrides become a weekly time sink.

## Publishing packages from a Melos workspace

When `design_system` ships to pub.dev while `app` stays private, Melos version coordinates bumps:

```bash
melos version --scope=design_system --all-versions
```

Tag releases in Git matching package versions. CI job on tag:

```yaml
- run: melos bootstrap
- run: melos exec --scope=design_system -- dart pub publish --force
```

Private packages set `publish_to: none` in pubspec. Document which packages are public in root README so contributors do not accidentally publish internal API clients.

## Local development ergonomics

Developers run `melos bootstrap` after every pull that touches pubspec locks—add a Makefile target or git hook reminder. VS Code multi-root workspace pointing at `packages/*` improves jump-to-definition across packages when root workspace analysis lags.

For hot reload across package boundaries: editing `design_system` triggers hot reload in dependent `app` when path dependency is wired—if not, run `melos exec --scope=app -- flutter pub get` once after bootstrap.

## Scaling to dozens of packages

Filter scripts prevent noise:

```yaml
scripts:
  test:changed:
    run: melos exec --since=origin/main -- flutter test
```

Use `--depends-on` and `--dependents-on` to rebuild only the graph affected by a PR. At 30+ packages, naive full-matrix CI exceeds ten minutes—partition by platform (`--flutter` vs pure Dart) and cache `.dart_tool` per package hash in CI.

## Conflict resolution in multi-package PRs

When PR touches `api_client` and `app`, CI must test dependents:

```bash
melos exec --dependents-on=api_client -- flutter test
```

Reviewers verify version constraints bumped if public API changed.

## Onboarding documentation

Root README sections: Prerequisites, bootstrap, common scripts, package map diagram. New hire first task: run example app in `packages/app` successfully within day one.


## Lockfile strategy

Commit `pubspec.lock` in apps; packages library may omit lock per team policy—document in CONTRIBUTING. Melos bootstrap respects locks per package.

## Selective publishing

`melos publish` dry-run in CI on tag—human approves publish job manually for public packages.

## Workspace resolver errors

When pub cannot resolve graph, `melos clean` then bootstrap—document troubleshooting in FAQ for common version conflict messages.

## Resources

- [Melos documentation](https://melos.invertase.dev/)
- [Melos on pub.dev](https://pub.dev/packages/melos)
- [Dart pub workspaces](https://dart.dev/tools/pub/workspaces)
- [Conventional Commits specification](https://www.conventionalcommits.org/)
- [Flutter monorepo CI example (Invertase)](https://github.com/invertase/melos)
