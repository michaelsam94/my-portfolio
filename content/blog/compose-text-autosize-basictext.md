---
title: "Auto-Sizing Text and the New BasicText APIs"
slug: "compose-text-autosize-basictext"
description: "Compose autosize text: how TextAutoSize and the new BasicText APIs fit text to its container, handle font scaling, and replace fragile manual measurement."
datePublished: "2026-04-14"
dateModified: "2026-04-14"
tags: ["Android", "Jetpack Compose", "UX"]
keywords: "Compose autosize text, BasicText, TextAutoSize, font scaling Compose, responsive text Compose"
faq:
  - q: "What is autosize text in Jetpack Compose?"
    a: "Autosize text in Jetpack Compose automatically scales a text's font size so it fits within the space its container gives it, instead of overflowing or truncating. You configure it through the TextAutoSize parameter on BasicText, giving a minimum, maximum, and step granularity, and Compose measures and picks the largest font size that fits. It replaces the manual measure-and-remeasure loops people used to write by hand."
  - q: "How is BasicText different from Text in Compose?"
    a: "BasicText is the low-level, unstyled foundation composable that Text is built on top of. Text applies your MaterialTheme typography and colors, while BasicText gives you direct control with no theme defaults. The autosize APIs landed on BasicText first because it's the primitive, so when you need autosizing you either use BasicText directly or a Text overload that forwards the autoSize parameter."
  - q: "Does autosize text respect the user's font scale setting?"
    a: "Yes, and that's the point of doing it properly. Autosizing works in scalable pixels (sp) and composes with the system font-scale accessibility setting rather than fighting it. A user who bumps their font size still gets the largest size that fits your container, so you keep layouts intact without hard-capping text in a way that breaks accessibility."
---

Text that has to fit a box it doesn't control is one of the oldest UI headaches: a headline that's perfect in English blows out in German, a countdown that reads "9" fine but clips at "10:00", a card title translated into a language with longer words. Compose's autosize text — configured through `TextAutoSize` on `BasicText` — solves this by letting the framework measure the available space and pick the largest font size that fits, down to a floor you set. No manual measurement, no `onTextLayout` callbacks recomputing sizes on every recomposition.

I remember the View-days version of this: `TextView`'s autosize attributes, which worked but were opaque and hard to reason about. The Compose version is more explicit and, crucially, plays nicely with the rest of the layout system. Here's how it works and where it genuinely earns its place.

## Why manual approaches were fragile

Before the built-in support, the pattern was grim. You'd render text, capture the layout result, check `didOverflowWidth` or `didOverflowHeight`, shrink the font size in state, and recompose — hoping to converge without an infinite loop:

```kotlin
// The old, fragile pattern — don't do this anymore
var fontSize by remember { mutableStateOf(24.sp) }
var ready by remember { mutableStateOf(false) }

Text(
    text = title,
    fontSize = fontSize,
    maxLines = 1,
    softWrap = false,
    onTextLayout = { result ->
        if (result.didOverflowWidth && fontSize > 12.sp) {
            fontSize *= 0.9f          // shrink and try again next frame
        } else {
            ready = true
        }
    },
    modifier = Modifier.drawWithContent { if (ready) drawContent() }
)
```

That code has three problems: it flickers while it converges over multiple frames, it's easy to loop if your bounds are ever ambiguous, and it fights recomposition because you're mutating layout-driving state from a layout callback. I've debugged the "text jitters on rotation" bug that this pattern causes more than once. The built-in autosize does the measurement inside a single layout pass — no extra frames, no state ping-pong.

## The new API in one call

The whole thing collapses to a parameter. You give it a range and a granularity, and Compose does the search:

```kotlin
BasicText(
    text = title,
    style = MaterialTheme.typography.headlineMedium,
    maxLines = 1,
    autoSize = TextAutoSize.StepBased(
        minFontSize = 12.sp,
        maxFontSize = 32.sp,
        stepSize = 1.sp
    )
)
```

