---
title: "Material 3 Theming and Dynamic Color"
slug: "flutter-theming-material3-dynamic"
description: "Material 3 ColorScheme, dynamic color from wallpaper on Android 12+, and harmonizing brand seed colors with system palettes in Flutter."
datePublished: "2025-03-23"
dateModified: "2025-03-23"
tags: ["Flutter", "Dart", "Material 3", "Mobile"]
keywords: "Material 3 Flutter, dynamic color Flutter, ColorScheme.fromSeed, M3 theming, wallpaper colors Android"
faq:
  - q: "How do I enable Material 3 in Flutter?"
    a: "Set ThemeData(useMaterial3: true)—default in recent Flutter templates. Use ColorScheme.fromSeed or dynamic ColorScheme.fromImageProvider for tonal palettes. Update components—M3 NavigationBar, Dialog, and FilledButton differ from M2."
  - q: "Does dynamic color work on iOS?"
    a: "Flutter dynamic color plugin targets Android 12+ wallpaper colors. iOS uses your defined ColorScheme unless you integrate platform-specific APIs separately. Design assuming static brand theme on iOS unless product specifies otherwise."
  - q: "What is a seed color vs primary color in M3?"
    a: "Seed color feeds the algorithm generating primary, secondary, tertiary, containers, and surfaces. You pick seed; Material tonal palette derives harmonious roles—reduces hand-picking twelve hex values."
---

Users enabled wallpaper-based theming on Android and our app stayed corporate blue while Gmail breathed with their photo. One `dynamic_color` integration later, surfaces picked up harmonized tones without abandoning our seed brand color on iOS where dynamic color is not available.

Material 3 in Flutter centers on `ColorScheme` roles—primary, onPrimary, surfaceContainer, errorContainer—and optional dynamic color from the OS.

## Static M3 theme from seed

```dart
ThemeData buildTheme(Brightness brightness) {
  final scheme = ColorScheme.fromSeed(
    seedColor: const Color(0xFF6750A4),
    brightness: brightness,
  );

  return ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    textTheme: Typography.material2021(platform: TargetPlatform.android)
        .black
        .apply(bodyColor: scheme.onSurface, displayColor: scheme.onSurface),
  );
}

MaterialApp(
  theme: buildTheme(Brightness.light),
  darkTheme: buildTheme(Brightness.dark),
  themeMode: ThemeMode.system,
  ...
);
```

Use `surfaceContainer*` roles for elevated cards in M3—not raw `Colors.grey[200]`.

## Dynamic color on Android

```yaml
dependencies:
  dynamic_color: ^1.7.0
```

```dart
class MyApp extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return DynamicColorBuilder(
      builder: (lightDynamic, darkDynamic) {
        final lightScheme = lightDynamic ?? ColorScheme.fromSeed(
          seedColor: const Color(0xFF6750A4),
        );
        final darkScheme = darkDynamic ?? ColorScheme.fromSeed(
          seedColor: const Color(0xFF6750A4),
          brightness: Brightness.dark,
        );

        return MaterialApp(
          theme: ThemeData(colorScheme: lightScheme, useMaterial3: true),
          darkTheme: ThemeData(colorScheme: darkScheme, useMaterial3: true),
          home: const HomeScreen(),
        );
      },
    );
  }
}
```

Fallback seed when dynamic palette unavailable—older Android, iOS, web.

## Component updates for M3

Replace deprecated widgets:

- `BottomNavigationBar` → `NavigationBar` or `NavigationRail`
- `ElevatedButton` for primary actions → often `FilledButton`
- Dialog shapes and default padding changed—re-test overflow

```dart
NavigationBar(
  selectedIndex: index,
  onDestinationSelected: onSelect,
  destinations: const [
    NavigationDestination(icon: Icon(Icons.home), label: 'Home'),
  ],
)
```

## Typography and shape

M3 typography uses updated type scale—wire through `TextTheme` from `ThemeData.textTheme`. Corner radii default larger; override `CardTheme`, `FilledButtonTheme` if brand guidelines require sharp corners.

## Contrast and accessibility

Dynamic palettes can produce low-contrast pairs on busy wallpapers. Validate with contrast checker:

```dart
// debug: print contrast ratios for onSurface vs surface
```

Offer in-app toggle to use brand static theme if enterprise policy disables personalization.

