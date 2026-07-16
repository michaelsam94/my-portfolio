---
title: "Kotlin Delegation: The `by` Keyword in Practice"
slug: "kotlin-delegation-by-keyword-patterns"
description: "How Kotlin's by keyword handles class and property delegation, what the compiler generates, and the composition patterns that beat inheritance in real code."
datePublished: "2024-06-04"
dateModified: "2024-06-04"
tags: ["Kotlin", "Architecture", "Design Patterns"]
keywords: "Kotlin delegation, by keyword, property delegation, class delegation, delegated properties, composition over inheritance"
faq:
  - q: "What does the by keyword do in Kotlin?"
    a: "The by keyword implements delegation. For class delegation, class A : B by b forwards all of interface B's methods to the object b unless A overrides them. For property delegation, val x by delegate routes the property's get and set through the delegate's getValue and setValue operators. In both cases the compiler generates the forwarding code so you don't write boilerplate."
  - q: "How is Kotlin class delegation different from inheritance?"
    a: "Inheritance couples you to a concrete superclass and its implementation, while class delegation composes behavior by holding an object that implements an interface and forwarding to it. Delegation lets you swap the delegate, wrap it, or combine several, which is exactly the flexibility inheritance denies. It's the language-level expression of composition over inheritance."
  - q: "What are lazy and observable property delegates?"
    a: "lazy computes a property's value on first access and caches it, which is ideal for expensive initialization. Delegates.observable fires a callback whenever the property changes, useful for reacting to state without manual setters. Both are standard-library delegates that plug into the same by mechanism you can use for your own delegates."
---

Kotlin's `by` keyword is two features wearing one keyword, and both exist to delete boilerplate the compiler can write better than you. Class delegation forwards an interface's methods to a held object so you can compose behavior instead of inheriting it; property delegation routes a property's reads and writes through a helper object so patterns like lazy initialization or change observation become one word. I've used both to collapse hundreds of lines of hand-written forwarding and getter/setter plumbing into declarations that read like intent.

The thing worth internalizing early is that `by` is not magic — it's codegen. Every `by` desugars to plain forwarding methods or `getValue`/`setValue` calls you could have written yourself. Once you can picture the generated code, you know exactly what you're paying for and where the sharp edges are.

## Class delegation: composition the compiler writes for you

Say you want a `List` that logs every read. The inheritance instinct is to extend `ArrayList` and override everything — brittle, and you inherit implementation you didn't ask for. Delegation composes instead:

```kotlin
class LoggingList<T>(
    private val backing: MutableList<T>,
) : MutableList<T> by backing {
    override fun get(index: Int): T {
        println("get($index)")
        return backing[index]
    }
}
```

`MutableList<T> by backing` tells the compiler: implement every `MutableList` method by forwarding to `backing`. You override only `get`. The other twenty-odd methods are generated as one-line forwarders. There's no fragile-base-class problem because you never inherited an implementation — you hold one and delegate to it, and you can swap `backing` for any `MutableList`.

The pattern that earns its keep in production is decorating a dependency:

```kotlin
class InstrumentedRepository(
    private val delegate: UserRepository,
    private val metrics: Metrics,
) : UserRepository by delegate {
    override suspend fun findById(id: UserId): User? {
        return metrics.time("findById") { delegate.findById(id) }
    }
}
```

I add timing to the one method I care about and forward the rest untouched. When the interface grows a method, I don't have to touch the decorator — the generated forwarder covers it. That's the opposite of what happens with inheritance-based wrappers, where every new method is a new override you can forget.

## The gotcha: delegation captures the reference, not `this`

The one behavior that surprises everyone: class delegation forwards to the *object you passed in*, and that object has no idea it's being delegated to. If the delegate calls one of its own methods internally, it calls *its own*, not your override.

```kotlin
interface Greeter {
    fun greet(): String
    fun greetLoud(): String   // calls greet() internally
}

class Base : Greeter {
    override fun greet() = "hi"
    override fun greetLoud() = greet().uppercase()  // 'this' is Base
}

class Shouty(b: Greeter) : Greeter by b {
    override fun greet() = "HELLO"
}

Shouty(Base()).greetLoud()  // "HI", not "HELLO"
```

