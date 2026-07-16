---
title: "Null Safety Across Kotlin/Java Interop"
slug: "android-strict-null-safety-java-interop"
description: "Kotlin's null safety stops at the Java boundary. Learn platform types, @Nullable/@NonNull annotations, strict null checks in Gradle, and patterns that prevent NPEs from Java APIs."
datePublished: "2024-08-21"
dateModified: "2024-08-21"
tags: ["Android", "Kotlin", "Java", "Null Safety"]
keywords: "Kotlin Java interop, platform types, Nullable NonNull, strict null checks, Android NPE, JetBrains annotations"
faq:
  - q: "What is a platform type in Kotlin?"
    a: "When Kotlin calls Java code without nullability annotations, the return type becomes a platform type — written as String! in IDE hints. The compiler treats it as both nullable and non-null, pushing the safety decision to you. Calling .length on an unguarded platform type causes an NPE if Java returned null."
  - q: "How do I enable strict null checking for Java interop?"
    a: "Add -Xjsr305=strict or -Xjsr305=warn to Kotlin compiler options in Gradle. strict treats unannotated Java types as nullable unless marked @NonNull, catching more issues at compile time. Also enable Android's null-safe annotations in libraries you control."
  - q: "Should I use !! on platform types?"
    a: "Avoid !! on platform types from Java APIs — that's where most production NPEs originate in mixed codebases. Prefer explicit null checks, safe calls, or requireNotNull with a message identifying the Java source. If a Java API guarantees non-null, add @NonNull to its declaration."
---

The worst NPEs in Kotlin Android apps don't come from Kotlin code — they come from Java. A `findViewById` that returns null on a stale reference, a Retrofit callback with a missing body, a legacy SDK method documented as "never null" that returns null on error. Kotlin's type system ends at the Java boundary, and the compiler silently gives you platform types that look safe but aren't.

## Platform types explained

When you call Java from Kotlin:

```java
// Java — LegacyApi.java
public String getDisplayName(User user) {
    return user != null ? user.getName() : null;
}
```

```kotlin
// Kotlin caller
val name: String = LegacyApi.getDisplayName(user) // platform type String!
println(name.length) // NPE if Java returned null — no compile warning
```

The IDE shows `String!` — the exclamation mark means "nullability unknown." Kotlin won't force you to check.

## Annotation-driven nullability

Java libraries that use `@Nullable` and `@NonNull` (JetBrains, AndroidX, JSR-305) propagate into Kotlin:

```java
import org.jetbrains.annotations.NotNull;
import org.jetbrains.annotations.Nullable;

public class SafeApi {
    @NotNull
    public String requiredId() { return "abc"; }

    @Nullable
    public String optionalLabel() { return null; }
}
```

```kotlin
val id: String = SafeApi.requiredId()       // non-null String
val label: String? = SafeApi.optionalLabel() // nullable String?
```

If you maintain Java code in a mixed project, annotate every public method. It's the highest-leverage fix for interop NPEs.

## Strict JSR-305 mode

In `build.gradle.kts`:

```kotlin
kotlin {
    compilerOptions {
        freeCompilerArgs.add("-Xjsr305=strict")
    }
}
```

| Mode | Unannotated Java return | Effect |
|------|------------------------|--------|
| Default | Platform type | No enforcement |
| warn | Treated nullable | Warning on unsafe use |
| strict | Treated nullable | Compile error on unsafe use |

`strict` breaks builds on careless platform type usage — exactly what you want when migrating a Java codebase to Kotlin incrementally.

## Android-specific patterns

**findViewById / ViewBinding:** ViewBinding eliminates this class of bug entirely. If you're still on findViewById in Java fragments, Kotlin callers get platform types.

```kotlin
// Before — platform type NPE risk
val textView = view.findViewById<TextView>(R.id.title)

// After — ViewBinding
val binding = FragmentHomeBinding.bind(view)
binding.title.text = "Hello" // always non-null view reference
```

**Bundle and Intent extras:**

```kotlin
val userId = requireArguments().getString(ARG_USER_ID)
    ?: throw IllegalArgumentException("userId required")
```

Never assume `getString` is non-null — Java put nothing there.

**Retrofit responses:**

