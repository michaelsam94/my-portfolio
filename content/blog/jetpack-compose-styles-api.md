---
title: "The Jetpack Compose Styles API, Explained"
slug: "jetpack-compose-styles-api"
description: "Jetpack Compose Styles API in Compose 1.11: design tokens, TextStyle and ShapeStyle reuse, MaterialTheme integration, and migration from ad-hoc styling."
datePublished: "2026-02-10"
dateModified: "2026-02-10"
tags: ["Android", "Jetpack Compose", "Design System", "UI"]
keywords: "Compose Styles API, Jetpack Compose styles, Compose 1.11, design system"
faq:
  - q: "What is the Jetpack Compose Styles API?"
    a: "The Styles API (stabilizing in Compose 1.11) provides a structured way to define, name, and reuse visual styles — typography, colors, shapes, and component-specific appearances — across composables, similar to design tokens in Figma tied to code."
  - q: "How is the Styles API different from MaterialTheme?"
    a: "MaterialTheme supplies Material Design defaults (colorScheme, typography, shapes). The Styles API lets you define custom style hierarchies and component styles beyond Material — branded buttons, cards, and text roles — and apply them consistently without passing individual parameters everywhere."
  - q: "Do I need the Styles API for a small Compose app?"
    a: "No. Small apps can rely on MaterialTheme and theme extensions. The Styles API pays off when you have a design system with named tokens, multiple brands, or frequent style updates that should not require hunting modifier chains across dozens of screens."
---

Compose teams hit the same wall around screen 40: `Text` calls with slightly different `fontSize` values, `RoundedCornerShape(12.dp)` copy-pasted with `14.dp` on another screen, and a "primary button" that looks different on checkout vs settings. **MaterialTheme** covers Material defaults; it does not solve branded component styles or design-token governance. The **Jetpack Compose Styles API** arriving in **Compose 1.11** (Compose BOM 2025.12+) addresses that gap — named, reusable styles you define once and apply like tokens.

I have migrated large XML-era design systems to Compose; the Styles API is the missing layer between `MaterialTheme` and one-off modifier chains. Here is how it works and when to adopt it.

## The problem it solves

Before Styles, teams used three patterns — all leaky:

| Pattern | Pain |
| --- | --- |
| Raw parameters on every composable | Drift, no single source of truth |
| Wrapper composables (`AppButton`) | Proliferation, hard to theme per brand |
| `CompositionLocal` for everything | Implicit, untyped, debug nightmares |

The Styles API introduces **first-class style objects** registered in a hierarchy and resolved at composition time — closer to CSS classes or SwiftUI view styles than to copying `TextStyle` instances.

## Core concepts in Compose 1.11

### Style definitions