`greetLoud` runs inside `Base`, where `greet` resolves to `Base.greet`. Your override is invisible to the delegate. This is different from inheritance, where `this` would be the subclass. It's not a bug — it's the honest consequence of composition — but it catches people who expect virtual dispatch to reach back into the wrapper. When you need the delegate to call back into your overrides, delegation is the wrong tool and you want real inheritance or an explicit callback.

## Property delegation: reads and writes through a helper

The second face of `by` sits on properties. `val x: T by something` compiles to a call to `something.getValue(thisRef, property)`; a `var` also uses `setValue`. The standard library ships the delegates you'll use most:

```kotlin
class Config {
    // Computed once, on first access, then cached. Thread-safe by default.
    val parsed: Schema by lazy { expensiveParse() }

    // Fires a callback on every change.
    var level: Int by Delegates.observable(0) { _, old, new ->
        log.info("level $old -> $new")
    }

    // Throws if read before being set — catches init-order bugs.
    var token: String by Delegates.notNull()
}
```

`lazy` is the one I reach for constantly: defer expensive construction until something actually reads it, and never compute it twice. It takes a `LazyThreadSafetyMode` if you want to trade the default synchronization for speed on confined data. `observable` and `vetoable` turn "I need a side effect on write" into a declaration instead of a hand-rolled setter. And `Delegates.notNull()` is a clean way to model "set once during init, guaranteed non-null afterward" without a nullable type leaking everywhere.

Delegating to a map is the other classic, handy for dynamic or config-shaped objects:

```kotlin
class Settings(private val map: Map<String, Any?>) {
    val host: String by map
    val port: Int by map
}
```

Each property reads `map["host"]`, `map["port"]`. It's how a lot of parsing and config layers avoid writing an accessor per field.

## Writing your own delegate

When the built-ins don't fit, a custom delegate is a few lines. A delegate that persists to `SharedPreferences`, for instance:

```kotlin
class PrefDelegate(
    private val prefs: SharedPreferences,
    private val key: String,
    private val default: String,
) {
    operator fun getValue(thisRef: Any?, property: KProperty<*>) =
        prefs.getString(key, default) ?: default

    operator fun setValue(thisRef: Any?, property: KProperty<*>, value: String) =
        prefs.edit().putString(key, value).apply()
}

class UserPrefs(prefs: SharedPreferences) {
    var theme: String by PrefDelegate(prefs, "theme", "system")
}
```

Now `userPrefs.theme = "dark"` writes straight to disk and reading it reads from disk — the persistence is invisible at the call site. Implement the two `operator` functions (or use the `ReadWriteProperty` interface) and any object becomes a delegate. This is the extension point that makes `by` genuinely open-ended rather than a fixed menu.

## When delegation is the right call

| Situation | Delegate? |
|---|---|
| Decorate/instrument a dependency, forward the rest | Yes — class delegation |
| Expensive init you want deferred and cached | Yes — `by lazy` |
| React to property changes | Yes — `observable`/`vetoable` |
| The delegate must call back into your overrides | No — use inheritance |
| A one-method interface you fully implement | No — just implement it |

Delegation is Kotlin's answer to "composition over inheritance," delivered as a keyword so the composition costs no boilerplate. Use class delegation to wrap and decorate without the fragility of subclassing, use property delegation to make cross-cutting property behavior declarative, and keep the desugaring in mind so the `this`-doesn't-reach-back gotcha never surprises you. The same instinct — hold and forward rather than extend — is what keeps larger designs like the ones in [ten years of Android architecture lessons](https://blog.michaelsam94.com/jetpack-compose-lessons-10-years-android/) flexible as they grow.

## Resources

- [Delegation — Kotlin documentation](https://kotlinlang.org/docs/delegation.html)
- [Delegated properties — Kotlin documentation](https://kotlinlang.org/docs/delegated-properties.html)
- [Standard delegates: lazy, observable, map](https://kotlinlang.org/docs/delegated-properties.html#standard-delegates)
- [ReadWriteProperty API reference](https://kotlinlang.org/api/latest/jvm/stdlib/kotlin.properties/-read-write-property/)
