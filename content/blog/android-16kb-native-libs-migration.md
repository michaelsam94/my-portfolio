---
title: "Migrating Native Libraries to 16KB Pages"
slug: "android-16kb-native-libs-migration"
description: "Prepare Android native libraries for 16KB page size devices: rebuild with NDK r27+, alignment flags, testing on 16KB emulators, and Play Console validation."
datePublished: "2026-07-08"
dateModified: "2026-07-08"
tags: ["Android", "NDK", "Native", "Performance"]
keywords: "Android 16KB page size, native library migration, NDK 16KB alignment, 16KB page size Google Play, ELF segment alignment"
faq:
  - q: "Why do Android apps need 16KB page size support?"
    a: "Newer ARM64 Android devices use 16KB memory pages instead of the traditional 4KB. Native libraries (.so files) compiled with 4KB ELF segment alignment may crash or fail to load on these devices. Google Play requires 16KB-compatible native libraries for apps targeting recent API levels on 16KB devices."
  - q: "How do I rebuild native libraries for 16KB pages?"
    a: "Use NDK r27 or later and add the linker flag -Wl,-z,max-page-size=16384 to your CMake or ndk-build configuration. Rebuild all native code including third-party SDK .so files. Verify alignment with readelf or the APK Analyzer before submitting to Play Console."
  - q: "How do I test 16KB page size compatibility?"
    a: "Use the Android Emulator with a 16KB page size system image (available for API 35+). Run your full test suite on this emulator. Also check the Play Console pre-launch report and the 16KB compatibility check in Android Studio's APK Analyzer."
---

Google Play's 16KB page size requirement caught a lot of teams off guard — especially ones with native SDKs they didn't compile themselves. If your app ships any `.so` files (your own NDK code, React Native, Flutter engine, analytics SDKs, game engines), those libraries must have ELF segments aligned to 16KB, not the traditional 4KB. An unaligned library doesn't always crash on your 4KB test devices; it fails silently or hard-crashes on the newest ARM64 hardware. I've walked three apps through this migration; the process is straightforward if you control your build, and painful if you depend on vendors who haven't rebuilt yet.

## What's actually changing

Android on ARM64 historically used 4KB memory pages. Newer devices (starting with certain Pixel and flagship chips) use 16KB pages for better TLB efficiency. Native libraries declare their page alignment in ELF program headers. Libraries built with 4KB alignment (`Align 0x1000`) may not load on 16KB-page devices (`Align 0x4000` required).

This affects:
- Your own JNI/NDK C/C++ code
- Flutter engine and plugins with native code
- React Native native modules
- Third-party SDKs shipping `.so` files (analytics, ads, ML, crypto)
- Game engines (Unity, Unreal)

Kotlin/Java-only apps with zero native code are unaffected.

## Rebuilding your native code

With NDK r27+ and CMake:

```cmake
# CMakeLists.txt
if(ANDROID)
    target_link_options(${CMAKE_PROJECT_NAME} PRIVATE
        "-Wl,-z,max-page-size=16384"
    )
endif()
```

With ndk-build (`Android.mk`):

```makefile
LOCAL_LDFLAGS += -Wl,-z,max-page-size=16384
```

Rebuild all ABIs you ship (`arm64-v8a` is the critical one; `x86_64` for emulator testing too). Clean build — don't incrementally compile.

For Gradle, ensure you're on AGP 8.5+ and NDK r27+:

```kotlin
android {
    ndkVersion = "27.0.12077973"
}
```

## Verifying alignment

Check your `.so` files before uploading:

```bash
# Check LOAD segment alignment
readelf -l libmyapp.so | grep LOAD
# Look for Align 0x4000 (16384) — good
# Align 0x1000 (4096) — needs rebuild
```

Android Studio's APK Analyzer also flags 16KB-incompatible libraries under `lib/` — use it on every release build.

For a quick audit of all libraries in your APK:

```bash
unzip -l app-release.apk 'lib/*/*.so' | awk '{print $4}' | while read so; do
    unzip -p app-release.apk "$so" > /tmp/check.so
    align=$(readelf -l /tmp/check.so | grep LOAD | head -1 | awk '{print $NF}')
    echo "$so: $align"
done
```

