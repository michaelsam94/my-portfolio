---
title: "Publishing Packages to pub.dev"
slug: "flutter-package-publishing-pub-dev"
description: "From pubspec scoring to verified publishers, a step-by-step guide to shipping Dart and Flutter packages that pass pub.dev analysis and earn trust."
datePublished: "2025-01-28"
dateModified: "2025-01-28"
tags: ["Flutter", "Dart", "Packages", "Mobile"]
keywords: "publish pub.dev, Flutter package publishing, pub.dev score, verified publisher Dart, pub publish dry-run"
faq:
  - q: "What pub.dev score do I need before publishing?"
    a: "There is no hard minimum, but aim for 130+ points: full documentation comments on public APIs, example app, valid LICENSE, CHANGELOG, passing pana analysis, and platform support declared honestly. Low scores hurt discoverability and signal unmaintained code."
  - q: "How do I publish under a verified publisher?"
    a: "Create a pub.dev publisher linked to your domain via DNS TXT record, then publish with dart pub publish --publisher=yourdomain.com. Verified publishers display a badge that increases trust for enterprise adopters."
  - q: "Can I unpublish or retract a bad version?"
    a: "You can unlist within 7 days if no other package depends on that version. After that, publish a fixed semver bump instead. Permanent deletion is rare—plan version constraints carefully before the first publish."
---

My first `dart pub publish` failed because the LICENSE file was missing and `pana` flagged 40% of public methods without doc comments. The package worked locally; pub.dev rejected the experience. Publishing to pub.dev is not just uploading code—it is passing automated quality gates that protect the ecosystem from broken dependencies.

This guide walks through preparing a Flutter or Dart package, dry-running analysis, publishing, and maintaining versions without breaking downstream apps.

## Package structure pub.dev expects

```
my_package/
  lib/
    my_package.dart       # barrel export
    src/                    # private implementation
  example/
    lib/main.dart           # runnable demo
  test/
  CHANGELOG.md
  LICENSE
  README.md
  pubspec.yaml
```

Export a minimal public API from `lib/my_package.dart`. Hide internals in `lib/src/` and never import `src` from consumer apps.

## pubspec.yaml hygiene

```yaml
name: my_package
description: A clear one-line description with keywords users search for.
version: 1.0.0
homepage: https://github.com/you/my_package
repository: https://github.com/you/my_package
issue_tracker: https://github.com/you/my_package/issues

environment:
  sdk: ^3.5.0
  flutter: ">=3.24.0"

dependencies:
  flutter:
    sdk: flutter

dev_dependencies:
  flutter_test:
    sdk: flutter
  flutter_lints: ^5.0.0
```

Accurate SDK constraints prevent resolution errors for consumers on older toolchains. Do not claim Flutter support if the package is pure Dart.

## Scoring well on pana

Run locally before publish:

```bash
dart pub global activate pana
pana --no-warning --line-length=80
```

Fix what it reports:

- Document every public class, method, and typedef with `///` comments.
- Provide an `example/` app that imports the package the way users will.
- Include MIT or Apache-2.0 LICENSE (match your org policy).
- Maintain CHANGELOG.md with semver sections.

```dart
/// Fetches configuration from remote or cache.
///
/// Returns [Config] on success. Throws [ConfigException] when
/// the remote endpoint returns non-200 status codes.
Future<Config> loadConfig({required Uri endpoint}) async { ... }
```

Thin docs beat empty docs. One sentence explaining return values and errors counts.

## Dry run and publish

Authenticate once:

```bash
dart pub login
```

Validate the upload:

```bash
dart pub publish --dry-run
```

Review the file list—`.git`, `build/`, and secrets must not appear. Add them to `.pubignore` if needed.

Publish:

```bash
dart pub publish
```

Semver rules: breaking API changes bump major, new backward-compatible features bump minor, fixes bump patch.

## Verified publisher setup

For organizations, DNS verification beats individual accounts:

1. Create publisher at pub.dev/create-publisher
2. Add TXT record to your domain
3. Publish with `--publisher=example.com`

Consumers see a verified badge next to package name—worth the ten minutes of DNS work.

## Flutter-specific packaging

Plugins need platform folders (`android/`, `ios/`, etc.) or federated sub-packages. Declare platforms in README and test on real devices, not just `flutter test`.

For FFI plugins, document supported architectures and include build hooks in README.

## Post-publish maintenance

Set up GitHub Actions:

```yaml
- run: dart analyze
- run: dart test
- run: pana --no-warning
```

Tag releases matching pubspec version. Dependabot on consumer repos will propose updates when you ship.

Deprecate thoughtfully:

```dart
@Deprecated('Use fetchUserV2 instead. Removed in 3.0.0.')
Future<User> fetchUser() => fetchUserV2();
```

## Common rejection reasons

- Git dependency in `dependencies:` (use hosted versions only for published packages).
- Missing `LICENSE`.
- Upload includes `.dart_tool` or build artifacts.
- Name squatting or misleading description (manual moderation).

## Pre-release checklist

Before every publish:

1. `dart analyze` clean on package and example
2. `dart test` full pass
3. `dart pub publish --dry-run` inspect file list
4. `pana` score reviewed—aim 130+
5. CHANGELOG entry for this version
6. Version bump matches semver intent
7. `example/` runs and demonstrates primary API

Tag Git release matching pubspec version. Consumers depend on semver ranges—breaking changes require major bump and migration notes in CHANGELOG.

## Handling breaking changes responsibly

Deprecate for one minor release before removal:

```dart
@Deprecated('Use connectSecure instead. Removed in 3.0.0.')
Future<void> connect() => connectSecure();
```

Publish migration guide in README for major versions. Search pub.dev dependents (if visible) or internal monorepo references before shipping breaking API.

## Private packages and internal registries

Not everything belongs on public pub.dev. Options:

- **Private pub server** — self-hosted or Cloudsmith
- **Git dependencies** — acceptable for apps, not for packages you publish publicly
- **Monorepo path deps** — Melos workspace without publishing

If publishing privately, same pana hygiene helps internal consumers trust quality.

## Maintainer operations

Enable GitHub Dependabot for dev_dependencies. Respond to issue triage weekly—unanswered issues hurt adoption. Set `repository` URL in pubspec so pub.dev links source correctly.

For plugins, CI matrix across platforms you claim to support. Missing iOS CI while claiming iOS support invites broken releases.

## Legal and licensing

Choose LICENSE before first publish—MIT and Apache-2.0 are common. Ensure bundled fonts/assets have compatible licenses. Trademark: do not imply official Google/Flutter endorsement in package name unless authorized.


## Transfer package ownership

Document bus factor—uploader accounts on pub.dev tied to individuals; use verified publisher domain so team owns namespace when people leave.

## Pre-publish integration tests

Run example app against published dry-run tarball locally—`dart pub publish --dry-run` output directory path validate before real publish.

## Dependency constraints tightening

Major bump when raising minimum SDK—communicate in CHANGELOG; consumers on old Dart blocked until they upgrade toolchain.

## Spam and name squatting policy

Choose package name early; pub.dev moderation rejects confusingly similar names to popular packages—check search before committing brand.

## Resources

- [Publishing packages (Dart docs)](https://dart.dev/tools/pub/publishing)
- [pub.dev policy](https://pub.dev/policy)
- [pana package](https://pub.dev/packages/pana)
- [Verified publishers guide](https://dart.dev/tools/pub/verified-publishers)
- [Flutter plugin development](https://docs.flutter.dev/packages-and-plugins/developing-packages)
