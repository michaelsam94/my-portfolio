---
title: "Flavors and Build Configuration"
slug: "flutter-flavors-build-configuration"
description: "Configure Flutter dev, staging, and prod flavors: dart-define, flavor-specific entrypoints, Android productFlavors, iOS schemes, and icons per environment."
datePublished: "2024-11-09"
dateModified: "2024-11-09"
tags: ["Flutter", "Dart"]
keywords: "Flutter flavors, dart-define, Flutter staging prod, productFlavors Android, iOS schemes Flutter"
faq:
  - q: "What are Flutter flavors?"
    a: "Flavors are build variants of the same app with different configuration—API URLs, app names, icons, bundle IDs, and feature flags. They let developers install dev, staging, and production builds side-by-side on one device without overwriting each other."
  - q: "How do I pass environment config in Flutter?"
    a: "Use --dart-define or --dart-define-from-file to inject compile-time constants read via String.fromEnvironment. Combine with separate main entrypoints (main_dev.dart, main_prod.dart) for flavor-specific DI and theme setup. Avoid hardcoding URLs in source."
  - q: "How do Android productFlavors work with Flutter?"
    a: "Define productFlavors in android/app/build.gradle with distinct applicationIdSuffix and resValue for app name. Pass flavor to Flutter via flutter build apk --flavor dev -t lib/main_dev.dart. Each flavor can have its own google-services.json and manifest placeholders."
---

Installing staging over production and not noticing until push notifications hit the wrong Firebase project—that happened on my team once. Flutter flavors fix it: distinct bundle IDs, app names, API endpoints, and icons per environment, all buildable from one codebase. The setup spans Dart entrypoints, `--dart-define`, Android `productFlavors`, and iOS schemes. Front-loaded config work; zero wrong-environment surprises later.

## Dart entrypoints and dart-define

**lib/main_dev.dart:**

```dart
import 'package:my_app/app.dart';
import 'package:my_app/config/env.dart';

void main() {
  Env.init(environment: Environment.dev);
  bootstrap();
}
```

**lib/config/env.dart:**

```dart
enum Environment { dev, staging, prod }

class Env {
  static late Environment environment;
  static late String apiBaseUrl;

  static void init({required Environment environment}) {
    Env.environment = environment;
    apiBaseUrl = const String.fromEnvironment(
      'API_BASE_URL',
      defaultValue: 'https://dev-api.example.com',
    );
  }

  static bool get isProd => environment == Environment.prod;
}
```

Run:

```bash
flutter run -t lib/main_dev.dart \
  --dart-define=API_BASE_URL=https://dev-api.example.com

flutter run -t lib/main_prod.dart \
  --dart-define=API_BASE_URL=https://api.example.com
```

**dart-define-from-file** for CI:

```json
// env/dev.json
{ "API_BASE_URL": "https://dev-api.example.com", "ENABLE_LOGS": "true" }
```

```bash
flutter build apk --dart-define-from-file=env/prod.json -t lib/main_prod.dart
```

## Android productFlavors

**android/app/build.gradle:**

```gradle
android {
    flavorDimensions "environment"
    productFlavors {
        dev {
            dimension "environment"
            applicationIdSuffix ".dev"
            resValue "string", "app_name", "MyApp Dev"
        }
        staging {
            dimension "environment"
            applicationIdSuffix ".staging"
            resValue "string", "app_name", "MyApp Staging"
        }
        prod {
            dimension "environment"
            resValue "string", "app_name", "MyApp"
        }
    }
}
```

**AndroidManifest.xml** app label:

```xml
<application android:label="@string/app_name" ...>
```

Flavor-specific resources:

```
android/app/src/dev/google-services.json
android/app/src/prod/google-services.json
android/app/src/dev/res/mipmap-*/ic_launcher.png
```

Build:

```bash
flutter build apk --flavor dev -t lib/main_dev.dart
flutter build appbundle --flavor prod -t lib/main_prod.dart
```

## iOS schemes and configurations

1. Xcode → Runner → Duplicate Debug/Release configurations: `Debug-dev`, `Release-prod`, etc.
2. Create schemes `dev`, `staging`, `prod` mapping to configurations.
3. Set bundle identifier per config: `com.example.app.dev`, `com.example.app`.
4. Display name via `INFOPLIST_KEY_CFBundleDisplayName` in build settings.

