---
title: "A Shared Ktor Client for Kotlin Multiplatform Apps"
slug: "kotlin-multiplatform-ktor-client"
description: "Build one Ktor client for KMP: shared networking across Android and iOS with serialization, engines per platform, auth, retries, and error handling."
datePublished: "2026-02-16"
dateModified: "2026-02-16"
tags: ["Kotlin", "Kotlin Multiplatform", "Networking", "Ktor"]
keywords: "Ktor client KMP, shared networking Kotlin Multiplatform, Ktor multiplatform, HTTP client KMP, serialization"
faq:
  - q: "What is a shared Ktor client in Kotlin Multiplatform?"
    a: "A shared Ktor client is a single HttpClient configuration written in your KMP common module and used by every target — Android, iOS, and beyond. Ktor abstracts the actual network transport behind pluggable engines, so you write serialization, auth, logging, and retry logic once in common code, and each platform supplies only its own engine (OkHttp on Android, Darwin on iOS)."
  - q: "Do I need different Ktor engines per platform?"
    a: "Yes, but only the engine differs. The client configuration — content negotiation, headers, timeouts, auth, retries — lives in common code. Each platform module adds a dependency on its engine (ktor-client-okhttp, ktor-client-darwin, ktor-client-js) and passes it in via expect/actual or a factory. Everything above the engine is shared."
  - q: "How does serialization work with a Ktor multiplatform client?"
    a: "Ktor integrates with kotlinx.serialization through the ContentNegotiation plugin. You register the JSON serializer once, annotate your data classes with @Serializable, and Ktor handles encoding request bodies and decoding responses on every platform. Because kotlinx.serialization is itself multiplatform, the exact same models and codecs run on Android and iOS."
---

