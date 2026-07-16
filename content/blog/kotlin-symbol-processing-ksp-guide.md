---
title: "Writing a KSP Processor: A Practical Guide"
slug: "kotlin-symbol-processing-ksp-guide"
description: "Build a Kotlin Symbol Processing plugin from scratch: the SymbolProcessor lifecycle, resolving symbols, generating code, incremental processing, and testing."
datePublished: "2024-06-14"
dateModified: "2024-06-14"
tags: ["Kotlin", "KSP", "Tooling"]
keywords: "KSP processor, Kotlin Symbol Processing, code generation Kotlin, SymbolProcessor, CodeGenerator, incremental processing"
faq:
  - q: "What is KSP and why use it over annotation processing?"
    a: "KSP (Kotlin Symbol Processing) is Google's API for reading Kotlin code and generating new code at compile time. Unlike KAPT, which generates Java stubs and runs the Java annotation processor, KSP understands Kotlin directly — nullability, extension functions, coroutines — and is typically about twice as fast because it skips stub generation. New processors should target KSP."
  - q: "What does a SymbolProcessor's process function return?"
    a: "It returns a list of KSAnnotated symbols that could not be processed in the current round, usually because they depend on symbols that haven't been generated yet. KSP re-invokes process in a later round with those deferred symbols once their dependencies exist. Returning an empty list means everything was handled and no further rounds are needed for your processor."
  - q: "How do you make a KSP processor incremental?"
    a: "You declare dependencies when writing each generated file by passing the source KSFiles that the output depends on to the Dependencies object. KSP uses that graph to regenerate only the outputs whose inputs changed, rather than reprocessing everything. Getting the dependency set right is what keeps incremental builds correct and fast."
---

KSP lets you read Kotlin source at compile time and generate new Kotlin from it — the mechanism behind Room, Moshi, Ktorfit, and most modern annotation-driven libraries. You write a `SymbolProcessor` that KSP hands a model of the program's declarations; you inspect the ones you care about (usually those carrying your annotation) and emit generated files. The reason to learn it: when you find yourself writing the same boilerplate by hand across dozens of classes, a small KSP processor generates it correctly every time, checked against the real types. And unlike the older KAPT, KSP understands Kotlin natively and runs roughly twice as fast because it never generates Java stubs.

I've written processors to generate mappers, DI factories, and serialization glue, and the learning curve is front-loaded: the concepts (rounds, deferral, incremental dependencies) are unfamiliar, but once they click, a processor is a couple hundred lines of straightforward code. Here's the shape of one, end to end.

## The two pieces: provider and processor

A KSP plugin is a `SymbolProcessorProvider` (the factory KSP discovers via a service file) that creates your `SymbolProcessor`:

```kotlin
class BuilderProcessorProvider : SymbolProcessorProvider {
    override fun create(env: SymbolProcessorEnvironment): SymbolProcessor =
        BuilderProcessor(env.codeGenerator, env.logger)
}

class BuilderProcessor(
    private val codeGenerator: CodeGenerator,
    private val logger: KSPLogger,
) : SymbolProcessor {
    override fun process(resolver: Resolver): List<KSAnnotated> {
        // find symbols, generate code, return anything deferred
        return emptyList()
    }
}
```

You register the provider by putting its fully-qualified name in `resources/META-INF/services/com.google.devtools.ksp.processing.SymbolProcessorProvider`. That service file is how KSP finds your processor — forget it and nothing runs, silently, which is the first gotcha everyone hits.

## Finding symbols with the Resolver

The `Resolver` is your query interface into the program. The common entry point is "give me everything annotated with X":

```kotlin
override fun process(resolver: Resolver): List<KSAnnotated> {
    val symbols = resolver
        .getSymbolsWithAnnotation("com.example.GenerateBuilder")
        .filterIsInstance<KSClassDeclaration>()

    val deferred = symbols.filterNot { it.validate() }   // not ready this round

    symbols.filter { it.validate() }.forEach { generateBuilder(it) }

    return deferred.toList()
}
```

Two important habits are visible here. First, filter to the declaration kind you expect (`KSClassDeclaration` for a class-level annotation) — the annotation can appear in places you don't handle. Second, `validate()` checks whether a symbol's types are fully resolvable *right now*; if a symbol references a type that another processor hasn't generated yet, it isn't ready, and you defer it by returning it. KSP will call `process` again in a later round once more code exists. That deferral-and-rounds model is how processors cooperate when one's output is another's input.

## Reading the model

Once you have a `KSClassDeclaration`, you walk its properties and types to decide what to generate:

