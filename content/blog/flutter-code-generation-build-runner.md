---
title: "Speeding Up build_runner"
slug: "flutter-code-generation-build-runner"
description: "Cut build_runner times in Flutter: build.yaml config, scoped builds, watch mode workflows, and avoiding the codegen conflicts that force full rebuilds."
datePublished: "2024-10-10"
dateModified: "2024-10-10"
tags: ["Flutter", "Dart"]
keywords: "build_runner Flutter, code generation speed, build.yaml, dart run build_runner, freezed json_serializable performance"
faq:
  - q: "Why is build_runner slow in Flutter projects?"
    a: "build_runner analyzes the entire dependency graph and runs all code generators—json_serializable, freezed, injectable, retrofit—on every full build. Large projects with thousands of inputs can take minutes. Conflicting outputs, missing build.yaml optimization, and running clean rebuilds instead of incremental watch mode multiply the pain."
  - q: "What is the fastest way to run build_runner?"
    a: "Use watch mode during development: dart run build_runner watch --delete-conflicting-outputs. It incrementally regenerates only changed files. For CI, cache .dart_tool/build and use --build-filter to scope generation to changed packages in monorepos."
  - q: "How do I fix conflicting outputs in build_runner?"
    a: "Conflicts occur when generated files exist from manual edits or stale outputs. Run with --delete-conflicting-outputs to remove and regenerate. Prevent recurrence by gitignoring *.g.dart and *.freezed.dart, never hand-editing generated files, and ensuring each input has unique part directives."
---

Three minutes every pull request waiting for `build_runner` adds up to a coffee break nobody enjoys. Our monorepo with freezed, json_serializable, injectable, and retrofit was hitting 4:30 on CI until we scoped builds, cached `.dart_tool/build`, and fixed three misconfigured generators that invalidated the entire graph on any file change. Codegen is necessary; slow codegen is optional.

## Understand what build_runner does

Generators register as `Builder` implementations in `build.yaml`. A full build:

1. Resolves asset graph across all dependencies.
2. Runs builders in topological order.
3. Writes `.g.dart`, `.freezed.dart`, `.config.dart` outputs.

Every `@JsonSerializable`, `@freezed`, `@injectable` class is an input node. More annotations = longer builds.

## Development workflow: watch mode

Never run one-shot builds during active development:

```bash
dart run build_runner watch --delete-conflicting-outputs
```

Leave it running in a terminal tab. Saves regenerate within seconds of save.

One-shot when needed:

```bash
dart run build_runner build --delete-conflicting-outputs
```

Add to README so new engineers don't wait full builds on every branch switch.

## build.yaml optimization

Create or tune `build.yaml` at project root:

```yaml
targets:
  $default:
    builders:
      json_serializable:
        options:
          explicit_to_json: true
          field_rename: snake
      freezed:
        options:
          union_key: type
          union_value_case: snake
    sources:
      exclude:
        - test/**
        - "**/*.g.dart"
        - "**/*.freezed.dart"
```

Exclude test files if generators don't need them—cuts input count.

For monorepos with melos, per-package `build.yaml` with scoped targets:

```yaml
targets:
  api_client:
    sources:
      include:
        - lib/**
    builders:
      retrofit_generator|retrofit:
        enabled: true
```

Run scoped:

```bash
dart run build_runner build --build-filter="lib/models/**"
```

## Reduce generator load

**Consolidate annotations.** One mega-freezed class beats five tiny ones if they're always used together—fewer builder invocations.

**Avoid redundant generators.** Don't add `@JsonSerializable` and manual `fromJson` on the same class.

**Use `json_serializable` `createFactory`/`createToJson` flags** to skip unused direction:

```dart
@JsonSerializable(createToJson: false)
class ReadOnlyDto { ... }
```

**Injectable:** prefer explicit `@module` over scanning entire lib:

```yaml
# build.yaml
injectable_generator|injectable_builder:
  generate_for:
    - lib/injection.dart
```

## CI caching

Cache the build runner asset graph:

