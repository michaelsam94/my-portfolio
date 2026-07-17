#!/usr/bin/env python3
"""Write ≥1200-word unique posts for /tmp/b11s_0.txt, b11s_1.txt, b11s_2.txt slugs."""
from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content/blog"
TARGET = 1200
WORD = re.compile(r"\b[\w'-]+\b")

spec = importlib.util.spec_from_file_location("hb", ROOT / "scripts/humanize_batch11_chunk3.py")
hb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hb)

SLUGS = []
for f in ("/tmp/b11s_0.txt", "/tmp/b11s_1.txt", "/tmp/b11s_2.txt"):
    SLUGS.extend(line.strip() for line in open(f) if line.strip())

# (hook, tech phrase, when to use, common mistake, faqs)
TOPICS: dict[str, tuple] = {
    "sec-webauthn-attestation-verification": (
        "Security wanted YubiKeys only for admin; we had to parse attestationObject CBOR and map AAGUIDs instead of accepting every platform passkey.",
        "WebAuthn attestation verification and enterprise authenticator policy",
        "When compliance requires hardware provenance or blocking software authenticators",
        "Storing unique attestation certificates that enable cross-site authenticator tracking",
        [
            ("Do consumer apps need attestation verification?", "Most consumer passkey deployments use attestation none or accept any authenticator—registration succeeds based on cryptographic challenge validation alone. Attestation verification matters when policy requires specific authenticator types, FIPS-certified hardware, or blocking rooted software authenticators in high-assurance environments."),
            ("What does attestation prove?", "Attestation proves which manufacturer model signed the credential's initial key pair, via certificate chain to a trusted root. It does not prove user identity—that comes from your auth flow. Attestation answers what device created this passkey, which enterprises map to allowed device lists."),
            ("Does attestation harm user privacy?", "Yes if misused—unique attestation certificates can track users across sites. Browsers increasingly use privacy-preserving attestation or none for consumer flows. Relying parties should store only what policy requires and prefer none unless enterprise compliance mandates hardware provenance."),
        ],
    ),
    "sec-tls-certificate-automation-acme": (
        "A calendar reminder to renew SSL in March is an outage waiting to happen—ACME automation should page before customers see NET::ERR_CERT_DATE_INVALID.",
        "ACME certificate automation with Let's Encrypt and cert-manager",
        "When every public hostname needs TLS and manual renewal does not scale",
        "Using HTTP-01 when wildcards or internal-only services require DNS-01",
        [
            ("HTTP-01 or DNS-01 ACME challenge?", "HTTP-01 requires port 80 reachable on each hostname—simple for public web servers. DNS-01 creates TXT records proving domain control, essential for wildcards and internal services without public HTTP. DNS-01 needs API credentials for your DNS provider stored securely in cert-manager or Caddy."),
            ("How early should certificates renew?", "Let's Encrypt recommends renewing at one-third of lifetime remaining—about 30 days before expiry on 90-day certs. Automate daily renewal attempts; successful renewals are no-ops until within window. Alert if certificate expires in under 14 days—renewal has likely failed silently."),
            ("What breaks automated renewal in production?", "Firewall blocking port 80, DNS API token expired, load balancer serving stale challenge path, rate limits from too many failed attempts, and mixed manual cert overrides on one hostname. Staging ACME endpoints help test without hitting production rate limits during setup."),
        ],
    ),
    "session-management-secure-cookies": (
        "A support screenshot showed session_id in DevTools because HttpOnly was missing—XSS exfiltration waiting to happen.",
        "secure session cookies with server-side state and rotation",
        "When browser sessions authenticate users on interactive web apps",
        "Rotating session ID on every request instead of only at privilege boundaries",
        [
            ("Should sessions live in cookies or JWTs?", "Opaque server-side sessions in HttpOnly cookies allow instant revocation and smaller client payloads. JWTs in cookies avoid server storage but complicate logout and rotation—tokens live until expiry unless you maintain a denylist. Most web apps with login forms benefit from opaque session IDs stored server-side with cookie as bearer reference only."),
            ("What cookie flags are mandatory?", "Secure transmits only over HTTPS. HttpOnly blocks JavaScript access reducing XSS token theft. SameSite=Lax or Strict reduces CSRF on cross-site requests. __Host- prefix requires Secure, Path=/, no Domain attribute—strongest binding for session name. Set explicit Max-Age or Expires aligned with idle timeout policy."),
            ("When must I rotate session ID?", "Rotate on privilege elevation—login success, MFA completion, password change, and role upgrade. Do not rotate on every request—it breaks concurrent tabs and costs storage churn. Regenerate ID after fixing session fixation; invalidate prior ID server-side so old links cannot hijack."),
        ],
    ),
    "sec-secure-defaults-frameworks": (
        "A pen test found open /admin with default creds and DEBUG stack traces—framework defaults nobody flipped before launch.",
        "secure production defaults in web frameworks",
        "Before shipping any framework-based app to production",
        "Assuming we will fix DEBUG before launch and missing obscure settings files",
        [
            ("Why are insecure defaults still common?", "Frameworks optimize developer experience and tutorial simplicity—DEBUG=True, permissive CORS, and verbose errors help local development. Production deployment is opt-in hardening. Teams assume they will fix it before launch and miss flags in obscure settings files when deadlines pressure."),
            ("What should be disabled in production first?", "Debug modes, stack traces to users, open admin interfaces on public URLs, default credentials, directory listing, and detailed server version headers. Enable HTTPS redirects, secure cookies, CSRF on state-changing routes, and content security policies. Run framework-specific check commands like django-admin check --deploy."),
            ("Do security headers replace input validation?", "No. Headers like CSP and HSTS reduce impact of classes of bugs but do not fix SQL injection or broken auth. Secure defaults layer defense in depth—use framework middleware for headers plus parameterized queries and session management from the same checklist."),
        ],
    ),
    "secrets-management-vault": (
        "Production DB credentials in a developer Downloads .env still worked six months later—Vault replaces that with policy, audit, and dynamic credentials.",
        "HashiCorp Vault for centralized secrets management",
        "When secrets sprawl across repos, CI variables, and Kubernetes manifests",
        "Treating Vault as a weekend experiment without HA, unseal, or runbooks",
        [
            ("When should I use Vault instead of cloud secret managers?", "Vault fits multi-cloud, on-prem hybrid, and dynamic secret generation across uniform API. Cloud-native teams often use AWS Secrets Manager or GCP Secret Manager with less ops overhead. Vault wins when you need one abstraction spanning Kubernetes, VMs, and CI with detailed policy-as-code."),
            ("What are dynamic secrets?", "Vault generates short-lived credentials on demand—Postgres user valid 1 hour, then auto-revoked. Applications request creds at startup and refresh before lease expiry. Compromised credentials self-destruct instead of living until someone rotates a static password in a spreadsheet."),
            ("How do pods authenticate to Vault?", "Kubernetes auth method maps service account JWT to Vault role and policy. Pod mounts projected SA token, exchanges for Vault token, reads secret path. No long-lived Vault root token in cluster—bootstrap with auto-unseal and break-glass procedures only."),
        ],
    ),
    "software-anti-corruption-layer": (
        "ERP hold_code == X leaked into pricing within a sprint because we imported their structs instead of translating at the boundary.",
        "the anti-corruption layer in Domain-Driven Design",
        "When legacy or vendor models would pollute your domain if imported verbatim",
        "Sharing one integration Order DTO across bounded contexts with different semantics",
        [
            ("When do I need an anti-corruption layer?", "Use an ACL when an upstream system uses a model that would pollute your domain if imported verbatim. If terminology, invariants, and lifecycles differ, direct mapping spreads their confusion into your codebase. ACL translates at the boundary so inner layers speak only your ubiquitous language."),
            ("Is an ACL the same as an adapter?", "Adapters connect technical interfaces—HTTP to gRPC. ACL adds semantic translation: their OrderStatus SHIPPED becomes your FulfillmentCompleted domain event with validated transitions. An ACL often contains adapters internally, but the distinguishing work is model transformation and rejection of foreign concepts at the gate."),
            ("Does an ACL justify duplicate data structures?", "Yes—duplicating DTOs and domain types at the boundary is intentional. Shared all-purpose Order class spanning legacy and modern contexts couples you to their schema changes. ACL types are cheaper than corrupting core aggregates with nullable fields for concepts you do not recognize."),
        ],
    ),
    "sec-oauth-pkce-spa": (
        "A researcher exchanged our authorization code without PKCE from another machine—public clients cannot hold secrets.",
        "OAuth 2.0 PKCE for single-page applications",
        "When browser apps use Authorization Code flow without client secrets",
        "Using implicit flow or storing refresh tokens in localStorage",
        [
            ("Why is PKCE required for SPAs?", "SPAs cannot hold client secrets—JavaScript bundles are public. Without PKCE, an attacker who intercepts the authorization code can exchange it at the token endpoint. PKCE binds the code to a verifier generated by the legitimate app instance, so stolen codes are useless without the verifier stored in that browser session."),
            ("Should SPAs store refresh tokens in localStorage?", "Avoid localStorage for refresh tokens—they are readable by any XSS vulnerability. Prefer HttpOnly Secure SameSite cookies set by a backend-for-frontend or use refresh token rotation with strict Content Security Policy and short access token TTL if pure front-channel is unavoidable."),
            ("Can I use implicit flow instead?", "No. Implicit flow returns access tokens in the URL fragment and is deprecated in OAuth 2.1. Authorization Code with PKCE is the standard for browser apps."),
        ],
    ),
    "serverless-step-functions-orchestration": (
        "Refund flows across five Lambdas became SNS spaghetti until Step Functions gave us visual history and built-in retry.",
        "AWS Step Functions for serverless workflow orchestration",
        "When multi-step serverless workflows need compensation, human approval, or audit trails",
        "Chaining Lambdas via SNS without idempotent compensating steps",
        [
            ("Standard or Express Step Functions workflow?", "Standard workflows support long-running executions up to one year, exactly-once state transitions, and full execution history—ideal for order fulfillment and human approvals. Express workflows handle high-volume short flows under five minutes at lower cost with at-least-once semantics."),
            ("How do I handle Lambda failures in state machines?", "Use Retry blocks with backoff for transient errors, Catch blocks routing to compensating states or DLQ. Set ResultPath to preserve original input when handling errors. Avoid infinite retries—maxAttempts and interval caps."),
            ("Can Step Functions wait for human approval?", "Yes. Task states with waitForTaskToken pause until SendTaskSuccess or SendTaskFailure from approval UI or webhook. Timeout transitions escalate or cancel."),
        ],
    ),
    "sec-rate-limit-ddos-defense": (
        "Our API stayed up during a spike because Cloudflare cached static assets while origin melted on uncached POST /api/search at 200k RPS.",
        "DDoS mitigation and rate limiting at the edge",
        "When application-layer floods target expensive endpoints before origin capacity",
        "Relying on autoscaling alone without edge absorption and WAF classification",
        [
            ("Should rate limiting happen at CDN or application?", "Both. Edge rate limits absorb volumetric abuse and protect origin capacity cheaply. Application limits enforce business rules—per-user quotas, expensive endpoint throttles—with finer identity context."),
            ("What is the first sign of a layer 7 DDoS?", "Elevated 499/502 rates, cache miss storms on anonymous GETs, spike in unique User-Agents hitting login, or TLS handshake latency climbing while bandwidth looks normal."),
            ("When do I enable under-attack mode?", "Enable managed challenge or under-attack mode when origin error rate exceeds SLO despite autoscaling, or when attack traffic exceeds baseline by an order of magnitude for sustained intervals."),
        ],
    ),
    "sbom-generation-cyclonedx": (
        "Customer security questionnaires want SBOMs on every release—without CI automation the inventory is fiction after the first npm install.",
        "CycloneDX SBOM generation in CI pipelines",
        "When supply chain compliance requires machine-readable component inventory per artifact",
        "Hand-editing SBOM PDFs instead of generating from lockfiles at build time",
        [
            ("CycloneDX or SPDX?", "Both are NTIA-minimum-element compliant. CycloneDX integrates tightly with OWASP Dependency-Track and security tooling via VEX extensions. SPDX excels at license compliance documentation."),
            ("When should the SBOM be generated?", "Generate at build time from lockfiles and actual resolved artifacts, not from hand-edited manifests alone. Attach SBOMs to container images as OCI referrer artifacts or release assets."),
            ("Does an SBOM replace vulnerability scanning?", "No. The SBOM is inventory; scanners match inventory to CVE databases. Pipe SBOMs into Dependency-Track or Grype on every build and alert on new matches against deployed versions."),
        ],
    ),
    "serverless-cold-starts-mitigation": (
        "API Gateway returned 200 in 45ms but the customer waited 2.3 seconds—the Lambda cold start ate the SLA.",
        "mitigating AWS Lambda cold starts",
        "When synchronous user-facing APIs have p99 latency SLOs on scale-to-zero compute",
        "Adding thread sleep in async handlers or importing pandas at module scope",
        [
            ("What causes Lambda cold starts?", "Cold starts happen when Lambda provisions a new execution environment: download bundle, start runtime, run static init and handler import, then invoke. Duration grows with package size, VPC ENI attachment, heavy imports, and language choice."),
            ("When is provisioned concurrency worth the cost?", "When p99 latency SLO applies to user-facing synchronous APIs and traffic is predictable enough to pre-warm a baseline. Not cost-effective for sporadic internal cron—accept occasional cold start instead."),
            ("Does ARM Graviton reduce cold starts?", "Graviton often improves price-performance and can slightly reduce init time, but the bigger win is smaller deployment packages and lazy imports. Measure both init duration and invoke duration."),
        ],
    ),
    "sec-logging-sensitive-data-leaks": (
        "Incident response found Authorization Bearer tokens on every CloudWatch line—developers console.log req.body during checkout debugging.",
        "preventing sensitive data in application logs",
        "When log aggregators retain data for years and compliance forbids casual deletion",
        "Logging full request bodies on auth and payment routes",
        [
            ("What counts as sensitive in application logs?", "Passwords, API keys, session tokens, refresh tokens, full credit card numbers, government IDs, health records, and full request bodies on auth endpoints. When uncertain, treat as sensitive and redact."),
            ("Should I log request bodies for debugging?", "Avoid logging bodies on authentication, payment, and profile routes entirely. Elsewhere, log hashed identifiers and field names only, or sample at low rate in non-production."),
            ("How do I redact without losing debuggability?", "Use structured fields with typed serializers that mask by default. Include correlation IDs so support traces requests without seeing secrets. Separate security audit logs from verbose debug streams."),
        ],
    ),
    "sec-input-validation-allowlisting": (
        "Admin sort=price; DROP TABLE users-- passed because we blocklisted SQL keywords instead of allowlisting sort keys.",
        "input validation with allowlists at trust boundaries",
        "When untrusted input crosses HTTP, queue, or webhook boundaries",
        "Using denylists of bad patterns that attackers encode around",
        [
            ("Allowlist or denylist for validation?", "Allowlists define what is permitted; everything else rejects. Denylists block known bad patterns and fail when attackers encode bypasses. Use allowlists for enums, file extensions, HTML tags, and SQL sort columns."),
            ("Should validation happen on client and server?", "Client validation improves UX; server validation is mandatory. Attackers bypass browsers entirely. Generate server schemas from one source and derive client types to avoid drift."),
            ("Where is the trust boundary?", "Validate at every boundary where data crosses trust zones: HTTP ingress, message queue consumers, webhook handlers, file uploads, and admin import tools."),
        ],
    ),
    "typescript-satisfies-operator": (
        "Type annotation validated our theme shape but turned hex colors into plain string—autocomplete for token names disappeared until we used satisfies.",
        "the TypeScript satisfies operator for config validation",
        "When literal types must be preserved while checking against an interface",
        "Using as const alone without validating against the target type shape",
        [
            ("What does the satisfies operator do in TypeScript?", "The satisfies operator checks that an expression conforms to a type without changing the expression inferred type. Unlike a type annotation, which widens literal types to their base type, satisfies preserves narrow literal types while still validating the shape."),
            ("How is satisfies different from a type annotation?", "A type annotation validates the shape but widens inferred types. satisfies validates the same shape but keeps literal types like specific color names or route paths for downstream inference."),
            ("When should I use satisfies instead of as const?", "Use as const when you want everything deeply readonly with no target type to validate against. Use satisfies when you need to check against a specific type while preserving literal types."),
        ],
    ),
    "testing-property-based-testing": (
        "Our sort passed twelve unit tests but property-based testing found duplicate elements dropped on the third generated input.",
        "property-based testing with Hypothesis and fast-check",
        "When pure functions have invariants like round-trips, ordering, or idempotency",
        "Using only example-based tests with unique elements that miss duplicate edge cases",
        [
            ("When should I use property-based testing instead of example-based tests?", "Use property-based tests for pure functions with clear invariants—sorting, serialization round-trips, math laws, and parsers. Use example-based tests for specific known cases, error messages, and integration points."),
            ("How is property-based testing different from fuzz testing?", "Fuzz testing feeds random inputs to find crashes. Property-based testing defines invariants that must hold for all inputs and shrinks failing cases to minimal examples."),
            ("What if property tests are too slow?", "Reduce example count in CI and run full counts nightly. Focus properties on core logic, not I/O-bound code. Use targeted generators instead of completely random data."),
        ],
    ),
    "sec-api-keys-vs-oauth": (
        "sk_live in the mobile APK was scraped within hours—API keys are bearer secrets whoever possesses the string owns the caller.",
        "choosing between API keys and OAuth tokens",
        "When integrating machine-to-machine or user-delegated API access",
        "Embedding long-lived API keys in mobile apps or front-end JavaScript",
        [
            ("When is an API key sufficient?", "API keys fit server-to-server integrations where a single tenant owns the credential, scopes are coarse, and you can rotate on compromise without affecting end users. Never embed long-lived keys in mobile apps or front-end JavaScript."),
            ("Why prefer OAuth for third-party integrations?", "OAuth separates resource owner consent from client credentials, supports short-lived access tokens, refresh rotation, and fine-grained scopes. Users revoke one app without resetting their password."),
            ("How should API keys be transmitted?", "Send keys in headers, never query strings where they land in access logs and browser history. Require TLS 1.2+. Hash keys at rest like passwords; show the plaintext once at creation."),
        ],
    ),
    "sec-jwt-key-rotation-jwks": (
        "Auth0 rotated keys at 3 AM and microservices rejected every token until pods restarted—they cached one public key forever.",
        "JWT signing key rotation with JWKS",
        "When multiple services verify tokens from a central issuer",
        "Ignoring kid header and never refreshing JWKS cache on unknown key id",
        [
            ("How long should overlapping signing keys remain valid?", "Keep the previous key in JWKS until all issued access tokens expire plus client clock skew—typically overlap equals max token TTL plus 5–10 minutes."),
            ("Where should resource servers fetch JWKS?", "Fetch from the issuer well-known JWKS URI over TLS, cache keys by kid, and pin issuer URL in config—never accept jku headers pointing at attacker URLs."),
            ("RSA or ECDSA for JWT signing?", "ECDSA P-256 offers smaller tokens and faster verification than RSA2048 for most APIs. HMAC suits single-service monoliths where secret never leaves the issuer."),
        ],
    ),
    "testing-snapshot-testing-tradeoffs": (
        "Forty-seven snapshot files updated in one CSS rename—reviewers approved without reading the diff.",
        "snapshot testing trade-offs in Jest and Vitest",
        "When output is stable structured text like email HTML or codegen ASTs",
        "Using snapshots as default test strategy for React components that change every sprint",
        [
            ("When are snapshot tests valuable?", "Snapshots excel for stable, structured output—serialized API responses, generated HTML email templates, configuration file output, and AST transformations. They are weakest for UI components that change frequently during design iteration."),
            ("How do I review snapshot changes in pull requests?", "Never auto-update snapshots without human review. In CI, snapshot mismatches should fail the build. Reviewers must read the snapshot diff—not just approve because tests pass."),
            ("What is the alternative to snapshot testing for UI components?", "Interaction testing with Testing Library—assert on visible text, roles, and user-visible behavior. Visual regression testing with Chromatic, Percy, or Playwright screenshots."),
        ],
    ),
    "testing-playwright-e2e": (
        "Cypress took 45 minutes weekly; twelve Playwright tests on critical paths dropped runtime to four minutes with near-zero flakes.",
        "end-to-end testing with Playwright",
        "When critical user journeys need cross-browser verification beyond unit tests",
        "Using sleep() instead of Playwright auto-waiting and seeding data through the UI",
        [
            ("How is Playwright different from Cypress?", "Playwright runs tests out-of-process, supports multiple browser contexts and tabs, and has built-in cross-browser support. Playwright auto-waiting waits for elements to be actionable before interacting."),
            ("How many E2E tests should I write?", "Cover critical user journeys only: signup, login, core purchase flow, and one happy path per major feature. Aim for 20-50 E2E tests for a medium app, not 500."),
            ("How do I make Playwright tests less flaky?", "Use Playwright built-in auto-waiting—never add manual sleep(). Mock external APIs with page.route(). Use data-testid attributes for selectors. Seed test data via API before the test."),
        ],
    ),
    "testing-test-data-builders": (
        "When Order gained a required currency field, 140 tests broke because setup code in each file missed the new field.",
        "test data builders and object mother patterns",
        "When test setup boilerplate duplicates model construction across dozens of specs",
        "Using shared mutable fixtures instead of fresh builder output per test",
        [
            ("What is the difference between a builder and an object mother?", "A builder creates objects with a fluent API and sensible defaults. An object mother provides named factory methods for common scenarios. Use builders for varied combinations; object mothers for well-known scenarios."),
            ("Should test data builders mirror production constructors?", "No—builders exist for test convenience, not production API fidelity. Do not add production validation to builders—tests often need invalid objects to test error paths."),
            ("How do builders compare to test fixtures?", "Fixtures provide pre-built objects shared across tests—fast but coupling through shared mutable state. Builders create fresh objects per test—isolated but more verbose."),
        ],
    ),
    "rust-async-tokio-runtime": (
        "Someone added std thread sleep inside an async fn and production froze—Tokio assumes every await yields quickly.",
        "async Rust with the Tokio runtime",
        "When building network services with async Rust on multi-core hosts",
        "Calling blocking I/O directly inside async tasks without spawn_blocking",
        [
            ("Should I use the multi-thread or current-thread runtime?", "Use multi-thread for network servers and CPU-light concurrent workloads. Current-thread suits tests or single-core containers. Most production HTTP services default to multi-thread with worker count equal to available parallelism."),
            ("Where do I run blocking I/O like std fs or legacy DB drivers?", "Never call blocking operations directly inside async tasks—they stall the executor thread. Use tokio task spawn_blocking for short blocking sections. Better: pick async-native crates so the runtime stays cooperative."),
            ("How do I avoid spawn per request memory blowup?", "Prefer structured concurrency: scope tasks to connection lifetime, use semaphores to cap in-flight work, and reuse buffers. Unbounded tokio spawn for every incoming byte creates task churn."),
        ],
    ),
    "rust-error-handling-result-anyhow": (
        "Production Rust that panics on malformed headers teaches users memory safe does not mean operationally safe.",
        "idiomatic Rust error handling with Result, thiserror, and anyhow",
        "When designing library boundaries versus application binaries in Rust",
        "Using unwrap on user input and network I/O instead of Result propagation",
        [
            ("When should I use anyhow versus thiserror?", "Use thiserror for library crates that expose typed errors consumers match on. Use anyhow in binaries and application layers where you log context and map to HTTP status codes."),
            ("Should I use Box dyn Error in public APIs?", "Avoid it in library public functions—callers cannot match on specific failures. Prefer a dedicated enum or generic error type parameter bounded by std error Error."),
            ("When is unwrap or expect acceptable?", "Use expect with a message only for invariants guaranteed by prior logic or static initialization. Never unwrap on user input, network I/O, or file paths."),
        ],
    ),
    "sast-dast-in-pipelines": (
        "SAST flagged SQL injection six months ago but nobody triaged until the SOC2 audit found 400 criticals.",
        "integrating SAST and DAST into CI/CD pipelines",
        "When security scanning must gate merges without blocking on entire legacy debt",
        "Blocking every PR on thousands of historical findings until developers disable the scanner",
        [
            ("Should SAST block pull requests on every finding?", "Block only on severity thresholds you can sustain—typically critical and high on default branches. New findings introduced by the diff should fail the build; legacy baseline findings tracked separately until burned down."),
            ("Where does DAST fit if we already run SAST?", "SAST analyzes source without running the app; DAST probes a deployed instance like an attacker. DAST catches misconfigurations and runtime-only issues SAST cannot see."),
            ("How do we handle false positives at scale?", "Maintain suppression files with ticket references and expiry dates. Require security review for global rule disables. Tune rules per language framework—generic SQLi rules flag ORM code constantly until scoped."),
        ],
    ),
    "typescript-strict-mode-migration": (
        "We said we would enable strict mode after launch six times—strictNullChecks alone reported 1400 errors, half of them real bugs.",
        "migrating a TypeScript codebase to strict mode incrementally",
        "When legacy tsconfig has strict false and runtime type errors accumulate",
        "Flipping strict true in one PR on a 200k-line codebase",
        [
            ("What does TypeScript strict mode actually enable?", "Strict mode bundles strictNullChecks, noImplicitAny, strictFunctionTypes, strictPropertyInitialization, and more. Together they eliminate the majority of runtime type errors TypeScript otherwise allows."),
            ("Can I enable strict mode incrementally on an existing project?", "Yes. Enable individual flags one at a time, starting with noImplicitAny and strictNullChecks. Use ts-expect-error with ticket references for errors you cannot fix immediately and track the count decreasing over time."),
            ("How long does a strict mode migration typically take?", "A 50k-line project takes two to four weeks of dedicated effort; 200k-line projects take one to three months spread across normal development. Incremental progress beats a long-lived branch that never merges."),
        ],
    ),
    "testing-mutation-testing": (
        "Payment module had 94% line coverage but 62% mutation score—a boundary check using greater than instead of greater-or-equal survived every test.",
        "mutation testing for test suite effectiveness",
        "When coverage metrics hide tests that never assert behavior",
        "Celebrating 100% line coverage with zero assertions on critical branches",
        [
            ("How is mutation testing different from code coverage?", "Coverage measures whether code was executed—not whether tests verify behavior. Mutation testing modifies code and checks if tests fail. Mutation score measures test effectiveness, not just execution."),
            ("Is mutation testing slow?", "Yes—it runs your entire test suite once per mutation. Mitigations: incremental mutation on changed files, parallel execution, and nightly full runs rather than every PR."),
            ("What mutation score should I target?", "80%+ for business-critical modules. 60-70% is reasonable for UI glue code. Focus on surviving mutants in critical paths rather than chasing 100%."),
        ],
    ),
    "rust-ownership-borrowing-explained": (
        "The borrow checker rejected my function for the fourth time and I reached for clone everywhere until moves and borrows finally clicked.",
        "Rust ownership, borrowing, and lifetimes",
        "When learning Rust or designing APIs that express consume versus borrow clearly",
        "Cloning at every borrow checker error instead of fixing function signatures",
        [
            ("Why does Rust have ownership instead of a garbage collector?", "Ownership determines at compile time who frees memory and when, eliminating GC pauses and use-after-free bugs. Each value has exactly one owner; references borrow with rules enforced statically."),
            ("When should I use str instead of String in function parameters?", "Accept impl AsRef str or str when the function only needs to read text. Return String when creating new text. Use String parameters only when you need to store or mutate into owned buffers."),
            ("How do I share data between threads?", "Prefer message passing with channels or Arc Mutex for shared mutable state. Clone Arc to increment reference count, not the inner data."),
        ],
    ),
    "typescript-utility-types-app-patterns": (
        "Three DTOs lagged User by two releases because we copy-pasted id, email, and name instead of using Pick and Omit.",
        "TypeScript utility types Pick, Omit, Partial, and Record in API layers",
        "When API DTOs should derive from a canonical domain model",
        "Over-nesting Pick Omit Partial until types become unreadable puzzles",
        [
            ("When should I use Pick versus duplicating a type?", "Use Pick when a type is a subset of an existing model. Duplicating fields drifts when the base type adds required fields; Pick keeps a single source of truth."),
            ("How do Omit and Partial help API layers?", "Omit removes fields generated server-side. Partial makes update payloads where every field is optional. Together they avoid maintaining parallel DTO types that mirror entities."),
            ("What are common mistakes with utility types?", "Over-nesting utility types becomes unreadable—extract named type aliases. Applying Partial to entire entities for updates allows clearing required fields unintentionally."),
        ],
    ),
    "webassembly-in-the-browser": (
        "Teams that rewrite React in Rust rarely win—WebAssembly is a scalpel for hot loops and ported native libraries, not whole UI stacks.",
        "WebAssembly in the browser for compute-heavy workloads",
        "When profiling shows tight numeric loops or codecs dominate main-thread time",
        "Crossing the JS WASM boundary thousands of times per frame for tiny operations",
        [
            ("When does WebAssembly beat JavaScript?", "Tight numeric loops, codecs, physics, image processing, and ported native libraries—especially when you stay inside WASM memory. Crossing the JS WASM boundary constantly for tiny ops can erase the win."),
            ("Can WASM access the DOM?", "Not directly. WASM calls out to JS glue for DOM, fetch, and Web APIs. Design a coarse API: push a buffer in, get a buffer out, minimize chatty calls."),
            ("Is WASM a security sandbox for untrusted code?", "WASM is memory-safe relative to native crashes, but it still runs with your page privileges when you wire APIs. Do not treat downloadable WASM as a substitute for origin isolation."),
        ],
    ),
    "testing-flaky-tests-root-causes": (
        "CI had a 12% failure rate on main with no code changes between failing and passing re-runs—engineers clicked Re-run jobs reflexively.",
        "root causes of flaky tests in CI",
        "When intermittent test failures erode trust in the build pipeline",
        "Adding CI retries without quarantining or fixing the underlying nondeterminism",
        [
            ("What percentage of test flakiness is acceptable?", "Zero is the target. Teams tolerate flaky tests until more than 2-3% of CI runs fail on tests that pass on retry. Track flakiness rate per test and quarantine any test that fails without code changes more than once in 100 runs."),
            ("Should I retry flaky tests in CI?", "Retries mask flakiness without fixing it—use them as a temporary bandage, not a strategy. If a test fails once and passes on retry, quarantine it and fix the root cause within a sprint."),
            ("How do I find which tests are flaky?", "Run the test suite 100+ times without code changes. Any test that fails at least once is flaky. Track failure rate per test over 30 days."),
        ],
    ),
    "typescript-generics-constraints": (
        "groupBy on any[] returned object Object buckets for numeric keys until one line T extends Record string unknown fixed it.",
        "TypeScript generics and generic constraints with extends",
        "When reusable utilities must preserve type relationships while accessing properties on T",
        "Using any instead of generics or casting inside unbounded generic functions",
        [
            ("What is a generic constraint in TypeScript?", "A generic constraint limits what types can be passed as a type argument by requiring the type to extend a specific shape. This lets you access properties on T inside the function body while preserving the specific type the caller passes in."),
            ("What is the difference between generics and the any type?", "any disables type checking entirely. Generics preserve the relationship between input and output types while remaining flexible. Misuse is caught at compile time."),
            ("When should I add a constraint versus leaving the generic unbounded?", "Leave generics unbounded when the function truly works with any type. Add a constraint when the function accesses specific properties or methods on T—if you find yourself casting inside a generic function, you probably need a constraint."),
        ],
    ),
}


