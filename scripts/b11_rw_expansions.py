"""Unique expansion sections per b11_rw slug — no shared boilerplate."""

EXPANSIONS: dict[str, list[str]] = {
    "software-domain-driven-design-strategic": [
        """## Event storming before service boundaries

Alberto Brandolini's event storming places domain events on orange stickies, commands on blue, and aggregates emerge from clusters. Run this workshop before drawing microservice boxes. Participants who never agreed on what "Policy Issued" means will not agree on API schemas either. A four-hour session with product, engineering, and a domain expert surfaces natural context boundaries faster than month-long entity modeling.

Bring the messiest workflow—claims processing, order fulfillment, subscription lifecycle. Mark external systems in pink. Draw context boundaries around stable language clusters last. The output is a whiteboard photo and a glossary, not a deployment diagram.""",
        """## Context map relationship patterns in production

Anti-corruption layers translate legacy ERP purchase orders into your `PurchaseOrder` aggregate—never import their generated client classes into domain code. Customer-supplier relationships need explicit SLAs: Policy Admin publishes `CoverageChanged` events with thirty-day deprecation on old fields. Conformist is honest surrender when the vendor will not adapt—you model their JSON, not your ideal.

Open host service publishes a versioned REST API with stability guarantees. Shared kernel stays tiny: `Money`, `TenantId`, `UtcTimestamp`—not business rules both teams argue about forever.""",
        """## Modular monolith enforcement

Gradle modules, Java packages, or Nx project boundaries enforce compile-time isolation before network isolation. ArchUnit test: `no_classes_that().resideInAPackage("..billing..").should().dependOnClassesThat().resideInAPackage("..crm.internal..")`. Illegal imports fail CI.

Extract services when scaling or deployment cadence forces it—not when the diagram looks cleaner. A modular monolith with clear contexts outperforms fourteen chatty microservices sharing one database.""",
        """## Measuring strategic DDD adoption

Leading indicators: time-to-onboard per context (should decrease), cross-context import violations in CI (should stay zero), glossary PRs per quarter (should be nonzero in active domains). Lagging: integration bugs at ACL boundaries versus random null-pointer failures in shared entities.

When "Customer" appears in five meeting agendas with five meanings, schedule event storming—not another entity-relationship diagram committee.""",
    ],
    "security-referrer-policy-configuration": [
        """## Referrer-Policy interaction with CSP and HSTS

Referrer-Policy complements Content-Security-Policy and Strict-Transport-Security—it does not replace them. CSP violation reports may include referrer URLs; treat report endpoints as sensitive logs. HSTS prevents downgrade attacks where referrers would otherwise leak HTTPS URLs to HTTP endpoints.

Deploy all three in Helmet or edge config as a set. Test with securityheaders.com and Playwright header assertions after every CDN config change.""",
        """## Analytics attribution after tightening policy

Marketing teams often depend on full referrer paths for campaign reporting. After `strict-origin-when-cross-origin`, cross-origin analytics sees origins only. Migrate attribution to first-party UTM capture stored server-side, or use analytics tools that accept origin-level referrers plus explicit campaign parameters in links you control.

Coordinate with growth team before deploy—revenue attribution regressions are harder to debug than privacy incidents.""",
        """## Enterprise TLS inspection edge cases

Corporate proxies that MITM TLS rarely change HTML bytes but can affect subresource integrity and referrer behavior in exotic setups. Document bypass rules for corporate customers if checkout embeds fail only on inspected networks. Support tickets citing "works on phone, fails on office Wi-Fi" often trace here.""",
        """## Incident response for referrer leaks

If a leaked URL appears in a third-party dashboard: rotate any tokens in the path immediately, set `no-referrer` on affected routes, audit which third-party scripts receive subresource referrers, and notify privacy/compliance if PII was exposed. Post-incident: move identifiers from URLs to opaque server-side session state.""",
    ],
    "software-architecture-decision-records": [
        """## ADR review in pull requests

Require ADR link in PR template for changes touching persistence, auth, messaging, or public API contracts. Reviewers ask: "Does this implement ADR-0007 or supersede it?" Implementation PRs without ADR context get sent back—not because process, but because the decision rationale is missing.

For superseding decisions, open ADR PR first, merge, then implementation. Two PRs, clear history.""",
        """## ADR quality rubric

Score Accepted ADRs on: named alternatives rejected, measurable consequences stated, owner team identified, links to evidence (benchmark, spike PR). Reject ADRs that say "we chose X because it is best" without tradeoff honesty.

One page maximum. If longer, the decision is probably a design doc, not an ADR—split accordingly.""",
        """## Onboarding with ADRs

New hire week-one task: read last five Accepted ADRs for their squad and annotate questions in PR comments on the ADR files. Questions become glossary improvements. Engineers who understand why Postgres was chosen do not propose Mongo migrations in week two without reading context.""",
        """## ADRs versus design docs and RFCs

ADRs record decisions made. RFCs explore problems before deciding. Design docs describe how to build a feature within decided constraints. Mixing these breeds documents nobody reads. ADR: we use SQS not Kafka. Design doc: order fulfillment queue schema and retry policy. RFC: should we adopt event-driven architecture?""",
    ],
    "software-cqrs-event-sourcing-tradeoffs": [
        """## Snapshot strategy for long event streams

Aggregates with ten thousand events replay slowly on every load. Snapshot every N events or M minutes—store aggregate state blob plus `stream_version` at snapshot. Load snapshot, replay only events after snapshot version.

Test snapshot frequency against p99 command latency. Financial aggregates may snapshot every transaction; catalog aggregates may snapshot nightly.""",
        """## Event versioning worked example

Version 1 `PaymentCaptured` stored `amountCents`. Version 2 renames to `amountMinorUnits` for ISO 4217 minor units. Upcaster runs on read during replay—never mutate stored JSON in place. Golden tests: production event fixtures from S3 archive must replay to identical aggregate state after upcast chain.""",
        """## CQRS read model selection

Elasticsearch for full-text search facets. PostgreSQL materialized views for reporting. Redis for session-scoped read-your-writes. Pick read stores per query shape—one projector can fan out to multiple sinks from the same event subscription.

Denormalize aggressively on read side. Joins at query time defeat the purpose.""",
        """## When CRUD wins

Admin panels with fifty fields editing one row, internal tools with five users, and MVPs validating product-market fit—CRUD with `updated_at` and audit columns beats event sourcing operational tax. Revisit when audit law, multiple read projections, or temporal queries become requirements—not when the codebase feels boring.""",
    ],
    "serverless-event-driven-architecture": [
        """## Event schema governance

AsyncAPI or EventBridge Schema Registry enforces backward-compatible evolution. CI step: producer test events validate against schema; consumer contract tests subscribe to fixture events. Breaking changes require version bump in `type` field (`order.placed.v2`) and parallel consumers during migration window.

Never rename fields in place on the bus—add new field, deprecate old, remove after consumers upgrade.""",
        """## Partial batch failure in SQS Lambda

Report partial batch failures so only failed messages retry:

```python
return {"batchItemFailures": [{"itemIdentifier": record["messageId"]} for record in failed]}
```

Without this, one poison message in a batch of ten causes nine successful messages to reprocess—multiplying idempotency pressure and cost.""",
        """## Event-driven testing strategy

Contract tests publish golden events to LocalStack EventBridge; consumers assert side effects. Chaos test: kill consumer mid-batch, verify idempotency and DLQ routing. Load test: publish rate exceeds consumer throughput—queue depth should grow linearly, not explode into throttling errors.""",
        """## Cost model for event granularity

EventBridge bills per event. Publishing `LineItemAdded` twelve times per order costs twelve times `OrderPlaced` once with embedded line items. Coarse events for high-volume paths; fine events only when replay granularity or integrator contracts require them.""",
    ],
    "web-performance-font-loading": [
        """## Measuring font swap in RUM

Segment Core Web Vitals by pages that load custom fonts versus system-font fallbacks. If CLS spikes correlate with font swap events, revisit `size-adjust` on fallback faces before blaming images. Log `fonts.ready` timing alongside LCP in your RUM beacon — a 200ms gap between LCP and font swap often explains support tickets about "text jumping" after load.""",
    ],
    "web-forms-native-validation": [
        """## Custom validity messages without libraries

Use `setCustomValidity('')` to clear errors after the user corrects input — stale custom messages block submit even when values look valid. Pair with `reportValidity()` on blur for immediate feedback without waiting for submit. Avoid replacing native tooltips with custom divs unless you replicate `aria-invalid` and `aria-describedby` completely.""",
    ],
    "running-local-llms-on-device": [
        """## Quantization tradeoffs on Apple Silicon

Q4_K_M GGUF models on M-series Macs often hit 30–50 tokens per second for 7B parameters — usable for drafting, not real-time chat at scale. Q8 improves quality at half the speed. Profile memory: 7B Q4 needs roughly 5GB RAM; running alongside Xcode and Chrome leaves little headroom on 16GB machines. Prefer 3B models for IDE integrations that must stay responsive.""",
        """## Privacy boundary for on-device inference

Local inference keeps prompts on hardware — critical for legal review, medical notes, and unreleased code. Document clearly in privacy policies that cloud fallback is disabled when offline mode is on. If hybrid routing sends complex queries to cloud APIs, users must opt in explicitly; silent escalation destroys trust built by marketing "runs locally".""",
    ],
    "shared-data-layer-room-kmp": [
        """## Sync conflict resolution in Room

Last-write-wins loses edits when two devices update the same row offline. Version columns with optimistic locking surface conflicts to UI: "Your change conflicts with a newer version — merge or discard?" For collaborative fields, CRDTs or field-level timestamps beat whole-row LWW. Test airplane-mode edit on two emulators before shipping sync.""",
        """## KMP expect/actual for platform secure storage

Shared `TokenRepository` interface with Android `EncryptedSharedPreferences` actual and iOS Keychain actual keeps secrets off plain Room tables. Never store refresh tokens in unencrypted SQLite even if "just for debugging" — backup exports and rooted devices expose them.""",
    ],
    "software-vertical-slice-architecture": [
        """## Slice sizing heuristics

A slice should ship user-visible value in one to two weeks with one team. If the slice needs three services and a migration, split: first slice read-only UI on existing API, second slice write path. Slices are learning vehicles — oversized slices hide integration risk until month-end demos fail.""",
    ],
    "web-components-form-association": [
        """## formAssociated custom elements in shadow DOM

Set `static formAssociated = true` and implement `formAssociatedCallback` to participate in form submission from closed shadow roots. Without association, nested custom inputs never reach `FormData` — a common bug in design system components wrapped in shadow boundaries.""",
    ],
    "software-domain-driven-design-tactical": [
        """## Aggregate invariants under concurrency

Two requests adding items to the same `Order` aggregate need optimistic locking on version or serializable isolation — otherwise duplicate line items slip through. Domain services coordinate cross-aggregate rules (transfer between accounts) inside one transaction boundary; do not scatter invariants across application layer if they belong to the model.""",
        """## Domain events versus integration events

`OrderPlaced` inside the bounded context carries rich domain objects. `order.placed.v1` on the bus carries IDs and primitives only. Map at the boundary — publishing domain entities couples integrators to your refactorings.""",
    ],
    "software-hexagonal-ports-adapters": [
        """## Testing with fake adapters

Replace `PostgresOrderRepository` with in-memory fake implementing the same port in unit tests. HTTP adapters get contract tests against WireMock; domain tests never spin containers. If tests need Spring context, the hexagon leaked inward.""",
        """## Package structure that enforces direction

```
domain/       — entities, value objects, domain services
application/  — use cases, port interfaces
adapters/
  in/web/     — controllers
  out/db/     — repositories
  out/email/  — SMTP
```

ArchUnit or import-linter rules: domain imports nothing from adapters. CI fails on `domain.. -> adapters..` dependency.""",
    ],
    "state-of-flutter-2026": [
        """## Impeller as default renderer

Impeller on iOS and Android reduces shader compilation jank versus Skia GL backend. Profile on Mali and Adreno GPUs — rare overdraw regressions appear on older devices. Keep Skia fallback flag until your analytics show Impeller stable on your minimum supported OS versions.""",
    ],
    "voice-agents-stt-tts-pipelines": [
        """## End-of-turn detection latency budget

Voice agents feel broken above 700ms between user stop-speaking and first TTS byte. Streaming STT partials into LLM before utterance end cuts perceived latency — but premature commits produce wrong answers. Hybrid: start LLM on high-confidence partial, cancel if final transcript diverges.""",
    ],
}
