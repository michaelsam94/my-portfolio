---
title: "Dynamic Color and Material You Theming in Jetpack Compose"
slug: "android-dynamic-color-material3"
description: "Implement Material You dynamic color in Jetpack Compose: wallpaper-based color schemes, tonal palettes, contrast, and graceful fallbacks for pre-Android 12 devices."
datePublished: "2024-07-29"
dateModified: "2024-07-29"
tags: ["Android", "Jetpack Compose", "Material 3", "Design Systems"]
keywords: "Material You dynamic color, Compose Material 3 theming, dynamicColorScheme, tonal palette, dynamic color Android, color roles"
faq:
  - q: "How do I enable dynamic color in Jetpack Compose?"
    a: "Call dynamicLightColorScheme(context) or dynamicDarkColorScheme(context) on Android 12+ and pass the result to MaterialTheme, guarding with a build version check. On older versions, fall back to your brand color scheme. Wrap the choice in your app theme composable so every screen inherits the resolved scheme."
  - q: "What are color roles in Material 3?"
    a: "Material 3 replaces fixed colors with semantic roles like primary, onPrimary, surface, surfaceContainer, and outline, each generated from tonal palettes. You style components against roles rather than raw hex values, which is what lets dynamic color and light/dark switching work without touching component code."
  - q: "Should I always use dynamic color?"
    a: "Not always. Dynamic color strengthens system cohesion and personalization, but it can dilute a strong brand identity and makes some screens unpredictable. Many apps ship dynamic color as an opt-in or use it only on secondary surfaces while keeping brand colors on key components. Test both light and dark and multiple wallpapers before committing."
---

Material You dynamic color lets your Compose app derive its entire palette from the user's wallpaper on Android 12+, and the whole thing hinges on one idea: you stop styling components with hex values and start styling them with *semantic color roles*. Once your UI references `primary`, `surfaceContainer`, and `onSurfaceVariant` instead of `Color(0xFF6200EE)`, swapping in a wallpaper-derived scheme — or a brand scheme, or a high-contrast scheme — is a single line at the theme root. I've retrofitted this onto an app that hardcoded colors everywhere, and 90% of the work was the migration to roles; the dynamic part was almost free once that was done.

## Roles, not colors

The mental shift Material 3 asks for is the important one. In the old world you had a handful of named colors and you'd reach for them ad hoc. In M3, color is a *system* of roles generated from tonal palettes:

- **Primary / secondary / tertiary** and their `on*` pairs for content drawn on top.
- **Surface family** — `surface`, `surfaceContainerLowest` through `surfaceContainerHighest`, `surfaceVariant` — for backgrounds at different elevations.
- **Utility roles** — `outline`, `outlineVariant`, `error`, `scrim`.

Each role guarantees a legible pairing (`primary` with `onPrimary`), so if you always draw text with the matching `on*` role you get correct contrast automatically across light, dark, and dynamic schemes. The discipline: never pick a color because it "looks right," pick the role that matches the element's *meaning*.

## Wiring dynamic color into the theme

The actual dynamic color call is small. The pattern is to resolve the scheme once in your app theme and let everything inherit it:

```kotlin
@Composable
fun AppTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    dynamicColor: Boolean = true,
    content: @Composable () -> Unit,
) {
    val context = LocalContext.current
    val colorScheme = when {
        dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S ->
            if (darkTheme) dynamicDarkColorScheme(context)
            else dynamicLightColorScheme(context)
        darkTheme -> BrandDarkColors
        else -> BrandLightColors
    }
    MaterialTheme(colorScheme = colorScheme, typography = AppType, content = content)
}
```

That's the entire integration. The version guard is mandatory — `dynamicLightColorScheme` only exists on API 31+ — and the `else` branches are your hand-authored brand fallback so pre-Android 12 users still get a coherent, on-brand look.

## Build your fallback scheme properly

The fallback is where teams get lazy and it shows. On a pre-12 device your brand `ColorScheme` is the whole experience, so generate it correctly rather than filling in five colors and leaving the rest at defaults. Use the Material Theme Builder to seed a full tonal palette from your brand color; it produces every role with proper tonal steps. Paste those into `lightColorScheme(...)`/`darkColorScheme(...)`. A half-filled scheme leaks default purple into `surfaceContainerHigh` and looks broken on exactly the older devices you're trying to serve well.

## Contrast and accessibility

Dynamic color can pair a muted wallpaper hue with a light surface and produce marginal contrast. Two safeguards:

