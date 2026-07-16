---
title: "Dart 3 Patterns: Records, Sealed Classes, Matching"
slug: "dart-3-patterns-records-sealed"
description: "How Dart 3 records, sealed classes, and pattern matching change everyday Flutter code — with real examples of exhaustive switch expressions and destructuring."
datePublished: "2026-05-07"
dateModified: "2026-05-07"
tags: ["Dart", "Flutter", "Pattern Matching", "Language"]
keywords: "Dart 3, Dart records, sealed classes, pattern matching Dart, Dart features, switch expressions, destructuring"
faq:
  - q: "What are records in Dart 3?"
    a: "Records are anonymous, immutable value types that bundle multiple values without declaring a class. They're ideal for returning more than one value from a function — for example (int code, String message) — with structural typing and built-in equality."
  - q: "How do sealed classes work in Dart 3?"
    a: "A sealed class restricts its subtypes to the same library, which lets the compiler know the full set of possible subtypes. That enables exhaustive switch expressions: if you add a new subtype and forget to handle it, the code fails to compile."
  - q: "Are Dart 3 patterns worth adopting in an existing Flutter app?"
    a: "Yes, incrementally. Records simplify multi-value returns immediately, and modeling UI or domain state as a sealed hierarchy with exhaustive switches removes a whole category of forgotten-case bugs. You can adopt them file by file without a migration."
---

Dart 3 quietly turned Dart from a competent app language into an expressive one. The additions — **records, sealed classes, and pattern matching** — aren't syntactic sugar you can ignore; used together they change how you model data and how much boilerplate a typical Flutter screen carries. I've been folding them into production Flutter code, and the wins are concrete: fewer one-off data classes, fewer forgotten-case bugs, and `switch` statements that the compiler actually keeps honest.

Let me show what each feature does on its own, then the combination that matters most — sealed hierarchies with exhaustive switch expressions for UI state.

## Records: multiple values without a class

Before Dart 3, returning two values meant either an out-parameter hack or declaring a throwaway class. **Records** fix that with anonymous, immutable, structurally-typed tuples:

```dart
(int, String) parseStatus(Response r) {
  return (r.statusCode, r.reasonPhrase ?? 'unknown');
}

final (code, message) = parseStatus(response); // destructured on assignment
```

Records support **named fields** too, which reads better for anything non-trivial:

```dart
({double lat, double lng}) currentLocation() => (lat: 30.0444, lng: 31.2357);

final loc = currentLocation();
print('${loc.lat}, ${loc.lng}');
```

They come with structural equality and `hashCode` for free, so two records with the same values are equal — no `==` override to write. The rule of thumb I use: reach for a record when the data is **local and structural** (a function returning a couple of related values), and for a named class when the type is a **domain concept** that deserves a name and a home.

## Sealed classes: a closed set of types

A **sealed class** tells the compiler that every subtype lives in the same library, so it knows the complete set. That single guarantee is what unlocks exhaustiveness. Model something that's "one of a fixed set of shapes" as a sealed hierarchy:

```dart
sealed class Payment {}

class Cash extends Payment {
  final double amount;
  Cash(this.amount);
}

class Card extends Payment {
  final String last4;
  final double amount;
  Card(this.last4, this.amount);
}

class Wallet extends Payment {
  final String provider;
  Wallet(this.provider);
}
```

Now the compiler knows a `Payment` is exactly `Cash`, `Card`, or `Wallet` — nothing else. That knowledge pays off the moment you switch over it.

## Pattern matching: switch expressions that must be exhaustive

Dart 3's `switch` became an **expression** that returns a value, and combined with sealed classes it must handle every case or it won't compile:

```dart
String describe(Payment payment) => switch (payment) {
  Cash(amount: final a) => 'Cash: \$${a.toStringAsFixed(2)}',
  Card(last4: final n, amount: final a) => 'Card ****$n: \$$a',
  Wallet(provider: final p) => 'Wallet via $p',
};
```

Two things are happening at once. The switch **destructures** each case, pulling fields out with the pattern (`amount: final a`), so there's no casting and no field access boilerplate. And because `Payment` is sealed, if I later add a `BankTransfer` subtype and forget to handle it here, **this code stops compiling**. The compiler becomes a checklist for every place that reasons about payments — exactly the safety net you want in a growing app.

Patterns also support guards and destructuring in `if-case`:

```dart
if (payment case Card(amount: final a) when a > 1000) {
  requireExtraVerification();
}
```

## The combination that matters: UI state

Where this all lands in Flutter is modeling screen state. Instead of a class with `isLoading`, `error`, and `data` fields that can contradict each other (loading *and* error at once?), model the states as a sealed hierarchy where illegal combinations simply can't be represented:

```dart
sealed class ProfileState {}
class Loading extends ProfileState {}
class Loaded extends ProfileState {
  final User user;
  Loaded(this.user);
}
class Failed extends ProfileState {
  final String message;
  Failed(this.message);
}
```

Then the widget renders with an exhaustive switch:

```dart
Widget build(BuildContext context) => switch (state) {
  Loading() => const CircularProgressIndicator(),
  Loaded(user: final u) => ProfileView(user: u),
  Failed(message: final m) => ErrorView(message: m, onRetry: _reload),
};
```

There is no `else`, no default that silently swallows a new state, no way to render a `Loaded` view while `isLoading` is somehow true. Add a state, and every `switch` that consumes `ProfileState` lights up until you handle it. This pairs perfectly with the state-management approaches I use in Flutter — it's the same modeling discipline behind [Riverpod vs Bloc in 2026](https://blog.michaelsam94.com/riverpod-vs-bloc-2026/), and it's why I reach for sealed state in [my Riverpod state management write-up](https://blog.michaelsam94.com/flutter-riverpod-state-management/).

## Practical adoption notes

- **Adopt incrementally.** None of this requires a migration. Start using records for multi-value returns today; convert one screen's state to a sealed hierarchy and feel the difference before doing the rest.
- **Prefer sealed over enum-with-fields.** If each variant carries different data, a sealed class beats an enum plus a bag of nullable fields.
- **Let exhaustiveness work for you.** Resist adding a `default` case to sealed switches — the whole point is that removing it makes the compiler catch new variants. A `default` throws that away.
- **Use named record fields for clarity.** Positional records are fine for two closely-related values; beyond that, name them so call sites read well.
- **Destructure at the boundary.** Pull fields out in the pattern rather than accessing them repeatedly in the body; it's cleaner and the intent is obvious.

Dart 3 didn't add features you *have* to learn to keep shipping — it added features that make the code you ship simpler and safer once you do. Records kill the throwaway-class tax, sealed classes make invalid states unrepresentable, and exhaustive switches turn "I forgot to handle that case" from a runtime crash into a compile error. That last shift, in particular, is the kind of thing you stop wanting to live without. These patterns also sit at the heart of what makes Flutter pleasant in 2026, which I covered in [the state of Flutter](https://blog.michaelsam94.com/state-of-flutter-2026/).

## Resources

- [Dart patterns — language documentation](https://dart.dev/language/patterns)
- [Records in Dart](https://dart.dev/language/records)
- [Branches: switch and if-case](https://dart.dev/language/branches)
- [Class modifiers (sealed, final, base)](https://dart.dev/language/class-modifiers)
- [Dart 3 announcement](https://medium.com/dartlang/announcing-dart-3-53f065a10635)
- [Pattern types reference](https://dart.dev/language/pattern-types)
