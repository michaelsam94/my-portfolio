---
title: "Adaptive and Monochrome App Icons on Android"
slug: "android-adaptive-icons-monochrome"
description: "How Android adaptive icons and the monochrome layer work: foreground/background layers, the safe zone, themed icons, and shipping an icon that looks right everywhere."
datePublished: "2024-09-29"
dateModified: "2024-09-29"
tags: ["Android", "App Icons", "Material Design", "UI"]
keywords: "Android adaptive icon, monochrome icon, themed icons Android, adaptive icon safe zone, ic_launcher foreground background"
faq:
  - q: "What is a monochrome layer in an Android adaptive icon?"
    a: "The monochrome layer is a single-color version of your icon that Android uses to render themed icons, where the launcher tints the icon to match the user's wallpaper and system theme. You add it as a <monochrome> element alongside the foreground and background in the adaptive icon XML. If you omit it, your app's icon simply won't participate in themed icons and will look inconsistent next to apps that do."
  - q: "Why does my adaptive icon get cropped?"
    a: "Adaptive icons are 108dp with only the central 66dp guaranteed visible — the outer ring is masked by device-specific shapes and used for parallax and motion. If key content sits outside that safe zone it gets clipped on round or squircle masks. Keep the logo within the central safe area and treat the edges as bleed, not content."
  - q: "Do I still need legacy icon assets?"
    a: "For modern minimum SDK levels you primarily ship the adaptive icon plus the monochrome layer, but you should still provide a legacy fallback bitmap for very old launchers and contexts that don't support adaptive icons. Android generates most density variants from the adaptive vector layers, so the maintenance burden is small. Provide the round icon resource too if your launcher targets expect it."
---

Android app icons stopped being "a PNG at five densities" years ago, and every so often I still see an app ship a logo that gets its edges chopped off on a Pixel or shows up as a flat gray blob when the user turns on themed icons. Adaptive icons — and now the **monochrome layer** that powers themed icons — are the reason. They're not complicated, but they have a specific geometry and a specific set of layers, and getting them right is the difference between an icon that looks intentional on every device and one that looks broken on half of them.

## The layer model: foreground, background, monochrome

An adaptive icon isn't one image. It's a set of layers the system composites and masks:

- **Background** — a full-bleed layer, often a solid color or subtle gradient. The launcher masks it into the device's icon shape (circle, squircle, rounded square).
- **Foreground** — your logo, drawn on top, also 108dp but with the logo confined to a safe zone (more on that below).
- **Monochrome** — a single-color silhouette of your icon that the system tints for **themed icons**.

You declare them in `res/mipmap-anydpi-v26/ic_launcher.xml`:

```xml
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@color/ic_launcher_background" />
    <foreground android:drawable="@drawable/ic_launcher_foreground" />
    <monochrome android:drawable="@drawable/ic_launcher_monochrome" />
</adaptive-icon>
```

Splitting the icon into layers is what lets the launcher do the things that make modern home screens feel alive: apply device-specific masks, animate parallax as you scroll, and — with the monochrome layer — recolor your icon to match the system theme.

## The safe zone is not optional

The single most common mistake: designing to the full 108dp canvas. Only the **central 66dp** is guaranteed visible. The outer ring exists for two reasons — device shape masks eat into it differently (a round mask clips more corner than a squircle), and the launcher uses that margin for parallax and pull-to-refresh motion. Anything important outside the central circle *will* get clipped somewhere.

Practically:

- Center the logo and keep it within the inner ~66dp.
- Treat the outer area as bleed — background color extends there, but no content you care about.
- Test against multiple mask shapes, not just your device's. A logo that looks fine on a squircle can lose a corner on a circle.

I've watched a brand's wordmark get its last letter shaved off on round-mask devices because it filled the canvas. The fix was thirty seconds of scaling down into the safe zone — but only after a user complained.

## The monochrome layer and themed icons

Themed icons let users tint every icon on the home screen to match their wallpaper and system color scheme. The system produces this by taking your **monochrome** layer, discarding its color, and applying the theme's tint. If you don't provide a monochrome layer, your icon opts out — it stays full-color while everything around it is themed, which looks like an oversight to users who enabled the feature.

Designing the monochrome layer is its own small craft:

1. **It's a silhouette, not a grayscale copy.** Provide flat, solid shapes; the system supplies the color. Gradients and multi-tone details flatten badly.
2. **Respect the safe zone again** — same 66dp constraint.
3. **Keep it legible as a single color.** Fine detail and thin strokes vanish when tinted; simplify to the recognizable core of your mark.
4. **Test it tinted, both light and dark.** What reads at full color can turn into an ambiguous blob in monochrome.

