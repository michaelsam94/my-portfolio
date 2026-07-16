---
title: "Kotlin Serialization Beyond JSON Basics"
slug: "kotlin-serialization-beyond-json"
description: "Go beyond kotlinx.serialization basics: polymorphic serialization of sealed classes, custom serializers, JSON tricks, and Protobuf for compact payloads."
datePublished: "2026-05-08"
dateModified: "2026-05-08"
tags: ["Kotlin", "Serialization", "API Design"]
keywords: "kotlinx.serialization, polymorphic serialization, custom serializers, sealed classes JSON, protobuf Kotlin"
faq:
  - q: "What is polymorphic serialization in kotlinx.serialization?"
    a: "Polymorphic serialization is how kotlinx.serialization encodes and decodes a value whose concrete type is one of several subtypes of a common supertype, typically a sealed class or interface. It writes a type discriminator (by default a 'type' key) alongside the data so the decoder knows which subclass to reconstruct. For sealed hierarchies it works automatically because the compiler knows all subtypes at compile time."
  - q: "When should I write a custom serializer?"
    a: "Write a custom serializer when a type's in-memory shape doesn't match its wire shape — for example serializing a value class as a bare primitive, encoding a date as an ISO string, or flattening a wrapper. You implement KSerializer with a serialize/deserialize pair and a descriptor. It's the escape hatch for when annotations and defaults can't express the format you need."
  - q: "Can kotlinx.serialization output formats other than JSON?"
    a: "Yes. The library separates serializers (generated per class) from formats (how bytes are laid out), so the same @Serializable class can be encoded as JSON, Protobuf, CBOR, or a properties map by swapping the format object. Protobuf and CBOR are binary and far more compact than JSON, which matters for storage, caching, or bandwidth-sensitive transport."
---

Most teams meet `kotlinx.serialization` through one line — `Json.encodeToString(user)` — and never go further. That's fine until the day you need to serialize a sealed hierarchy of events, encode a value class as a bare string, or shrink a payload that JSON makes needlessly fat. The library is built for exactly those cases: it cleanly separates *serializers* (generated per class from `@Serializable`) from *formats* (JSON, Protobuf, CBOR), and it gives you polymorphism and custom serializers as first-class tools rather than afterthoughts.

I'll skip the "add the plugin, annotate a data class" tutorial and go straight to the parts that show up in real APIs: polymorphic sealed classes, custom serializers, the JSON config knobs that prevent production incidents, and when to abandon JSON entirely for a binary format.

## Polymorphic serialization of sealed hierarchies

Sealed classes are the natural model for "a message that's one of N kinds" — WebSocket events, API responses, command types. Because the compiler knows every subtype of a sealed class, `kotlinx.serialization` can handle the polymorphism with zero registration:

```kotlin
@Serializable
sealed class WsEvent {
    @Serializable
    @SerialName("message")
    data class Message(val from: String, val body: String) : WsEvent()

    @Serializable
    @SerialName("typing")
    data class Typing(val from: String) : WsEvent()

    @Serializable
    @SerialName("presence")
    data class Presence(val userId: String, val online: Boolean) : WsEvent()
}
```

