---
title: "Polymorphic Serialization in Kotlin"
slug: "kotlin-serialization-polymorphic"
description: "Polymorphic JSON with kotlinx.serialization: sealed classes, class discriminators, custom serializers, and registry patterns for API evolution."
datePublished: "2026-01-04"
dateModified: "2026-01-04"
tags: ["Android", "Kotlin"]
keywords: "kotlinx.serialization, polymorphic, sealed class, JsonClassDiscriminator, SerializersModule, JSON API"
faq:
  - q: "How does kotlinx.serialization encode polymorphic types by default?"
    a: "You register subclasses in a SerializersModule and enable polymorphic serialization. JSON output includes a type discriminator field—default key \"type\" with fully qualified class name unless configured. Deserialization uses the discriminator to pick the correct serializer."
  - q: "Should I use class names or short type labels in JSON?"
    a: "Never expose fully qualified JVM class names in public APIs—they leak implementation and break on refactor. Use JsonClassDiscriminator with @SerialName on each subclass for stable short labels like \"card\" and \"bank_transfer\"."
  - q: "How do I handle unknown polymorphic types from a server?"
    a: "Register a default deserializer or catch SerializationException and map to Unknown sealed subtype. For forward compatibility, ignore unknown discriminators when business rules allow, or version your API explicitly."
---

Our webhook endpoint accepted `"type": "com.internal.LegacyRefund"` in JSON because polymorphic defaults were left on. A partner rename broke mobile clients on the next release. **Polymorphic serialization** in kotlinx.serialization is powerful when you control the wire format; careless defaults turn JSON into a classpath leak.

**kotlinx.serialization** supports polymorphic hierarchies through sealed classes, explicit subclass registration, and custom serializers—without Gson-style runtime reflection.

## Sealed class with discriminator

```kotlin
@Serializable
@JsonClassDiscriminator("payment_method")
sealed interface PaymentMethod {
    @Serializable
    @SerialName("card")
    data class Card(val last4: String, val brand: String) : PaymentMethod

    @Serializable
    @SerialName("bank")
    data class Bank(val routing: String) : PaymentMethod
}
```

JSON:

```json
{
  "payment_method": "card",
  "last4": "4242",
  "brand": "visa"
}
```

Configure Json:

```kotlin
val json = Json {
    serializersModule = SerializersModule {
        polymorphic(PaymentMethod::class) {
            subclass(PaymentMethod.Card::class)
            subclass(PaymentMethod.Bank::class)
        }
    }
    classDiscriminator = "payment_method"
    ignoreUnknownKeys = true
}
```

## Open polymorphism (non-sealed)

For interfaces not sealed—register all subclasses explicitly:

```kotlin
polymorphic(Event::class) {
    subclass(PageView::class)
    subclass(ButtonClick::class)
}
```

Missing registration fails deserialization—compile-time module safety when combined with tests.

## Custom serializer for legacy APIs

When discriminator format is non-standard:

```kotlin
object PaymentMethodSerializer : JsonContentPolymorphicSerializer<PaymentMethod>(PaymentMethod::class) {
    override fun selectDeserializer(element: JsonElement): DeserializationStrategy<PaymentMethod> {
        val type = element.jsonObject["payment_method"]?.jsonPrimitive?.content
        return when (type) {
            "card" -> PaymentMethod.Card.serializer()
            "bank" -> PaymentMethod.Bank.serializer()
            else -> throw SerializationException("Unknown payment_method: $type")
        }
    }
}

@Serializable(with = PaymentMethodSerializer::class)
sealed interface PaymentMethod { /* ... */ }
```

Use for nested discriminators or union types from OpenAPI `oneOf`.

## Lists of polymorphic items

```kotlin
@Serializable
data class Batch(val items: List<@Polymorphic PaymentMethod>)
```

Or wrap:

```kotlin
@Serializable
data class Envelope(val payload: PaymentMethod)
```

Ensure module registers all runtime subtypes.

## Testing round-trip

```kotlin
@Test
fun roundTrip() {
    val original: PaymentMethod = PaymentMethod.Card("4242", "visa")
    val encoded = json.encodeToString(PolymorphicSerializer(PaymentMethod::class), original)
    val decoded = json.decodeFromString(PolymorphicSerializer(PaymentMethod::class), encoded)
    assertEquals(original, decoded)
}
```

