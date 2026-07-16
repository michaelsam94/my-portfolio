---
title: "Code Push with Shorebird for Flutter"
slug: "flutter-shorebird-code-push"
description: "A practical look at Shorebird code push for Flutter: how OTA patching works, what you can and can't ship, rollout controls, and the limits store rules impose."
datePublished: "2026-04-23"
dateModified: "2026-04-23"
tags: ["Flutter", "Deployment", "Mobile"]
keywords: "Shorebird, Flutter code push, over the air updates, patch Flutter, hotfix mobile, OTA Flutter"
faq:
  - q: "What is Shorebird code push for Flutter?"
    a: "Shorebird is an over-the-air update service that lets you ship Dart code changes to a released Flutter app without going through the app store review cycle. It patches the compiled Dart runtime on the device, so a bug fix that would normally take a full store submission can reach users in minutes or hours instead of days. It's built by members of the original Flutter team and works with the standard Flutter toolchain."
  - q: "Can Shorebird update anything in my app?"
    a: "No — it only patches Dart code. Changes to native code, plugins with native components, assets bundled at build time, or the Flutter engine itself require a full store release. If your fix is pure Dart (business logic, UI, a null-check bug), a patch works; if it touches the native layer, you still ship through the store."
  - q: "Is Shorebird allowed by the App Store and Play Store?"
    a: "Yes, within limits. Apple's guideline 3.3.2 permits interpreted or downloaded code as long as it doesn't change the app's primary purpose or introduce features unrelated to what was reviewed. Shorebird patches Dart, not native functionality, so it stays inside those bounds — but shipping a whole new feature set via patch is against the spirit of the rules and risky."
---

Every mobile engineer has lived this nightmare: a one-line null-check bug ships to production, and the fix is trivial, but it's stuck behind a 24–48 hour store review while crash reports pile up. Shorebird code push exists to kill that specific pain. It's an over-the-air update service for Flutter that patches the Dart code of a released app on-device, so a critical fix reaches users without a new store submission.

I've used code-push systems on the React Native side for years (CodePush, before Microsoft sunset it), and the Flutter ecosystem lacked a solid equivalent until Shorebird. Here's how it actually works, where it helps, and the boundaries you have to respect so you don't get your app pulled.

## How on-device patching works

A normal Flutter release compiles your Dart to native ARM code (AOT) and bundles it into the app. Shorebird's insight is to make that compiled Dart patchable. When you run `shorebird release`, it builds your app against a Shorebird-modified Flutter engine that knows how to load patches. When you later run `shorebird patch`, it computes the diff between your new Dart code and the released version, uploads it, and the engine applies that diff at launch.

The device checks for a patch on startup, downloads it in the background if one exists, and applies it — typically on the next launch. Users don't tap anything. The patch is scoped to a specific release version, so a patch for `1.4.0` never lands on `1.3.0`; version discipline is enforced by the tooling.

## What you can and cannot ship

This is the part people get wrong, so be blunt about it. Shorebird patches **Dart code only**. The dividing line:

| Change | Patchable via Shorebird? |
|---|---|
| Business logic / bug fix in Dart | Yes |
| UI tweaks, layout, widget changes | Yes |
| New assets added at build time | No — needs a release |
| Native plugin code (Kotlin/Swift) | No — needs a release |
| Flutter engine / SDK upgrade | No — needs a release |
| Adding a plugin dependency | No — needs a release |

If your fix is pure Dart, you patch. If it crosses into native territory, you're back to the store. In practice, a large share of production hotfixes *are* pure Dart — logic errors, off-by-one, a bad conditional, a formatting bug — so the coverage is better than the constraint list suggests.

## The actual workflow

The commands mirror your normal build steps but through the Shorebird CLI:

```bash
# Cut a release build (this is what you upload to the stores)
shorebird release android
shorebird release ios

# Later, after fixing a Dart bug on the same version:
shorebird patch android
shorebird patch ios
```

The mental model that keeps teams safe: **every store submission is a `release`; every hotfix between submissions is a `patch`.** You never patch across a release boundary. When you ship `1.5.0` to the store, that's a new release, and patches for `1.4.x` stop applying.

## Staged rollout and rollback

The feature that turns this from "scary" to "usable" is controlled rollout. You can release a patch to a percentage of users, watch your crash and metrics dashboards, and either promote it to 100% or pull it. If a patch itself is bad, you roll it back and devices revert to the last-good code on next launch.

This changes the risk calculus. A traditional store hotfix is all-or-nothing and slow; a Shorebird patch is incremental and reversible. I treat the first hour of any patch as a canary — 10% of traffic, eyes on the dashboards — before widening. That habit has caught more than one "fix" that fixed the reported bug and introduced a subtler one.

If your app already relies on background data reconciliation, code push pairs well with the patterns in [offline-first Flutter with local-first sync](https://blog.michaelsam94.com/offline-first-flutter-sync/) — you can hotfix a sync-conflict bug in Dart without forcing every user to update through the store, which for offline-heavy apps can otherwise take weeks to propagate.

## Store rules: staying on the right side

Apple's guideline 3.3.2 is the one people worry about. It permits executing downloaded or interpreted code *provided* it doesn't change the app's primary purpose, provide features unrelated to what was submitted, or circumvent App Review's intent. Shorebird patches Dart code that was already part of the reviewed app's architecture — you're fixing and adjusting behavior, not smuggling in a new app.

Where teams get in trouble is treating code push as a way to *avoid* review for genuinely new features. Don't. If you're adding a whole new screen flow or monetization path via patch, you're gambling with your account. Use it for what it's for: fixes and small adjustments to already-reviewed functionality. Google Play is generally more permissive here, but the same discipline applies.

## Where it fits in a 2026 Flutter stack

Shorebird has matured into infrastructure I'd recommend for any app with a meaningful user base and a real support burden. The value isn't shipping features faster — it's collapsing your mean-time-to-recovery for production bugs from days to minutes. When you look at the broader ecosystem trends in the [state of Flutter for 2026](https://blog.michaelsam94.com/state-of-flutter-2026/), reliable OTA patching is one of the gaps that's finally been filled properly, and it removes one of the last real advantages web deployment had over native mobile.

A couple of honest caveats. It's a paid, hosted service with a self-host-unfriendly model, so you're taking a dependency on Shorebird's infrastructure and pricing. Patch size and the modified engine add a bit of overhead. And you must keep your release/patch version hygiene tight — sloppy versioning is the fastest way to ship a patch to the wrong build. Manage those, and it's one of the higher-leverage tools you can add to a mobile release pipeline.

## Resources

- [Shorebird — official documentation](https://docs.shorebird.dev/)
- [Shorebird code push overview](https://shorebird.dev/)
- [Apple App Store Review Guidelines (3.3.2)](https://developer.apple.com/app-store/review/guidelines/)
- [Google Play — device and software requirements policy](https://support.google.com/googleplay/android-developer/answer/9888379)
- [Flutter — deployment documentation](https://docs.flutter.dev/deployment)
- [Shorebird GitHub organization](https://github.com/shorebirdtech)
