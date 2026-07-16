---
title: "Localization and RTL Support on Android, Done Right"
slug: "android-localization-rtl-support"
description: "Android localization and RTL support: per-app language, plurals and formatting, start/end vs left/right, mirroring, and the pseudolocale trick that finds bugs early."
datePublished: "2024-08-25"
dateModified: "2024-08-25"
tags: ["Android", "Localization", "Kotlin"]
keywords: "Android localization, RTL support, per-app language, string plurals, LayoutDirection, pseudolocales, bidi text"
faq:
  - q: "How do I support right-to-left languages on Android?"
    a: "Set android:supportsRtl=\"true\" in the manifest, then replace every left/right reference with start/end in layouts, paddings, and drawables so the UI mirrors automatically for Arabic, Hebrew, Farsi, and Urdu. Test with a real RTL locale or the RTL pseudolocale, and manually mirror only the icons that imply direction, like back arrows and progress. The framework mirrors most layout for you once you commit to start/end everywhere."
  - q: "What is per-app language on Android and why use it?"
    a: "Per-app language, introduced in Android 13, lets a user pick a language for one app that differs from the system language, which matters for multilingual users who want their banking app in English but their messaging app in Arabic. You declare a locales_config XML and, on older versions, AppCompat backports the behavior. It replaces the fragile pattern of manually swapping Locale and recreating activities."
  - q: "Should I use string formatting or concatenation for translations?"
    a: "Always use positional string resources with placeholders and plurals rather than concatenating strings in code. Word order differs across languages, so building a sentence by gluing fragments produces broken grammar in translation, and pluralization rules vary far beyond English's one/other. Placeholders and the plurals resource let translators reorder and pluralize correctly without touching code."
---

Localization on Android fails in two predictable ways: someone concatenates strings in code so translations come out grammatically broken, and someone hardcodes `left`/`right` so the whole UI shatters in Arabic. Both are entirely avoidable if you commit to a few disciplines from the start — positional string resources, `start`/`end` everywhere, and testing with pseudolocales before a single real translation lands. I've retrofitted RTL into apps that didn't plan for it, and it's an order of magnitude more painful than doing it up front, because the assumptions leak into hundreds of layout files.

This is the practical playbook: how to structure strings so translators can do their job, how to make the UI mirror correctly for right-to-left languages, and how to catch the bugs early with tooling instead of a bug report from a user in Cairo.

## Strings: never build sentences in code

The cardinal rule. Word order is not universal, so a sentence assembled from fragments will be wrong somewhere. Use positional placeholders and let the translation reorder them:

```xml
<!-- Bad: "You have " + count + " new messages" — untranslatable -->
<!-- Good -->
<string name="new_messages">You have %1$d new messages from %2$s</string>
```

A translator into a language with different word order can write the equivalent of "From %2$s you have %1$d messages" and it just works, because the placeholders carry their own position.

Pluralization is the second trap. English has two forms (one/other); Arabic has six, Russian has several, and there's no way to express that with an `if (count == 1)`. Use the `plurals` resource:

```xml
<plurals name="message_count">
    <item quantity="one">%d message</item>
    <item quantity="other">%d messages</item>
</plurals>
```

```kotlin
val label = resources.getQuantityString(R.plurals.message_count, count, count)
```

The framework picks the correct form per locale. Also format numbers, dates, and currency through `NumberFormat`/`DateFormat` with the current locale — never hand-format, or you'll show `1,000.50` to someone who writes `1.000,50`.

## RTL: commit to start/end and let the framework mirror

Turn it on, then stop thinking in absolute directions:

```xml
<application android:supportsRtl="true" ... >
```

The mechanical work is replacing every directional attribute with its relative equivalent, in layouts and in code:

| Absolute (wrong for RTL) | Relative (correct) |
|---|---|
| `paddingLeft` / `paddingRight` | `paddingStart` / `paddingEnd` |
| `layout_marginLeft` | `layout_marginStart` |
| `layout_alignParentLeft` | `layout_alignParentStart` |
| `drawableLeft` | `drawableStart` |
| `gravity="left"` | `gravity="start"` |

