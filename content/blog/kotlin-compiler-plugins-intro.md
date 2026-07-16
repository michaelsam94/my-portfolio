---
title: "Getting Started with Kotlin Compiler Plugins"
slug: "kotlin-compiler-plugins-intro"
description: "How Kotlin compiler plugins work beyond KSP: FIR frontend extensions, IR backend transforms, what plugins like Compose and all-open actually do, and the K2 shift."
datePublished: "2024-06-16"
dateModified: "2024-06-16"
tags: ["Kotlin", "Compiler", "Tooling"]
keywords: "Kotlin compiler plugin, FIR IR, K2 compiler, IrGenerationExtension, compiler plugin tutorial, Compose compiler"
faq:
  - q: "What is the difference between a KSP processor and a compiler plugin?"
    a: "A KSP processor can only read code and generate new files; it cannot modify existing declarations or their bodies. A compiler plugin operates inside the compiler and can change the frontend model (add declarations, alter resolution) and rewrite the IR (transform method bodies). Compose, all-open, and kotlinx.serialization need compiler plugins precisely because they modify existing code, which KSP cannot do."
  - q: "What are FIR and IR in the Kotlin compiler?"
    a: "FIR (Frontend Intermediate Representation) is the K2 frontend's model of your program used for resolution and type checking, where a plugin can add synthetic declarations or influence resolution. IR (Intermediate Representation) is the backend model that gets lowered to JVM bytecode, JS, or native, where a plugin can rewrite the actual bodies of functions. Plugins hook one or both stages depending on what they need to do."
  - q: "Are Kotlin compiler plugin APIs stable?"
    a: "No. The compiler plugin APIs, especially around FIR and IR, are explicitly unstable and change between Kotlin versions, which is why very few third-party compiler plugins exist compared to KSP processors. If you write one you should expect to update it for new Kotlin releases. For most needs KSP is the stable, supported choice; reach for a compiler plugin only when you must modify existing code."
---

A Kotlin compiler plugin does the thing KSP fundamentally can't: it modifies *existing* code. KSP reads your program and generates new files alongside it, but it cannot change a declaration or rewrite a function body. Compiler plugins run *inside* the compiler, so they can add synthetic members, influence type resolution, and transform the actual bodies of your functions before they become bytecode. That's why Jetpack Compose, `kotlinx.serialization`, `all-open`, and `no-arg` are compiler plugins and not KSP processors — every one of them needs to alter code that already exists, not just append to it.

The honest caveat up front: the compiler plugin APIs are *unstable* and change between Kotlin versions. That's the reason there are thousands of KSP processors and only a handful of third-party compiler plugins. But understanding how they work demystifies a lot of Kotlin "magic" — and occasionally you have a problem that genuinely requires one. Here's the model.

## Two stages: FIR (frontend) and IR (backend)

The K2 compiler processes your code in two stages a plugin can hook:

