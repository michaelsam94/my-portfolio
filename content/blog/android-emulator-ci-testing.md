---
title: "Running the Android Emulator in CI"
slug: "android-emulator-ci-testing"
description: "Run Android emulator tests in CI with hardware acceleration, reusable AVD snapshots, GitHub Actions, and Gradle Managed Devices for reliable automated UI testing."
datePublished: "2026-07-16"
dateModified: "2026-07-16"
tags: ["Android", "CI", "Testing", "DevOps"]
keywords: "Android emulator CI, GitHub Actions Android emulator, AVD CI testing, Gradle Managed Devices CI, android-emulator-runner"
faq:
  - q: "Can you run the Android emulator in CI?"
    a: "Yes, on Linux CI runners with KVM hardware acceleration enabled. GitHub Actions, GitLab CI, and CircleCI support nested virtualization on their standard Linux runners. Use the reactivecircus/android-emulator-runner action or Gradle Managed Devices to boot an AVD, run instrumentation tests, and shut down."
  - q: "What is the fastest way to run emulator tests in CI?"
    a: "Use AVD snapshots — boot the emulator once, save a snapshot after system boot completes, and restore from snapshot on subsequent runs. This cuts boot time from 60–90 seconds to 5–10 seconds. Gradle Managed Devices with persistent AVDs on self-hosted runners is even faster for high-volume CI."
  - q: "Should I use emulator or physical devices for CI?"
    a: "Emulators for PR checks — fast feedback on UI logic, navigation, and Compose tests. Physical device farms (Firebase Test Lab, BrowserStack) for pre-release validation on real hardware with GPU, sensors, and OEM-specific behavior. Most teams run emulator tests on every PR and device farm tests nightly or pre-release."
---

Running the Android emulator in CI used to be a punchline — slow, flaky, and requiring custom KVM setup on bare metal. That's changed. GitHub Actions' `android-emulator-runner`, Gradle Managed Devices, and snapshot-based boot make emulator CI viable on every PR. I've cut a team's instrumentation test feedback loop from "run locally before merge" to "CI runs it in 8 minutes" by combining AVD snapshots with a well-configured runner. The emulator isn't a perfect substitute for physical devices, but it's good enough for 90% of UI test coverage — and it runs on every commit.

## GitHub Actions setup

```yaml
name: Android Instrumentation Tests

on: [pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up JDK 17
        uses: actions/setup-java@v4
        with:
          java-version: 17
          distribution: temurin

      - name: Enable KVM
        run: |
          echo 'KERNEL=="kvm", GROUP="kvm", MODE="0666", OPTIONS+="static_node=kvm"' | sudo tee /etc/udev/rules.d/99-kvm.rules
          sudo udevadm control --reload-rules
          sudo udevadm trigger --name-match=kvm

      - name: Run instrumentation tests
        uses: reactivecircus/android-emulator-runner@v2
        with:
          api-level: 34
          target: google_apis
          arch: x86_64
          profile: pixel_6
          disable-animations: true
          emulator-options: -no-snapshot-save -no-window -gpu swiftshader_indirect -noaudio -no-boot-anim
          script: ./gradlew connectedDebugAndroidTest

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: test-results
          path: app/build/reports/androidTests/
```

Key flags:
- `disable-animations: true` — removes animation delays in tests
- `-no-boot-anim` — skips boot animation
- `-gpu swiftshader_indirect` — software GPU rendering (no GPU on CI runners)
- `x86_64` arch — required for hardware acceleration on Linux CI

## AVD snapshots for speed

Without snapshots, every CI run boots the emulator from cold — 60–90 seconds before your first test runs. Create a snapshot:

```bash
# Boot emulator locally
emulator -avd CI_Test -no-window -gpu swiftshader_indirect &
adb wait-for-device
adb shell input keyevent 82  # unlock

# Save snapshot
adb emu avd snapshot save ci_booted
```

Reference in CI:

```yaml
emulator-options: -snapshot ci_booted -no-snapshot-save -no-window -gpu swiftshader_indirect
```

Boot drops to 5–10 seconds. Regenerate the snapshot when you change API level or system image.

## Gradle Managed Devices

AGP 7.0+ provides managed devices that handle AVD creation and lifecycle:

```kotlin
android {
    testOptions {
        managedDevices {
            devices {
                create("pixel6Api34", ManagedVirtualDevice::class) {
                    device = "Pixel 6"
                    apiLevel = 34
                    systemImageSource = "google"
                }
            }
        }
    }
}
```