## Third-party SDK problem

Your code may be aligned while a vendor SDK isn't. Audit every `.so` in your APK:

1. List all native libraries: `./gradlew app:dependencies` + APK Analyzer
2. Check alignment of each
3. For misaligned vendor libs: update to the vendor's 16KB-compatible release, or contact them
4. If no fix available: evaluate whether you can drop the SDK or switch vendors

This is the bottleneck for most teams — your build is fine, but `libsomeanalytics.so` from a SDK you imported two years ago isn't.

## Testing on 16KB emulator

Google provides 16KB page size system images for API 35+:

1. SDK Manager → download "Google APIs ARM 64 v8a 16 KB Page Size" system image
2. Create an AVD with this image
3. Run your full test suite — focus on app startup, native-heavy screens, and SDK initialization paths

Also enable the 16KB page size option on physical Pixel devices in Developer Options for real-hardware validation.

The [Android 16KB page sizes guide](https://blog.michaelsam94.com/android-16kb-page-sizes/) covers the device-side context; this post is about the native build migration.

## Play Console checks

Play Console now reports 16KB compatibility in pre-launch reports and app bundle analysis. Before submitting:

- Upload to internal testing track
- Check the "16 KB page size" section in bundle details
- Fix any flagged libraries before promoting to production

Don't wait for a rejection email — the check is available at upload time.

## Migration checklist

1. Update NDK to r27+, AGP to 8.5+
2. Add `-Wl,-z,max-page-size=16384` to all native build configs
3. Clean rebuild all ABIs
4. Audit every `.so` in the release APK with `readelf`
5. Update third-party SDKs to 16KB-compatible versions
6. Test on 16KB emulator system image
7. Verify in Play Console bundle analysis
8. Add 16KB emulator to CI (optional but recommended)

Treat production rollout as a measured change: ship with observability, validate rollback, and review metrics 24 hours after deploy — patterns that look obvious in docs fail when skipped under release pressure.

## Common production mistakes

Teams get 16kb native libs migration wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Shipping 16kb native libs migration on Android fails quietly when you test only on flagship devices, skip process-death scenarios, or assume `minSdk` behavior matches latest API docs. Emulator-only validation misses OEM-specific battery optimizations and background execution limits.

## Debugging and triage workflow

When 16kb native libs migration misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## NDK r28 and linker flags

`-Wl,-z,max-page-size=16384` required for prebuilt `.so` from vendors not yet rebuilt. Audit transitive SDK AARs with `readelf -l libfoo.so | grep LOAD` in CI — fail build on 4KB-only prebuilts when targeting 16KB devices.

## Emulator 16KB page image

Android 15 system images with 16KB pages catch alignment bugs x86 misses — add dedicated CI job on 16KB emulator before Pixel 9 hardware lab.

## 16Kb Native Libs Migration Supplement 0 on Samsung and Pixel divergence

Exercise 16kb native libs migration supplement 0 on Galaxy A-series and Pixel a-series — emulators hide OEM battery and storage quirks. Capture Macrobenchmark or Firebase trace for the critical path touching 16kb; regressions above 8% block release for `android-16kb-native-libs-migration-supplement-0`.

Document permission and background behavior in internal runbook: what breaks under Doze, what requires foreground service, and what Play policy declarations apply. Support tickets referencing "16Kb Native Libs Migration Supplement 0" should map to a single runbook section with known workarounds.

## Migration regression gates for Play Vitals

Before promoting `android-16kb-native-libs-migration-supplement-0` changes past 20% rollout, compare ANR rate, slow cold start, and excessive wakeups against seven-day baseline. Fail rollback review if 0 path shows >5% increase in `slow frames` without documented trade-off approval.

## Resources

- [Android 16 KB page size guide](https://developer.android.com/guide/practices/page-sizes)
- [NDK r27 release notes](https://github.com/android/ndk/wiki/Changelog-r27)
- [ELF program header specification](https://refspecs.linuxfoundation.org/elf/gabi4+/ch5.pheader.html)
- [Google Play 16KB requirement announcement](https://android-developers.googleblog.com/)
- [Android 16KB page sizes overview](https://blog.michaelsam94.com/android-16kb-page-sizes/)
