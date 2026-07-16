---
title: "Per-App Language Preferences with AppCompat"
slug: "android-per-app-language-appcompat"
description: "Let users pick a language just for your app using AppCompat's per-app language APIs, locale config XML, and the system settings integration that backs it."
datePublished: "2024-09-18"
dateModified: "2024-09-18"
tags: ["Android", "Localization", "AppCompat", "UI"]
keywords: "per-app language, AppCompatDelegate setApplicationLocales, locales_config, LocaleManager, Android in-app language, app language settings"
faq:
  - q: "How do I set a per-app language in Android?"
    a: "Call AppCompatDelegate.setApplicationLocales with a LocaleListCompat built from the chosen language tag. AppCompat persists the choice and applies it across app restarts, and on Android 13 and above it delegates to the platform LocaleManager so the preference also shows in system settings. You do not manually swap resources or restart the activity yourself."
  - q: "What is the locales_config XML file for?"
    a: "locales_config.xml lists the locales your app supports, and you reference it from the application tag with android:localeConfig. On Android 13 and above the system reads it to render a per-app language picker in Settings, so users can change your app's language from the system without opening the app. Without it, the system picker will not appear."
  - q: "Does per-app language work below Android 13?"
    a: "Yes. AppCompat backports the feature, so setApplicationLocales works down to older versions by storing the preference and applying it via the AppCompat delegate. The difference is that the system Settings picker only appears on Android 13 and above; on older versions you provide your own in-app language selector that calls the same API."
---

Per-app language lets a user run *your* app in Spanish while the rest of their phone stays in English — and AppCompat makes it a two-call feature. You define the locales you support in an XML file, and you call `AppCompatDelegate.setApplicationLocales()` when the user picks one. AppCompat persists the choice, reapplies it on every launch, and on Android 13+ hands it to the platform `LocaleManager` so the preference even appears in system Settings. No manual resource swapping, no activity-restart gymnastics, and it backports cleanly to older versions.

Before this API existed, per-app language meant hacking `Configuration` overrides in `attachBaseContext` and praying across every activity. I maintained one of those homegrown systems for years; migrating to the AppCompat API deleted a whole class of bugs. Here's how to do it properly.

## Step 1: declare your supported locales

Create `res/xml/locales_config.xml` listing every language tag your app ships translations for:

```xml
<?xml version="1.0" encoding="utf-8"?>
<locale-config xmlns:android="http://schemas.android.com/apk/res/android">
    <locale android:name="en" />
    <locale android:name="es" />
    <locale android:name="fr" />
    <locale android:name="ar" />
    <locale android:name="pt-BR" />
</locale-config>
```

Reference it from the `<application>` tag:

```xml
<application
    android:localeConfig="@xml/locales_config"
    ... >
```

This file is what makes the *system* per-app language picker appear in Settings on Android 13+. Skip it and users can only change the language from inside your app. The list must match the locales you actually have resources for — advertising a locale you haven't translated just shows English strings under a Spanish label.

## Step 2: set the locale when the user chooses

Wherever your in-app language selector lives, translate the choice into a `LocaleListCompat` and hand it to AppCompat:

```kotlin
fun onLanguageSelected(languageTag: String) {
    val locales = LocaleListCompat.forLanguageTags(languageTag) // "es", "pt-BR", ...
    AppCompatDelegate.setApplicationLocales(locales)
}
```

That's the whole write path. AppCompat stores the preference (in its own storage below Android 13, via `LocaleManager` at 13+), recreates the activity to apply it, and restores it automatically on subsequent launches. To reset to the system default, pass an empty list:

```kotlin
AppCompatDelegate.setApplicationLocales(LocaleListCompat.getEmptyLocaleList())
```

Reading the current value back for your settings UI:

```kotlin
val current = AppCompatDelegate.getApplicationLocales()
```

## Step 3: the one manifest piece for AndroidX startup

