/** Topic-specific intros and technical sections keyed by slug prefix or exact slug. */
export const SPECIFIC = {
  "kotlin-context-receivers-practical": {
    intro: "Context receivers (formerly known as context parameters in early previews) let you pass implicit capabilities into functions without threading the same dependency through every call site. If you have ever written a deeply nested Compose or domain API where every layer needs a CoroutineScope, a Logger, or a TransactionManager, context receivers are Kotlin's answer to Scala's implicit parameters — with clearer syntax and compiler enforcement.",
    sections: [
      {
        h: "What context receivers actually solve",
        p: [
          "The pain point is parameter pollution. A function that needs a database connection, a clock, and a metrics registry forces every caller to supply them — or you hide them in a god-object `Environment` that everyone passes anyway. Context receivers invert the dependency direction: the caller declares what contexts are available, and the callee requests only what it needs in its signature.",
          "The compiler resolves contexts at compile time. Missing contexts are errors, not runtime surprises. That is the critical difference from service-locator antipatterns: you cannot accidentally call `processOrder()` without a `PaymentGateway` in scope.",
        ],
      },
      {
        h: "Syntax and scoping rules",
        p: [
          "A function with context receivers looks like this:",
          "```kotlin\ncontext(Logger, CoroutineScope)\nsuspend fun syncInventory(sku: String) {\n  log.info(\"sync $sku\")\n  launch { warehouse.push(sku) }\n}\n```",
          "Callers must also be in a context that provides `Logger` and `CoroutineScope`, or use a `with` block to introduce them. The resolution is lexical — contexts do not leak across unrelated scopes.",
          "Keep the number of contexts small. More than three implicit contexts on a function usually means your module boundary is wrong; extract an explicit facade instead.",
        ],
      },
    ],
    code: `context(Repo, Clock)\nfun placeOrder(id: OrderId): Order {\n  val now = clock.now()\n  return repo.save(Order(id, createdAt = now))\n}`,
  },
};

/** Paragraph variants selected by hash for generic topics — reduces verbatim repetition. */
export const VARIANTS = {
  intro: [
    (s, c) => `${s} is one of those topics that looks straightforward in a slide deck and gets complicated the first time traffic spikes or an auditor asks how you know it works. In ${c.toLowerCase()} systems, the difference between "we implemented it" and "we can operate it" shows up in metrics, incident history, and how confidently new engineers change the code.`,
    (s, c) => `Most teams encounter ${s.toLowerCase()} after the happy path is shipped — when retries stack up, costs climb, or a security review asks uncomfortable questions. That is the right time to treat it as engineering work with explicit tradeoffs, not a checklist item. This piece covers what I look for in design reviews and what I have seen fail in production ${c.toLowerCase()} stacks.`,
    (s, c) => `${s} sits in the boring center of reliable ${c.toLowerCase()} delivery: not flashy, but load-bearing. Get it wrong and you fight the same incident repeatedly; get it right and features ship on top of a stable base. Below is how I think about design, implementation, testing, and day-two operations.`,
  ],
  ops: [
    (s) => `Runbooks for ${s.toLowerCase()} should fit on one page: symptoms, dashboards, mitigation, rollback. If mitigation requires a senior engineer's tribal knowledge, the system is not operable yet.`,
    (s) => `Alert on user-visible symptoms for ${s.toLowerCase()} — error rate, latency SLO burn, queue depth — not on every internal counter. Noise desensitizes on-call engineers.`,
    (s) => `Game-day exercises for ${s.toLowerCase()} beat documentation every time. Inject latency, kill dependencies, and verify that retries, fallbacks, and idempotency behave as designed.`,
  ],
};

export const TERM_GLOSSARY = {
  idempotency: "An operation is idempotent if repeating it with the same arguments produces the same system state as executing it once — critical for safe retries on flaky networks.",
  "circuit-breaker": "A circuit breaker stops calling a failing dependency after error thresholds, giving it time to recover instead of drowning it in retry traffic.",
  outbox: "The transactional outbox pattern writes domain events to the same database transaction as business data, then a relay publishes them — avoiding dual-write inconsistency.",
  saga: "A saga coordinates multi-step distributed transactions with compensating actions instead of holding locks across services.",
  backpressure: "Backpressure signals upstream producers to slow down when consumers cannot keep pace, preventing unbounded memory growth.",
  rbac: "Role-based access control assigns permissions to roles, then roles to principals — simple to audit, coarse if roles proliferate.",
  webauthn: "WebAuthn enables passwordless authentication using public-key cryptography bound to authenticator devices.",
  crdt: "Conflict-free replicated data types merge concurrent edits without coordination, enabling offline-first sync.",
  otel: "OpenTelemetry provides vendor-neutral APIs for traces, metrics, and logs across services.",
  canary: "Canary releases route a small traffic slice to a new version before full rollout, limiting blast radius.",
};

export const pick = (arr, seed) => arr[Math.abs(hash(seed)) % arr.length];
export const hash = (s) => [...s].reduce((a, c) => ((a << 5) - a + c.charCodeAt(0)) | 0, 0);
