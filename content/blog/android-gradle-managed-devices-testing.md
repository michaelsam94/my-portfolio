---
title: "Gradle Managed Devices for UI Tests"
slug: "android-gradle-managed-devices-testing"
description: "Use Gradle Managed Devices for Android UI testing: declarative AVD config, CI integration, screenshot tests, and comparison with manual emulator setup."
datePublished: "2026-07-16"
dateModified: "2026-07-16"
tags: ["Android", "Testing", "Gradle", "CI"]
keywords: "Gradle Managed Devices, GMD Android testing, managed virtual devices, Android UI test CI, declarative AVD Gradle"
faq:
  - q: "What are Gradle Managed Devices?"
    a: "Gradle Managed Devices (GMD) let you declare virtual test devices in build.gradle.kts and run instrumentation tests against them with a single Gradle task. Gradle handles AVD creation, boot, test execution, and teardown. No manual emulator setup or CI YAML emulator configuration required."
  - q: "How do Gradle Managed Devices differ from connectedDebugAndroidTest?"
    a: "connectedDebugAndroidTest requires a running emulator or physical device connected via ADB. GMD creates and manages its own emulator instance automatically. GMD is designed for CI and reproducible test environments; connected tests are for local development with whatever device you have plugged in."
  - q: "Can Gradle Managed Devices run in CI?"
    a: "Yes, on Linux runners with KVM enabled. Gradle downloads the system image, creates the AVD, boots it, runs tests, and shuts down — all within the Gradle task. Combine with GitHub Actions or self-hosted runners. Boot time is the main cost; use snapshots on self-hosted runners for faster iteration."
---

Gradle Managed Devices are Android's answer to "why do I need 40 lines of YAML just to boot an emulator in CI?" You declare the device you want in `build.gradle.kts`, run one Gradle task, and Gradle handles AVD creation, boot, test execution, and teardown. No `android-emulator-runner` action, no manual SDK component installation, no "works on my machine" AVD configs. I switched a project's CI from custom emulator scripts to GMD and deleted 120 lines of pipeline config — the tests run the same, but onboarding a new developer is `./gradlew pixel6Api34DebugAndroidTest` instead of "first install these SDK packages and create this AVD."

## Basic setup

```kotlin
// app/build.gradle.kts
android {
    testOptions {
        managedDevices {
            devices {
                create("pixel6Api34", ManagedVirtualDevice::class) {
                    device = "Pixel 6"
                    apiLevel = 34
                    systemImageSource = "google"
                }
                create("pixel4Api30", ManagedVirtualDevice::class) {
                    device = "Pixel 4"
                    apiLevel = 30
                    systemImageSource = "google-atd"  // Android Test Device — faster
                }
            }
            groups {
                create("ciDevices") {
                    targetDevices.add(devices["pixel6Api34"])
                    targetDevices.add(devices["pixel4Api30"])
                }
            }
        }
    }
}
```

Run tests:

```bash
# Single device
./gradlew :app:pixel6Api34DebugAndroidTest

# Device group
./gradlew :app:ciDevicesDebugAndroidTest
```

Gradle creates the AVD if it doesn't exist, boots it, runs all instrumentation tests, collects results, and shuts down.

## ATD images for speed

Android Test Device (ATD) system images are optimized for testing — reduced system apps, faster boot:

```kotlin
create("ciPhone", ManagedVirtualDevice::class) {
    device = "Pixel 4"
    apiLevel = 30
    systemImageSource = "google-atd"
}
```

ATD images boot 30–50% faster than standard Google API images. Use them for CI; use standard images when you need full Google Play Services behavior.

## CI integration

GitHub Actions with KVM:

```yaml
jobs:
  ui-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with:
          java-version: 17
          distribution: temurin

      - name: Enable KVM
        run: |
          echo 'KERNEL=="kvm", GROUP="kvm", MODE="0666", OPTIONS+="static_node=kvm"' | sudo tee /etc/udev/rules.d/99-kvm.rules
          sudo udevadm control --reload-rules
          sudo udevadm trigger --name-match=kvm

      - name: Run UI tests
        run: ./gradlew :app:pixel6Api34DebugAndroidTest --info

      - name: Upload results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: ui-test-results
          path: app/build/reports/androidTests/
```