1. **Trust the `on*` roles.** Because they're generated to contrast with their base role, `onSurface` on `surface` is safe. Contrast problems almost always come from mixing roles that weren't designed to pair — `primary` text on `surfaceVariant`, say.
2. **Support the system contrast setting.** Android 14+ exposes user contrast preferences; the dynamic scheme APIs and the material color utilities can produce medium/high-contrast variants. Respect them for users who need it rather than assuming your default tones are enough.

Verify with a real contrast checker at design time, especially for `onSurfaceVariant` used on secondary text, which is the pairing most likely to sit near the 4.5:1 line.

## When *not* to go fully dynamic

Dynamic color is a personalization feature, not an unconditional good. A brand with strong equity in a specific color loses recognizability if its primary button becomes whatever the wallpaper dictates. My usual compromise:

- Keep **key brand moments** (the main CTA, logo lockups, splash) on fixed brand color.
- Let **ambient surfaces** (backgrounds, cards, nav containers) go dynamic so the app still feels woven into the system.
- Offer dynamic color as a **toggle** for users who want it, defaulting to whatever matches your brand strategy.

This is a product decision, not a technical one, and it's worth a real conversation with design rather than flipping `dynamicColor = true` and moving on.

## Testing that actually catches problems

Dynamic color multiplies your visual surface area: every screen now has *many* possible palettes. Manually eyeballing one wallpaper proves nothing. Two habits help:

- **Cycle wallpapers deliberately** — pick a vivid one, a muted one, a near-monochrome one, and a very dark one, in both light and dark mode. Bugs hide in the extremes.
- **Screenshot test the theme layer.** Rendering key screens against a few fixed seed colors with a tool like [Paparazzi](https://blog.michaelsam94.com/android-screenshot-testing-paparazzi/) catches role-mapping regressions — someone hardcoding a hex, or a component that stopped using `onSurface` — before they ship.

Because everything routes through roles, the same [design-system discipline](https://blog.michaelsam94.com/jetpack-compose-lessons-10-years-android/) that keeps a Compose codebase maintainable is what makes dynamic color trivial to add later. Roles first, dynamic color second.

## What I'd take away

Dynamic color isn't really a feature you "add" — it's the reward for theming against semantic roles instead of raw colors. Do the role migration, generate a complete brand fallback scheme with the theme builder, guard the dynamic APIs behind a version check, lean on `on*` roles for automatic contrast, respect system contrast settings, and treat "how much to go dynamic" as a branding decision. Get the roles right and you can flip between wallpaper-driven, brand, and high-contrast palettes from a single point in your theme.

## Wallpaper colors on enterprise devices

Managed devices may disable wallpaper extraction — fallback dynamic scheme must meet contrast WCAG without wallpaper. Test on devices with solid-color wallpaper and high-contrast accessibility mode simultaneously.

## Seed color for brand lock

`dynamicDarkColorScheme(context)` ignores brand when full dynamic — offer `dynamicLightColorScheme(context, primary = BrandBlue)` overload to blend brand anchor with harmonized palette.

## Dynamic Color Material3 Supplement 0 on Samsung and Pixel divergence

Exercise dynamic color material3 supplement 0 on Galaxy A-series and Pixel a-series — emulators hide OEM battery and storage quirks. Capture Macrobenchmark or Firebase trace for the critical path touching dynamic; regressions above 8% block release for `android-dynamic-color-material3-supplement-0`.

Document permission and background behavior in internal runbook: what breaks under Doze, what requires foreground service, and what Play policy declarations apply. Support tickets referencing "Dynamic Color Material3 Supplement 0" should map to a single runbook section with known workarounds.

## Material3 regression gates for Play Vitals

Before promoting `android-dynamic-color-material3-supplement-0` changes past 20% rollout, compare ANR rate, slow cold start, and excessive wakeups against seven-day baseline. Fail rollback review if 0 path shows >5% increase in `slow frames` without documented trade-off approval.

## Field testing dynamic with battery saver enabled

Xiaomi and Oppo ship aggressive background killers. After implementing dynamic color material3 supplement 0, run 24-hour monkey test on three OEM devices with battery saver enabled. Failures here predict one-star reviews that Crashlytics never captures — especially for 0 flows that assume reliable background delivery.

## Resources

- [Material 3 dynamic color](https://developer.android.com/develop/ui/compose/designsystems/material3#dynamic-color)
- [Material 3 color system](https://m3.material.io/styles/color/system/overview)
- [Material Theme Builder](https://m3.material.io/theme-builder)
- [Compose Material 3 theming guide](https://developer.android.com/develop/ui/compose/designsystems/material3)
- [Color contrast accessibility (web.dev)](https://web.dev/articles/color-and-contrast-accessibility)
