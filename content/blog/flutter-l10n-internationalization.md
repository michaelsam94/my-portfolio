---
title: "Internationalizing Flutter with intl"
slug: "flutter-l10n-internationalization"
description: "Set up Flutter localization with intl and gen-l10n: ARB files, pluralization, date/number formatting, RTL layouts, and locale resolution."
datePublished: "2024-12-18"
dateModified: "2024-12-18"
tags: ["Flutter", "Dart"]
keywords: "Flutter localization, intl package, gen-l10n, ARB files, Flutter i18n, RTL Flutter"
faq:
  - q: "How do I localize a Flutter app?"
    a: "Enable generate: true in pubspec.yaml flutter section, create lib/l10n/app_en.arb template files, run flutter gen-l10n to generate AppLocalizations class. Wire localizationsDelegates and supportedLocales in MaterialApp, then access strings via AppLocalizations.of(context)!.keyName in widgets."
  - q: "What are ARB files in Flutter localization?"
    a: "ARB (Application Resource Bundle) files are JSON dictionaries mapping string keys to translated values with optional metadata for placeholders, plurals, and descriptions. app_en.arb is the template; app_es.arb, app_fr.arb etc. provide translations. Flutter's gen-l10n tool generates type-safe Dart accessors from ARB files."
  - q: "How do I handle pluralization in Flutter l10n?"
    a: "Define plural keys in ARB with @keyName placeholder metadata specifying plural type and form counts: zero, one, two, few, many, other. gen-l10n generates methods accepting count parameter returning correct plural form per locale rules."
---

Shipping in the US only works until App Store Connect shows 40% of downloads from markets you didn't translate. Flutter's official localization toolchain—ARB files, `gen-l10n`, `intl` formatters—generates type-safe string accessors and catches missing translations at compile time. I've migrated two apps from hardcoded strings and the first compile after enabling l10n always surfaces eighty forgotten English literals.

## Project configuration

**pubspec.yaml:**

```yaml
dependencies:
  flutter:
    sdk: flutter
  flutter_localizations:
    sdk: flutter
  intl: any

flutter:
  generate: true
```

**l10n.yaml** (optional, project root):

```yaml
arb-dir: lib/l10n
template-arb-file: app_en.arb
output-localization-file: app_localizations.dart
nullable-getter: false
```

**lib/l10n/app_en.arb:**

```json
{
  "@@locale": "en",
  "appTitle": "My Shop",
  "@appTitle": {
    "description": "Application title shown in app bar"
  },
  "itemCount": "{count, plural, =0{No items} =1{1 item} other{{count} items}}",
  "@itemCount": {
    "placeholders": {
      "count": { "type": "int" }
    }
  },
  "welcomeMessage": "Hello, {name}!",
  "@welcomeMessage": {
    "placeholders": {
      "name": { "type": "String" }
    }
  }
}
```

**lib/l10n/app_es.arb:**

```json
{
  "@@locale": "es",
  "appTitle": "Mi Tienda",
  "itemCount": "{count, plural, =0{Sin artículos} =1{1 artículo} other{{count} artículos}}",
  "welcomeMessage": "¡Hola, {name}!"
}
```

Generate:

```bash
flutter gen-l10n
# or automatically on flutter build/run with generate: true
```

## Wire MaterialApp

```dart
import 'package:flutter_gen/gen_l10n/app_localizations.dart';

MaterialApp(
  localizationsDelegates: const [
    AppLocalizations.delegate,
    GlobalMaterialLocalizations.delegate,
    GlobalWidgetsLocalizations.delegate,
    GlobalCupertinoLocalizations.delegate,
  ],
  supportedLocales: const [
    Locale('en'),
    Locale('es'),
    Locale('ar'),
  ],
  locale: userSelectedLocale, // optional override
  home: HomePage(),
)
```

Missing `GlobalMaterialLocalizations` breaks date pickers and Material widgets in non-English locales.

## Using localized strings

```dart
class CartPage extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    return Scaffold(
      appBar: AppBar(title: Text(l10n.appTitle)),
      body: Text(l10n.itemCount(cartItems.length)),
    );
  }
}
```

Compile error if key missing from ARB—safer than string constants.

## Date and number formatting with intl

```dart
import 'package:intl/intl.dart';

final locale = Localizations.localeOf(context).toString();
final price = NumberFormat.currency(locale: locale, symbol: '\$').format(42.5);
final date = DateFormat.yMMMd(locale).format(DateTime.now());
```

Respect user locale for formatting even when UI strings stay English.