`StepBased` tries sizes from `maxFontSize` downward in `stepSize` increments and keeps the largest that fits the constraints and `maxLines`. A couple of details matter in practice:

- **Keep the range sane.** A `minFontSize` of 12.sp and `maxFontSize` of 32.sp is a 20-point spread; that's usually plenty. A huge range with a tiny `stepSize` means more candidate measurements, which isn't free in a list.
- **Constrain the axis you care about.** Autosizing only means something relative to bounds. If the composable has unbounded width, there's nothing to shrink toward. Give it a real width (a weight, a `fillMaxWidth`, a fixed size) so "fit" is well defined.
- **`maxLines` is part of the fit.** Autosize will shrink until the text fits in the allowed lines, so a single-line headline and a two-line one behave differently.

## Autosize plus accessibility font scaling

The part people get wrong: autosizing and the user's system font-scale setting are not in conflict, and you must not "fix" layouts by disabling scaling. Because the range is expressed in `sp`, it already composes with the accessibility scale. A user who sets a 1.3x font scale still gets the largest size *that fits* — the framework just does the fitting against the scaled values.

The wrong instinct is to switch to `dp`-based sizing or hard-cap text to protect your pixel-perfect design. That breaks the low-vision users who most need larger text. Autosize is actually the accessibility-friendly answer: it lets you keep layouts intact under aggressive font scaling without truncating. This is the same mindset I push in [Compose accessibility and semantics](https://blog.michaelsam94.com/compose-accessibility-semantics/) — work *with* the platform's accessibility settings, never around them. Test at 130% and 200% font scale; if a headline still fits gracefully because it autosized down to your floor, you've done it right.

## Where it fits — and where it doesn't

Autosize is not a hammer for all text. My rules:

| Use autosize | Don't bother |
| --- | --- |
| Headlines / titles in fixed-height cards | Body copy meant to wrap and scroll |
| Numbers/timers in fixed widgets | Long paragraphs |
| Localized labels that vary wildly in length | Text with generous, flexible space |
| Buttons that must stay one line | Anything where truncation is acceptable |

For flowing body text, let it wrap and scroll — shrinking a paragraph to fit a box usually produces something worse than a scroll. Autosize shines for *constrained, prominent, short* text: the exact places where overflow looks broken and truncation loses meaning.

It also pairs naturally with responsive layout work. When you're already adapting structure across window sizes — the territory of [adaptive layouts in Compose](https://blog.michaelsam94.com/adaptive-layouts-compose-grid-flexbox/) — autosize handles the *typographic* half of responsiveness so a title looks intentional on both a phone and an unfolded foldable without you maintaining separate font sizes per breakpoint.

## A note on BasicText vs Text

Autosize arrived on `BasicText` because that's the primitive `Text` is built from. If you want the feature with your theme's typography and color applied, either use the `Text` overload that forwards `autoSize`, or reach for `BasicText` and pass a `TextStyle` derived from `MaterialTheme.typography` yourself. I usually stick with `Text` for consistency with the rest of the screen and only drop to `BasicText` when I'm building a component that shouldn't carry theme defaults at all — a design-system primitive, say.

The larger point: this is a small API that removes a whole category of hacky code. If you've got a `remember { mutableStateOf(fontSize) }` loop somewhere shrinking text frame by frame, delete it. Give the framework a range, constrain the box, test under font scaling, and let the layout pass do the work it was always meant to do.

## Resources

- [BasicText and autosize — Compose API reference](https://developer.android.com/reference/kotlin/androidx/compose/foundation/text/package-summary)
- [Text in Compose — official guide](https://developer.android.com/develop/ui/compose/text)
- [Support different font sizes (accessibility)](https://developer.android.com/develop/ui/compose/accessibility/text)
- [Compose layout basics](https://developer.android.com/develop/ui/compose/layouts/basics)
- [Android accessibility — font size](https://support.google.com/accessibility/android/answer/11183305)