No emulator-runner action needed — GMD handles everything within Gradle.

## Multiple API levels

Test across API levels with device groups:

```kotlin
groups {
    create("allApis") {
        targetDevices.addAll(devices.values)
    }
}
```

```bash
./gradlew :app:allApisDebugAndroidTest
```

Runs the full test suite on each declared device sequentially. Parallel execution requires Gradle 8.0+ parallel device testing or separate CI jobs per API level.

For CI cost control, run full matrix nightly and single latest-API on PRs:

```yaml
on:
  pull_request:
    # PR: latest API only
    run: ./gradlew :app:pixel6Api34DebugAndroidTest
  schedule:
    - cron: '0 2 * * *'
    # Nightly: all APIs
    run: ./gradlew :app:allApisDebugAndroidTest
```

## GMD vs alternatives

| Approach | Setup | CI config | Boot time | Flexibility |
|----------|-------|-----------|-----------|-------------|
| GMD | build.gradle.kts | Minimal | Medium | Device declaration only |
| android-emulator-runner | YAML + SDK setup | Heavy YAML | Fast (with snapshots) | Full emulator flags |
| Firebase Test Lab | None (cloud) | One line | N/A (cloud) | Real devices, costs $ |
| Paparazzi/Roborazzi | Gradle plugin | None (JVM) | Instant | Screenshots only, no interaction |

Use GMD for instrumentation tests in CI. Use [Paparazzi/Roborazzi](https://blog.michaelsam94.com/android-screenshot-testing-paparazzi/) for screenshot tests (no emulator needed). Use Firebase Test Lab for pre-release device matrix validation.

## Gradle Managed Devices + screenshot tests

GMD runs Espresso and Compose UI tests. For screenshot-only testing, prefer JVM-based tools:

```kotlin
// Paparazzi — no emulator needed
@Test
fun screenshot_homeScreen() {
    paparazzi.snapshot { HomeScreen() }
}
```

Reserve GMD emulator time for tests that need real Android framework interaction — touch events, permissions, Intents, system services.

## Troubleshooting

**"No system image found"** — Gradle downloads images automatically on first run, but CI needs network access and sufficient disk (~10GB per image).

**Timeout on boot** — Increase timeout in `gradle.properties`: `android.experimental.testOptions.managedDevices.maxConcurrentDevices=1`

**KVM not available** — GMD requires hardware acceleration. On macOS CI (no KVM), use Firebase Test Lab instead.

**Tests pass locally, fail on GMD** — Usually animation/timing issues. Disable animations and add proper idling.

Run GMD tests on CI with `-Pandroid.testoptions.manageddevices.emulator.gpu=swiftshader_indirect` for headless stability.

## GMD in CI matrix

```kotlin
testing {
  devices {
    pixel6Api34(com.android.build.api.dsl.ManagedVirtualDevice) {
      device = "Pixel 6"
      apiLevel = 34
    }
  }
}
```

GMD tests run on local JVM with Gradle — faster than emulator-runner Action for small suites, slower setup for first run.

## Common production mistakes

Teams get gradle managed devices testing wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Shipping gradle managed devices testing on Android fails quietly when you test only on flagship devices, skip process-death scenarios, or assume `minSdk` behavior matches latest API docs. Emulator-only validation misses OEM-specific battery optimizations and background execution limits.

## Debugging and triage workflow

When gradle managed devices testing misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Gradle Managed Devices documentation](https://developer.android.com/studio/test/gradle-managed-devices)
- [Android Test Device (ATD) images](https://developer.android.com/studio/test/gradle-managed-devices#atd)
- [android-emulator-runner for CI](https://blog.michaelsam94.com/android-emulator-ci-testing/)
- [Testing Compose UIs](https://developer.android.com/jetpack/compose/testing)
- [Screenshot testing with Paparazzi](https://blog.michaelsam94.com/android-screenshot-testing-paparazzi/)
