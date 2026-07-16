---
title: "OkHttp Interceptor Patterns That Survive Production"
slug: "android-okhttp-interceptors-patterns"
description: "OkHttp interceptor patterns for Android: application vs network interceptors, auth token refresh with Authenticator, retries, logging, and the ordering that bites you."
datePublished: "2024-08-19"
dateModified: "2024-08-19"
tags: ["Android", "Kotlin", "Backend"]
keywords: "OkHttp interceptors, application vs network interceptor, Authenticator token refresh, retry interceptor, header interceptor, chain proceed"
faq:
  - q: "What is the difference between an application and a network interceptor in OkHttp?"
    a: "An application interceptor runs once per call, sees the original request, doesn't see redirects or retries, and always executes even for cached responses. A network interceptor runs for every actual network request including redirects and retries, sees the real over-the-wire request and response, but is skipped entirely when a response is served from cache. Use application interceptors for auth headers and logging of logical calls, and network interceptors when you need the true network view, like rewriting caching headers."
  - q: "Should I refresh auth tokens in an interceptor or an Authenticator?"
    a: "Use an Authenticator for token refresh, not an interceptor. OkHttp calls the Authenticator specifically when a 401 comes back, gives you the failed response to inspect, and automatically retries the request with your new credentials. Doing refresh inside an interceptor forces you to reimplement 401 detection and retry logic that the Authenticator already handles correctly, including loop prevention via responseCount."
  - q: "Does interceptor order matter in OkHttp?"
    a: "Yes, interceptors form a chain and run in the order you add them, wrapping each other like layers. The first-added application interceptor is outermost, so it sees the request first and the response last. Order matters most when one interceptor depends on another's output, for example a logging interceptor should usually be added last so it logs the final request after auth headers have been attached."
---

OkHttp's interceptor mechanism is the cleanest extension point in Android networking, and also the one where I see the most subtly broken code. An interceptor is a single method — `intercept(chain)` — that receives the outgoing request, calls `chain.proceed(request)` to hand control down the chain, and returns a response back up. That "hand down, get back up" structure is the whole model: every interceptor wraps the ones added after it, so you get a layered pipeline where each layer can modify the request on the way out and the response on the way in.

The trouble starts because there are *two* kinds of interceptor with different guarantees, token refresh has a dedicated mechanism people ignore, and the chain ordering has non-obvious consequences. Let me walk the patterns I actually ship.

## Application vs network interceptors: pick the right layer

This is the distinction that trips everyone up.

| | Application interceptor | Network interceptor |
|---|---|---|
| Runs per | Logical call (once) | Every network request (redirects, retries) |
| Sees redirects/retries | No | Yes |
| Runs on cache hit | Yes | No (skipped) |
| Sees | Your original request | The real on-the-wire request |
| Added via | `addInterceptor` | `addNetworkInterceptor` |

The practical rule: **auth headers, API-key injection, and logging of logical calls go in application interceptors.** They run once, always execute even if the response comes from cache, and don't get confused by redirects. **Network interceptors are for when you need ground truth** — rewriting `Cache-Control` headers on responses, inspecting the actual bytes after a redirect, or measuring real network timing. Ninety percent of the time you want an application interceptor.

## The header interceptor (do it right)

The bread-and-butter pattern — attach a header to every request:

```kotlin
class AuthHeaderInterceptor(
    private val tokenStore: TokenStore,
) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val original = chain.request()
        // Don't attach auth to the refresh endpoint itself.
        if (original.header("No-Auth") != null) {
            return chain.proceed(original.newBuilder().removeHeader("No-Auth").build())
        }
        val request = original.newBuilder()
            .header("Authorization", "Bearer ${tokenStore.accessToken()}")
            .build()
        return chain.proceed(request)
    }
}
```