```yaml
# GitHub Actions example
- uses: actions/cache@v4
  with:
    path: |
      .dart_tool/build
      .dart_tool/build_resolvers
    key: build-runner-${{ hashFiles('pubspec.lock', 'build.yaml', '**/*.dart') }}
```

Run build only when generated files might change:

```bash
dart run build_runner build --delete-conflicting-outputs
git diff --exit-code lib/ || (echo "Generated files out of date" && exit 1)
```

Or commit generated files (team preference varies)—CI skips build_runner entirely at cost of merge conflicts on `.g.dart` files.

## Debugging slow builds

Enable verbose logging:

```bash
dart run build_runner build --verbose
```

Identify the slow builder—often `injectable_generator` scanning all of `lib/`.

Check for **dependency cycles** causing full invalidation. One file importing generated output incorrectly can rebuild the world.

**build_runner doctor** (community scripts) or manual inspection of `.dart_tool/build/generated/` for unexpected entries.

### Common failure modes

| Problem | Fix |
|---------|-----|
| Conflicting outputs | `--delete-conflicting-outputs` |
| Stale generated code | Clean: `dart run build_runner clean` then build |
| OOM on CI | Increase memory; scope with `--build-filter` |
| Generator not running | Check `part` directive and `build.yaml` `generate_for` |
| Infinite watch loop | IDE and watch both writing—exclude generated from analysis auto-save |

### Alternatives and complements

- **json_serializable** → consider `dart_mappable` or hand-written for small DTO sets.
- **freezed** → worth it for unions; skip for simple data classes.
- **KSP-style:** Dart lacks KSP; codegen is the path for now. Watch `macros` language feature progress for future native compile-time generation.

Until macros ship stable, optimize the build_runner workflow you have rather than eliminating codegen entirely.

### Splitting codegen across packages

In monorepos, run build_runner per package with melos:

```bash
melos exec --depends-on=build_runner -- dart run build_runner build
```

Package A's generated code shouldn't trigger full rebuild of Package B unless dependency graph changed—configure `build.yaml` `generate_for` narrowly. Developers working on UI-only packages skip codegen entirely, saving minutes per switch.

Watch mode conflicts when IDE and terminal both run build_runner—pick one. VS Code build_runner task on save works; Android Studio users often prefer terminal watch. Document team standard to prevent duplicate generator processes locking build cache.

Production teams should treat this guidance as living documentation: revisit assumptions after major platform upgrades, measure outcomes with real metrics rather than checklist compliance, and pair written standards with automated checks in CI. The patterns here reflect what held up in shipped apps—not theoretical perfection. Adapt thresholds, timeouts, and tooling to your stack, but keep the underlying principles: explicit configuration, testable behavior, and failure modes users can understand.

When onboarding new engineers, walk through one end-to-end example in a debug build before asking them to extend the pattern. Most failures I have seen came from skipped platform setup steps—manifest entries, API keys, code generation, or permission prompts—not from misunderstanding the Dart layer. Keep a troubleshooting section in your team wiki linking official docs and the exact commands that worked for your last upgrade.

Schedule a quarterly review of this implementation against current SDK release notes—Flutter and cloud providers ship breaking changes on six-month cadences, and assumptions that held last year may need adjustment. Capture before-and-after metrics when you change configuration so regressions are obvious in retrospect rather than debated from memory.

Version-pin dependencies mentioned here in your pubspec.lock or infrastructure modules, and note the Flutter/Dart SDK constraint your team validated. Upgrading without re-running the verification steps in this article is the most common source of regressions. If something fails after an upgrade, compare release notes first, then your git history for the last known-good configuration.

## Resources

- [build_runner package](https://pub.dev/packages/build_runner)
- [build.yaml configuration](https://github.com/dart-lang/build/blob/master/docs/build_yaml_config.md)
- [json_serializable](https://pub.dev/packages/json_serializable)
- [freezed package](https://pub.dev/packages/freezed)
- [Dart build system documentation](https://dart.dev/tools/build_system)
