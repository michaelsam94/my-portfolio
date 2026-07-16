---
title: "Kotlin/JS Interop Fundamentals"
slug: "kotlin-js-interop-basics"
description: "Kotlin/JS interop essentials: calling JavaScript from Kotlin with external declarations, dynamic, and the tradeoffs of consuming npm packages safely."
datePublished: "2024-09-24"
dateModified: "2024-09-24"
tags: ["Kotlin", "Kotlin/JS", "Web", "Kotlin Multiplatform"]
keywords: "Kotlin JS interop, external declaration Kotlin, kotlin dynamic type, Kotlin npm, kotlin js typescript definitions"
faq:
  - q: "How do I call a JavaScript library from Kotlin/JS?"
    a: "Declare the library's API with external declarations — external interfaces, classes, and functions that describe the JS shapes without implementing them. The compiler trusts these signatures and emits calls to the underlying JS. For well-typed libraries you can generate declarations from TypeScript definitions with Dukat-style tooling, but hand-writing the small slice you actually use is often more reliable."
  - q: "When should I use the dynamic type in Kotlin/JS?"
    a: "Use dynamic as an escape hatch when a JS value has no stable type you can model — deeply untyped config objects, or rapidly changing APIs. It turns off type checking for that value, so treat it like an unsafe cast and confine it to a small adapter layer. Prefer external declarations everywhere you can, and only drop to dynamic where typing would be fiction."
  - q: "Can I use npm packages in a Kotlin/JS project?"
    a: "Yes. Add the dependency with the npm() helper in your Gradle build, and the Kotlin/JS toolchain wires it through webpack. You still need Kotlin-side external declarations to call it in a typed way. The runtime dependency and the type declarations are separate concerns — npm() provides the code, external declarations describe its shape."
---

Kotlin/JS lets you write Kotlin and run it in a browser or Node, but its real test is how well it talks to the enormous world of existing JavaScript. Interop is where Kotlin/JS earns or loses its keep, because no matter how much Kotlin you write, you'll be calling into `fetch`, a charting library, or some npm package that has no idea Kotlin exists. The fundamentals come down to three tools — **external declarations**, the **`dynamic`** type, and the **npm dependency pipeline** — and knowing which to reach for keeps the boundary type-safe instead of a pile of casts.

## External declarations: describe JS, don't implement it

The idiomatic way to call JavaScript from Kotlin is to *declare* its shape with the `external` keyword. You're telling the compiler "this thing exists at runtime, here's its type, trust me" — and the compiler emits the corresponding JS calls without generating any implementation.

```kotlin
external interface Options {
    var retries: Int
    var timeoutMs: Int
}

external fun fetchJson(url: String, options: Options): dynamic

external class Chart(canvas: HTMLCanvasElement, config: ChartConfig) {
    fun update()
    fun destroy()
}
```

This is the same idea as a TypeScript `.d.ts` declaration file: a typed description of untyped-at-runtime code. The discipline that matters is scope — **declare only the slice of the API you actually use.** I've seen teams try to model an entire charting library's surface up front; it's a waste and it rots. Declare the three methods you call, add more when you call more.

## Building JS config objects cleanly

External interfaces double as a clean way to construct JS options objects. Because they compile to plain JS object literals, you can build them with a small helper instead of assembling untyped maps:

```kotlin
fun options(block: Options.() -> Unit): Options =
    (js("{}") as Options).apply(block)

val opts = options {
    retries = 3
    timeoutMs = 5000
}
```

This pattern — `js("{}")` cast to the external interface, configured with an `apply` block — gives you a typed, DSL-ish way to produce the config objects JS libraries expect, without hand-writing object literals everywhere.

## dynamic: the deliberate escape hatch

Sometimes a JS value genuinely has no stable type worth modeling — a config blob, a loosely-typed event payload, an API that changes shape between versions. That's what `dynamic` is for. A `dynamic` value skips type checking entirely: you can call any method and read any property, and it's your problem if it's wrong at runtime.

```kotlin
val response: dynamic = fetchJson("/api/user", opts)
val name: String = response.profile.displayName as String   // no compile-time safety here
```

`dynamic` is powerful and dangerous in equal measure. My rule: **confine it to a thin adapter layer** that immediately converts the untyped value into a proper Kotlin data class. Don't let `dynamic` flow into your business logic — parse it at the edge, validate, and hand the rest of the app real types. Treated as a boundary tool it's fine; treated as a lifestyle it throws away the reason you chose Kotlin.

## Consuming npm packages

Runtime code and type declarations are separate concerns, and Kotlin/JS keeps them separate. You pull the actual JavaScript in through Gradle:

```kotlin
kotlin {
    js(IR) {
        browser()
        binaries.executable()
    }
    sourceSets {
        val jsMain by getting {
            dependencies {
                implementation(npm("date-fns", "3.6.0"))
            }
        }
    }
}
```

`npm()` makes the package available at runtime via the toolchain's webpack integration. It does *not* give you types — for that you still write `external` declarations describing the functions you call. So consuming an npm package is two steps: `npm()` for the code, external declarations for the shape. Keeping them mentally separate avoids the common confusion of "I added the dependency, why can't I call it?" — you added the code, now describe it.

## Generating declarations vs writing them

For libraries that ship TypeScript definitions, tooling can generate Kotlin external declarations from the `.d.ts` files. It sounds like a free win, but generated declarations are often verbose, occasionally incorrect for exotic TS types, and drift when you upgrade. My honest take after doing both: for a small, well-understood API surface, **hand-write the declarations for exactly what you use** — it's a few minutes and you understand every line. Reach for generation only when the surface is large and you'd otherwise transcribe hundreds of methods.

| Approach | Best when | Watch out for |
| --- | --- | --- |
| Hand-written external declarations | You use a small, stable slice | Manual upkeep on upgrades |
| Generated from `.d.ts` | Large API surface | Verbosity, edge-case type errors, drift |
| `dynamic` | No stable type to model | Zero compile-time safety |

## How this connects to multiplatform

If your Kotlin/JS target is part of a Kotlin Multiplatform project, keep the JS interop confined to the `jsMain` source set and expose a clean, typed Kotlin API to common code — ideally an interface bound per platform, the same separation described in [expect/actual patterns that scale](https://blog.michaelsam94.com/kotlin-multiplatform-expect-actual-patterns/). Common code should never see `dynamic` or `external`; those are `jsMain` implementation details. That boundary is what lets the same shared logic run on Android, iOS, and the web without leaking JS-isms upward.

## What I'd take away

Kotlin/JS interop is mostly about drawing a clean, typed boundary around untyped JavaScript. Describe the JS you call with `external` declarations, and declare only what you use. Use `dynamic` as a deliberate, narrow escape hatch confined to an adapter layer that immediately produces real Kotlin types. Pull runtime code with `npm()` and remember it's separate from typing. Hand-write declarations for small surfaces; generate for large ones and expect to fix a few. Do that and the vast JS ecosystem becomes callable from Kotlin without surrendering the type safety that made you pick Kotlin in the first place.

## Resources

- [Kotlin/JS — using JavaScript from Kotlin (external declarations)](https://kotlinlang.org/docs/js-interop.html)
- [Kotlin dynamic type](https://kotlinlang.org/docs/dynamic-type.html)
- [Kotlin/JS — using dependencies (npm)](https://kotlinlang.org/docs/js-project-setup.html)
- [MDN — JavaScript reference](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference)
