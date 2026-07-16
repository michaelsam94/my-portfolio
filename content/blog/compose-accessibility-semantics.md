---
title: "Accessibility Semantics in Jetpack Compose"
slug: "compose-accessibility-semantics"
description: "Compose accessibility done right: the semantics tree, contentDescription, merging nodes, custom actions, and testing with TalkBack so screen readers work."
datePublished: "2026-06-25"
dateModified: "2026-06-25"
tags: ["Android", "Jetpack Compose", "Accessibility"]
keywords: "Compose accessibility, semantics Compose, TalkBack, content description, merge semantics, a11y Android"
faq:
  - q: "What are semantics in Jetpack Compose?"
    a: "Semantics are the metadata layer Compose builds alongside your UI that describes what each element means to accessibility services like TalkBack — its role, label, state, and available actions. Because Compose draws pixels rather than emitting Android View objects, the semantics tree is the only thing a screen reader can see, so getting it right is what makes an app usable without sight."
  - q: "When should I use mergeDescendants in Compose?"
    a: "Use mergeDescendants when several child elements form one logical unit that should be announced as a single focusable item — a row with an avatar, a name, and a subtitle, for example. Merging stops TalkBack from forcing the user to swipe through each fragment separately and instead reads them as one coherent label."
  - q: "How do I test accessibility in a Compose app?"
    a: "Combine automated and manual testing. Compose UI tests can assert on semantics with matchers like assertContentDescriptionEquals and onNodeWithContentDescription, and Google's Accessibility Scanner flags contrast and target-size issues. But nothing replaces turning on TalkBack and exploring the screen by touch yourself, because ordering and merging problems only surface with a real screen reader."
---

Most Compose accessibility bugs I review come down to a single misunderstanding: developers think the visual UI *is* the interface, when for a screen-reader user the semantics tree is the entire interface. Compose accessibility works by building a parallel tree of meaning — roles, labels, states, and actions — that TalkBack reads instead of the pixels. If an icon button has no label, it doesn't matter how obvious the icon looks; to a blind user it's an unlabeled tap target announced as "button, double tap to activate," with no hint of what it does.

I care about this beyond compliance. An app that works cleanly with TalkBack is almost always an app with a clearer information hierarchy, and the same discipline pays off for switch access, large-text users, and voice control. Here's how the semantics system works and the handful of things that fix 90% of the problems.

## The semantics tree is the real UI

Every composable can contribute a `SemanticsNode`. Some do it automatically — `Text` exposes its string, `Button` exposes a click action and a "button" role — and some contribute nothing until you tell them to. An `Image` or a custom `Canvas` drawing is invisible to TalkBack unless you attach a description, because Compose can't guess what a bitmap means.

The mental model I use: after every screen, ask "if I could only hear this screen, would I know what's on it and what I can do?" That question catches decorative-vs-meaningful confusion, missing labels, and state that's shown only with color.

## contentDescription and when to skip it

The most common fix is also the most misused. `contentDescription` labels non-text content:

```kotlin
Icon(
    imageVector = Icons.Default.Delete,
    contentDescription = "Delete message",
)
```

But decorative images should be explicitly *null*, not labeled with noise. A background flourish announced as "abstract blue shape" is worse than silence:

```kotlin
Image(
    painter = painterResource(R.drawable.header_pattern),
    contentDescription = null, // purely decorative — hide from TalkBack
)
```

The rule: describe the *meaning*, not the picture. A trash icon is "Delete message," not "trash can icon." And never bake the role into the label — TalkBack already appends "button," so `contentDescription = "Delete message button"` gets read as "Delete message button, button."

## Merging descendants into one node

Cards are where accessibility usually breaks. A conversation row with an avatar, a name, a message preview, and a timestamp naturally produces four separate focusable nodes, forcing the user to swipe four times to hear one message. `mergeDescendants` collapses them:

```kotlin
Row(
    modifier = Modifier
        .clickable { open(conversation) }
        .semantics(mergeDescendants = true) {}
) {
    Avatar(conversation.contact)
    Column {
        Text(conversation.name)
        Text(conversation.lastMessage, maxLines = 1)
    }
    Text(conversation.timestamp)
}
```

Now TalkBack reads "Ahmed, see you tomorrow, 4:32 PM" as one item with one activation. Interactive children like a nested button break out of the merge automatically, which is exactly what you want. Getting merging right is closely tied to how you structure layout in the first place — the same grouping instincts show up when building [adaptive layouts with Compose grids and flexbox](https://blog.michaelsam94.com/adaptive-layouts-compose-grid-flexbox/).

## State, roles, and custom actions

Labels are only half the story; a screen reader also needs to announce *state*. A toggle that only changes color communicates nothing. Use `toggleableState`, `selected`, `stateDescription`, and roles so the current value is spoken:

```kotlin
Modifier.semantics {
    role = Role.Switch
    stateDescription = if (enabled) "On" else "Off"
}
```

For gestures a TalkBack user can't perform — swipe-to-archive, long-press menus — expose an equivalent through `customActions` so the functionality isn't gated behind a gesture:

```kotlin
Modifier.semantics {
    customActions = listOf(
        CustomAccessibilityAction("Archive") { archive(item); true },
        CustomAccessibilityAction("Mark unread") { markUnread(item); true },
    )
}
```

These surface in TalkBack's actions menu. I treat any swipe or long-press action as incomplete until it has a `customAction` twin — otherwise a whole class of users simply can't reach the feature.

## Traversal order and live regions

TalkBack reads in a default order derived from layout position, and usually that's correct. When it isn't — say a floating summary that should be read before a long list — use `traversalIndex` and `isTraversalGroup` to steer it rather than reordering your composables and wrecking the visual layout.

For content that updates without user action, like a "message sent" confirmation or a loading result, mark it a live region so it's announced automatically:

```kotlin
Text(
    text = statusMessage,
    modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite },
)
```

`Polite` waits for a gap in speech; `Assertive` interrupts. Reserve assertive for genuinely urgent state — overusing it makes the app feel like it's shouting.

## Testing it for real

Automated tests keep regressions out. Compose's test APIs read the same semantics tree TalkBack does, so you assert on meaning, not pixels:

```kotlin
composeTestRule
    .onNodeWithContentDescription("Delete message")
    .assertHasClickAction()
```

That said, I've never shipped an accessible screen on automated tests alone. Turn on TalkBack, put the phone down, and navigate the screen by swipe and by explore-by-touch. Ordering problems, awkward merges, and unlabeled targets jump out in thirty seconds of real use. Pair that with the Accessibility Scanner for contrast and touch-target size, and fold the semantics assertions into your broader UI suite the same way you would any other [Compose UI test](https://blog.michaelsam94.com/testing-compose-uis-v2/). Text scaling matters too — verify labels survive large font settings, which ties into how [autosizing text with BasicText](https://blog.michaelsam94.com/compose-text-autosize-basictext/) behaves when users crank the system font up.

Accessibility in Compose isn't a checklist you bolt on at the end. It's a small, learnable set of semantics primitives that, applied as you build, make the app work for everyone and — not coincidentally — make it cleaner for everyone else too.

## Resources

- [Compose accessibility documentation](https://developer.android.com/develop/ui/compose/accessibility)
- [Semantics in Compose](https://developer.android.com/develop/ui/compose/semantics)
- [Android accessibility principles](https://developer.android.com/guide/topics/ui/accessibility/principles)
- [Web Content Accessibility Guidelines (WCAG)](https://www.w3.org/WAI/standards-guidelines/wcag/)
- [Testing Compose layouts](https://developer.android.com/develop/ui/compose/testing)
