---
title: "Full-Stack Kotlin: A Ktor Backend for Your App"
slug: "full-stack-kotlin-ktor-backend"
description: "Build a production Ktor backend in Kotlin for mobile apps: routing, JWT auth, kotlinx.serialization, WebSockets, and shared models with Android clients."
datePublished: "2026-04-04"
dateModified: "2026-04-07"
tags: ["Kotlin", "Ktor", "Backend", "Coroutines"]
keywords: "Ktor, full-stack Kotlin, Kotlin backend, Ktor server, Kotlin API, coroutines server, shared models"
faq:
  - q: "Is Ktor production-ready for a real backend?"
    a: "Yes. Ktor is JetBrains' asynchronous server framework built on coroutines, used in production for APIs and microservices. It's lighter than Spring Boot and pairs naturally with a Kotlin or KMP mobile client, though you assemble more yourself than with a batteries-included framework."
  - q: "Can I share code between a Ktor backend and an Android/KMP app?"
    a: "Yes. With Kotlin Multiplatform you can put DTOs, validation, and serialization models in a shared module used by both the Ktor server and the mobile client, eliminating a whole class of client/server contract mismatches."
  - q: "How does Ktor handle concurrency?"
    a: "Ktor handlers are suspend functions running on coroutines, so blocking I/O is cheap to model and the server handles many concurrent requests without a thread per request. Just keep genuinely blocking calls off the main dispatchers."
---

