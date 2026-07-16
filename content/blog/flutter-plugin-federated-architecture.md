---
title: "Federated Plugin Architecture"
slug: "flutter-plugin-federated-architecture"
description: "Federated plugins split platform implementations into separate packages. How to structure app-facing APIs, platform interfaces, and endorsed implementations."
datePublished: "2025-02-06"
dateModified: "2025-02-06"
tags: ["Flutter", "Dart", "Plugins", "Mobile"]
keywords: "Flutter federated plugin, plugin_platform_interface, endorsed plugin, Flutter plugin architecture, multi-platform plugin"
faq:
  - q: "What problem do federated plugins solve?"
    a: "They decouple the app-facing API from platform-specific implementations so third parties can ship web or desktop support without forking the whole plugin. The core package defines the interface; platform packages register implementations."
  - q: "What is an endorsed implementation?"
    a: "When the main plugin re-exports a default platform package in its pubspec, pub resolves it automatically—users add one dependency and get Android, iOS, web, etc. Non-endorsed implementations require explicit dependency overrides for alternate vendors."
  - q: "Do I need federation for a simple Android+iOS plugin?"
    a: "No. Single-repo plugins with android/ and ios/ folders are fine for two mobile platforms. Federation pays off when you expect community platform packages, independent release cycles, or optional platform support."
---

I maintained a plugin where someone opened a PR adding Windows support inside the same repo as Android. CI broke iOS because the Windows CMake touched shared headers. Federated architecture would have put Windows in its own package with its own pipeline, leaving mobile releases alone.

A federated Flutter plugin is a family of packages: an app-facing facade, a platform interface, and one implementation package per platform (plus optional endorsements).

## Package roles

```
my_plugin/                  # app-facing API users import
my_plugin_platform_interface/  # abstract contract + token verification
my_plugin_android/
my_plugin_ios/
my_plugin_web/
```

Apps depend only on `my_plugin`. That package exports a simple API and delegates to the platform interface singleton.

## Platform interface pattern

```dart
// my_plugin_platform_interface
abstract class MyPluginPlatform extends PlatformInterface {
  MyPluginPlatform() : super(token: _token);
  static final Object _token = Object();
  static MyPluginPlatform _instance = MethodChannelMyPlugin();

  static MyPluginPlatform get instance => _instance;

  static set instance(MyPluginPlatform instance) {
    PlatformInterface.verifyToken(instance, _token);
    _instance = instance;
  }

  Future<String> getPlatformVersion();
}
```

Implementations extend the class and call `super()` so token verification passes.

## App-facing package

```dart
// my_plugin
class MyPlugin {
  Future<String> getPlatformVersion() {
    return MyPluginPlatform.instance.getPlatformVersion();
  }
}
```

`pubspec.yaml` endorses default implementations:

```yaml
dependencies:
  my_plugin_platform_interface: ^1.0.0
  my_plugin_android: ^1.0.0
  my_plugin_ios: ^1.0.0

flutter:
  plugin:
    platforms:
      android:
        default_package: my_plugin_android
      ios:
        default_package: my_plugin_ios
```

Pub pulls endorsed packages transitively—users run `flutter pub add my_plugin` and get mobile implementations without listing each.

## Platform implementation package

```dart
// my_plugin_android
class MyPluginAndroid extends MyPluginPlatform {
  static void registerWith() {
    MyPluginPlatform.instance = MyPluginAndroid();
  }

  @override
  Future<String> getPlatformVersion() async {
    return 'Android ${android.os.Build.VERSION.release}';
  }
}
```

Register in `pubspec.yaml` plugin section for that platform only.

## Testing with fakes

Tests swap the platform instance:

```dart
class FakeMyPlugin extends MyPluginPlatform {
  @override
  Future<String> getPlatformVersion() async => 'Fake 1.0';
}

void main() {
  setUp(() {
    MyPluginPlatform.instance = FakeMyPlugin();
  });
}
```

No method channel mocking required for unit tests of Dart logic above the interface.

## When to federate vs monolith

**Monolith plugin** — one team, mobile-only, fast iteration, shared native code.

**Federated** — multiple contributors per platform, web/desktop arriving later, enterprise forks (e.g., custom Linux build for kiosks).

