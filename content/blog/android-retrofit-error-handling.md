---
title: "Robust Retrofit Error Handling with Sealed Results"
slug: "android-retrofit-error-handling"
description: "Robust Retrofit error handling in Kotlin: model network, HTTP, and parsing failures as a sealed Result type, use a CallAdapter or runCatching, and stop swallowing errors."
datePublished: "2024-08-20"
dateModified: "2024-08-20"
tags: ["Android", "Kotlin", "Backend"]
keywords: "Retrofit error handling, sealed result, Kotlin network error, HttpException, CallAdapter, suspend Retrofit"
faq:
  - q: "How should I handle errors from Retrofit suspend functions?"
    a: "Wrap the call so that HTTP failures, IO/network failures, and serialization failures all surface as distinct, typed outcomes rather than exceptions you might forget to catch. A common approach is a sealed Result type produced by runCatching or a custom CallAdapter, so the compiler forces callers to handle the failure branch. Directly calling a suspend endpoint and only catching a generic Exception tends to swallow the difference between a 404, no connectivity, and a malformed body."
  - q: "What exceptions does Retrofit throw?"
    a: "For suspend functions, a non-2xx response throws HttpException carrying the status code and error body, connectivity or socket problems throw IOException subclasses like UnknownHostException and SocketTimeoutException, and a body that fails to parse throws a serialization exception from your converter such as JsonDataException for Moshi. Distinguishing these matters because the user-facing response differs: retry for IO, show a message for HTTP, and report parsing errors as bugs."
  - q: "Should I use a custom CallAdapter or just wrap calls manually?"
    a: "For a small app, wrapping each call in a runCatching helper that maps exceptions to your Result type is simple and explicit. For a larger codebase, a custom CallAdapter that makes every endpoint return your Result type removes the per-call boilerplate and guarantees consistency, at the cost of some setup. Both are valid; the important thing is that every call goes through one place that classifies errors."
---

