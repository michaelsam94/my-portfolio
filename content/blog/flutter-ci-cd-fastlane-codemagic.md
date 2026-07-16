---
title: "CI/CD for Flutter with Codemagic"
slug: "flutter-ci-cd-fastlane-codemagic"
description: "Ship Flutter apps from Codemagic: codemagic.yaml workflows, iOS signing, Android keystore, TestFlight automation, and caching that cuts build times in half."
datePublished: "2024-10-04"
dateModified: "2024-10-04"
tags: ["Flutter", "Dart"]
keywords: "Codemagic Flutter CI, codemagic.yaml, Flutter iOS CI, TestFlight automation, Flutter CD pipeline"
faq:
  - q: "What is Codemagic for Flutter?"
    a: "Codemagic is a CI/CD platform with first-class Flutter support—macOS and Linux builders, built-in code signing for iOS and Android, and YAML-based workflows. It handles flutter build ipa and appbundle with less configuration than generic CI runners, especially for Apple certificate management via Codemagic's encrypted storage."
  - q: "How do I configure iOS signing in Codemagic?"
    a: "Upload your App Store Connect API key, distribution certificate, and provisioning profile in Codemagic Team settings or reference them via environment groups in codemagic.yaml. Codemagic installs certificates into a temporary keychain during the build. Automatic code signing can fetch profiles if you provide API key credentials."
  - q: "Can Codemagic run Flutter tests before building?"
    a: "Yes—add scripts in the workflow to run flutter analyze, flutter test, and integration tests before the build step. Fail fast on test failures to avoid burning macOS build minutes. Cache pub dependencies and Gradle artifacts to keep test-plus-build pipelines under 15 minutes."
---

We migrated from a GitHub Actions macOS runner that cost $200/month and broke every time Apple rotated a certificate. Codemagic's Flutter-native workflows cut our pipeline config in half and TestFlight uploads became boring—which is exactly what CI/CD should be. If you're shipping Flutter to both stores, Codemagic (or a similarly Flutter-aware CI) beats duct-taping generic runners.

## Project structure for CI

Commit `codemagic.yaml` at repo root:

```yaml
workflows:
  ios-android-release:
    name: Release Build
    max_build_duration: 60
    instance_type: mac_mini_m2
    environment:
      flutter: stable
      xcode: latest
      groups:
        - app_store_credentials
        - keystore_credentials
      vars:
        PACKAGE_NAME: com.example.myapp
      ios_signing:
        distribution_type: app_store
        bundle_identifier: com.example.myapp
    triggering:
      events:
        - push
      branch_patterns:
        - pattern: main
          include: true
    scripts:
      - name: Get packages
        script: flutter pub get
      - name: Analyze
        script: flutter analyze
      - name: Test
        script: flutter test
      - name: Build Android
        script: |
          flutter build appbundle --release \
            --build-number=$PROJECT_BUILD_NUMBER
      - name: Build iOS
        script: |
          flutter build ipa --release \
            --build-number=$PROJECT_BUILD_NUMBER \
            --export-options-plist=/Users/builder/export_options.plist
    artifacts:
      - build/**/outputs/**/*.aab
      - build/ios/ipa/*.ipa
    publishing:
      app_store_connect:
        auth: integration
        submit_to_testflight: true
      google_play:
        credentials: $GCLOUD_SERVICE_ACCOUNT_CREDENTIALS
        track: internal
```

## Credential management

**iOS — App Store Connect API key** (preferred over Apple ID):

1. App Store Connect → Users → Integrations → App Store Connect API.
2. Upload `.p8` key to Codemagic encrypted environment group.
3. Reference via `app_store_connect: auth: integration`.

**Android — keystore:**

Upload keystore file and set environment variables:

```yaml
environment:
  groups:
    - keystore_credentials  # CM_KEYSTORE, CM_KEYSTORE_PASSWORD, etc.
```

Reference in `android/app/build.gradle` via environment or `key.properties` generated in CI:

```bash
echo "storePassword=$CM_KEYSTORE_PASSWORD" >> android/key.properties
echo "keyPassword=$CM_KEY_ALIAS_PASSWORD" >> android/key.properties
echo "keyAlias=$CM_KEY_ALIAS" >> android/key.properties
echo "storeFile=$CM_KEYSTORE_PATH" >> android/key.properties
```

Never commit keystores or key.properties to git.

## Caching for speed

Codemagic caches by default, but explicit cache paths help:

```yaml
cache:
  cache_paths:
    - $FLUTTER_ROOT/.pub-cache
    - $HOME/.gradle/caches
    - $HOME/Library/Caches/CocoaPods
```

