---
title: "Authentication in Ktor"
slug: "ktor-authentication-jwt"
description: "Implement JWT authentication in Ktor: Authentication plugin, JWT verifier, role-based routing, refresh tokens, and securing WebSocket sessions."
datePublished: "2026-01-08"
dateModified: "2026-01-08"
tags: ["Backend", "Ktor"]
keywords: "Ktor JWT, Authentication plugin, bearer token, role-based access, Ktor security, refresh token"
faq:
  - q: "Where should JWT validation happen in a Ktor application?"
    a: "Install the Authentication plugin at application scope and define a jwt provider that verifies signature, issuer, audience, and expiry. Protect routes with authenticate(\"jwt\") blocks. Validation runs in the pipeline before route handlers—never trust client claims without cryptographic verification."
  - q: "How do I access the authenticated user in route handlers?"
    a: "Call call.principal<JWTPrincipal>() or your custom UserPrincipal class mapped from claims. Extract subject, roles, and tenant ID from verified token payload—not from request headers directly."
  - q: "Should refresh tokens use the same JWT configuration as access tokens?"
    a: "Use separate signing keys, shorter access token TTL (minutes), longer refresh TTL (days), and store refresh tokens server-side or in HttpOnly cookies with rotation. Access tokens stay in Authorization header; refresh endpoints require stricter rate limiting."
---

First production incident on our Ktor API: a route checked `call.request.header("X-User-Id")` because JWT wiring was "temporary." It shipped that way for four months. **Ktor's Authentication plugin** exists so identity comes from verified tokens in the pipeline, not from headers clients forge.

Ktor treats auth as another pipeline feature—install once, configure providers, wrap routes. JWT is the common case for mobile and SPA backends.

## Dependencies and setup

```kotlin
// build.gradle.kts
implementation("io.ktor:ktor-server-auth-jwt:3.0.3")
implementation("com.auth0:java-jwt:4.4.0")
```

```kotlin
fun Application.module() {
    install(Authentication) {
        jwt("auth-jwt") {
            realm = "api"
            verifier(
                JWT.require(Algorithm.HMAC256(jwtSecret))
                    .withAudience("mobile-app")
                    .withIssuer("https://auth.example.com")
                    .build()
            )
            validate { credential ->
                val userId = credential.payload.subject
                val roles = credential.payload.getClaim("roles").asList(String::class.java)
                if (userId != null) UserPrincipal(userId, roles) else null
            }
        }
    }
}
```

Returning `null` from `validate` yields 401 Unauthorized.

## Protecting routes

```kotlin
routing {
    authenticate("auth-jwt") {
        get("/me") {
            val user = call.principal<UserPrincipal>()!!
            call.respond(UserResponse(user.id))
        }

        route("/admin") {
            authorize("admin") {
                get("/metrics") { /* ... */ }
            }
        }
    }

    post("/auth/login") { /* public */ }
}
```

Role check helper:

```kotlin
fun Route.authorize(role: String, build: Route.() -> Unit): Route {
    return createChild(object : RouteSelector() {
        override suspend fun evaluate(context: RoutingResolveContext, segmentIndex: Int): RouteSelectorEvaluation {
            val principal = context.call.principal<UserPrincipal>()
            return if (principal?.roles?.contains(role) == true) {
                RouteSelectorEvaluation.Transparent
            } else {
                context.call.respond(HttpStatusCode.Forbidden)
                RouteSelectorEvaluation.Failed
            }
        }
    }).apply(build)
}
```

Or use built-in `withRoles` patterns from community extensions.

## Issuing tokens at login

```kotlin
post("/auth/login") {
    val creds = call.receive<LoginRequest>()
    val user = userService.authenticate(creds.email, creds.password)
        ?: return@post call.respond(HttpStatusCode.Unauthorized)

    val token = JWT.create()
        .withSubject(user.id)
        .withAudience("mobile-app")
        .withIssuer("https://auth.example.com")
        .withClaim("roles", user.roles)
        .withExpiresAt(Date(System.currentTimeMillis() + 15 * 60 * 1000))
        .sign(Algorithm.HMAC256(jwtSecret))

    call.respond(TokenResponse(accessToken = token))
}
```

Use RS256 with JWKS when multiple services verify tokens.

## Multiple auth schemes

```kotlin
install(Authentication) {
    jwt("user-jwt") { /* ... */ }
    bearer("service-token") {
        authenticate { token ->
            if (token == validServiceToken) ServicePrincipal else null
        }
    }
}

authenticate("user-jwt", "service-token", strategy = AuthenticationStrategy.FirstSuccessful) {
    get("/internal/sync") { /* ... */ }
}
```

## WebSocket auth

Validate during handshake:

```kotlin
webSocket("/ws") {
    val token = call.request.queryParameters["token"]
        ?: throw UnauthorizedException()
    val principal = verifyJwt(token) ?: throw UnauthorizedException()
    // session tied to principal
}
```

Prefer short-lived tokens for WS; reconnect with fresh token on expiry.

## Security checklist

- Load secrets from environment, not source control
- Validate `aud`, `iss`, `exp`, and clock skew
- Never log bearer tokens
- Rate-limit `/auth/login` and refresh endpoints
- Rotate signing keys with overlapping JWKS validity

## Clock skew and leeway

JWT validation fails when pod clocks drift. NTP on nodes is mandatory. Auth0 and java-jwt support `acceptLeeway` seconds for `exp` and `nbf`—use small leeway (30–60s), not hours.

## Key rotation with JWKS

For RS256, fetch JWKS from identity provider and cache with TTL. During rotation, accept keys from both `kid` values until old key expires—most providers publish overlapping JWKS entries.


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


## Version and compatibility notes

Pin library and control-plane versions in production manifests; track upstream release notes quarterly. Run upgrade drills in non-production before bumping minor versions that touch serialization, auth, or CRD schemas. Keep a compatibility matrix in your internal wiki listing supported Kubernetes, broker, and SDK versions validated together.

## Resources

- [Ktor Authentication documentation](https://ktor.io/docs/authentication.html) — plugin overview
- [Ktor JWT auth provider](https://ktor.io/docs/server-jwt.html) — configuration reference
- [Auth0 JWT best practices](https://auth0.com/docs/secure/tokens/json-web-tokens/json-web-token-best-practices) — claim design and storage
- [OWASP JWT cheat sheet](https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_for_Java_Cheat_Sheet.html) — common vulnerabilities
