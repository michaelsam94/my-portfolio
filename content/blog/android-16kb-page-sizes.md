---
title: "Preparing Android Apps for 16 KB Page Sizes"
slug: "android-16kb-page-sizes"
description: "16 KB page sizes are becoming mandatory on Android. What changes for native libraries, how to check ELF alignment, rebuild with the NDK, and verify."
datePublished: "2026-01-27"
dateModified: "2026-01-27"
tags: ["Android", "Performance", "NDK"]
keywords: "16 KB page sizes, Android page size, native libraries alignment, NDK 16kb, ELF alignment, app compatibility"
faq:
  - q: "What are 16 KB page sizes on Android?"
    a: "A memory page is the smallest block the OS maps and manages, and Android historically used 4 KB pages. Newer Android devices run a 16 KB page kernel, which lets the memory manager track larger chunks per entry, reducing overhead and improving performance. Apps with native code compiled and aligned for 4 KB pages can fail to load on these devices unless rebuilt."
  - q: "Does my app need changes if it has no native code?"
    a: "If your app is pure Kotlin or Java with no NDK libraries and no third-party SDKs that bundle .so files, it already works on 16 KB devices with no changes. The risk is almost entirely in native shared libraries — your own C/C++ and, more often, the ones buried inside dependencies you didn't write."
  - q: "How do I check if my app is 16 KB compatible?"
    a: "Inspect the ELF program headers of every .so in your APK or App Bundle and confirm the LOAD segments are aligned to 16 KB (0x4000). Google provides an alignment check script, and you can also read segment alignment directly with readelf or llvm-objdump. Testing on a 16 KB emulator system image is the definitive verification."
---

Google is moving Android toward 16 KB memory pages, and for anyone shipping native code it's not an optional optimization — it's a hard compatibility requirement with a deadline. The short version: a memory page is the smallest unit the kernel maps, Android used 4 KB pages for its whole history, and newer devices boot a kernel with 16 KB pages to squeeze better performance out of modern hardware. Native shared libraries (`.so` files) that were compiled and aligned assuming 4 KB pages can refuse to load on those devices, crashing the app on launch.

The frustrating part is that this rarely surfaces in *your* code. It hides in the transitive native dependencies you didn't write — an image codec, an analytics SDK, a database engine — and it doesn't show up until an app runs on 16 KB hardware. I've spent enough time chasing "works on my Pixel, crashes on the new device" reports to take this one seriously and early.

## Why Android changed the page size

Larger pages mean the memory management unit tracks fewer, bigger entries, which cuts translation lookaside buffer (TLB) misses and page-fault overhead. Google's published numbers point to faster app launches, lower power draw, and better performance under memory pressure — meaningful on devices with a lot of RAM. The cost is paid by anything that assumed the old page size, primarily native binaries whose segments were aligned to 4 KB boundaries.

If your app is pure Kotlin or Java, you can mostly relax; the runtime handles it. This is entirely a native-code story, which is exactly why it catches teams off guard — they don't think of themselves as "having native code" because they never wrote a line of C++.

## What actually breaks

An ELF shared library declares `LOAD` segments with an alignment value. The dynamic linker maps those segments at page boundaries. When the segment alignment is 4 KB but the kernel enforces 16 KB pages, the linker can't satisfy the mapping and the load fails. The app dies with a linker error before your code runs.

There are two flavors of problem:
1. **Segment alignment** — the `.so`'s `LOAD` segments must be aligned to 16 KB.
2. **Hardcoded assumptions** — code that calls `getpagesize()` or `sysconf(_SC_PAGESIZE)` and assumes the answer is 4096, or that `mmap`s with 4 KB offsets. This is rarer but nastier because it's a runtime logic bug, not a load failure.

Most apps only hit the first flavor, and rebuilding fixes it.

## Checking your libraries

Before changing anything, audit what you actually ship. Pull the `.so` files out of your APK and inspect their program headers. `llvm-readelf` from the NDK shows the alignment of each `LOAD` segment:

```bash
# Unzip the APK, then inspect a native lib
unzip -o app-release.apk -d extracted/
llvm-readelf -l extracted/lib/arm64-v8a/libfoo.so | grep LOAD
```

You're looking at the `Align` column. `0x4000` (16384) is good; `0x1000` (4096) is the old alignment that will fail. Google also ships a `check_elf_alignment.sh` script that scans an entire APK and reports every unaligned library at once — run that in CI so a dependency bump can't silently reintroduce a 4 KB library. Catching it in the pipeline is the same instinct behind gating startup regressions with [baseline profiles](https://blog.michaelsam94.com/baseline-profiles-android-startup/): make the machine notice before a device does.

## Rebuilding your own native code

If the offending library is yours, the fix is a rebuild with a recent NDK. NDK r28 and later default to 16 KB-compatible alignment, so often just upgrading is enough. For older toolchains, pass the linker flag explicitly:

```bash
# In your CMake or ndk-build flags
-Wl,-z,max-page-size=16384
```

With CMake, that goes in your `CMakeLists.txt`:

```cmake
target_link_options(foo PRIVATE "-Wl,-z,max-page-size=16384")
```

And in Gradle, make sure your AGP and NDK versions are current, then confirm the resulting `.so` with `readelf` again. Don't trust that the flag worked — verify the output. I've been burned by a flag that was silently ignored because it was set on the wrong target.

## The dependency problem

Your own code is the easy case. The hard case is a third-party AAR that bundles a 4 KB `.so` and hasn't shipped a 16 KB build. Your options, in order of preference:

| Situation | Action |
|---|---|
| Dependency has a newer version | Upgrade — most major SDKs shipped 16 KB builds through 2024–2025 |
| Maintained but no 16 KB build yet | File an issue, pin, and track it |
| Unmaintained | Replace it, or rebuild from source if licensed |
| No alternative | Escalate — this can block your release |

The lesson I keep relearning: audit native dependencies *now*, not the week before the Play Store enforcement date. A single unmaintained library with a bundled `.so` can hold an entire release hostage, and finding a replacement takes weeks, not days.

## Testing on real 16 KB targets

Static checks tell you about alignment; they don't prove the app runs. Google provides 16 KB-enabled Android emulator system images — boot one and run your full smoke suite. On device, you can confirm the page size at runtime:

```bash
adb shell getconf PAGE_SIZE
# 16384 on a 16 KB device
```

Automate a launch-and-navigate pass on the 16 KB emulator in CI. Pair it with your existing performance instrumentation — the same [Macrobenchmark profiling](https://blog.michaelsam94.com/android-macrobenchmark-profiling/) harness you use for startup can double as the vehicle that proves the app even loads on the new page size, and it'll catch any real performance shift from the larger pages while you're there.

## My take

This is a classic infrastructure migration: technically simple, organizationally annoying. The actual fix is usually one NDK bump and a linker flag. The work is the audit — finding every native library in a dependency graph you didn't fully know you had, and chasing the one maintainer who hasn't updated. Do the audit early, wire the alignment check into CI, and add a 16 KB emulator to your test matrix. Then the deadline becomes a non-event instead of a fire drill.

## Resources

- [Android 16 KB page size support guide](https://developer.android.com/guide/practices/page-sizes)
- [Android NDK downloads and release notes](https://developer.android.com/ndk/downloads)
- [ELF alignment check script (Android platform tools)](https://android.googlesource.com/platform/system/extras/+/refs/heads/main/tools/check_elf_alignment.sh)
- [ELF specification (Tool Interface Standard)](https://refspecs.linuxfoundation.org/elf/elf.pdf)
- [Android Studio and emulator system images](https://developer.android.com/studio)