In Compose, the padding and arrangement modifiers are already direction-aware — `Modifier.padding(start = 16.dp)` mirrors automatically, and `Row` lays out in the reading direction. You mostly get RTL for free in Compose *if* you use `start`/`end` and don't hardcode `Alignment.Start` as "left." Read `LocalLayoutDirection` when you genuinely need to know.

Once you've committed to relative attributes, the framework flips the entire layout for an RTL locale. That's the payoff: you don't mirror screens by hand, you just stop using absolute directions.

## The icons you must mirror by hand

Not everything should flip. Text mirrors, layout mirrors, but *content* is nuanced:

- **Mirror**: back arrows, forward/next chevrons, progress bars, list reveal chevrons — anything encoding "direction of travel."
- **Don't mirror**: a play button (media time is universal), a checkmark, a logo, a phone icon, most brand imagery.

For vector drawables that should flip, set `android:autoMirrored="true"` and the system mirrors them in RTL. Get this wrong and you either have a back arrow pointing the wrong way (jarring) or a mirrored play button (nonsensical). This judgment overlaps with [accessibility](https://blog.michaelsam94.com/android-accessibility-talkback-testing/): a back arrow that doesn't mirror also confuses the mental model of screen-reader users navigating in RTL.

## Bidirectional text: wrap the wild parts

Even in an English UI, user-generated content might be Arabic, and vice versa. Mixing directions in one line (a phone number inside Arabic text, an Arabic name in an English sentence) produces the infamous scrambled bidi output. Wrap dynamic, direction-ambiguous substrings with the bidi formatter:

```kotlin
val bidi = BidiFormatter.getInstance()
val display = getString(R.string.greeting, bidi.unicodeWrap(userName))
```

This inserts the right Unicode direction marks so the substring renders as its own island and doesn't reorder the surrounding text.

## Per-app language: the modern way to switch

Users who live in multiple languages want their banking app in English and their chat app in Arabic. Since Android 13 that's a first-class feature. Declare the locales you support:

```xml
<!-- res/xml/locales_config.xml -->
<locale-config xmlns:android="http://schemas.android.com/apk/res/android">
    <locale android:name="en" />
    <locale android:name="ar" />
    <locale android:name="fr" />
</locale-config>
```

Reference it in the manifest, then set the language with AppCompat, which backports the behavior to older versions:

```kotlin
AppCompatDelegate.setApplicationLocales(
    LocaleListCompat.forLanguageTags("ar")
)
```

This replaced the old, fragile pattern of swapping `Locale` and recreating the activity yourself, which broke in dozens of edge cases. Let the platform own it.

## Catch bugs before translators do: pseudolocales

The trick I wish more teams used: Android ships **pseudolocales** you enable in developer options. `en-XA` wraps every string in accents and padding (`[Ëxämplé one two]`), which instantly reveals hardcoded strings (they stay plain ASCII) and text that gets truncated when a translation runs ~40% longer than English. `ar-XB` forces RTL layout using Latin text, so you can spot mirroring bugs without reading Arabic.

Turn these on and click through the app before any real localization work. Every hardcoded string, every clipped label, every un-mirrored layout jumps out. It's the cheapest possible localization QA and it front-loads the fixes to when they're easy.

## The short version

Externalize every string with positional placeholders and use `plurals`; format numbers and dates with the locale; go all-in on `start`/`end` and let the framework mirror; hand-mirror only directional icons via `autoMirrored`; wrap bidirectional user content with `BidiFormatter`; adopt per-app language through AppCompat; and test everything with the `en-XA` and `ar-XB` pseudolocales before real translations arrive. Do these from day one and localization is a config exercise. Retrofit them under deadline and it's a slog.

## Resources

- [Support different languages and cultures (Android)](https://developer.android.com/guide/topics/resources/localization)
- [Per-app language preferences](https://developer.android.com/guide/topics/resources/app-languages)
- [RTL / bidirectional support](https://developer.android.com/training/basics/supporting-devices/languages)
- [Quantity strings (plurals)](https://developer.android.com/guide/topics/resources/string-resource#Plurals)
- [Test with pseudolocales](https://developer.android.com/guide/topics/resources/pseudolocales)