Two details that matter: never mutate the original request (it's effectively immutable — use `newBuilder()`), and give yourself an escape hatch (`No-Auth`) so your login and refresh calls don't get an expired token stapled onto them and cause an infinite refresh loop.

## Token refresh belongs in an Authenticator, not an interceptor

The single most common mistake: implementing 401 detection and retry inside an interceptor. OkHttp has a purpose-built hook, `Authenticator`, which it invokes *only* when the server returns 401, hands you the failed response, and automatically retries with whatever credentials you return.

```kotlin
class TokenAuthenticator(
    private val tokenStore: TokenStore,
    private val refresher: TokenRefresher,
) : Authenticator {
    override fun authenticate(route: Route?, response: Response): Request? {
        // Give up after a couple of attempts to avoid a refresh storm.
        if (responseCount(response) >= 2) return null

        val newToken = synchronized(this) {
            // Another thread may have refreshed already; re-check first.
            val current = tokenStore.accessToken()
            if (response.request.header("Authorization") != "Bearer $current") {
                current // someone else refreshed; just reuse it
            } else {
                refresher.refreshBlocking() ?: return null
            }
        }
        return response.request.newBuilder()
            .header("Authorization", "Bearer $newToken")
            .build()
    }

    private fun responseCount(response: Response): Int {
        var r = response.priorResponse; var count = 1
        while (r != null) { count++; r = r.priorResponse }
        return count
    }
}
```

The `synchronized` block plus the "did someone already refresh?" check is what stops ten concurrent 401s from firing ten refresh calls — the classic thundering-herd bug. The `responseCount` guard prevents an infinite loop when refresh itself keeps failing. This is the correct home for refresh logic, and it plugs into the same layer as your [Retrofit error handling](https://blog.michaelsam94.com/android-retrofit-error-handling/).

## Retry with backoff

OkHttp retries some connection failures itself, but not application-level ones like 503. A small retry interceptor with jittered backoff covers idempotent calls:

```kotlin
class RetryInterceptor(private val maxRetries: Int = 3) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        var attempt = 0
        while (true) {
            val response = chain.proceed(chain.request())
            if (response.code != 503 || attempt >= maxRetries) return response
            response.close() // must close before retrying
            attempt++
            Thread.sleep((200L * (1 shl attempt)) + (0..100L).random())
        }
    }
}
```

Two non-negotiables: close the response body before retrying (leaking connections here is a real bug), and only retry idempotent requests unless the server sends an idempotency key. Blindly retrying a POST that charged a card is how you double-bill someone.

## Ordering: the outermost sees the request first

Interceptors run in add-order, each wrapping the next. So `addInterceptor(A)` then `addInterceptor(B)` means A is outermost: A sees the request first, B sees it second, B sees the response first, A sees it last. The consequence:

- Add your **auth header interceptor before your logging interceptor**, so the log shows the request *with* the `Authorization` header attached.
- Add **retry outside auth** if you want a retried request to get a fresh token evaluated each attempt.

Get this backwards and your logs show requests missing the headers that were actually sent — an infuriating debugging session waiting to happen.

## Logging without leaking secrets

`HttpLoggingInterceptor` is great, but `Level.BODY` will happily dump auth tokens and PII into logcat. I redact and gate it:

```kotlin
val logging = HttpLoggingInterceptor().apply {
    level = if (BuildConfig.DEBUG) HttpLoggingInterceptor.Level.BODY
            else HttpLoggingInterceptor.Level.NONE
    redactHeader("Authorization")
    redactHeader("Cookie")
}
```

Never ship `BODY` logging in release. I've found bearer tokens in production crash logs more than once because someone forgot this line.

## The setup I reuse

A typical client: auth header interceptor (application), retry interceptor (application, outer), a `TokenAuthenticator` for refresh, and a redacted logging interceptor added last so it captures the final request. Reserve network interceptors for genuine wire-level needs. Keep refresh out of interceptors, close bodies before retrying, and mind the order — that's most of the bugs, avoided.

## Resources

- [OkHttp interceptors documentation](https://square.github.io/okhttp/features/interceptors/)
- [OkHttp Authenticator API reference](https://square.github.io/okhttp/4.x/okhttp/okhttp3/-authenticator/)
- [HttpLoggingInterceptor reference](https://square.github.io/okhttp/4.x/logging-interceptor/okhttp3/logging/-http-logging-interceptor/)
- [OkHttp recipes](https://square.github.io/okhttp/recipes/)
- [MDN: HTTP conditional and caching headers](https://developer.mozilla.org/en-US/docs/Web/HTTP/Caching)