You define styles with the `style` DSL (API names per [Compose 1.11 release notes](https://developer.android.com/jetpack/androidx/releases/compose-ui#1.11.0)):

```kotlin
// Design system module — styles/ChargePortStyles.kt
import androidx.compose.ui.styles.Style
import androidx.compose.ui.styles.style

val ChargePortStyles = Style("ChargePort") {
    textStyle("headingLarge") {
        fontSize = 28.sp
        fontWeight = FontWeight.SemiBold
        lineHeight = 36.sp
    }
    textStyle("bodyMuted") {
        fontSize = 14.sp
        color = Color(0xFF6B7280)
        lineHeight = 20.sp
    }
    shapeStyle("card") {
        shape = RoundedCornerShape(16.dp)
    }
}
```

### Applying styles

Composables that support the Styles API expose `style` parameters or use `Modifier.style()`:

```kotlin
@Composable
fun ChargerStatusCard(
    title: String,
    modifier: Modifier = Modifier,
) {
    Card(
        modifier = modifier.style(ChargePortStyles.shapeStyle("card")),
    ) {
        Text(
            text = title,
            style = ChargePortStyles.textStyle("headingLarge"),
        )
    }
}
```

The win: designers rename `headingLarge` in one file; every screen updates. No grep for `28.sp`.

### Style hierarchy and overrides

Styles compose in a parent-child tree — child styles inherit unspecified properties:

```kotlin
val BaseButtonStyle = Style("Button") {
    textStyle("label") {
        fontSize = 16.sp
        fontWeight = FontWeight.Medium
    }
}

val PrimaryButtonStyle = BaseButtonStyle.extend("PrimaryButton") {
    textStyle("label") {
        color = Color.White  // overrides only color
    }
    // fontSize 16.sp inherited
}
```

This mirrors design-token trees in Figma: `button/primary/label` extends `button/label`.

## Integration with MaterialTheme

MaterialTheme remains the foundation for Material 3 color roles and elevation. **Styles sit beside Material, not instead of it:**

```kotlin
@Composable
fun ChargePortTheme(
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = chargePortLightColors,
        typography = Typography(), // Material baseline
    ) {
        StyleProvider(ChargePortStyles) {
            content()
        }
    }
}
```

Use `MaterialTheme.colorScheme.primary` inside style definitions for theme-aware colors:

```kotlin
textStyle("link") {
    color = MaterialTheme.colorScheme.primary
}
```

Read that inside a `@Composable` context or use deferred color providers where the API requires composition-bound values.

For broader Compose architecture — state, recomposition, migration — see [Jetpack Compose lessons from 10 years in Android](https://blog.michaelsam94.com/jetpack-compose-lessons-10-years-android/).

## Component styles vs text styles

The API distinguishes:

- **TextStyle tokens** — typography roles (`titleMedium`, `caption`, `monospaceCode`)
- **ShapeStyle tokens** — corners, outlines for cards, chips, sheets
- **Component styles** (where supported) — bundled foreground, background, padding for `Button`, `TextField`

```kotlin
componentStyle("filledButton") {
    shape = RoundedCornerShape(12.dp)
    colors = ButtonColors(
        containerColor = Color(0xFF0F766E),
        contentColor = Color.White,
    )
    padding = PaddingValues(horizontal = 24.dp, vertical = 12.dp)
}
```

Prefer component styles when the design system specifies **combinations** that must not mix arbitrarily.

## Multi-brand and dynamic theming

EV and fleet apps often white-label per operator. Styles enable brand packs:

```kotlin
fun brandStyles(operatorId: String): Style = when (operatorId) {
    "op_cairo" -> CairoOperatorStyles
    "op_gulf" -> GulfOperatorStyles
    else -> DefaultChargePortStyles
}

@Composable
fun BrandedApp(operatorId: String, content: @Composable () -> Unit) {
    StyleProvider(brandStyles(operatorId)) {
        MaterialTheme(colorScheme = schemeFor(operatorId)) {
            content()
        }
    }
}
```

Swap `StyleProvider` at the root — child composables stay unchanged. This is cleaner than `if (brand == X) 14.dp else 12.dp` inside UI.

## Migration from ad-hoc styling

Incremental path I use on production migrations:

1. **Audit** — static analysis or Compose compiler reports listing unique `TextStyle` / shape literals.
2. **Tokenize top 10** — headings, body, caption, primary/secondary button, card shape.
3. **Wrap, do not rewrite** — existing `AppButton` delegates to `componentStyle("filledButton")`.
4. **Lint** — custom detekt rule blocking raw `fontSize =` outside the design system module.
5. **Screenshot tests** — one golden per style token on a reference device.

Do not big-bang migrate 200 screens. Tokenize shared components first; screens inherit on contact.

## Testing and previews

Styles are composition-local state — test with explicit providers:

```kotlin
@Preview
@Composable
private fun ChargerCardPreview() {
    StyleProvider(ChargePortStyles) {
        ChargePortTheme {
            ChargerStatusCard(title = "CP-204 online")
        }
    }
}
```

For JVM screenshot tests (Roborazzi, Paparazzi), pin `StyleProvider` in the test harness the same way you pin `MaterialTheme`.

## Performance considerations

Style resolution happens at composition; cached style objects are cheap. Avoid creating new `Style { }` blocks inside recomposition — define styles as **top-level vals**, not inside composable bodies. Same rule as `MaterialTheme.typography` — allocate once.

If you pass styles through unstable data classes, mark holders `@Immutable` to preserve skipping — the same stability discipline from large Compose codebases.

## When to wait

- Compose BOM below 2025.12 / UI below 1.11 — pin versions before adopting unstable APIs.
- No design token document — styles encode governance; without design buy-in, you recreate chaos with extra steps.
- Single-brand toy app — `MaterialTheme` extensions suffice.

## BOM setup

```kotlin
// libs.versions.toml
[versions]
composeBom = "2025.12.00"

[libraries]
compose-bom = { group = "androidx.compose", name = "compose-bom", version.ref = "composeBom" }
compose-ui = { group = "androidx.compose.ui", name = "ui" }
```

```kotlin
dependencies {
    implementation(platform(libs.compose.bom))
    implementation(libs.compose.ui)
}
```

Check [Compose UI release notes](https://developer.android.com/jetpack/androidx/releases/compose-ui) for API renames as Styles stabilizes — the concept is stable even if DSL names shift slightly across betas.

## Summary

The Compose Styles API is design tokens for Compose: named text and shape styles, hierarchies with inheritance, and brand packs via `StyleProvider`. Keep `MaterialTheme` for Material color and type baselines; use Styles for product-specific component appearance. Define tokens in one module, lint against raw literals, and migrate through shared components — not screen-by-screen parameter hunts.

## Resources

- [Compose UI 1.11 Release Notes](https://developer.android.com/jetpack/androidx/releases/compose-ui)
- [Jetpack Compose BOM Versions](https://developer.android.com/jetpack/compose/bom)
- [Material 3 in Compose](https://developer.android.com/develop/ui/compose/designsystems/material3)
- [Compose Material 3 Theming](https://m3.material.io/develop/android/jetpack-compose)
- [Android Developers — Compose Performance](https://developer.android.com/develop/ui/compose/performance)
- [Compose Compiler Metrics Guide](https://github.com/androidx/androidx/blob/androidx-main/compose/compiler/design/compiler-metrics.md)