The pitch for a shared [Ktor](https://ktor.io/) client in Kotlin Multiplatform is simple: write your networking layer once — serialization, auth, retries, error mapping — and run it byte-for-byte identically on Android and iOS. No more "the iOS team parses the API slightly differently" bugs, no duplicated retry logic drifting apart. Ktor makes this practical by splitting the client into a shared configuration and a per-platform *engine*, so the only platform-specific line is which transport does the actual socket work.

I've shipped this setup in production KMP apps, and the payoff is real: the networking layer becomes one of the most stable parts of the codebase because there's exactly one of it. But there are traps — engine selection, coroutine dispatch on iOS, and error handling across platforms — that are worth getting right the first time.

## Dependencies and the engine split

The mental model that keeps this clean: **the client config is common, the engine is per-target.** In your `commonMain` you depend on the core client plus the plugins you want everywhere. Each platform source set adds only its engine.

```kotlin
// build.gradle.kts (module-level)
kotlin {
    sourceSets {
        commonMain.dependencies {
            implementation("io.ktor:ktor-client-core:3.0.0")
            implementation("io.ktor:ktor-client-content-negotiation:3.0.0")
            implementation("io.ktor:ktor-serialization-kotlinx-json:3.0.0")
            implementation("io.ktor:ktor-client-logging:3.0.0")
        }
        androidMain.dependencies {
            implementation("io.ktor:ktor-client-okhttp:3.0.0")
        }
        iosMain.dependencies {
            implementation("io.ktor:ktor-client-darwin:3.0.0")
        }
    }
}
```

OkHttp on Android gives you a mature, battle-tested transport with connection pooling you already understand. Darwin on iOS uses `NSURLSession`, which means the OS handles things like background transfer policies and system proxy settings correctly. Don't fight these defaults — the whole reason to use platform engines is to inherit platform behavior.

## Configuring the client once

Here's the shared factory. Everything that defines *how your app talks to your API* lives here, in common code:

```kotlin
fun createHttpClient(engine: HttpClientEngine, tokenProvider: TokenProvider): HttpClient =
    HttpClient(engine) {
        expectSuccess = true

        install(ContentNegotiation) {
            json(Json {
                ignoreUnknownKeys = true
                explicitNulls = false
            })
        }

        install(Logging) { level = LogLevel.INFO }

        install(HttpTimeout) {
            requestTimeoutMillis = 30_000
            connectTimeoutMillis = 10_000
        }

        install(HttpRequestRetry) {
            retryOnServerErrors(maxRetries = 3)
            exponentialDelay()
        }

        defaultRequest {
            url("https://api.example.com/")
            header(HttpHeaders.Accept, ContentType.Application.Json.toString())
        }
    }
```

Two settings I always change from the defaults. `ignoreUnknownKeys = true` because backends add fields without asking, and you don't want a new field to crash every client in the field. `expectSuccess = true` because I'd rather non-2xx responses throw a typed exception I handle deliberately than silently return a body I forgot to check.

The `engine` and `tokenProvider` come in as parameters, which keeps this function testable — you can pass Ktor's `MockEngine` in tests and never touch a real socket. This shared-module discipline is the same one I lean on throughout the [Kotlin Multiplatform production guide](https://blog.michaelsam94.com/kotlin-multiplatform-production-guide/): keep platform specifics at the edges and make the core pure.

## Auth that actually refreshes

The naive approach bolts a token onto `defaultRequest` and calls it done. Real apps need refresh-on-401. Ktor's `Auth` plugin with `bearer` handles the token dance, including retrying the original request after a refresh, in common code:

```kotlin
install(Auth) {
    bearer {
        loadTokens { BearerTokens(store.accessToken(), store.refreshToken()) }
        refreshTokens {
            val refreshed = client.post("auth/refresh") {
                markAsRefreshTokenRequest()
                setBody(RefreshRequest(store.refreshToken()))
            }.body<TokenResponse>()
            store.save(refreshed)
            BearerTokens(refreshed.accessToken, refreshed.refreshToken)
        }
    }
}
```

The `markAsRefreshTokenRequest()` call is the detail people miss — it prevents the refresh call itself from triggering another refresh, which is how you get infinite loops. This logic living in common code means Android and iOS refresh identically, which matters a lot when you're debugging a token bug at 2 a.m. and don't want two implementations to reason about.

## Modeling responses and errors

Because kotlinx.serialization is multiplatform, your DTOs are shared too. Annotate and go:

```kotlin
@Serializable
data class UserDto(
    val id: String,
    val name: String,
    @SerialName("avatar_url") val avatarUrl: String? = null,
)

suspend fun HttpClient.getUser(id: String): Result<UserDto> = runCatching {
    get("users/$id").body()
}.recoverCatching { e ->
    throw when (e) {
        is ClientRequestException -> ApiError.NotFound
        is HttpRequestTimeoutException -> ApiError.Timeout
        else -> ApiError.Unknown(e.message)
    }
}
```

Map Ktor's exceptions into your own sealed error type at the boundary. Then your ViewModels and iOS presenters consume one shared error taxonomy instead of platform-specific transport exceptions. This is where a shared client earns its keep — the API contract *and* its failure semantics are defined exactly once.

## The gotchas I wish someone had told me

A few things that cost me time:

- **iOS dispatch.** Ktor calls are `suspend` functions and expect a coroutine context. From Swift, bridge them properly (a `suspend`-to-callback adapter or a library like KMP-NativeCoroutines); calling into a raw suspend function from the main thread naively will bite you.
- **Logging in release builds.** The Logging plugin at `LogLevel.ALL` will dump auth headers. Gate the level by build type or you'll leak tokens into logs.
- **Timeouts are not retries.** A generous request timeout plus aggressive retries can stack into a 90-second hang on a flaky network. Budget them together.
- **Certificate pinning is per-engine.** If you pin, you configure it on OkHttp and Darwin separately — that's genuinely platform-specific and belongs in the platform source sets.

If your backend is also Kotlin, there's a compounding win: the same `@Serializable` models can be shared between client and server. That end-to-end type safety is exactly what I build toward in the [full-stack Kotlin with a Ktor backend](https://blog.michaelsam94.com/full-stack-kotlin-ktor-backend/) approach, where one set of DTOs defines the contract for both sides and the compiler catches mismatches before they ship.

A shared Ktor client isn't the flashiest part of a KMP app, and that's the point. Get the engine split, the auth refresh, and the error mapping right, and networking becomes a solved problem you rarely reopen — which frees you to spend your attention on the parts of the app that are actually hard.

## Resources

- [Ktor client — official documentation](https://ktor.io/docs/client-create-multiplatform-application.html)
- [Ktor client engines](https://ktor.io/docs/client-engines.html)
- [kotlinx.serialization guide](https://github.com/Kotlin/kotlinx.serialization/blob/master/docs/serialization-guide.md)
- [Kotlin Multiplatform documentation](https://kotlinlang.org/docs/multiplatform.html)
- [Ktor client authentication plugin](https://ktor.io/docs/client-auth.html)
- [KMP-NativeCoroutines](https://github.com/rickclephas/KMP-NativeCoroutines)