## RTL support

Arabic and Hebrew require right-to-left layout:

```dart
MaterialApp(
  supportedLocales: const [Locale('ar'), Locale('en')],
  // ...
)

// Debug RTL in development
MaterialApp(
  builder: (context, child) {
    return Directionality(
      textDirection: TextDirection.rtl,
      child: child!,
    );
  },
)
```

Flutter mirrors most widgets automatically when locale direction is RTL. Verify custom painters and asymmetric padding manually.

Test:

```dart
testWidgets('renders RTL', (tester) async {
  await tester.pumpWidget(
    MaterialApp(
      locale: Locale('ar'),
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: HomePage(),
    ),
  );
});
```

## Locale resolution

```dart
MaterialApp(
  localeResolutionCallback: (locale, supportedLocales) {
    for (final supported in supportedLocales) {
      if (supported.languageCode == locale?.languageCode) {
        return supported;
      }
    }
    return supportedLocales.first; // fallback to English
  },
)
```

Match language without region (`en` matches `en_GB`) or require exact match per product requirements.

### User locale preference

Persist selection:

```dart
class LocaleCubit extends Cubit<Locale?> {
  LocaleCubit(this._prefs) : super(null) {
    _load();
  }
  final SharedPreferences _prefs;

  void _load() {
    final code = _prefs.getString('locale');
    if (code != null) emit(Locale(code));
  }

  Future<void> setLocale(Locale locale) async {
    await _prefs.setString('locale', locale.languageCode);
    emit(locale);
  }
}

// MaterialApp
locale: context.watch<LocaleCubit>().state, // null = system default
```

Per-app language on Android 13+ also needs `locale` list in Android manifest—see `flutter_localizations` Android docs.

### CI checks

Fail build on missing translations:

```bash
flutter gen-l10n
# Compare keys across ARB files with script
dart run tool/check_arb_parity.dart
```

Script asserts every key in `app_en.arb` exists in all locale ARB files.

### Context-free strings in Cubits

Cubits shouldn't call AppLocalizations.of(context)—emit error codes; widgets map to l10n. For snackbars from repository layer, use callback or event bus carrying Failure enum, not pre-localized strings, keeping data layer locale-agnostic.

Pseudo-localization (long strings, accents) in debug builds exposes layout overflow before translators deliver final ARB files. Flutter tooling supports debug locale generation—enable during QA sprints before international launch milestones.

Production teams should treat this guidance as living documentation: revisit assumptions after major platform upgrades, measure outcomes with real metrics rather than checklist compliance, and pair written standards with automated checks in CI. The patterns here reflect what held up in shipped apps—not theoretical perfection. Adapt thresholds, timeouts, and tooling to your stack, but keep the underlying principles: explicit configuration, testable behavior, and failure modes users can understand.

When onboarding new engineers, walk through one end-to-end example in a debug build before asking them to extend the pattern. Most failures I have seen came from skipped platform setup steps—manifest entries, API keys, code generation, or permission prompts—not from misunderstanding the Dart layer. Keep a troubleshooting section in your team wiki linking official docs and the exact commands that worked for your last upgrade.

Schedule a quarterly review of this implementation against current SDK release notes—Flutter and cloud providers ship breaking changes on six-month cadences, and assumptions that held last year may need adjustment. Capture before-and-after metrics when you change configuration so regressions are obvious in retrospect rather than debated from memory.

Version-pin dependencies mentioned here in your pubspec.lock or infrastructure modules, and note the Flutter/Dart SDK constraint your team validated. Upgrading without re-running the verification steps in this article is the most common source of regressions. If something fails after an upgrade, compare release notes first, then your git history for the last known-good configuration.

## Common production mistakes

Teams get l10n internationalization wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Flutter teams implementing l10n internationalization often regress performance by rebuilding entire subtrees on every frame, ignoring platform channel latency, or testing only on iOS simulators. Profile on mid-range Android hardware before calling the work done.

## Resources

- [Flutter internationalization](https://docs.flutter.dev/ui/accessibility-and-internationalization/internationalization)
- [intl package](https://pub.dev/packages/intl)
- [ARB file format](https://github.com/google/app-resource-bundle/wiki/ApplicationResourceBundleSpecification)
- [GlobalMaterialLocalizations](https://api.flutter.dev/flutter/flutter_localizations/GlobalMaterialLocalizations-class.html)
- [flutter_localizations](https://api.flutter.dev/flutter/flutter_localizations/flutter_localizations-library.html)