```kotlin
interface Api {
    @GET("user/{id}")
    suspend fun getUser(@Path("id") id: String): User // Kotlin — non-null contract
}

// Java callback style — platform types everywhere
api.getUser(id).enqueue(object : Callback<User> {
    override fun onResponse(call: Call<User>, response: Response<User>) {
        val body = response.body() // User! — check before use
        body?.let { updateUi(it) }
    }
    override fun onFailure(call: Call<User>, t: Throwable) { /* ... */ }
})
```

## Wrapping Java APIs in Kotlin

When a Java SDK lacks annotations, wrap it:

```kotlin
class LocationClient(private val javaClient: com.vendor.LocationClient) {

    fun currentCity(): String? =
        javaClient.getCity()?.takeIf { it.isNotBlank() }

    fun requireCity(): String =
        currentCity() ?: error("LocationClient returned null city")
}
```

The wrapper is the single place you absorb Java null ambiguity. Everything above it uses proper Kotlin types.

## @JvmSuppressWildcards and nullability in generics

Java's `List<String>` at the Kotlin boundary becomes `List<String!>` elements. When passing Kotlin lists to Java:

```kotlin
fun processItems(items: List<String>) { /* ... */ }

// Java sees List<? extends String> by default
// Use @JvmSuppressWildcards if Java expects mutable List<String>
fun acceptItems(items: List<@JvmSuppressWildcards String>) { /* ... */ }
```

Generic nullability mismatches cause subtle ClassCastException and NPE at collection boundaries, not on individual calls.

## Lint and static analysis

Enable Android Lint's `UnknownNullness` check. Detekt's `UnsafeCallOnNullableType` catches some `!!` abuse. None replace `-Xjsr305=strict` for Java sources — run all three on CI.

My rule when reviewing mixed PRs: any new Java public API without `@Nullable`/`@NonNull` gets a comment. Any Kotlin `!!` on a platform type gets blocked.

## Migration playbook for legacy Java modules

Rolling strict null safety across a large Android codebase:

1. **Enable `-Xjsr305=strict` in a dedicated CI job** — don't block main builds initially; report platform type count per module
2. **Annotate leaf modules first** — utilities with few dependents
3. **Add Kotlin facades** — wrap unannotated SDKs before touching feature code
4. **Track `!!` count per module** — fail CI if count increases

```kotlin
// Gradle task: count platform type usages (conceptual)
tasks.register("nullSafetyReport") {
    // detekt or custom lint rule output
}
```

Expect 2–4 weeks per major module. Don't enable strict mode and rewrite everything in one PR — merge conflicts will block the team for months.

## Common crash signatures

| Stack trace | Root cause | Fix |
|-------------|------------|-----|
| NPE in Kotlin calling Java | Missing `@Nullable` | Annotate Java or wrap |
| NPE on `findViewById` | View not in layout variant | Nullable binding + early return |
| `IllegalStateException: lateinit` | Init order vs lifecycle | `by lazy` or nullable |
| Generic NPE in `List.get` | Java raw list | `@JvmSuppressWildcards` + filter |

Crashlytics breadcrumbs showing Java class names in Kotlin stack frames usually mean platform type leak — grep the calling Kotlin file for implicit null assumptions.

Pair with [Android strict mode debugging](https://blog.michaelsam94.com/android-strictmode-debugging/) for detecting main-thread violations alongside null issues during development.

## Common production mistakes

Teams get strict null safety java interop wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Shipping strict null safety java interop on Android fails quietly when you test only on flagship devices, skip process-death scenarios, or assume `minSdk` behavior matches latest API docs. Emulator-only validation misses OEM-specific battery optimizations and background execution limits.

## Resources

- [Kotlin Java interop — nullability annotations](https://kotlinlang.org/docs/java-to-kotlin-nullability-guide.html)
- [JSR-305 compiler flag documentation](https://kotlinlang.org/docs/gradle-configure-project.html#gradle-java-toolchain-support)
- [JetBrains @Nullable / @NotNull](https://www.jetbrains.com/help/idea/nullable-and-notnull-annotations.html)
- [Android ViewBinding migration guide](https://developer.android.com/topic/libraries/view-binding)
- [AndroidX null-safe annotations](https://developer.android.com/reference/kotlin/androidx/annotation/Nullable)
