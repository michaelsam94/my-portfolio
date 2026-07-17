---
title: "Android 16's Adaptive Apps Mandate: What Actually Changes"
slug: "android-16-adaptive-apps-mandate"
description: "Android 16 ignores orientation and resize restrictions on large screens. What the adaptive apps mandate means, who it affects, and how to prepare your app."
datePublished: "2024-09-15"
dateModified: "2024-09-15"
tags: ["Android", "Adaptive UI", "Foldables", "Architecture"]
keywords: "Android 16 adaptive apps, orientation lock ignored, resizableActivity, large screen mandate, foldables, android:screenOrientation"
faq:
  - q: "What is the Android 16 adaptive apps mandate?"
    a: "On large-screen devices, Android 16 ignores app-declared orientation, resizability, and aspect-ratio restrictions for apps targeting the new SDK. That means android:screenOrientation locks and resizeableActivity=false no longer prevent your app from being rotated or resized on screens above a certain width, so your UI must handle any size and orientation."
  - q: "Does the Android 16 orientation change affect phones?"
    a: "No. The mandate applies to large screens — displays at or above roughly 600dp in the smallest width, meaning tablets, foldables in their unfolded state, and desktop windowing. On standard phones your orientation and resize declarations are still respected, so a portrait-only phone game is unaffected."
  - q: "How do I prepare my app for the adaptive apps requirement?"
    a: "Stop relying on orientation locks and fixed aspect ratios for layout correctness. Drive layout from window size classes, preserve state across configuration changes with rememberSaveable and SavedStateHandle, and test in resizable emulators and split-screen. Treat every screen as something that can appear at any size at any time."
---

Android 16 changes a rule that a lot of apps quietly depended on: on large-screen devices, the system now *ignores* your app's orientation, resizability, and aspect-ratio restrictions. If you target the new SDK level, `android:screenOrientation="portrait"` and `resizeableActivity="false"` stop having their old protective effect on tablets, unfolded foldables, and desktop windowing. The device will rotate and resize your app whether you declared you support it or not. This is the "adaptive apps mandate," and the practical takeaway is blunt: on big screens, you no longer get to opt out of being resizable.

I've spent the last several release cycles helping teams unwind orientation locks, and the ones panicking are the ones who used those locks as a *layout crutch* rather than a genuine product decision. Let me separate the real work from the noise.

## What actually changed, precisely

The mandate is scoped to **large screens** — displays whose smallest width is roughly 600dp or more. That's tablets, foldables when unfolded, ChromeOS, and desktop-mode windows. On a normal phone, nothing changes: a portrait-only phone game stays portrait-only. But on the big devices, for apps targeting the relevant SDK:

- `android:screenOrientation` restrictions are ignored — the app can be rotated freely.
- `resizeableActivity="false"` is ignored — the app can be resized, including split-screen and free-form windows.
- Fixed aspect-ratio (`maxAspectRatio`) constraints are ignored — the app fills whatever window it's given.

The system is essentially saying: on a device large enough that these restrictions hurt the user, the user's control wins over the developer's lock.

## Why Google is forcing this

Large screens have been a second-class experience for years precisely *because* apps lock orientation and refuse to resize. You unfold a foldable expecting a tablet layout and get a stretched phone UI frozen in portrait. Google tried encouragement (large-screen guidelines, quality tiers) and it didn't move the needle enough, so this is the enforcement step. The bet is that removing the escape hatch on big screens pushes the ecosystem toward genuinely adaptive UI — the kind that treats window size as an input, not an exception.

If you've already built [adaptive layouts driven by window size classes](https://blog.michaelsam94.com/adaptive-layouts-compose-grid-flexbox/), this mandate is a non-event. The apps in trouble are the ones that hardcoded portrait and never handled a wide window.

## The two failure modes you must fix

There are really only two ways an app breaks under this change, and both are fixable without a rewrite.

**1. Layout that assumes portrait.** UI that hardcodes a narrow, tall arrangement looks broken stretched across a landscape tablet. The fix isn't to fight the resize — it's to branch layout on window size class so a wide window gets a wide layout (two panes, a list-detail split) instead of a stretched single column.

**2. State lost on configuration change.** A rotation or resize is a configuration change, and an activity that doesn't preserve state recreates and loses the user's place. If you locked orientation partly to *avoid* dealing with recreation, that shortcut is gone. You now must survive recreation properly.

## Surviving recreation is the real homework

The orientation lock let sloppy state handling hide. Remove it and every unsaved bit of UI state becomes a visible bug on rotate. The fixes are well-established:

- **`rememberSaveable`** for transient UI state in Compose — scroll positions, expanded/collapsed, text field contents — so it round-trips through the saved instance state bundle.
- **`SavedStateHandle`** in your ViewModel for state that must survive not just rotation but process death. This is the same discipline covered in [surviving process death with SavedStateHandle](https://blog.michaelsam94.com/android-savedstatehandle-process-death/) — the mandate just makes it non-optional on large screens.
- **Don't cache Activity-scoped things that a resize invalidates**, like a `Configuration`-derived dimension captured once.

If your app already handles rotation cleanly on a phone, resize on a tablet is the same machinery at a different size.

## A preparation checklist

Here's the sequence I run teams through:

1. **Audit the manifest.** Find every `screenOrientation`, `resizeableActivity="false"`, and `maxAspectRatio`. For each, ask: was this a real product need or a layout crutch? Keep only genuine needs (and know they won't be honored on large screens anyway).
2. **Drive layout from `WindowSizeClass`.** Replace any implicit portrait assumption with explicit compact/medium/expanded branches.
3. **Test in a resizable emulator.** Use the resizable (foldable) emulator and drag the window through sizes. Rotate. Split-screen. Fold and unfold.
4. **Verify state across every config change.** Type into a field, rotate, confirm it survives. Scroll a list, resize, confirm the position holds.
5. **Check touch targets and insets at the new sizes.** Edge-to-edge behavior and cutouts differ across form factors.

## What you don't have to do

A few things teams over-worry about. You don't have to support *phones* in landscape if landscape genuinely doesn't make sense for your product — the mandate is large-screen only, so a portrait phone game is fine. You don't have to build a bespoke tablet UI overnight; a competent responsive layout that reflows is enough to pass and to be usable. And you don't have to abandon orientation preferences entirely — you can still *request* an orientation, it just won't be *enforced* on large screens.

| Concern | Reality under the mandate |
| --- | --- |
| Phone portrait lock | Still respected |
| Tablet/foldable orientation lock | Ignored |
| `resizeableActivity=false` on large screen | Ignored |
| Need a separate tablet app | No — one adaptive app |
| State loss on resize | Your responsibility to fix |

## What I'd take away

Android 16's adaptive apps mandate removes the ability to lock orientation and resizing on large screens, and it does so to end the era of stretched phone UIs on tablets and foldables. If your app is already adaptive — layout branched on window size class, state preserved with `rememberSaveable` and `SavedStateHandle` — you're done. If it leaned on orientation locks as a layout crutch, the work is to make layout a function of window size and to survive configuration changes cleanly. Audit the manifest, test in a resizable emulator, and verify state across every rotate and resize. The mandate isn't asking for a rewrite; it's asking you to stop pretending the window can't change size.

## Tablet layout rejection criteria

Android 16 adaptive mandate requires resizable activities — locked portrait without resizeMode exception risks visibility downgrade on large screens. Test `WindowSizeClass.COMPACT` vs EXPANDED with same navigation graph.

## Fixed orientation exceptions

Games and camera may qualify — document in Play Console declaration. Banking apps often do not qualify; implement list-detail scaffolds instead of seeking exception.

## 16 Adaptive Apps Mandate Supplement 0 on Samsung and Pixel divergence

Exercise 16 adaptive apps mandate supplement 0 on Galaxy A-series and Pixel a-series — emulators hide OEM battery and storage quirks. Capture Macrobenchmark or Firebase trace for the critical path touching 16; regressions above 8% block release for `android-16-adaptive-apps-mandate-supplement-0`.

Document permission and background behavior in internal runbook: what breaks under Doze, what requires foreground service, and what Play policy declarations apply. Support tickets referencing "16 Adaptive Apps Mandate Supplement 0" should map to a single runbook section with known workarounds.

## Mandate regression gates for Play Vitals

Before promoting `android-16-adaptive-apps-mandate-supplement-0` changes past 20% rollout, compare ANR rate, slow cold start, and excessive wakeups against seven-day baseline. Fail rollback review if 0 path shows >5% increase in `slow frames` without documented trade-off approval.

## Resources

- [Large screen app quality (Android developers)](https://developer.android.com/develop/ui/compose/layouts/adaptive)
- [Make apps adaptive / device compatibility modes](https://developer.android.com/guide/practices/device-compatibility-mode)
- [Support different screen sizes](https://developer.android.com/develop/ui/compose/layouts/adaptive/support-different-screen-sizes)
- [Configuration changes](https://developer.android.com/guide/topics/resources/runtime-changes)
- [Window size classes](https://developer.android.com/develop/ui/compose/layouts/adaptive/use-window-size-classes)