Migration path: extract interface first, move Android code to sub-package, keep old import path stable via export files.

## Publishing and versioning

Version interface breaking changes as major bumps across all packages simultaneously—or use tight constraint ranges (`my_plugin_platform_interface: ^2.0.0`) and changelog coordination. Melos helps monorepo-style plugin families.

Document which platforms are community-maintained vs officially endorsed so issue triage lands in the right repo.

## Common mistakes

- Forgetting `PlatformInterface.verifyToken` — security against rogue implementations in production isolates (mostly tests, but keep the pattern).
- Endorsing broken web implementation by default — mark experimental platforms optional.
- Circular dependencies between implementation packages — only depend on the interface package.

## Version coordination across packages

When `my_plugin_platform_interface` bumps major, all implementation packages must publish compatible ranges simultaneously. Melos or a monorepo prevents version skew:

```yaml
# my_plugin_android pubspec
dependencies:
  my_plugin_platform_interface: ^2.0.0
```

Changelog in app-facing package summarizes breaking changes across family. Consumers should only import `my_plugin`—document that importing implementation packages directly voids support.

## Web and desktop implementations

Federation shines when web team ships `my_plugin_web` without blocking mobile release. Endorse web optionally:

```yaml
flutter:
  plugin:
    platforms:
      web:
        default_package: my_plugin_web
```

If web is experimental, omit endorsement—users add dependency explicitly knowing maturity.

## Code generation inside implementations

Pigeon definitions live in interface package or app-facing package; implementations consume generated native stubs. Avoid duplicating Pigeon outputs—single generation step in CI.

## Consumer override for tests

```dart
MyPluginPlatform.instance = FakeMyPluginPlatform();
```

Document in README for integrators writing tests. Reset instance in `tearDown` to prevent test pollution.

## Governance

Assign CODEOWNERS per platform package in monorepo. Cross-platform API changes require review from each platform owner before merge—prevents Android-only breaks landing on iOS unchecked.


## Real-world plugin family example

Study `url_launcher` on GitHub: app-facing API, platform interface, endorsed Android/iOS/web implementations. Notice how `LinkTarget` enum lives in interface package—platform code depends on shared types without circular imports.

When forking for enterprise (custom URL allowlist), fork interface + app package only; swap implementation package via pubspec dependency override in internal apps.

## Release checklist per platform package

- Platform CI green (analyze, test, native lint)
- CHANGELOG entry cross-linked
- Version constraint updated in app-facing package
- Example app updated if API surface changed
- Migration note if breaking change on interface


## Stub implementations

Provide no-op stub for unsupported platforms returning `UnimplementedError` or graceful fallback—consumers check `Platform.isX` or catch at app level.

## Plugin federation and Melos

Monorepo all packages with Melos bootstrap—single PR updates interface and all platforms atomically; ideal federation workflow.

## Documentation site

Auto-generate platform support table in README from pubspec plugin declarations—script in CI updates checkmarks so docs never stale.

## Breaking change communication

Major interface bump: publish migration guide with before/after snippets for each platform implementation team.

## Platform channel removal

When migrating MethodChannel plugin to federated Pigeon, deprecate old channel with debug log warning one release—consumers upgrading see clear migration message in console.

## Additional release coordination

Schedule federated plugin family releases Tuesday–Thursday mornings team timezone—avoid Friday deploys of native platform packages requiring store review correlation. Rollback plan pins previous version constraints in app-facing package pubspec within one hour if crash spike detected in Crashlytics tagged release version.

Version federated plugin interfaces independently — breaking interface change in platform interface package breaks all implementations simultaneously.

## Resources

- [Developing packages and plugins (Flutter docs)](https://docs.flutter.dev/packages-and-plugins/developing-packages)
- [Federated plugin description](https://docs.flutter.dev/packages-and-plugins/developing-packages#federated-plugins)
- [plugin_platform_interface package](https://pub.dev/packages/plugin_platform_interface)
- [Flutter plugin template (ffigen / create)](https://docs.flutter.dev/packages-and-plugins/developing-packages#plugin-templates)
- [url_launcher federated example (GitHub)](https://github.com/flutter/packages/tree/main/packages/url_launcher)