For the backport to persist and reapply correctly on older versions, AppCompat uses an `androidx.appcompat` metadata component that its manifest already contributes. In modern AppCompat versions this is wired for you via the `AppLocalesMetadataHolderService` merged from the library manifest — you generally don't touch it. The thing to verify is that you're on a recent AppCompat (1.6+) so the API and its persistence exist. If per-app language "forgets" the choice after a cold start on Android 12 or below, an outdated AppCompat is the usual culprit.

## Why this beats the old approach

The homegrown method wrapped every base context and juggled `Configuration`. It broke constantly: dialogs and notifications used the wrong locale, `WebView` reset it, and process death lost the choice. The AppCompat API centralizes all of that. A comparison:

| Concern | Old `attachBaseContext` hack | AppCompat per-app language |
| --- | --- | --- |
| Persistence | You store & reapply | Handled by AppCompat |
| System Settings integration | None | Yes (Android 13+) |
| Backport below 13 | Manual, fragile | Built in |
| Activity recreation | You trigger it | Handled |
| Notifications / services | Frequently wrong locale | Consistent |

## Things that still trip people up

A few production realities the API doesn't fully abstract away.

- **Right-to-left layouts.** Selecting Arabic or Hebrew flips layout direction only if your layouts use `start`/`end` (not `left`/`right`) and you've set `android:supportsRtl="true"`. The language API changes strings and locale; it's on you to have built RTL-clean layouts. If you're on Compose, the layout system respects `LayoutDirection` automatically when you use logical alignment.
- **Notifications posted from background work.** A notification built in a `WorkManager` job runs outside the activity context. Fetch localized strings using a context that reflects the application locales, or build the notification text on the main app process where AppCompat's locale is active.
- **Server-driven content.** The API localizes your *resources*. Content coming from your backend (emails, push payloads, API text) needs the selected locale sent to the server so it responds in the right language. Send the language tag as a header or parameter.
- **Testing.** Change the language, then force-stop and cold-start the app to confirm persistence. Also test switching *from* an RTL locale back to LTR — the layout should flip back cleanly.

## Wiring it into a settings screen

The typical UX is a language row in settings that opens a picker of your supported locales, with the current selection checked. Build the option list from the same tags in `locales_config.xml` (I keep them in a single source of truth so the XML and the UI can't drift), show each language in *its own* script («Español», «العربية») rather than translated into the current language, and call `setApplicationLocales` on selection. On Android 13+ you can additionally deep-link users to the system per-app language screen, but an in-app picker is what gives you consistent behavior across all supported versions.

Getting locale handling right is part of the same broader discipline of respecting configuration as an input rather than an assumption — the same reason [adaptive layouts](https://blog.michaelsam94.com/adaptive-layouts-compose-grid-flexbox/) branch on window size instead of hardcoding a device.

## What I'd take away

Per-app language is no longer a hack. Declare your supported locales in `locales_config.xml`, reference it with `android:localeConfig`, and call `AppCompatDelegate.setApplicationLocales()` with a `LocaleListCompat` when the user picks — AppCompat handles persistence, activity recreation, the Android 13+ Settings integration, and the backport to older versions. Stay on AppCompat 1.6+ so the persistence works, build RTL-clean layouts with logical alignment, localize background-generated notifications deliberately, and send the chosen locale to your backend for server content. Do that and users get a genuinely localized app they can control per-app — without the fragile `Configuration` wrangling that used to be required.

## Resources

- [Per-app language preferences (Android developers)](https://developer.android.com/guide/topics/resources/app-languages)
- [AppCompatDelegate.setApplicationLocales reference](https://developer.android.com/reference/androidx/appcompat/app/AppCompatDelegate#setApplicationLocales(androidx.core.os.LocaleListCompat))
- [Localize your app](https://developer.android.com/guide/topics/resources/localization)
- [Support different languages and cultures](https://developer.android.com/training/basics/supporting-devices/languages)
- [LocaleManager (platform API)](https://developer.android.com/reference/android/app/LocaleManager)
