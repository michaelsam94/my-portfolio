---
title: "Per-App Language Preferences on Android"
slug: "android-per-app-language"
description: "Per-app language preferences on Android let users pick a language for one app independent of the system locale, using LocaleManager and a small resources config."
datePublished: "2026-01-17"
dateModified: "2026-01-17"
tags: ["Android", "Localization", "UX"]
keywords: "per-app language, Android localization, locale config, app language preferences, LocaleManager, i18n Android"
faq:
  - q: "What are per-app language preferences on Android?"
    a: "Per-app language preferences are a platform feature, introduced in Android 13, that lets a user choose a display language for an individual app that differs from the system-wide language. The choice is stored by the system, surfaced in Settings under the app, and applied automatically on launch, so a user can run one app in Arabic while the rest of the phone stays in English."
  - q: "How do I make my app support per-app languages?"
    a: "You declare the languages your app supports in a locales_config XML file referenced from the manifest, and on modern AGP you enable automatic generation of that list. The system then shows a language picker for your app in Settings. You can also read and set the preference programmatically through LocaleManager (or AppCompatDelegate for backward compatibility)."
  - q: "Does this work below Android 13?"
    a: "The system Settings UI and LocaleManager exist from Android 13 onward. For older versions, AndroidX AppCompat backports the behavior: AppCompatDelegate.setApplicationLocales stores the preference and applies it, and the same locales_config drives an in-app picker. So you can offer per-app language down to older API levels, just without the system Settings entry."
---

Cairo is a bilingual city, and a lot of the people I build for keep their phone in English but want a specific app — a banking app, a government service, a reader — in Arabic. Before Android 13, giving them that meant hand-rolling a locale-switching hack: wrapping `Context`, persisting a choice in `SharedPreferences`, recreating activities, and fighting the framework the whole way. Per-app language preferences replace all of that with a first-class platform feature. The user picks a language for your app specifically, the system remembers it, and it's applied on launch — no custom `Context` gymnastics.

If you've ever maintained one of those DIY locale wrappers, you know how brittle they were. This feature is the fix, and adopting it is mostly configuration rather than code.

## The old way, and why it hurt

The pre-13 pattern looked something like: store a language code, override `attachBaseContext` to build a `Context` with an updated `Configuration`, and recreate every activity when the choice changed. It sort of worked, but it leaked in a dozen places — `WebView` resetting the locale, resources loaded from the application `Context` ignoring the override, configuration changes on rotation clobbering state. I've debugged all of those, and none of them were fun. The core issue was that locale is genuinely a *process/system* concern, and we were trying to fake it at the app layer.

Per-app languages move the responsibility back to where it belongs: the system owns the preference and applies it before your app's UI is built.

## Declaring your supported languages

The feature needs to know which languages your app actually ships. You express that in a `locales_config` resource:

```xml
<!-- res/xml/locales_config.xml -->
<locale-config xmlns:android="http://schemas.android.com/apk/res/android">
    <locale android:name="en"/>
    <locale android:name="ar"/>
    <locale android:name="fr"/>
    <locale android:name="de"/>
</locale-config>
```

Reference it from the manifest:

```xml
<application
    android:localeConfig="@xml/locales_config">
</application>
```

On a modern Android Gradle Plugin you don't even hand-maintain that file — you opt into automatic generation and AGP builds the list from the resource folders you actually have translations for:

```kotlin
android {
    androidResources {
        generateLocaleConfig = true
    }
    // Declare the default/unqualified locale so the tool knows the base language
    defaultConfig {
        resourceConfigurations += setOf("en", "ar", "fr", "de")
    }
}
```

I strongly prefer the generated approach. A hand-maintained locale list drifts — someone adds a `values-es` folder and forgets the XML, and Spanish silently never appears in the picker. Letting the build derive it from real resources removes an entire category of "why isn't my language showing up" tickets.

## Reading and setting the preference in code