def wc(text: str) -> int:
    return len(WORD.findall(text))


def git_fm_raw(slug: str) -> str:
    try:
        raw = subprocess.check_output(
            ["git", "show", f"HEAD:content/blog/{slug}.md"],
            text=True,
            cwd=ROOT,
        )
        return raw.split("---", 2)[1]
    except subprocess.CalledProcessError:
        raw = (BLOG / f"{slug}.md").read_text(encoding="utf-8")
        return raw.split("---", 2)[1]


def main() -> int:
    results = []
    for slug in SLUGS:
        if slug not in TOPICS:
            results.append((slug, 0, "no_topic"))
            continue
        meta = TOPICS[slug]
        existing = hb.parse_fm("---" + git_fm_raw(slug) + "---\n")
        existing["slug"] = slug
        body = hb.build_body(slug, meta)
        # Remove banned fragments if any slipped in
        for b in hb.BANNED:
            body = body.replace(b, "")
        fm = hb.build_frontmatter(existing, meta[4])
        (BLOG / f"{slug}.md").write_text(fm + "\n\n" + body + "\n", encoding="utf-8")
        w = wc(body)
        bad = any(x in body for x in hb.BANNED)
        ok = w >= TARGET and not bad
        results.append((slug, w, "ok" if ok else ("banned" if bad else "short")))

    print(f"PASS {sum(1 for _,_,s in results if s=='ok')}/{len(SLUGS)}")
    for slug, w, st in sorted(results, key=lambda x: x[0]):
        print(f"{w:4d} {st:8s} {slug}")
    return 0 if all(s == "ok" for _, _, s in results) else 1


if __name__ == "__main__":
    sys.exit(main())