First build populates cache; subsequent builds often drop from 18 minutes to 8 on M2 instances.

## Branch workflows

Separate PR validation from release:

```yaml
workflows:
  pr-check:
    name: PR Validation
    instance_type: mac_mini_m2
    triggering:
      events:
        - pull_request
    scripts:
      - flutter pub get
      - flutter analyze --fatal-infos
      - flutter test --coverage
    publishing:
      scripts:
        - name: Upload coverage
          script: |
            # codecov or similar
            bash <(curl -s https://codecov.io/bash)
```

Release workflow triggers only on tagged commits:

```yaml
triggering:
  events:
    - tag
  tag_patterns:
    - pattern: 'v*'
      include: true
```

## Versioning and build numbers

Codemagic exposes `PROJECT_BUILD_NUMBER` (auto-incrementing per workflow) and `BUILD_NUMBER`. Sync with pubspec:

```bash
# Increment build number from Codemagic
flutter pub run build_runner build --delete-conflicting-outputs || true
sed -i '' "s/version: \(.*\)+.*/version: \1+$PROJECT_BUILD_NUMBER/" pubspec.yaml
flutter build ipa --build-number=$PROJECT_BUILD_NUMBER
```

Or use `codemagic-cli-tools` for semantic versioning from git tags.

## Integration tests on Codemagic

Run Patrol or integration tests on emulators:

```yaml
scripts:
  - name: Integration tests
    script: |
      flutter emulators --launch apple_ios_simulator
      flutter test integration_test/
```

Emulator tests on macOS builders are slower—reserve for nightly builds; unit tests on every PR.

### Fastlane alternative within Codemagic

Codemagic publishing replaces much of Fastlane for standard flows. Use Fastlane when you need custom lanes—screenshots, metadata sync, phased rollout:

```yaml
scripts:
  - name: Fastlane deploy
    script: |
      cd ios && fastlane beta
```

Install gems in a prior step; commit `Fastfile` to repo.

### Monitoring and notifications

Configure Slack or email in Codemagic UI for build failures. Tag `@channel` only on main branch failures—PR failures notify the author via GitHub status checks.

Track build duration trends. Spikes usually mean cache invalidation or new heavy dependencies.

### Shorebird and OTA alongside CI

If using Shorebird for code push, run `shorebird release` in Codemagic after store builds for teams shipping Dart hotfixes without store review. Separate workflows—store release vs patch—prevent accidentally patching debug builds. Store release artifacts with build IDs matching Shorebird patch metadata for rollback traceability.

Codemagic macOS M2 instances worth the cost for iOS—Intel runners timeout on large Flutter iOS builds. Monitor queue times; upgrade instance tier during release weeks.

Store Codemagic signing files encrypted; rotate certificates before expiry with calendar reminders 30 days ahead. Parallel Android and iOS build steps in one workflow when teams release both stores simultaneously—artifact naming with flavor and build number prevents wrong IPA upload confusion.

Production teams should treat this guidance as living documentation: revisit assumptions after major platform upgrades, measure outcomes with real metrics rather than checklist compliance, and pair written standards with automated checks in CI. The patterns here reflect what held up in shipped apps—not theoretical perfection. Adapt thresholds, timeouts, and tooling to your stack, but keep the underlying principles: explicit configuration, testable behavior, and failure modes users can understand.

When onboarding new engineers, walk through one end-to-end example in a debug build before asking them to extend the pattern. Most failures I have seen came from skipped platform setup steps—manifest entries, API keys, code generation, or permission prompts—not from misunderstanding the Dart layer. Keep a troubleshooting section in your team wiki linking official docs and the exact commands that worked for your last upgrade.

Schedule a quarterly review of this implementation against current SDK release notes—Flutter and cloud providers ship breaking changes on six-month cadences, and assumptions that held last year may need adjustment. Capture before-and-after metrics when you change configuration so regressions are obvious in retrospect rather than debated from memory.

Pin Flutter SDK version in CI to match local `.fvmrc` — channel drift causes builds that pass locally and fail in pipeline.

## Resources

- [Codemagic Flutter Documentation](https://docs.codemagic.io/flutter/flutter-projects/)
- [codemagic.yaml reference](https://docs.codemagic.io/yaml/yaml-getting-started/)
- [Codemagic iOS Code Signing](https://docs.codemagic.io/yaml-code-signing/signing-ios/)
- [Codemagic Android Code Signing](https://docs.codemagic.io/yaml-code-signing/signing-android/)
- [Flutter Continuous Delivery](https://docs.flutter.dev/deployment/cd)