- **FIR — Frontend Intermediate Representation.** This is where resolution and type checking happen. A FIR plugin can add *synthetic declarations* (members that don't appear in source but exist to the type checker), alter how names resolve, and generate signatures. It shapes what the compiler *believes* your program contains.
- **IR — Intermediate Representation.** This is the backend model, close to the target (JVM bytecode, JS, native). An IR plugin rewrites the *bodies* — the actual instructions. It can wrap a function, inject calls, replace expressions.

The division matters because it determines what your plugin can do. Need to make the type checker see an extra method? That's FIR. Need to change what a function actually *does* at runtime? That's IR. Many real plugins use both: declare a synthetic member in FIR so code type-checks, then fill in its body in IR.

## What the well-known plugins actually do

Grounding this in plugins you've used:

- **`all-open` / `kotlin-spring`**: FIR-level. Spring needs classes to be non-final to create proxies, but Kotlin classes are final by default. The plugin makes annotated classes open without you writing `open` everywhere. Pure declaration modification.
- **`no-arg` / JPA**: generates a synthetic no-argument constructor JPA needs, without exposing it to your code. Synthetic declaration.
- **`kotlinx.serialization`**: generates serializer classes and the `serialize`/`deserialize` logic. It both adds declarations (FIR) and generates bodies (IR).
- **Compose compiler**: the deepest example — it rewrites every `@Composable` function's body (IR) to thread through the `$composer` parameter, insert recomposition scopes, and track state reads. The transformation behind Compose's [recomposition and skipping](https://blog.michaelsam94.com/kotlin-immutable-collections-kotlinx/) is entirely a compiler-plugin body rewrite you never see in source.

Once you know Compose is an IR transform inserting bookkeeping into your functions, its performance model stops being mysterious — the compiler literally edits your composables.

## The shape of an IR plugin

The entry point is a `CompilerPluginRegistrar` that registers extensions. An IR transform registers an `IrGenerationExtension`:

```kotlin
class MyPluginRegistrar : CompilerPluginRegistrar() {
    override val supportsK2 = true
    override fun ExtensionStorage.registerExtensions(config: CompilerConfiguration) {
        IrGenerationExtension.registerExtension(MyIrExtension())
    }
}

class MyIrExtension : IrGenerationExtension {
    override fun generate(module: IrModuleFragment, pluginContext: IrPluginContext) {
        module.transform(MyTransformer(pluginContext), null)
    }
}
```

The `MyTransformer` extends `IrElementTransformerVoid` and overrides visit methods to rewrite nodes — for example, wrapping every function annotated `@Logged` so it logs entry and exit:

```kotlin
override fun visitFunctionNew(declaration: IrFunction): IrStatement {
    if (declaration.hasAnnotation(LOGGED_FQN)) {
        // build IR that prepends a log call to the body
        declaration.body = wrapWithLogging(declaration)
    }
    return super.visitFunctionNew(declaration)
}
```

Building IR by hand is the hard part: you construct calls, references, and expressions against the `IrPluginContext`, which resolves symbols for the functions you want to call. It's low-level and verbose, and it's where the API instability bites hardest — the IR builders shift between versions.

## Delivering the plugin to the build

A compiler plugin ships in two halves: the plugin implementation (loaded by the compiler) and a Gradle plugin that registers it with the Kotlin compile tasks and passes options. The Gradle side implements `KotlinCompilerPluginSupportPlugin`, telling Gradle which artifact is the compiler plugin and wiring any options through `SubpluginOption`. This is more moving parts than a KSP processor, which is just a dependency plus a service file — another reason to prefer KSP when it suffices.

## The K2 shift you can't ignore

K2 rebuilt the frontend around FIR, and it changed the plugin story significantly. Plugins written for the old (K1) frontend don't automatically work with FIR; a plugin declares `supportsK2 = true` only once it's been adapted. If you're maintaining a compiler plugin, K2 support is the migration that matters, and the FIR APIs for generating synthetic declarations are different from the old descriptor-based approach. New plugins should target FIR from the start. This is the single biggest reason to check a plugin's Kotlin-version compatibility before depending on it.

## When to actually reach for one

Be honest with yourself about the decision:

| You need to... | Use |
|---|---|
| Generate new files from annotations | KSP |
| Read code, emit companion code | KSP |
| Make existing classes open / add constructors | compiler plugin (FIR) |
| Rewrite function bodies (instrumentation, DSLs) | compiler plugin (IR) |
| Change type resolution / add synthetic members | compiler plugin (FIR) |

The vast majority of "I want to automate this boilerplate" problems are KSP problems — you're generating adjacent code, not modifying existing code. Reach for a compiler plugin only when you genuinely must alter code in place, and go in expecting to maintain it across Kotlin releases. The payoff, when it fits, is enormous: Compose and serialization exist because a compiler plugin can do what no library API could. But the cost — unstable APIs, low-level IR construction, per-version maintenance — is real, so it's a deliberate choice, not a default. When you can get there with a [KSP processor](https://blog.michaelsam94.com/kotlin-symbol-processing-ksp-guide/), that's almost always the better trade.

## Resources

- [Kotlin compiler plugins overview](https://kotlinlang.org/docs/all-open-plugin.html)
- [K2 compiler and FIR (Kotlin blog)](https://blog.jetbrains.com/kotlin/2024/03/k2-compiler-performance-benchmarks-and-how-to-measure-them-on-your-projects/)
- [Writing Your First Kotlin Compiler Plugin (Kevin Most talk notes)](https://github.com/kevinmost/devfest-2018-compiler-plugin)
- [Compose compiler documentation](https://developer.android.com/develop/ui/compose/compiler)