```kotlin
private fun generateBuilder(cls: KSClassDeclaration) {
    val props = cls.getAllProperties()
        .filter { it.hasBackingField }
        .map { it.simpleName.asString() to it.type.resolve() }
        .toList()
    // ... use props to emit a builder ...
}
```

`type.resolve()` gives you a `KSType` you can inspect for nullability (`isMarkedNullable`), type arguments, and the declaration it points to. This is where KSP's Kotlin-awareness pays off over KAPT: you see nullability, `suspend` modifiers, default values, and extension receivers as first-class facts, not erased Java approximations. You're reasoning about the actual Kotlin, which is exactly why it's the right foundation for tools like [Ktorfit's networking generation](https://blog.michaelsam94.com/kotlin-multiplatform-networking-ktorfit/).

## Generating code (and declaring dependencies)

You emit files through the `CodeGenerator`, and this is where incrementality lives. When you create a file, you tell KSP which source files it depends on:

```kotlin
private fun writeBuilder(cls: KSClassDeclaration, code: String) {
    val file = codeGenerator.createNewFile(
        dependencies = Dependencies(
            aggregating = false,
            sources = arrayOf(cls.containingFile!!),  // this output depends on this source
        ),
        packageName = cls.packageName.asString(),
        fileName = "${cls.simpleName.asString()}Builder",
    )
    file.bufferedWriter().use { it.write(code) }
}
```

The `Dependencies` object is the incremental-build contract. By declaring that `FooBuilder.kt` depends on `Foo.kt`, KSP knows to regenerate it only when `Foo.kt` changes. Get this wrong — omit a real dependency — and you'll ship stale generated code on incremental builds; over-declare (`aggregating = true` when it's not) and you'll regenerate too much. `aggregating = true` is for outputs that depend on *all* matching inputs (like a generated registry of everything annotated), `false` for per-source outputs. Most builders are `false`.

For the actual code string, hand-concatenating Kotlin is painful past trivial cases. Use **KotlinPoet**, which builds Kotlin source via a typed API and handles imports, formatting, and escaping:

```kotlin
val builder = TypeSpec.classBuilder("${name}Builder")
    .addFunction(/* ... */)
    .build()
FileSpec.builder(pkg, "${name}Builder").addType(builder).build()
    .writeTo(codeGenerator, aggregating = false)
```

KotlinPoet's `writeTo(codeGenerator, ...)` overload wires the dependency declaration for you, which is another reason to use it over raw strings.

## Testing without a full build

The workflow that makes processor development bearable is **kotlin-compile-testing** (the KSP-supporting fork), which compiles source snippets with your processor in-process and lets you assert on the generated output:

```kotlin
@Test fun `generates a builder`() {
    val result = KotlinCompilation().apply {
        sources = listOf(SourceFile.kotlin("Foo.kt", "..."))
        symbolProcessorProviders = listOf(BuilderProcessorProvider())
        inheritClassPath = true
    }.compile()

    assertEquals(ExitCode.OK, result.exitCode)
    // assert the generated file exists and contains what you expect
}
```

Without this you're doing full Gradle builds to test each change, which is miserably slow. In-process compilation tests turn the loop into seconds. Log diagnostics through the injected `KSPLogger` (`logger.error(msg, symbol)`) so that malformed input produces a clear compile error pointing at the offending declaration, not a confusing stack trace.

## What to keep in mind

A few hard-won rules:

- **The service file is mandatory and easy to forget.** No `META-INF/services` entry, no processing, no error.
- **Respect rounds and `validate()`.** Defer symbols that aren't ready; don't assume everything exists in round one.
- **Declare dependencies honestly** or incremental builds go wrong in ways that are maddening to debug.
- **Prefer KotlinPoet** over string building once you're past a toy.
- **Test with in-process compilation** from the first day.

KSP is one of those tools where the payoff scales with how much repetitive, mechanical code your codebase has. A processor is an investment — you're writing a compiler plugin, effectively — but for the right problem it replaces error-prone hand-written boilerplate with generated code that's correct by construction and stays in sync with your types automatically. When the boilerplate is *behavioral* rather than structural, you graduate to full [Kotlin compiler plugins](https://blog.michaelsam94.com/kotlin-compiler-plugins-intro/); KSP is the pragmatic first stop for code generation.

## Resources

- [Kotlin Symbol Processing (KSP) documentation](https://kotlinlang.org/docs/ksp-overview.html)
- [KSP quickstart and API (Google)](https://kotlinlang.org/docs/ksp-quickstart.html)
- [KotlinPoet — Kotlin code generation](https://square.github.io/kotlinpoet/)
- [kotlin-compile-testing (with KSP support)](https://github.com/tschuchortdev/kotlin-compile-testing)