Run tests:

```bash
./gradlew pixel6Api34DebugAndroidTest
```

Gradle creates the AVD, boots it, runs tests, and tears down. Less YAML configuration than raw emulator-runner, but less control over snapshot optimization.

For deeper GMD configuration, see [Gradle Managed Devices for UI tests](https://blog.michaelsam94.com/android-gradle-managed-devices-testing/).

## What to test on emulator vs device farm

| Test type | Emulator CI | Device farm |
|-----------|------------|-------------|
| Compose UI tests | Every PR | Nightly |
| Navigation flows | Every PR | Nightly |
| Screenshot tests (Paparazzi/Roborazzi) | Every PR (JVM, no emulator) | N/A |
| Camera/sensor features | Skip | Pre-release |
| Performance benchmarks | Unreliable | Pre-release |
| OEM-specific behavior | Skip | Pre-release |

[Paparazzi and Roborazzi](https://blog.michaelsam94.com/android-screenshot-testing-paparazzi/) run on JVM without an emulator — use them for visual regression on every PR and reserve emulator time for interaction tests.

## Flakiness mitigation

Emulator tests flake more than unit tests. Reduce it:

- **Disable animations**: `adb shell settings put global animator_duration_scale 0`
- **Idling resources**: Use Espresso's IdlingResource for async operations
- **Compose test sync**: `composeTestRule.waitForIdle()` before assertions
- **Retry flaky tests**: Gradle test retry plugin (1 retry in CI)
- **Isolate tests**: Each test resets app state; no shared state between tests

```kotlin
@get:Rule
val retryRule = RetryRule(retries = 1)  // custom JUnit rule
```

## Self-hosted runners for scale

If you're running 50+ instrumentation tests per PR across multiple API levels, GitHub-hosted runners get expensive and slow. A self-hosted runner with:
- KVM-enabled Linux machine
- Persistent AVD with snapshot
- Pre-warmed Gradle daemon

...runs the same suite in half the time at lower cost. The trade-off is runner maintenance.

## Snapshot and cold boot optimization

AVD snapshots cut emulator boot from 60s to 5s:

```yaml
- name: AVD snapshot
  uses: reactivecircus/android-emulator-runner@v2
  with:
    api-level: 34
    target: google_apis
    arch: x86_64
    force-avd-creation: false
    emulator-options: -no-snapshot-save -no-boot-anim -gpu swiftshader_indirect
    script: ./gradlew connectedDebugAndroidTest
```

Create snapshot once on runner setup, reuse across CI runs. `-no-snapshot-save` prevents drift from test pollution.

## Parallel sharding

Split instrumentation tests across matrix jobs:

```yaml
strategy:
  matrix:
    shard: [0, 1, 2, 3]
steps:
  - run: ./gradlew connectedDebugAndroidTest -Pandroid.testInstrumentationRunnerArguments.numShards=4 -Pandroid.testInstrumentationRunnerArguments.shardIndex=${{ matrix.shard }}
```

Four shards on four runners finish 4× faster than one sequential job — worth the GitHub Actions minute cost for PR feedback latency.

## Emulator vs physical device gaps

Emulators miss real-world issues:

- GPS/location mocking differs from actual sensor fusion
- Camera HAL not emulated faithfully
- GPU rendering differs from Mali/Adreno on device
- Notification channels behave differently under OEM skins

Budget Firebase Test Lab or internal device lab for pre-release — emulator CI catches logic bugs, device farm catches hardware integration.

Pair with [Android baseline profiles CI](https://blog.michaelsam94.com/android-baseline-profiles-ci/) to warm startup paths before benchmark runs on emulators.

## Common production mistakes

Teams get emulator ci testing wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Shipping emulator ci testing on Android fails quietly when you test only on flagship devices, skip process-death scenarios, or assume `minSdk` behavior matches latest API docs. Emulator-only validation misses OEM-specific battery optimizations and background execution limits.

## Resources

- [android-emulator-runner GitHub Action](https://github.com/ReactiveCircus/android-emulator-runner)
- [Gradle Managed Devices](https://developer.android.com/studio/test/gradle-managed-devices)
- [Test Android apps with Firebase Test Lab](https://firebase.google.com/docs/test-lab)
- [Espresso idling resources](https://developer.android.com/training/testing/espresso/idling-resource)
- [Gradle Managed Devices testing guide](https://blog.michaelsam94.com/android-gradle-managed-devices-testing/)