A good monochrome layer is usually a simplified version of your foreground — the essential shape, no color, generous strokes.

## Shipping checklist

| Asset | Purpose | Notes |
| --- | --- | --- |
| `ic_launcher.xml` (adaptive) | Modern launchers | Foreground + background + monochrome |
| `ic_launcher_foreground` | Your logo | Confined to 66dp safe zone |
| `ic_launcher_background` | Full-bleed backdrop | Color or simple vector |
| `ic_launcher_monochrome` | Themed icons | Single-color silhouette |
| Legacy bitmap fallback | Old launchers/contexts | Static PNG |
| `ic_launcher_round` | Round-icon launchers | If targeted |

Prefer **vector drawables** for the foreground and monochrome layers. Android generates density variants from the vectors, so you maintain one source of truth instead of exporting a matrix of PNGs — the same "decide once, let the system adapt" instinct behind [adaptive layouts in Compose](https://blog.michaelsam94.com/adaptive-layouts-compose-grid-flexbox/).

## A workflow that avoids surprises

The way I set icons up now, to catch problems before users do:

- Design foreground and monochrome as vectors on a 108dp artboard with the 66dp safe circle marked.
- Use Android Studio's Image Asset tooling to scaffold the adaptive icon and preview it against multiple masks.
- Explicitly toggle the themed-icon preview and check the monochrome layer tinted in both light and dark.
- Test on a real device with a colorful wallpaper and themed icons on — the emulator is fine but nothing beats seeing it tinted on a home screen.

The whole thing takes an afternoon once and then rarely changes. What it buys is an icon that looks deliberate on every launcher shape and participates cleanly when users theme their home screen — instead of the flat gray silhouette that quietly signals "this app didn't bother."

## What I'd take away

Modern Android icons are layered: a masked background, a foreground logo confined to the central 66dp safe zone, and a monochrome silhouette that powers themed icons. Design to the safe zone or lose your edges to device masks; ship a monochrome layer or opt out of theming and look inconsistent. Use vectors so Android generates the density variants for you, keep a legacy fallback for old contexts, and always preview against multiple mask shapes and the tinted themed-icon mode. Do that and your icon reads correctly everywhere — which is the entire point of the adaptive system.

## Themed icon API 33+

Monochrome layer must be single-color silhouette — gradients break on Pixel launcher themed icons. Provide `@drawable/ic_launcher_monochrome` separate from full-color adaptive layers; verify on Android 13 QPR themed icon setting.

## OEM launcher variance

Samsung OneUI may ignore monochrome — ship legacy icon fallback in manifest for pre-13 and test on top three OEM launchers in pre-launch report.

## Adaptive Icons Monochrome Supplement 0 on Samsung and Pixel divergence

Exercise adaptive icons monochrome supplement 0 on Galaxy A-series and Pixel a-series — emulators hide OEM battery and storage quirks. Capture Macrobenchmark or Firebase trace for the critical path touching adaptive; regressions above 8% block release for `android-adaptive-icons-monochrome-supplement-0`.

Document permission and background behavior in internal runbook: what breaks under Doze, what requires foreground service, and what Play policy declarations apply. Support tickets referencing "Adaptive Icons Monochrome Supplement 0" should map to a single runbook section with known workarounds.

## Monochrome regression gates for Play Vitals

Before promoting `android-adaptive-icons-monochrome-supplement-0` changes past 20% rollout, compare ANR rate, slow cold start, and excessive wakeups against seven-day baseline. Fail rollback review if 0 path shows >5% increase in `slow frames` without documented trade-off approval.

## Field testing adaptive with battery saver enabled

Xiaomi and Oppo ship aggressive background killers. After implementing adaptive icons monochrome supplement 0, run 24-hour monkey test on three OEM devices with battery saver enabled. Failures here predict one-star reviews that Crashlytics never captures — especially for 0 flows that assume reliable background delivery.

## Resources

- [Android — Create app icons (adaptive icons)](https://developer.android.com/develop/ui/views/launch/icon_design_adaptive)
- [Adaptive icons reference](https://developer.android.com/develop/ui/views/launch/icon_design_adaptive#design-adaptive-icons)
- [Material Design — Product icons](https://m3.material.io/styles/icons/overview)
- [Vector drawables overview](https://developer.android.com/develop/ui/views/graphics/vector-drawable-resources)