Encoding a `WsEvent.Message` produces `{"type":"message","from":"...","body":"..."}`. The `type` discriminator is what lets the decoder pick the right subclass. Two things I always do here: set an explicit `@SerialName` on each subtype so the wire value is stable and doesn't break when someone renames a class, and — if I'm integrating with a backend that uses a different discriminator key — change it via `Json { classDiscriminator = "kind" }`. Sealed hierarchies are the same modeling win I lean on in Dart; if you work across both stacks, the parallels with [Dart 3 patterns, records, and sealed classes](https://blog.michaelsam94.com/dart-3-patterns-records-sealed/) are strong — exhaustive `when`/`switch` over a closed set is the payoff on both platforms.

For open hierarchies (interfaces with subtypes across modules), you register subtypes in a `SerializersModule` instead. That's more ceremony, so I reach for it only when a sealed class genuinely can't express the hierarchy.

## Custom serializers: when the wire shape differs

The most useful advanced feature is the custom `KSerializer`. Reach for it whenever the in-memory representation and the serialized representation should differ. A classic case is a value class you want on the wire as a bare primitive, not a nested object:

```kotlin
@JvmInline
value class UserId(val raw: String)

object UserIdSerializer : KSerializer<UserId> {
    override val descriptor =
        PrimitiveSerialDescriptor("UserId", PrimitiveKind.STRING)
    override fun serialize(encoder: Encoder, value: UserId) =
        encoder.encodeString(value.raw)
    override fun deserialize(decoder: Decoder): UserId =
        UserId(decoder.decodeString())
}

@Serializable
data class Account(
    @Serializable(with = UserIdSerializer::class) val id: UserId,
    val name: String,
)
```

Now `id` serializes as `"u_42"` instead of `{"raw":"u_42"}`. The same pattern handles dates as ISO strings, enums with custom labels, or third-party types you can't annotate. The one rule: your `descriptor` must honestly describe the output shape, because that's what formats and tooling rely on. Getting the descriptor wrong is the most common source of confusing "expected X, found Y" errors, so match it to what `serialize` actually writes.

## JSON config that prevents incidents

The default `Json` is strict, which is great in tests and dangerous in production if you don't tune it. These are the settings I change on nearly every real client:

```kotlin
val json = Json {
    ignoreUnknownKeys = true      // backend adds a field -> don't crash old clients
    explicitNulls = false         // omit nulls instead of writing "field": null
    coerceInputValues = true      // null for a non-null default -> use the default
    encodeDefaults = false        // keep payloads lean
}
```

`ignoreUnknownKeys = true` is the one that has saved me from a field-wide crash: a backend team adds a property, and every client that hasn't updated blows up on decode unless you set this. `explicitNulls = false` keeps payloads clean and avoids the `null` vs absent ambiguity. These aren't stylistic — they're resilience settings. A senior review of any serialization PR should check them.

## Beyond JSON: Protobuf and CBOR

Here's the feature most people don't realize they have: the *same* `@Serializable` class can be encoded as binary. Swap the format object and you get Protobuf or CBOR with no changes to your models:

```kotlin
@OptIn(ExperimentalSerializationApi::class)
val bytes = ProtoBuf.encodeToByteArray(account)
val restored = ProtoBuf.decodeFromByteArray<Account>(bytes)
```

When does this matter? Roughly:

| Format | Size | Human-readable | Use when |
| --- | --- | --- | --- |
| JSON | Largest | Yes | Public APIs, debuggability, browser clients |
| CBOR | Smaller | No | Compact JSON-like binary, IoT |
| Protobuf | Smallest | No | Storage, caching, bandwidth-critical transport |

I've cut on-disk cache size meaningfully by switching a local `DataStore`-style blob from JSON to Protobuf, with a one-line format swap and identical models. The caveat: `kotlinx.serialization`'s Protobuf uses field *order* to assign field numbers unless you annotate with `@ProtoNumber`, so if you need schema evolution compatible with a `.proto` file, pin the numbers explicitly. Don't reorder fields casually in a Protobuf-serialized class — that silently changes the wire format.

## Practical guardrails

A few habits that keep serialization boring in the good way:

- **Pin wire names.** Use `@SerialName` on properties and subtypes so refactors don't change the contract. Kotlin names are for you; wire names are for the protocol.
- **Version your discriminators.** For long-lived event streams, treat the discriminator set like an API — additive changes only.
- **Keep serializers pure.** A `KSerializer` should transform data, not perform I/O or logging. If you need ambient dependencies during (de)serialization, that's a design smell — resolve them at the boundary, the way I'd handle cross-cutting scope with [Kotlin context parameters](https://blog.michaelsam94.com/kotlin-context-parameters/) rather than smuggling them into a serializer.
- **Test round-trips.** For every custom serializer, assert `decode(encode(x)) == x`. It catches descriptor mistakes immediately.

The through-line: `kotlinx.serialization` rewards you for treating serialization as a real design surface rather than a one-liner. Model your variants as sealed classes, use custom serializers to keep wire shapes clean, tune the JSON config for resilience, and remember the binary formats are one swap away when payload size starts to matter. That's the difference between serialization being a quiet, dependable layer and being the thing that pages you when the backend adds a field.

## Resources

- [kotlinx.serialization guide](https://github.com/Kotlin/kotlinx.serialization/blob/master/docs/serialization-guide.md)
- [Polymorphism in kotlinx.serialization](https://github.com/Kotlin/kotlinx.serialization/blob/master/docs/polymorphism.md)
- [Custom serializers](https://github.com/Kotlin/kotlinx.serialization/blob/master/docs/serializers.md)
- [JSON configuration reference](https://github.com/Kotlin/kotlinx.serialization/blob/master/docs/json.md)
- [Alternative and custom formats (Protobuf, CBOR)](https://github.com/Kotlin/kotlinx.serialization/blob/master/docs/formats.md)
- [Kotlin sealed classes documentation](https://kotlinlang.org/docs/sealed-classes.html)
