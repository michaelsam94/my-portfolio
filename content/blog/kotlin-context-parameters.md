---
title: "Kotlin 2.4 Context Parameters in Practice"
slug: "kotlin-context-parameters"
description: "Kotlin 2.4 context parameters explained with real examples: cleaner dependency passing, scoped APIs, how they differ from context receivers, and when to use them."
datePublished: "2026-03-20"
dateModified: "2026-03-20"
tags: ["Kotlin", "Language Features", "API Design", "Android"]
keywords: "Kotlin context parameters, Kotlin 2.4, context receivers, Kotlin scoping, dependency passing, Kotlin"
faq:
  - q: "What are context parameters in Kotlin?"
    a: "Context parameters are declared function or property dependencies that the compiler supplies implicitly from the calling scope, using the 'context(...)' syntax. They let you pass ambient dependencies like a logger, dispatcher, or transaction without threading them through every parameter list."
  - q: "How are context parameters different from context receivers?"
    a: "Context parameters are the redesigned, stabilized replacement for the experimental context receivers. They can be named and don't implicitly become the receiver 'this', which removes the ambiguity and scoping problems that kept context receivers experimental."
  - q: "When should I use context parameters instead of regular parameters?"
    a: "Use them for cross-cutting, ambient dependencies that many functions in a call chain need — logging, coroutine scope, database session, analytics. Use regular parameters for the actual data a function operates on. Overusing context parameters hides dependencies and hurts readability."
---

Every Kotlin codebase eventually grows functions whose signatures are half real arguments and half plumbing — a `Logger` here, a `CoroutineScope` there, a database `Transaction` threaded through six layers just so the bottom one can use it. Context parameters, stabilized in Kotlin 2.4, are the language's answer to that plumbing. They let you declare "this function needs a logger in scope" and have the compiler supply it implicitly, without adding it to the ordinary parameter list.

I was skeptical of the earlier `context receivers` experiment — it had real sharp edges — but the redesigned context parameters fix the problems that kept it out of stable releases. Here's how they work and, more importantly, when they're the right tool.

## The syntax and the idea

You declare a context requirement with `context(...)` before a function or property. Callers don't pass it explicitly; the compiler resolves it from the enclosing scope.

```kotlin
interface Logger { fun log(msg: String) }

context(logger: Logger)
fun saveUser(user: User) {
    logger.log("saving ${user.id}")
    repository.insert(user)
}

// Calling it: a Logger must be in scope
context(consoleLogger: Logger)
fun handleRequest(user: User) {
    saveUser(user)   // logger flows implicitly, no need to pass it
}
```

The key improvement over the old context receivers: **context parameters are named** (`logger` here) and do *not* silently become `this`. With context receivers you got an anonymous receiver that could collide with other receivers and make it unclear which `this` you were calling on. Naming removes that ambiguity — you refer to `logger` explicitly — while the compiler still handles the wiring.

## What it's actually good for

The honest framing: context parameters are for **ambient, cross-cutting dependencies**, not for data. A dependency qualifies when it's needed by many functions in a call chain, it's environmental rather than the subject of the computation, and threading it manually adds noise without adding meaning. Classic fits:

- A `Logger` or telemetry span you want available throughout a request path.
- A `CoroutineScope` or dispatcher for structured concurrency.
- A database `Session`/`Transaction` scoped to a unit of work.
- An analytics or feature-flag context.

Contrast with the `User` in the example above — that's *data*, the thing the function operates on, so it stays a regular parameter. The line I use: if removing it changes *what* the function computes, it's a real parameter; if it only changes *how/where* the computation is observed or resourced, it's a candidate for a context parameter.

## A scoped-API example

Where this shines is designing DSLs and scoped APIs. Say you want an analytics API where events can only be logged inside an initialized session:

```kotlin
class AnalyticsSession(val userId: String) {
    fun track(event: String, props: Map<String, Any> = emptyMap()) { /* ... */ }
}

context(session: AnalyticsSession)
fun trackScreenView(name: String) =
    session.track("screen_view", mapOf("screen" to name))

fun withAnalytics(userId: String, block: context(AnalyticsSession) () -> Unit) {
    with(AnalyticsSession(userId)) { block() }
}

// Usage — trackScreenView only compiles inside the session scope
withAnalytics(userId = "u_42") {
    trackScreenView("Home")
    trackScreenView("Settings")
}
```

`trackScreenView` is *only callable* where an `AnalyticsSession` is in context. The compiler enforces the scoping — you can't accidentally track an event without a session — and the call sites stay clean because the session isn't repeated on every line. That combination of compile-time safety plus low ceremony is the sweet spot.

## Context parameters vs the alternatives

There are several ways to pass ambient dependencies in Kotlin, and context parameters don't replace all of them:

| Approach | Best for | Downside |
|---|---|---|
| Regular parameters | The actual data | Verbose for cross-cutting deps |
| Constructor injection (Hilt/DI) | Object-lifetime deps | Awkward for call-scoped deps |
| Context parameters | Call-scoped ambient deps | Can hide dependencies if overused |
| `CompositionLocal` (Compose) | UI-tree ambient values | Compose-only |

Notice DI and context parameters aren't rivals — [Hilt](https://blog.michaelsam94.com/hilt-dependency-injection-patterns/) is great for dependencies tied to an object's lifetime (a repository injected into a ViewModel), while context parameters excel for dependencies scoped to a *call* (a transaction open for this operation only). I use both, for different jobs.

## The failure mode: hidden dependencies

The obvious risk is the same one that makes global state dangerous — context parameters can make a function's real dependencies *implicit*. Read `saveUser` in isolation and you might not notice it needs a `Logger` unless you look at the `context(...)` clause. Overuse it and you get functions whose behavior depends on invisible ambient state, which is exactly what makes code hard to reason about.

My guardrails, learned partly from watching context receivers get misused:

- Keep the set of context types small and well-known across the codebase — a handful of "everyone knows what this is" types, not a grab bag.
- Never put *data* in context. If it's the input to the computation, it's a parameter.
- Prefer context parameters for genuinely orthogonal concerns (logging, tracing, transactions) where explicit threading would be pure noise.
- Name them clearly; the naming is the feature, so use it to document intent.

## Does it fit multiplatform and coroutines?

Yes on both. Context parameters are a language feature, so they work across [Kotlin Multiplatform](https://blog.michaelsam94.com/kotlin-multiplatform-production-guide/) targets, which makes them handy for shared-module APIs that need a platform-provided ambient (say, a shared logger with platform-specific sinks). And they pair naturally with [coroutines and Flow patterns](https://blog.michaelsam94.com/kotlin-coroutines-flow-patterns/) — a `CoroutineScope` or a custom coroutine context wrapper as a context parameter reads cleanly and keeps structured concurrency explicit-but-tidy.

## The verdict

Context parameters are a genuinely useful addition once you internalize the boundary: they're for ambient, cross-cutting, call-scoped dependencies, and nothing else. Used that way they remove real boilerplate and let you build scoped APIs that the compiler polices for you. Reach past that boundary — start hiding data or piling on context types — and you've just reinvented implicit global state with nicer syntax. Kept disciplined, they're one of the better ergonomics wins in recent Kotlin.

## Resources

- [Kotlin context parameters documentation](https://kotlinlang.org/docs/context-parameters.html)
- [KEEP: context parameters proposal](https://github.com/Kotlin/KEEP/blob/master/proposals/context-parameters.md)
- [Kotlin language releases](https://kotlinlang.org/docs/releases.html)
- [Kotlin coroutines documentation](https://kotlinlang.org/docs/coroutines-overview.html)
- [The Kotlin Blog](https://blog.jetbrains.com/kotlin/)
