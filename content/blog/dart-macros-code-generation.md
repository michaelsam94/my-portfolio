---
title: "Dart Macros and the Future of Code Generation"
slug: "dart-macros-code-generation"
description: "Dart macros promised code generation without build_runner. What they were, why the Dart team paused them, and where Dart code generation goes next."
datePublished: "2026-04-21"
dateModified: "2026-04-21"
tags: ["Dart", "Flutter", "Code Generation"]
keywords: "Dart macros, code generation Dart, build_runner replacement, JsonCodable macro, metaprogramming Dart"
faq:
  - q: "What are Dart macros?"
    a: "Dart macros were an experimental metaprogramming feature that let code generate other code at compile time, directly in the language, without a separate build step. The flagship example was a JsonCodable macro that added fromJson and toJson methods to a class just by annotating it — no build_runner, no generated .g.dart file. The feature was previewed but never stabilized."
  - q: "Why did the Dart team pause macros?"
    a: "The Dart team announced in 2025 that they were stopping work on the macros feature, citing that the implementation could not meet the performance and compiler-complexity bar they needed, especially for incremental compilation and IDE responsiveness. Rather than ship a feature that degraded the whole toolchain, they shelved it and redirected effort toward improving the existing code-generation experience."
  - q: "What should I use for code generation in Dart today?"
    a: "The established path remains build_runner with source_gen and packages like json_serializable, freezed, and drift. It's a separate build step that emits .g.dart files, which is more ceremony than macros promised, but it's stable, well-understood, and continually improved. The Dart team is also investing in making that workflow faster and less intrusive."
---

For about a year, Dart macros were the most exciting thing on the language roadmap. The pitch was genuinely great: annotate a class with `@JsonCodable` and get `fromJson`/`toJson` methods generated at compile time, inside the language, with no `build_runner`, no `.g.dart` files, and no `part` directives cluttering your source. Metaprogramming that felt native. Then, in 2025, the Dart team announced they were stopping work on it. If you're picking up the topic now, that reversal *is* the story — and it's a more interesting one than a feature tour would have been.

I followed macros closely because JSON boilerplate and `build_runner` friction are daily annoyances in Flutter work. So this is part post-mortem, part honest assessment of where Dart code generation actually stands, from someone who wanted macros to win.

## What macros were supposed to be

The core idea: a macro is Dart code that runs during compilation and augments your program — adding methods, fields, or whole classes — based on what it sees. The canonical demo was serialization:

```dart
// The promised world — no part file, no build step
import 'package:json/json.dart';

@JsonCodable()
class User {
  final String name;
  final int age;
}

// fromJson / toJson generated automatically at compile time
final user = User.fromJson(jsonData);
```

Compare that to today's reality, where the same class needs a `part 'user.g.dart';` directive, a `build_runner` invocation, and a generated file you commit or gitignore. Macros would have erased all of it. The appeal wasn't just less typing — it was removing an entire out-of-band build tool from the inner loop.

## Why it fell apart

The reason the Dart team gave was fundamentally about performance and complexity, and it's worth taking at face value rather than as a euphemism. A macro system that runs arbitrary code during compilation has to integrate with everything: the incremental compiler, hot reload, the analyzer that powers IDE autocomplete, and the language server that has to stay responsive as you type. Making macros correct *and* fast enough to not degrade that whole experience turned out to be a bar they couldn't clear.

There's a senior-engineering lesson buried here that I respect: they chose not to ship. It's easy to launch an impressive demo; it's disciplined to recognize that a feature which makes every keystroke in the IDE slower is a net negative even when the demo dazzles. Metaprogramming that slows the analyzer would have taxed every Dart developer, every day, to save some of them boilerplate some of the time. Killing it was the right call, even though it stung.

## What this means for your code today

Nothing changes, which is the point. The established stack is still the stack:

| Need | Tool |
|---|---|
| JSON serialization | `json_serializable` |
| Immutable data / unions | `freezed` |
| Local database | `drift` |
| DI / routing codegen | `injectable`, `go_router_builder` |
| Foundation | `build_runner` + `source_gen` |

These all rely on `build_runner` running `source_gen` to emit `.g.dart` / `.freezed.dart` files. It's more ceremony than macros promised, but it is stable, battle-tested, and — crucially — it doesn't slow your editor, because generation happens as an explicit step rather than continuously during analysis. Much of the pattern-matching ergonomics that `freezed` provides for sealed unions are now partly available natively too, which I covered in [Dart 3 patterns, records, and sealed classes](https://blog.michaelsam94.com/dart-3-patterns-records-sealed/) — the language absorbed some of what codegen used to be needed for.

## Living well with build_runner

Since codegen isn't going anywhere, the practical move is to make it hurt less. A few habits that genuinely help:

```bash
# Watch mode regenerates on save — leave it running
dart run build_runner watch --delete-conflicting-outputs

# One-shot build for CI
dart run build_runner build --delete-conflicting-outputs
```

Keep `watch` running in a terminal during development so generation is invisible; the friction people complain about is almost always from running one-shot `build` repeatedly. In a monorepo, the story compounds because you're coordinating generation across packages — I laid out how I structure that in [managing a Flutter monorepo with Melos](https://blog.michaelsam94.com/flutter-monorepo-melos/), where a single `melos run generate` fans out across every package that needs it.

Two more opinions from experience: decide deliberately whether to commit generated files (I gitignore them and generate in CI, which keeps diffs clean), and keep annotated classes small so regeneration is cheap. A 40-field mega-model regenerates slower and merges worse than several focused ones.

## Will macros come back?

The team hasn't slammed the door on metaprogramming as a goal — they've stepped back from *this* implementation. It's plausible a narrower, more constrained form returns later, one that doesn't require running arbitrary code in the analyzer's hot path. But I wouldn't architect anything around that hope. The realistic future of Dart code generation for the next few years is an incrementally faster `build_runner` experience, plus more capability pulled into the language itself (as records and patterns already did), reducing how often you need generation at all.

If you were holding your breath for macros before adopting serialization or a database package — stop holding it. Use `json_serializable`, `freezed`, and `drift` today. They work, they're maintained, and they don't punish your IDE. The dream of annotation-only codegen was real and it was good, but shipping software means building on what exists, not what was demoed. Macros are a case study in a team caring more about the daily experience of every developer than about a headline feature, and honestly, that's the kind of restraint I want from the language I ship production apps in.

## Resources

- [Dart language and codegen documentation](https://dart.dev/tools/build_runner)
- [source_gen package](https://pub.dev/packages/source_gen)
- [json_serializable package](https://pub.dev/packages/json_serializable)
- [freezed package](https://pub.dev/packages/freezed)
- [Dart language GitHub (macros discussion)](https://github.com/dart-lang/language)
- [Dart blog](https://medium.com/dartlang)