Most mobile developers treat the backend as someone else's language. It doesn't have to be. **Ktor** lets you write the server in the same Kotlin you already use for Android, with coroutines instead of callbacks and — if you go Kotlin Multiplatform — literally the same model classes on both sides of the wire. When I built the API layer for an [EV-charging platform](https://blog.michaelsam94.com/how-i-architected-an-ev-charging-platform/), keeping the DTOs in a shared module meant a field rename was a compile error, not a runtime surprise discovered by a user. That alone justified the choice.

This is a tour of what a real Ktor backend looks like: routing, serialization, coroutine-based handlers, auth, and the shared-model trick that makes "full-stack Kotlin" more than a slogan. It assumes you know Kotlin and have wired up a REST client before.

## What Ktor is, and what it isn't

Ktor is JetBrains' asynchronous framework built directly on Kotlin coroutines. It's **unopinionated and modular** — you install exactly the features (plugins) you need rather than inheriting a large framework. That's a strength and a cost: it's lighter and faster to start than Spring Boot, but you assemble more of the picture yourself. For a mobile-facing API of moderate size, that trade almost always favors Ktor.

You configure a server by installing plugins and defining routes. Here's a minimal but real setup:

```kotlin
fun main() {
    embeddedServer(Netty, port = 8080) {
        install(ContentNegotiation) { json() }
        install(StatusPages) {
            exception<IllegalArgumentException> { call, cause ->
                call.respond(HttpStatusCode.BadRequest, ErrorResponse(cause.message ?: "bad request"))
            }
        }
        configureRouting()
    }.start(wait = true)
}
```

`ContentNegotiation` with `json()` (kotlinx.serialization) handles turning your Kotlin data classes into JSON and back. `StatusPages` gives you one place to map exceptions to HTTP responses instead of try/catch littered through every handler.

## Routing and coroutine handlers

Routes are a DSL, and every handler is a `suspend` function — so calling your database or another service is just a normal suspending call, no callback pyramids:

```kotlin
fun Application.configureRouting() {
    routing {
        route("/api/chargers") {
            get {
                val chargers = chargerRepository.findAll() // suspend
                call.respond(chargers)
            }
            get("/{id}") {
                val id = call.parameters["id"] ?: throw IllegalArgumentException("id required")
                val charger = chargerRepository.find(id)
                    ?: return@get call.respond(HttpStatusCode.NotFound)
                call.respond(charger)
            }
            post {
                val request = call.receive<CreateChargerRequest>()
                val created = chargerRepository.create(request)
                call.respond(HttpStatusCode.Created, created)
            }
        }
    }
}
```

Because handlers are coroutines, Ktor serves many concurrent requests without dedicating a thread to each. The one rule to internalize: **don't block the event loop.** A genuinely blocking JDBC call belongs on `Dispatchers.IO` (`withContext(Dispatchers.IO) { ... }`), or use a coroutine-native driver. Block the wrong dispatcher and throughput collapses under load — it's the Ktor equivalent of doing disk I/O on the Android main thread.

## Shared models: the KMP payoff

Here's the part that makes full-stack Kotlin genuinely different from writing a Node backend for a Kotlin app. Put your DTOs in a Kotlin Multiplatform shared module:

```kotlin
// commonMain — used by BOTH the Ktor server and the mobile client
@Serializable
data class Charger(
    val id: String,
    val name: String,
    val status: ChargerStatus,
    val powerKw: Double,
)

@Serializable
enum class ChargerStatus { AVAILABLE, CHARGING, FAULTED, OFFLINE }
```

The server serializes `Charger`, the client deserializes the exact same class, and the contract is enforced by the compiler. Rename `powerKw`, and both sides fail to build until you fix them. Add an enum case the client doesn't handle, and the `when` is no longer exhaustive. This kills the most tedious category of API bugs — silent client/server drift — before code review. If you're weighing how far to take shared code, I compared the options in [Kotlin Multiplatform in production](https://blog.michaelsam94.com/kotlin-multiplatform-production-guide/).

## Authentication

Ktor's `Authentication` plugin handles the common schemes. For a mobile API, JWT bearer tokens are the usual pick:

```kotlin
install(Authentication) {
    jwt("auth-jwt") {
        realm = "charging-api"
        verifier(
            JWT.require(Algorithm.HMAC256(secret))
                .withIssuer("charging-api")
                .build()
        )
        validate { credential ->
            if (credential.payload.getClaim("userId").asString().isNotEmpty())
                JWTPrincipal(credential.payload) else null
        }
    }
}

routing {
    authenticate("auth-jwt") {
        get("/api/me") {
            val userId = call.principal<JWTPrincipal>()!!.payload.getClaim("userId").asString()
            call.respond(userRepository.find(userId))
        }
    }
}
```

Wrap protected routes in `authenticate(...)` and the plugin rejects unauthenticated requests before your handler runs. Keep the signing secret out of source (see [secrets management](https://blog.michaelsam94.com/secrets-management/)) and rotate it like any other credential.

## The pieces around the edges

A few plugins turn the demo into something you'd actually operate:

| Concern | Plugin |
| --- | --- |
| Request/response logging | `CallLogging` |
| Structured errors | `StatusPages` |
| CORS for web clients | `CORS` |
| Compression | `Compression` |
| Rate limiting | `RateLimit` |
| Metrics/tracing | Micrometer + OpenTelemetry |

For persistence, Exposed (JetBrains' SQL framework) or a coroutine-friendly driver keeps you in idiomatic Kotlin. For observability, wire OpenTelemetry so traces from the mobile client can be stitched to server spans — I go deeper on that in [designing for observability and SLOs](https://blog.michaelsam94.com/designing-for-observability-slos/).

## When to reach for Ktor — and when not

Ktor shines when your team is already Kotlin-fluent, when the API primarily serves your own mobile clients, and when you value a small, explicit stack over a large convention-driven one. It's a great fit for a [backend-for-frontend](https://blog.michaelsam94.com/backend-for-frontend-bff/) sitting in front of heavier services.

I'd think twice if you need the vast Spring ecosystem (mature data, batch, and integration modules), or if the team has no Kotlin experience and a deep Java/Spring bench — the "same language as the app" advantage evaporates then. But for a mobile-first product built by people who already think in coroutines and data classes, writing the backend in Kotlin turns the client/server boundary from a translation layer into a shared codebase. That's a genuinely different way to build, and once you've shipped it you don't want to go back.

## Resources

- [Ktor — official documentation](https://ktor.io/docs/welcome.html)
- [Ktor server routing](https://ktor.io/docs/server-routing.html)
- [kotlinx.serialization](https://github.com/Kotlin/kotlinx.serialization)
- [Ktor Authentication plugin](https://ktor.io/docs/server-auth.html)
- [Kotlin Multiplatform](https://kotlinlang.org/docs/multiplatform.html)
- [Exposed SQL framework](https://github.com/JetBrains/Exposed)