Flavor-specific `GoogleService-Info.plist`:

```
ios/Runner/Firebase/dev/GoogleService-Info.plist
ios/Runner/Firebase/prod/GoogleService-Info.plist
```

Add Run Script build phase copying correct plist per configuration.

Build from CLI:

```bash
flutter build ios --flavor dev -t lib/main_dev.dart
flutter build ipa --flavor prod -t lib/main_prod.dart
```

## Visual differentiation

Users and QA should instantly recognize environment:

- **App icon badge** — "DEV" overlay on icon assets per flavor.
- **Banner widget** in non-prod:

```dart
if (!Env.isProd)
  Banner(
    message: 'DEV',
    location: BannerLocation.topEnd,
    child: child,
  );
```

- **Theme tint** — subtle color shift for staging.

## CI matrix per flavor

```yaml
strategy:
  matrix:
    flavor: [dev, staging, prod]
steps:
  - run: |
      flutter build apk \
        --flavor ${{ matrix.flavor }} \
        -t lib/main_${{ matrix.flavor }}.dart \
        --dart-define-from-file=env/${{ matrix.flavor }}.json
```

Deploy dev/staging to internal tracks; prod to production with manual approval gate.

## Common pitfalls

1. **Wrong google-services.json** — verify Firebase project per flavor.
2. **Forgetting `-t` entrypoint** — flavor builds prod main by default.
3. **Deep link domains** — each bundle ID needs separate AASA/assetlinks or shared domain with path routing.
4. **API keys in repo** — dart-define from CI secrets, not committed JSON for prod keys.
5. **Plugin flavor unawareness** — some plugins need flavor-specific manifest entries.

Document run commands in README:

```bash
# Dev
flutter run --flavor dev -t lib/main_dev.dart --dart-define-from-file=env/dev.json
```

### FlutterFire per flavor

```bash
flutterfire configure --project=dev-project --out=lib/firebase_options_dev.dart
flutterfire configure --project=prod-project --out=lib/firebase_options_prod.dart
```

Select options file in main entrypoint. Crashlytics and Analytics must point to correct Firebase project per flavor—mixing causes production crashes in dev dashboards and vice versa.

Integration test flavors pointing at staging API prevent accidental prod data mutation in CI. Use different app icon overlays per flavor so QA screenshots metadata doesn't confuse store listings. Document dart-define keys in env/*.json with comments for non-obvious values.

Production teams should treat this guidance as living documentation: revisit assumptions after major platform upgrades, measure outcomes with real metrics rather than checklist compliance, and pair written standards with automated checks in CI. The patterns here reflect what held up in shipped apps—not theoretical perfection. Adapt thresholds, timeouts, and tooling to your stack, but keep the underlying principles: explicit configuration, testable behavior, and failure modes users can understand.

When onboarding new engineers, walk through one end-to-end example in a debug build before asking them to extend the pattern. Most failures I have seen came from skipped platform setup steps—manifest entries, API keys, code generation, or permission prompts—not from misunderstanding the Dart layer. Keep a troubleshooting section in your team wiki linking official docs and the exact commands that worked for your last upgrade.

Schedule a quarterly review of this implementation against current SDK release notes—Flutter and cloud providers ship breaking changes on six-month cadences, and assumptions that held last year may need adjustment. Capture before-and-after metrics when you change configuration so regressions are obvious in retrospect rather than debated from memory.

## Common production mistakes

Teams get flavors build configuration wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Flutter teams implementing flavors build configuration often regress performance by rebuilding entire subtrees on every frame, ignoring platform channel latency, or testing only on iOS simulators. Profile on mid-range Android hardware before calling the work done.

## Resources

- [Flutter flavors documentation](https://docs.flutter.dev/deployment/flavors)
- [dart-define compile-time variables](https://dart.dev/libraries/core/environment-declarations)
- [Android product flavors](https://developer.android.com/build/build-variants)
- [Xcode schemes documentation](https://developer.apple.com/documentation/xcode/customizing-the-build-schemes-for-a-project)
- [flutter_flavorizr package](https://pub.dev/packages/flutter_flavorizr)
