---
title: "MultiPreview Annotations for Faster Compose UI Work"
slug: "compose-preview-tooling-multipreview"
description: "Speed up Compose UI iteration with MultiPreview annotations: custom @Preview groups for themes, locales, font scales, and screen sizes in one shot."
datePublished: "2024-09-13"
dateModified: "2024-09-13"
tags: ["Android", "Jetpack Compose", "Tooling", "UI"]
keywords: "Compose MultiPreview, Preview annotation, custom preview annotation, PreviewParameter, Compose preview groups, font scale preview"
faq:
  - q: "What is a MultiPreview annotation in Jetpack Compose?"
    a: "A MultiPreview annotation is a custom annotation you define that is itself annotated with several @Preview annotations. Applying your single annotation to a composable renders all of those previews at once — for example light and dark themes, multiple font scales, and several locales — so you see every important variation without repeating @Preview declarations on every composable."
  - q: "How do I preview light and dark themes together in Compose?"
    a: "Create a custom annotation annotated with two @Preview entries, one with uiMode set to UI_MODE_NIGHT_NO and one with UI_MODE_NIGHT_YES, both wrapped in your app theme. Apply that one annotation to any composable and the preview pane shows both themes side by side, keeping theme coverage consistent across the codebase."
  - q: "What is PreviewParameter used for in Compose previews?"
    a: "PreviewParameter feeds a range of sample data into a preview so you can see how a composable renders with different inputs — empty state, long text, error state — from one preview function. You supply a PreviewParameterProvider that yields the values, and the tooling renders one preview per value, which is ideal for catching layout issues with edge-case data."
---

The single highest-leverage tooling habit in Compose is defining your own MultiPreview annotations. Instead of pasting five `@Preview` blocks — light, dark, large font, small screen, RTL locale — onto every composable, you define one custom annotation *once* that bundles all those variations, then apply that single annotation everywhere. Change the bundle in one place and every screen's preview set updates. It's a small feature that quietly fixes the biggest weakness of previews: people don't check the variations that matter because declaring them is tedious.

I've made this the default on every Compose project I've led, and the payoff is that theme, locale, and accessibility regressions get caught at design time in the preview pane instead of in QA.

## The problem MultiPreview solves

A `@Preview` renders one configuration. To see your card in dark mode you add a second `@Preview` with `uiMode = UI_MODE_NIGHT_YES`. To check large-font accessibility, a third with `fontScale = 1.5f`. To check a small device, a fourth with a device spec. That's four annotations, copied onto every composable you care about — and inevitably people copy three of the four, or none, and dark-mode bugs slip through.

MultiPreview inverts it. Because a `@Preview` can annotate *another annotation*, you build a named bundle:

```kotlin
@Preview(name = "Light", uiMode = UI_MODE_NIGHT_NO, showBackground = true)
@Preview(name = "Dark", uiMode = UI_MODE_NIGHT_YES, showBackground = true)
annotation class ThemePreviews
```

Now one line covers both themes:

```kotlin
@ThemePreviews
@Composable
private fun GreetingPreview() {
    AppTheme { Greeting(name = "Sam") }
}
```

Add a third `@Preview` to `ThemePreviews` — say a high-contrast theme — and every composable using it instantly gains that preview. That's the leverage.

## The bundles I define on every project

I standardize on a small set of MultiPreview annotations that encode the variations the team actually cares about:

```kotlin
@Preview(name = "Light", uiMode = UI_MODE_NIGHT_NO)
@Preview(name = "Dark", uiMode = UI_MODE_NIGHT_YES)
annotation class ThemePreviews

@Preview(name = "85%", fontScale = 0.85f)
@Preview(name = "100%", fontScale = 1.0f)
@Preview(name = "150%", fontScale = 1.5f)
@Preview(name = "200%", fontScale = 2.0f)
annotation class FontScalePreviews

@Preview(name = "Phone", device = Devices.PHONE)
@Preview(name = "Foldable", device = Devices.FOLDABLE)
@Preview(name = "Tablet", device = Devices.TABLET)
annotation class DevicePreviews
```

The font-scale bundle earns its keep constantly — a layout that looks fine at 100% often clips or truncates at 200%, which is a real accessibility requirement, not a nicety. Seeing all four scales at once means you fix it before it ships. The device bundle pairs naturally with building [adaptive layouts](https://blog.michaelsam94.com/adaptive-layouts-compose-grid-flexbox/): you're validating your window-size-class branches visually in one glance.

## Stacking annotations

MultiPreview annotations compose — you can apply several and get the cross-product where it makes sense, or apply the one that matters for a given component:

```kotlin
@ThemePreviews
@FontScalePreviews
@Composable
private fun ButtonPreview() {
    AppTheme { PrimaryButton(text = "Continue", onClick = {}) }
}
```

Be a little careful stacking too many — the preview pane has to render every combination, and a `ThemePreviews` × `FontScalePreviews` × `DevicePreviews` cross-product is a lot of renders that slows the pane. In practice I apply `ThemePreviews` broadly, `FontScalePreviews` to text-heavy components, and `DevicePreviews` to full screens rather than leaf components.

## PreviewParameter for data variations

Configuration is one axis; *data* is the other. A list row needs to be checked with a short title, a wrapping long title, a missing image, an error badge. Rather than write a preview per case, feed sample data with `@PreviewParameter`:

```kotlin
class UserPreviewProvider : PreviewParameterProvider<User> {
    override val values = sequenceOf(
        User(name = "Sam", verified = true),
        User(name = "A very long display name that will wrap", verified = false),
        User(name = "", verified = false),   // empty edge case
    )
}

@ThemePreviews
@Composable
private fun UserRowPreview(
    @PreviewParameter(UserPreviewProvider::class) user: User,
) {
    AppTheme { UserRow(user) }
}
```

The tooling renders one preview per value — and because it's combined with `@ThemePreviews`, you get each data case in both themes. This is the fastest way I know to catch "looks great with the demo data, breaks with real data" bugs before they reach a device.

## Keep previews cheap and hermetic

Previews render in the IDE without a real app, so anything that needs runtime — a live ViewModel, a repository, network — won't work and slows or breaks the pane. Two habits keep previews fast and reliable:

- **Preview the stateless composable, not the stateful screen.** Hoist state so your leaf composables take plain parameters; feed them fake data in the preview. The `MyScreen(state, onEvent)` shape previews trivially, while `MyScreen(viewModel)` does not.
- **Provide fakes, never DI graphs.** If a preview needs a dependency, hand it a hardcoded fake in the preview function. Previews should have zero knowledge of Hilt or your real data layer.

This is the same stateless-first discipline that makes composables testable in general; previews are just another consumer of well-hoisted state.

## What I'd take away

Define MultiPreview annotations once and the whole team gets consistent, thorough coverage for free. Standardize a `ThemePreviews` for light/dark, a `FontScalePreviews` for accessibility, and a `DevicePreviews` for form factors, then apply them by relevance rather than stacking everything everywhere. Use `@PreviewParameter` to sweep edge-case data — empty, long, error — through those same configurations. And keep previews hermetic by previewing hoisted, stateless composables with fake data. The result is that theme, font-scale, and data-shape regressions surface in the preview pane during development, which is by far the cheapest place to fix them.

## Resources

- [Preview your UI with composable previews](https://developer.android.com/develop/ui/compose/tooling/previews)
- [Multipreview annotations](https://developer.android.com/develop/ui/compose/tooling/previews#multipreview)
- [Preview parameters](https://developer.android.com/develop/ui/compose/tooling/previews#preview-data)
- [Compose tooling overview](https://developer.android.com/develop/ui/compose/tooling)