Add golden-file tests for partner payloads.

## Versioning and unknown types

```kotlin
@Serializable
@SerialName("unknown")
data class UnknownPayment(val raw: JsonObject) : PaymentMethod
```

Fallback deserializer maps unrecognized discriminators to `Unknown` for logging without crashing.

Document allowed `SerialName` values in OpenAPI—serialization labels are your public contract.

## KMP and iOS

Keep `@SerialName` stable across platforms. Generated serializers live in commonMain—same JSON on Android and iOS without Swift Codable duplication.

## Performance and wire size considerations

Polymorphic JSON carries a discriminator on every object—budget for the extra bytes on high-volume topics. Prefer sealed hierarchies with a single known supertype per endpoint rather than one mega-interface serialized polymorphically everywhere. When payloads are large and types are known at compile time, a non-polymorphic sealed wrapper avoids discriminator overhead:

```kotlin
@Serializable
data class PaymentEnvelope(val method: PaymentMethod) // concrete field, not @Polymorphic
```

For server-driven types you cannot seal, cache `SerializersModule` instances—building modules per request allocates unnecessarily.

## Debugging deserialization failures

SerializationException messages include JSON path when using `Json { isLenient = false }`. Log the raw payload hash, not the payload itself, when PII is present. Common fixes:

- Missing subclass registration in `SerializersModule`
- `@SerialName` mismatch with partner's `type` field
- Nullable field marked required in Kotlin but absent in JSON—use defaults or `@Required` discipline

Add contract tests in CI that decode fixture files from `commonTest/resources/partner-payloads/` on every PR.

## What to measure after rollout

Track error rates, tail latency, and resource utilization for two weeks after changes land—most regressions appear under real traffic mixes, not in staging smoke tests. Keep a rollback path documented: feature flags, Helm revision, or Git revert with known good digest. Review on-call pages tied to the topic quarterly; delete alerts that never fire and add thresholds that would have caught your last incident.

Run a short blameless postmortem if production surprised you, even for minor issues. The goal is updating this runbook section with one concrete lesson per quarter so the next engineer inherits context, not just configuration snippets.


## Documentation your team should maintain

Maintain a one-page runbook link from your main service README: prerequisites, owner rotation, last drill date, and known sharp edges. Link to vendor docs in the Resources section below but capture org-specific decisions (CIDR ranges, cluster names, approval gates) in internal docs that stay current. New hires should deploy a safe canary within a week using only that runbook—if they cannot, the doc is incomplete.


## Pre-production checklist

Before promoting to production, walk through this list with someone who was not the primary author—fresh eyes catch assumptions.

- **Staging parity**: The staging environment exercises the same code paths as production, including failure modes you expect to handle (timeouts, retries, partial outages).
- **Observability**: Dashboards and alerts exist for the metrics and log patterns discussed above; on-call knows where to look first.
- **Rollback**: You can revert to the previous known-good state in one documented step without improvising.
- **Access control**: Only the principals that need access have it; audit logs are enabled where the topic touches secrets or infrastructure APIs.
- **Load test**: You have evidence—not intuition—about behavior at expected peak plus headroom.

If any item is "we will do that later," treat it as a release blocker for tier-1 services.


## Common questions from reviewers

Reviewers and auditors often ask whether this approach scales with team growth and whether it fails safely. Answer explicitly in your design doc: what happens when dependencies are down, when credentials expire, and when traffic doubles overnight. Prefer defaults that deny or degrade gracefully over defaults that fail open. Document known limits (throughput ceilings, supported versions, regions) in the same place operators look during incidents—avoid scattering critical constraints across Slack threads.


## Resources

- [kotlinx.serialization polymorphic docs](https://github.com/Kotlin/kotlinx.serialization/blob/master/docs/polymorphic.md) — official guide
- [JsonClassDiscriminator API](https://kotlinlang.org/api/kotlinx.serialization/kotlinx-serialization-core/kotlinx.serialization.json/-json-class-discriminator/) — annotation reference
- [SerializersModule builder](https://kotlinlang.org/api/kotlinx.serialization/kotlinx-serialization-core/kotlinx.serialization.modules/-serializers-module/) — registration patterns
- [OpenAPI oneOf mapping strategies](https://swagger.io/docs/specification/data-models/oneof-anyof-allof-not/) — aligning JSON schema with Kotlin models