## Harmonized custom colors

`ColorScheme.fromImageProvider` generates scheme from brand hero image—useful for media apps:

```dart
final scheme = await ColorScheme.fromImageProvider(
  provider: const AssetImage('assets/brand_hero.png'),
);
```

## Testing both schemes

Widget tests pump light and dark:

```dart
await tester.pumpWidget(
  MaterialApp(
    theme: buildTheme(Brightness.light),
    darkTheme: buildTheme(Brightness.dark),
    themeMode: ThemeMode.dark,
    home: const HomeScreen(),
  ),
);
```

Golden tests per brightness catch regressions.

## Brand vs dynamic tension

Enterprise brand may forbid wallpaper-driven primary—disable dynamic color:

```dart
final scheme = ColorScheme.fromSeed(seedColor: brandSeed, brightness: brightness);
```

Offer user toggle **Use system colors** in settings wired to DynamicColorBuilder vs static theme.

## Surface tone contrast

M3 surfaces use tonal elevation—cards on `surfaceContainerLow` vs `surface`. Audit contrast for body text on each surface role in both light and dark.

## Component theme overrides

```dart
ThemeData(
  colorScheme: scheme,
  filledButtonTheme: FilledButtonThemeData(
    style: FilledButton.styleFrom(minimumSize: Size(88, 48)),
  ),
)
```

Centralize component tweaks—avoid hardcoded colors in feature widgets.


## Elevation and surface containers

Material 3 replaces elevation shadows with tonal surface steps—migrate cards from `elevation: 4` to `color: scheme.surfaceContainerHighest` for hierarchy. Audit dark mode: pure black shadows invisible; tonal difference carries depth.

## Fixed brand elements

Logos and campaign artwork may require fixed colors outside dynamic scheme—define `BrandColors` ThemeExtension for immovable assets while surfaces adapt to wallpaper.

## QA matrix

Test themes: light static, dark static, light dynamic, dark dynamic, large font, RTL layout. Screenshot diff top ten screens on each combination before major release—dynamic color regressions slip through manual QA.

## Web and desktop

Dynamic color from Android wallpaper does not apply on Flutter web—use static seed. Desktop macOS accent color future integration may arrive—abstract theme builder behind `AppThemeFactory` interface to swap sources per platform.

## Typography scale adjustments

After applying dynamic color, re-check headline styles on surface containers—sometimes automatic onSurface variant low contrast on certain wallpaper seeds; override textTheme for displayLarge if audit fails WCAG AA.

## Rollout guidance

Dynamic color user setting default off enterprise white label builds—consumer app default on A/B test conversion onboarding completion rate metric decides default policy data driven.

## Team practices

Shipping Flutter Theming Material3 Dynamic in production taught our team that documentation beats hero demos. We wrote runbooks covering failure modes, on-call steps, and rollback triggers before the second release, not after the first outage.

When reviewing PRs touching Flutter Theming Material3 Dynamic, we ask for measurable outcomes: latency, crash rate, or support ticket volume—not subjective feels faster. If metrics are unavailable, the PR includes a DevTools trace or load test snippet proving the change.

Onboarding engineers paste a checklist into their first Flutter Theming Material3 Dynamic PR description: environment setup verified, tests added or updated, accessibility spot-checked, and release notes drafted for user-visible changes.

We keep a living FAQ in the repo wiki for Flutter Theming Material3 Dynamic questions repeated in Slack more than twice. FAQ entries link to source files and Slack threads, reducing tribal knowledge and repeated explanations in code review.

Cross-functional review includes design for UX-facing work, security for auth or storage, and platform for native bridges. Flutter Theming Material3 Dynamic spans layers; skipping reviewers recreated bugs we fixed months ago.

Staging soaks 24 hours for risky changes while dashboards watch error rates.canary cohorts internal staff first, then five percent production, then full rollout if crash-free sessions hold within baseline tolerance.

## Resources

- [Material 3 for Flutter](https://docs.flutter.dev/ui/design/material)
- [dynamic_color package](https://pub.dev/packages/dynamic_color)
- [ColorScheme class](https://api.flutter.dev/flutter/material/ColorScheme-class.html)
- [Material Design 3 color system](https://m3.material.io/styles/color/system)
- [Use Material 3 migration guide](https://docs.flutter.dev/release/breaking-changes/material-3-migration)