Two situations need code. First, an in-app language picker (many users never open system Settings, so offering one inside the app is good UX). Second, reflecting or reacting to the current choice. Use `AppCompatDelegate` for the widest compatibility, since it backports below Android 13:

```kotlin
// Set the app's locale — persists and applies immediately
fun applyLanguage(tag: String) {
    val locales = LocaleListCompat.forLanguageTags(tag)
    AppCompatDelegate.setApplicationLocales(locales)
}

// Read the current choice to pre-select it in a picker
fun currentLanguageTag(): String =
    AppCompatDelegate.getApplicationLocales()
        .toLanguageTags()
        .ifEmpty { "system" }
```

On Android 13+ you can also go straight to the platform `LocaleManager`:

```kotlin
val localeManager = getSystemService(LocaleManager::class.java)
localeManager.applicationLocales = LocaleList.forLanguageTags("ar")
```

My recommendation: use the AppCompat API as your single code path. It does the right thing on every version — delegating to `LocaleManager` where it exists and applying the backport where it doesn't — so you write the picker once and it just works from old devices to new.

## Getting the details right

The mechanism is easy. The polish is where apps fall down. The things I check on every localization pass:

- **RTL layout.** Switching to Arabic isn't just translated strings; it's a mirrored layout. Make sure you're using `start`/`end` instead of `left`/`right` everywhere and test the whole app in RTL, not just one screen. This overlaps with the same attention to detail you need when [going edge-to-edge on Android](https://blog.michaelsam94.com/edge-to-edge-android-16/) — layout assumptions you never questioned suddenly matter.
- **Formatting, not just text.** Numbers, dates, currency, and plurals must follow the chosen locale. Use `NumberFormat`, `DateTimeFormatter` with the locale, and proper `plurals` resources — a hardcoded "3 items" that never pluralizes correctly reads as broken to a native speaker.
- **Server-driven content.** The per-app locale affects resources, but your API might still return content in the system language. Send the app's chosen language in an `Accept-Language` header so server content matches the UI.
- **Font and truncation.** German compounds are long, Arabic script has different height metrics. Layouts that look fine in English clip or overflow in other languages. Test with the longest and tallest languages you support.

## The accessibility connection

Language choice is fundamentally an accessibility and inclusion feature — it's about letting people use your app in the language they think in. That same mindset should extend to how the app announces itself. When you localize strings, localize your [content descriptions and Compose accessibility semantics](https://blog.michaelsam94.com/compose-accessibility-semantics/) too, so a screen reader in Arabic reads Arabic labels, not leftover English ones. I've seen apps that translated every visible string but left the `contentDescription`s in English, which makes the app effectively unusable for a blind Arabic speaker. Treat the accessibility tree as part of the translation surface, not an afterthought.

## Should you adopt it?

If your app ships more than one language, yes, unconditionally. The feature is low-effort — a locales config, one AGP flag, and the AppCompat API for an in-app picker — and it replaces the fragile locale-wrapping code that has caused bugs in every app I've seen attempt it manually. It also gives users a discoverable option in system Settings that they increasingly expect.

The one honest caveat: it doesn't magically make your app well-localized. It makes *switching* clean. The hard work — accurate translations, RTL correctness, locale-aware formatting, and matching server content — is still yours. But separating "how the user picks a language" from "how well the app speaks that language" is exactly the right decomposition, and per-app language preferences finally handle the first half properly so you can spend your effort on the second.

## Resources

- [Per-app language preferences — Android docs](https://developer.android.com/guide/topics/resources/app-languages)
- [App localization overview](https://developer.android.com/guide/topics/resources/localization)
- [AppCompatDelegate API reference](https://developer.android.com/reference/androidx/appcompat/app/AppCompatDelegate)
- [Support different languages and cultures](https://developer.android.com/training/basics/supporting-devices/languages)
- [Unicode CLDR — locale data](https://cldr.unicode.org/)
