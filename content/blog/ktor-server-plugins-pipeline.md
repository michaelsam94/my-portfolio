---
title: "Ktor Server Plugins and Pipeline"
slug: "ktor-server-plugins-pipeline"
description: "Extend Ktor with server plugins: ApplicationCallPipeline phases, custom interceptors, plugin ordering, and patterns for logging, metrics, and request context."
datePublished: "2026-01-12"
dateModified: "2026-01-12"
tags: ["Backend", "Ktor"]
keywords: "Ktor plugins, ApplicationCallPipeline, intercept, Feature, plugin order, custom Ktor plugin"
faq:
  - q: "What is the difference between a Ktor plugin and a route interceptor?"
    a: "Plugins install into the Application or Routing pipeline and apply globally or to configured subsets. Route interceptors attach to specific routes. Plugins handle cross-cutting concerns—serialization, auth, logging—while route interceptors fit localized behavior."
  - q: "Does plugin install order matter?"
    a: "Yes. Authentication must run before authorization routes. ContentNegotiation should run before handlers that receive bodies. CallLogging typically installs early to capture full request lifecycle. Wrong order causes subtle bugs like logging unauthenticated paths with wrong identity."
  - q: "How do I pass data from a plugin to route handlers?"
    a: "Use call.attributes with AttributeKey, or call.application.environment.monitor for app-wide state. Request-scoped values belong in call.attributes set during an intercept phase and read in handlers."
---

We added request timing in three places— a Filter-style plugin, a route wrapper, and manual `measureTimeMillis` in handlers— and p99 metrics triple-counted latency. One **custom Ktor plugin** at the right pipeline phase fixed it. Ktor's pipeline model rewards knowing where your code runs relative to routing, auth, and serialization.

Ktor processes each request through **ApplicationCallPipeline** phases. **Plugins** (formerly Features) hook phases to add behavior without wrapping every route manually.

## Pipeline phases overview

Key phases in order:

1. **Setup** — initial call setup
2. **Monitoring** — hooks for observers
3. **Plugins** — plugin-specific (varies)
4. **Call** — routing, handlers
5. **Fallback** — unhandled routes

Within routing, nested pipelines handle sub-routes. Plugins install at `Application`, `Routing`, or `Route` level.

## Installing standard plugins

```kotlin
fun Application.module() {
    install(CallLogging) {
        level = Level.INFO
        filter { call -> call.request.path().startsWith("/api") }
        format { call -> "${call.request.httpMethod.value} ${call.request.uri} ${call.response.status()}" }
    }

    install(ContentNegotiation) {
        json(Json { ignoreUnknownKeys = true })
    }

    install(StatusPages) {
        exception<ValidationException> { call, cause ->
            call.respond(HttpStatusCode.BadRequest, ErrorBody(cause.message))
        }
    }

    routing {
        get("/health") { call.respond(HealthOk) }
    }
}
```

Order in `module()`: Logging → Negotiation → Auth → StatusPages → Routing is a common stack.

## Custom plugin with createApplicationPlugin

Ktor 2.x+ API:

```kotlin
val RequestIdPlugin = createApplicationPlugin("RequestId") {
    onCall { call ->
        val id = call.request.header("X-Request-Id") ?: UUID.randomUUID().toString()
        call.attributes.put(RequestIdKey, id)
        call.response.header("X-Request-Id", id)
    }
}

val RequestIdKey = AttributeKey<String>("RequestId")

// Application.module()
install(RequestIdPlugin)
```

Read in routes:

```kotlin
get("/orders") {
    val requestId = call.attributes[RequestIdKey]
    logger.info("fetch orders req=$requestId")
}
```

## Intercept specific phases

```kotlin
val TimingPlugin = createApplicationPlugin("Timing") {
    onCall { call ->
        val start = System.nanoTime()
        try {
            proceed()
        } finally {
            val ms = (System.nanoTime() - start) / 1_000_000
            call.application.environment.monitor.raise(TimingEvent(call, ms))
        }
    }
}
```

Use `onCallReceive` / `onCallRespond` for body-level hooks in ContentNegotiation-style plugins.

## Route-scoped plugins

```kotlin
route("/api") {
    install(RateLimitPlugin) {
        requestsPerMinute = 100
    }
    authenticate("jwt") {
        get("/data") { /* ... */ }
    }
}
```

Scoped plugins apply only to subtree—useful for different rate limits per tenant tier.

## Plugin vs inline middleware

| Use plugin when | Use route wrapper when |
|-----------------|------------------------|
| Global logging/metrics | One-off experiment |
| Auth/session | Route-specific validation |
| Request ID propagation | Single endpoint transform |

Plugins compose; copy-paste interceptors diverge.

## Testing plugins

```kotlin
@Test
fun requestIdEchoed() = testApplication {
    application { install(RequestIdPlugin); routing { get("/") { respond("ok") } } }
    val response = client.get("/") { header("X-Request-Id", "abc-123") }
    assertEquals("abc-123", response.headers["X-Request-Id"])
}
```

`testApplication` runs full pipeline—plugins included.

## DoubleReceive plugin

Install `DoubleReceive` when middleware and handlers both need raw body—without it, first consumer exhausts InputStream.

```kotlin
install(DoubleReceive)
```

Log at WARN when body size exceeds threshold to catch accidental full-buffer of uploads.


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


## Custom plugin example

```kotlin
val RequestLoggingPlugin = createApplicationPlugin(name = "RequestLogging") {
    onCall { call ->
        val start = System.currentTimeMillis()
        call.response.pipeline.intercept(ApplicationSendPipeline.Before) {
            val duration = System.currentTimeMillis() - start
            application.log.info("${call.request.httpMethod} ${call.request.uri} ${call.response.status()} ${duration}ms")
        }
    }
}

fun Application.configureMonitoring() {
    install(RequestLoggingPlugin)
}
```

Plugins install once at startup — avoid creating objects per request inside plugin hooks.

## Route-scoped vs application-scoped plugins

```kotlin
routing {
    route("/api") {
        install(Authentication) { /* JWT */ }
        install(RateLimiting) { requestsPerMinute = 100 }
        get("/users") { /* ... */ }
    }
    route("/health") {
        // No auth plugin — public
        get { call.respond("OK") }
    }
}
```

Scope authentication and rate limiting to routes that need them — global auth breaks health checks and metrics scrapers.

Pair with [API authentication JWT vs sessions](https://blog.michaelsam94.com/api-authentication-jwt-vs-sessions/) when implementing JWT validation plugins.

## Resources

- [Ktor plugins documentation](https://ktor.io/docs/plugins.html) — creating and installing plugins
- [ApplicationCallPipeline reference](https://api.ktor.io/ktor-server-core/io.ktor.server.application/-application-call-pipeline/index.html) — phase enum
- [Custom plugin migration guide](https://ktor.io/docs/migrating-2.html) — createApplicationPlugin vs legacy Feature API
- [Ktor samples repository](https://github.com/ktorio/ktor-samples) — reference implementations