The default way people call Retrofit — invoke the suspend function, wrap the whole thing in one `try/catch (e: Exception)`, show a generic "Something went wrong" — throws away almost all the information the network layer just handed you. Robust Retrofit error handling means treating the three fundamentally different failure classes as *different things*: a transport failure (no connectivity, timeout), an HTTP failure (the server answered with 4xx/5xx), and a deserialization failure (the body didn't match your model). Each demands a different response, and the only way to enforce that is to make failure a typed value the compiler won't let you ignore.

I model outcomes as a sealed type and route every call through one converter. Here's how it holds up in production.

## Model the outcome, don't throw it around

```kotlin
sealed interface ApiResult<out T> {
    data class Success<T>(val data: T) : ApiResult<T>
    data class HttpError(val code: Int, val body: String?) : ApiResult<Nothing>
    data class NetworkError(val cause: IOException) : ApiResult<Nothing>
    data class UnknownError(val cause: Throwable) : ApiResult<Nothing>
}
```

Now a call site is forced to reckon with each branch:

```kotlin
when (val result = repo.loadProfile()) {
    is ApiResult.Success -> render(result.data)
    is ApiResult.HttpError -> when (result.code) {
        401 -> logout()
        404 -> showEmpty()
        in 500..599 -> showRetry()
        else -> showGeneric()
    }
    is ApiResult.NetworkError -> showOfflineBanner()
    is ApiResult.UnknownError -> reportBug(result.cause)
}
```

That `when` is exhaustive, so if I add a new variant later, every call site fails to compile until I handle it. That compiler pressure is the entire point — it's the opposite of a catch-all that silently degrades.

## One place that classifies exceptions

The simplest way to produce that type is a `runCatching`-style helper that knows how to bucket exceptions:

```kotlin
suspend fun <T> apiCall(block: suspend () -> T): ApiResult<T> =
    try {
        ApiResult.Success(block())
    } catch (e: HttpException) {
        ApiResult.HttpError(e.code(), e.response()?.errorBody()?.string())
    } catch (e: IOException) {
        ApiResult.NetworkError(e)            // no connectivity, timeout, DNS
    } catch (e: Throwable) {
        ApiResult.UnknownError(e)            // parsing, unexpected
    }
```

Note the catch order: `HttpException` and `IOException` first, `Throwable` last. `IOException` is where connectivity, DNS (`UnknownHostException`), and timeouts (`SocketTimeoutException`) land — the retryable class. Serialization failures from Moshi/kotlinx.serialization fall through to `UnknownError`, which is correct: a body that won't parse is almost always a *bug* (backend contract drift), not something the user can fix by retrying. Reporting it as such is how you catch API contract breaks before your users do.

## Parse the error body, don't just show the code

A 422 with a JSON body explaining *which* field failed is far more useful than "Error 422." Give yourself a helper to decode the error envelope your backend uses:

```kotlin
data class ApiErrorBody(val message: String, val field: String?)

fun ApiResult.HttpError.decoded(moshi: Moshi): ApiErrorBody? =
    body?.let {
        runCatching {
            moshi.adapter(ApiErrorBody::class.java).fromJson(it)
        }.getOrNull()
    }
```

I wrap the decode in `runCatching` because error bodies are exactly where servers get sloppy — an HTML 502 page from a load balancer where you expected JSON will otherwise throw a *second* exception while you're handling the first.

## Scaling up: a custom CallAdapter

Wrapping every call in `apiCall { }` is fine for a small app but gets repetitive. For a larger codebase I use a `CallAdapter.Factory` so endpoints can just declare `suspend fun loadProfile(): ApiResult<Profile>` and the adapter does the classification centrally. It's more setup, but it guarantees no endpoint slips through with ad-hoc handling, and it composes cleanly with the [OkHttp interceptor and Authenticator layer](https://blog.michaelsam94.com/android-okhttp-interceptors-patterns/) underneath — the Authenticator handles 401 refresh transparently, so by the time a `HttpError(401)` reaches your `ApiResult`, refresh has genuinely failed.

## Timeouts and cancellation are not errors

A distinction I insist on with teams: when a user navigates away and the coroutine scope cancels, Retrofit throws `CancellationException`. **Do not** map that into your error type or report it — it's normal lifecycle behavior. `runCatching` and broad `catch (Throwable)` will swallow `CancellationException`, which breaks structured concurrency. Rethrow it explicitly:

```kotlin
} catch (e: CancellationException) {
    throw e            // let cancellation propagate
} catch (e: Throwable) {
    ApiResult.UnknownError(e)
}
```

Miss this and you'll see phantom "unknown error" toasts firing every time someone hits back at the wrong moment.

## What good handling changes in practice

- **Offline** becomes a specific, friendly state (a banner, cached data) instead of a scary error dialog, because `NetworkError` is distinguishable.
- **Auth expiry** routes to logout/refresh, not a generic message.
- **Backend contract drift** surfaces as reported `UnknownError`/parsing failures you can alert on, catching breakage before it becomes a support wave.
- **Server outages** (5xx) get a retry affordance while client errors (4xx) don't, because you branched on the code range.

None of this requires a heavy framework. It requires refusing to collapse three different failures into one `Exception`, and putting the classification in exactly one place the compiler makes you respect.

## Common production mistakes

Teams get retrofit error handling wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Shipping retrofit error handling on Android fails quietly when you test only on flagship devices, skip process-death scenarios, or assume `minSdk` behavior matches latest API docs. Emulator-only validation misses OEM-specific battery optimizations and background execution limits.

## Resources

- [Retrofit documentation](https://square.github.io/retrofit/)
- [Kotlin sealed classes and interfaces](https://kotlinlang.org/docs/sealed-classes.html)
- [Kotlin exceptions and runCatching](https://kotlinlang.org/api/latest/jvm/stdlib/kotlin/run-catching.html)
- [Coroutines: cancellation and exceptions](https://kotlinlang.org/docs/exception-handling.html)
- [Moshi JSON library](https://github.com/square/moshi)
