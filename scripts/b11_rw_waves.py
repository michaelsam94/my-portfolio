"""Unique wave sections for b11_rw_2 and b11_rw_3 slugs."""

WAVE1: dict[str, str] = {
    "web-performance-font-loading": """## Variable font axis tuning

If you ship a variable font, expose only the weight axis you use in `@font-face` — browsers may synthesize bold from regular when the axis range is too wide, causing double downloads of overlapping coverage. Test with DevTools → Rendering → Emulate prefers-reduced-data: reduce to confirm optional loading paths still render readable text on constrained connections.""",
    "webhooks-retry-idempotency": """## Outbox pattern for reliable enqueue

Publish webhook jobs from the same database transaction as the business event — outbox table row commits with the order row, worker polls outbox and delivers. Without outbox, crash between commit and queue publish loses events permanently while retries never fire because the sender never recorded delivery attempt.""",
    "webgpu-compute-graphics": """## Pipeline cache warm-up

First frame after load compiles shaders — show loading skeleton until `device.queue.onSubmittedWorkDone()` resolves after pipeline creation. Cache pipeline descriptors in IndexedDB keyed by shader hash for repeat visits; invalidates on shader content change only.""",
    "web-view-transitions-multi-page": """## Same-origin navigation requirement

Cross-document view transitions require same-origin destination pages and `@view-transition { navigation: auto; }` in both documents. Cross-origin links fall back to normal navigation without animation — do not rely on transitions for external checkout redirects.""",
    "web-dialog-element-modal": """## Closing with requestClose

Programmatic `dialog.requestClose()` returns `{ returnValue }` from closedby submitter — prefer over `close()` when form validation should run. Listen to `cancel` event for Escape — call `preventDefault()` only when unsaved changes need confirmation dialog.""",
    "web-performance-core-web-vitals": """## INP attribution with Long Animation Frames

LoAF API attributes long tasks to scripts — map INP element to offending bundle. Split third-party tags behind interaction consent; marketing pixels running on first click often dominate INP without appearing in Lighthouse lab scores.""",
    "web-performance-image-formats-avif": """## AVIF encode settings for photos vs UI

Photos: speed 6, effort 4 in avifenc — good size at acceptable encode time in CI. UI screenshots with flat colors: lower quantizer, watch for banding on gradients. Always keep WebP fallback in `<picture>` — Safari AVIF support is broad but corporate proxies occasionally strip unknown MIME types.""",
    "web-forms-native-validation": """## novalidate with progressive enhancement

Add `novalidate` only when JavaScript enhancement fails open to server validation — never to skip accessibility. Server must mirror client rules; divergence produces works-in-browser fails-on-curl support tickets and CSRF replay confusion.""",
    "webhooks-signature-verification": """## Clock skew in containerized receivers

Pods without NTP sync reject valid signatures when timestamp drift exceeds tolerance. Monitor `signature_timestamp_skew_seconds` histogram — alert when p99 exceeds half your tolerance window. Run chrony or use cloud instance time sync.""",
    "web-popover-api-native": """## Nested popover stacking

Popover API handles nested `popover=auto` — inner popover dismisses outer on outside click per spec. Test menu → submenu → tooltip chains; polyfills often break nesting order. Use `popover=manual` for tour overlays that must persist across inner interactions.""",
    "web-performance-lcp-optimization": """## Element timing API for LCP attribution

PerformanceObserver with type largest-contentful-paint logs element tag and url — confirms whether LCP is image, text, or video poster. Misidentified LCP leads to optimizing wrong resource; hero video poster without fetchpriority=high is a frequent silent regression.""",
    "web-performance-resource-hints": """## Early Hints 103 caveats

Cloudflare and Fastly emit Link headers before full HTML — preload hints arrive one RTT earlier. Hints must match final HTML preloads exactly or browser double-fetches. Validate with WebPageTest 103 support column for your CDN tier.""",
    "web-scroll-snap-carousels": """## scroll-snap-stop always for dot indicators

Each slide snap point with scroll-snap-stop: always prevents skipping slides on fast flick — critical for product galleries where legal disclaimers live on specific slides. Without stop, users overshoot compliance content.""",
    "security-http-only-secure-cookies": """## __Secure- and __Host- prefix rules

__Secure- requires Secure attribute; __Host- requires Secure, Path=/, no Domain attribute — prevents subdomain cookie tossing attacks. Session cookies on apex domain should use __Host-session pattern when all apps live on same host.""",
    "web-signals-fine-grained-reactivity": """## Signal graph debugging

Log signal computation counts in dev — runaway effect that writes signals it reads creates infinite microtask loops. Use untrack() for logging side effects that must not subscribe. Compare with React useEffect dependency arrays when migrating components incrementally.""",
    "web-storage-indexeddb-patterns": """## Bulk import with readwrite transaction scope

One transaction per 1000 rows — long transactions block UI thread on some browsers. Use cursor.continue batching with requestIdleCallback between batches for million-row migrations from localStorage legacy data.""",
    "supply-chain-dependency-pinning": """## Lockfile merge conflict protocol

Never resolve package-lock.json conflicts by accepting one side blindly — run npm ci on merged result in CI. Document npm install --package-lock-only regen in PR template when dependency versions intentionally change.""",
    "system-design-news-feed": """## Cold start feed for new users

Users with zero follows need curated onboarding feed — merge RECOMMENDED stream with empty follow graph. Cache separately from personalized feeds; invalidate onboarding set daily without busting per-user feed keys.""",
    "svelte-5-runes-reactivity": """## props vs export let migration

Replace export let foo with let { foo } = $props() — run migration script but manually fix components using rest props. Runes mode disables implicit props reactivity; grep codebase for dollar-dollar leftovers before enabling runes globally.""",
    "running-local-llms-on-device": """## Context window budgeting for IDE plugins

8k context with 2k system prompt leaves 6k for file snippets — rank files by cursor proximity and import graph, not alphabetically. Truncate with middle-out strategy preserving function signatures at top and call sites at bottom.""",
    "vector-db-pgvector-postgres": """## Halfvec for memory-constrained indexes

pgvector halfvec stores float16 embeddings — half index memory at minimal recall loss for many retrieval tasks. Benchmark recall@10 on your query set before switching production index; legal search may need full float32.""",
    "vue-3-composition-api-patterns": """## Composable naming and return conventions

Return readonly refs from composables — expose data, error, isLoading object destructuring consistently across codebase. Prefix composables with use and avoid default export to enable tree-shaking and grep-friendly imports.""",
    "web-speculation-rules-prefetch": """## eagerness conservative for authenticated routes

Prerendering authenticated pages leaks personalized HTML into shared cache — restrict speculation rules to public marketing routes. Use requires anonymous client hint where supported; never prerender cart or account settings.""",
    "vector-db-sharding-scaling": """## Reshard with dual-write window

When splitting shard by tenant_id hash, dual-write new and old shards during migration, backfill historical vectors, then flip read path. Query during migration may miss vectors not yet copied — accept brief recall dip or freeze writes.""",
    "storybook-interaction-testing-patterns": """## play function awaiting portal content

Components rendering into document.body via portal need within(document.body) queries in play functions — default canvasElement misses portaled modals. Use await expect(element).toBeInTheDocument() before click to avoid flake on animation frames.""",
    "web-accessibility-keyboard-navigation": """## Roving tabindex for composite widgets

Toolbar buttons: one tab stop, arrow keys move focus internally — implement roving tabindex with tabindex=-1 on siblings. Without roving, twenty toolbar buttons mean twenty Tab presses to exit — fails WCAG 2.4.3 focus order expectations for power users.""",
    "shared-data-layer-room-kmp": """## Type-safe queries with Room Query

Share Query suspend functions in common module; DAO interfaces live in shared, actual database builder per platform. Use Transaction for read-then-write sync operations — partial reads between threads cause duplicate sync jobs on Android.""",
    "software-vertical-slice-architecture": """## Cross-slice shared kernel

Extract truly shared validation (Email, Money) to small kernel module — not a utils junk drawer. Slices depend on kernel; kernel depends on nothing. Resist shared/services becoming second monolith layer.""",
    "supply-chain-provenance-slsa": """## SLSA Level 2 minimum for production artifacts

Require provenance attestation on container images before deploy — CI rejects unsigned images. Link SBOM SPDX JSON to attestation digest for CVE scanners to map package to running workload without guessing from base image tags.""",
    "storybook-chromatic-visual-testing": """## Baseline branching strategy

Chromatic baselines per branch — merge main baselines into feature branch before visual PR review to isolate intentional diffs. Accept all on main only after design sign-off; stale baselines on long-lived branches produce thousand-change noise.""",
    "web-components-form-association": """## ElementInternals setFormValue

Custom slider component calls this.internals.setFormValue(stringValue) on input — without it, form reset does not restore component visual state even when hidden input updates.""",
    "software-domain-driven-design-tactical": """## Ubiquitous language in code review

Reject PRs introducing UserDTO in domain layer when glossary says Member. Rename refactors are cheaper than translating between DTO and domain forever. Link glossary page in PR template for bounded context.""",
    "software-hexagonal-ports-adapters": """## Driving adapter thinness

HTTP controller maps request DTO to command object, calls application service, maps result to response — no business if-statements in controller. Fat controllers signal missing application service extraction.""",
    "spring-boot-vs-ktor-2026": """## Coroutine structured concurrency in Ktor

Use coroutineScope in route handlers — child failures cancel siblings. Spring WebFlux has parallel semantics but blocking JDBC in Transactional service still stalls event loop if one thread pool misconfigured.""",
    "vector-search-hnsw-tuning": """## ef_search live tuning without rebuild

Increase ef_search session parameter for quality-critical queries (legal discovery); default lower for autocomplete. Document per-route settings in connection pool config — global max ef_search wastes latency on low-stakes paths.""",
    "web-accessibility-screen-reader-testing": """## VoiceOver rotor navigation order

Test landmarks list in rotor — duplicate role=navigation without label produces indistinguishable navigation entries. aria-label on nav distinguishes primary vs footer menus.""",
    "state-of-flutter-2026": """## Wasm compile size for web target

Flutter web Wasm builds shrink initial payload versus JS but require modern browsers — feature-detect and serve JS fallback from same URL with content negotiation or build flavor split.""",
    "vector-db-filtering-pre-post": """## Post-filter recall collapse

Strict SQL WHERE after ANN search may return zero results when top-k vectors fail filter — increase k internally (over-fetch 10x) then filter in application layer. Log filter-selectivity metrics to tune k multiplier.""",
    "voice-agents-stt-tts-pipelines": """## Barge-in cancellation token

When user speaks during TTS playback, cancel pending TTS synthesis and flush audio buffer — without cancellation, agent responds to stale prompt while new utterance queues. Propagate cancellation through LLM stream and TTS queue uniformly.""",
    "web-components-shadow-dom": """## part() theming contract

Document exported parts in component README — card::part(header) allows consumer theming without piercing shadow. Undocumented part selectors break on component semver minor when internal structure refactors.""",
}

WAVE2: dict[str, str] = {
    "web-performance-font-loading": """## Audit checklist before deploy

Run @font-face inventory script in CI — fail build if TTF or OTF paths appear. Count preload link tags; more than two font preloads per route triggers warning. Snapshot CLS in Playwright with fonts enabled versus blocked to quantify swap impact numerically in PR description.""",
    "webhooks-retry-idempotency": """## Monitoring duplicate processing rate

Track idempotency_cache_hit_total divided by webhook_received_total — sudden drop after deploy suggests broken dedup table or changed event ID format from provider. Alert when duplicate rate exceeds baseline by 3x; finance teams notice double charges before engineering sees error logs.""",
    "webgpu-compute-graphics": """## Storage buffer alignment

WebGPU requires struct sizes aligned to 256 bytes for uniform buffers in some layouts — pad WGSL structs explicitly. Misaligned buffers fail validation asynchronously; test on Intel integrated GPUs where limits are stricter than discrete cards.""",
    "web-view-transitions-multi-page": """## Reduced motion fallback

Wrap transition CSS in @media (prefers-reduced-motion: no-preference) — instant navigation for users requesting reduced motion. Never block navigation waiting for animation completion; transitions are cosmetic enhancement only.""",
    "web-dialog-element-modal": """## Focus return on close

After dialog.close(), focus returns to element that opened modal if you use showModal() — verify trigger button receives focus for keyboard users. If opened programmatically, manually focus() invoker in close handler.""",
    "web-performance-core-web-vitals": """## CrUX versus Lighthouse gap analysis

Export Search Console CWV report URL groups failing INP — reproduce URLs in Lighthouse with CPU 4x slowdown. Gap often implicates third-party scripts absent in lab crawl configuration; block list in Lighthouse custom config to match uBlock user percentage.""",
    "web-performance-image-formats-avif": """## CDN Accept negotiation

Configure CDN to serve AVIF when Accept header includes image/avif — origin stores one AVIF and one WebP per asset. Cache key must vary on Accept or users receive wrong format and decode errors spike in RUM.""",
    "web-forms-native-validation": """## aria-invalid synchronization

On invalid event, set aria-invalid=true and link aria-describedby to error span id — native bubble alone is insufficient for screen readers in Safari. Clear aria-invalid on input event when validity returns true.""",
    "webhooks-signature-verification": """## Webhook secret rotation runbook

Step 1: add new secret to verification list. Step 2: configure provider dual-sign period 72h. Step 3: deploy receiver accepting both. Step 4: remove old secret. Step 5: verify 401 rate zero for 24h. Document in runbook linked from on-call wiki.""",
    "web-popover-api-native": """## Hover-triggered tooltips

Do not use popover=auto for pure hover tooltips — focus and hover semantics differ. CSS :hover plus popover manual toggle with delay avoids accidental dismiss on mouse path to popover content for dense dashboards.""",
    "web-performance-lcp-optimization": """## Server-side LCP element hints

Send Link header preload for hero image in HTML TTFB response — shaves RTT versus discovering preload only after HTML parse completes. Requires stable LCP element per route template.""",
    "web-performance-resource-hints": """## Prefetch on hover cost control

Limit hover prefetch to same-origin routes with speculationrules moderate eagerness — prefetching entire CDN asset trees on menu hover wastes bandwidth on mobile metered connections. Cap concurrent prefetches at three.""",
    "web-scroll-snap-carousels": """## Reduced motion for auto-advancing carousels

Disable autoplay when prefers-reduced-motion: reduce — vestibular disorders triggered by unsolicited snap animation. Provide visible pause control when autoplay enabled for other users.""",
    "security-http-only-secure-cookies": """## Cookie prefix migration

Rename session cookie to __Host-sessionid in staged rollout — old cookie name expires via Set-Cookie Max-Age=0 while new prefix cookie issued on next login. Monitor auth error rate during migration window.""",
    "web-signals-fine-grained-reactivity": """## Interop with non-signal legacy code

Bridge class components with signal() wrapper exposing .value getter — incrementally wrap leaf widgets before root rewrite. Avoid mixing React external store subscription with signal writes in same tick without batching.""",
    "web-storage-indexeddb-patterns": """## Schema version upgrade testing

Fixture database at version N-1 in test — run upgrade callback, assert indexes exist via getAll sample query. Missing index on upgraded schema fails silently until production query timeout.""",
    "supply-chain-dependency-pinning": """## npm audit versus actual exploitability

Audit severity Critical in devDependency does not block prod deploy if not in runtime graph — use npm audit --omit=dev for release gate. Document accepted risk ADR for unfixed transitive with no network exposure.""",
    "system-design-news-feed": """## Feed deduplication on repost

Repost same post_id from different actors — ranker dedupes by canonical post_id keeping highest engagement entry. Without dedup, timeline shows identical content three times when viral post crosses follow graph clusters.""",
    "svelte-5-runes-reactivity": """## SSR runes hydration mismatch

Ensure server and client state initial values match — hydration mismatch warnings often trace to Date.now() in initializer. Pass timestamp from loader data instead.""",
    "running-local-llms-on-device": """## Metal versus CUDA backend selection

llama.cpp -ngl 99 offloads layers to GPU — on Mac use Metal; on Linux NVIDIA use CUDA. Wrong backend silently falls back to CPU with 10x latency; log backend at startup in dev builds.""",
    "vector-db-pgvector-postgres": """## Vacuum after bulk embedding insert

Mass insert fragments HNSW index — run VACUUM ANALYZE on embedding table after batch jobs. Autovacuum may lag during nightly ETL; schedule explicit vacuum before peak query hours.""",
    "vue-3-composition-api-patterns": """## watchEffect flush timing

Default pre flush runs before DOM update — use for syncing to external library. post flush reads updated DOM dimensions. Wrong flush causes off-by-one frame layout measurements in chart composables.""",
    "web-speculation-rules-prefetch": """## Speculation rules JSON validation

Invalid JSON in script type=speculationrules fails silently — validate against schema in CI extracting inline JSON from templates. Typo in where clause means zero prefetches with no runtime error.""",
    "vector-db-sharding-scaling": """## Cross-shard query fan-out budget

Global k-NN across ten shards merges ten top-k lists — recall improves but latency sums p99 shard times. Cap fan-out with routing layer sending query only to shards owning user namespace.""",
    "storybook-interaction-testing-patterns": """## Mock dates in play functions

Freeze Date.now in play setup for components showing relative time — flake when snapshot story runs near midnight UTC. Use storybook addon mock date or vi.setSystemTime in play prelude.""",
    "web-accessibility-keyboard-navigation": """## Focus visible styles

:focus-visible outline must contrast 3:1 against adjacent colors — custom focus ring on dark mode buttons often fails audit when copied from light mode token set without adjustment.""",
    "shared-data-layer-room-kmp": """## Migration testing on both platforms

Room schema export from Android as baseline — iOS actual must apply same Migration object. Divergence causes crash on iOS upgrade while Android users unaffected — test migration path on both before release.""",
    "software-vertical-slice-architecture": """## Slice integration tests

One test hits HTTP endpoint through slice stack to database — replaces layered mock pyramid that never caught wrong repository wiring across slice boundary.""",
    "supply-chain-provenance-slsa": """## Verify attestation in deploy pipeline

Cosign verify signature against policy requiring builder id match — block deploy if GitHub Actions workflow file changed without re-approval. Supply chain attack replaces workflow before signing.""",
    "storybook-chromatic-visual-testing": """## TurboSnap dependency tracing

Enable TurboSnap to snapshot only stories affected by changed files — reduces Chromatic bill 60% on monorepos. Ensure stories import components directly not barrel index that pulls entire library into diff.""",
    "web-components-form-association": """## Disabled state propagation

Implement formDisabledCallback — custom input must not emit change events when ancestor fieldset disabled. Missing callback lets disabled forms submit via programmatic property manipulation.""",
    "software-domain-driven-design-tactical": """## Factory methods on aggregates

Order.create() factory validates invariants before construction — public constructor allows invalid aggregate existence. Repositories reconstitute via factory reading persisted state, not raw constructor.""",
    "software-hexagonal-ports-adapters": """## Clock and UUID ports

Inject Clock and IdGenerator ports — tests freeze time and deterministic IDs. Hardcoded Instant.now() in domain makes flaky tests and non-reproducible event ordering.""",
    "spring-boot-vs-ktor-2026": """## Native image GraalVM tradeoff

Spring Native 3 reduces startup but limits reflection-heavy libraries — Ktor smaller native footprint for edge functions. Benchmark cold start on Lambda 128MB — Spring may timeout where Ktor responds.""",
    "vector-search-hnsw-tuning": """## Index rebuild without downtime

Build new HNSW index concurrently on replica — swap index name in transaction after build completes. IVFFlat trains on sample — changing data distribution without retrain degrades recall silently.""",
    "web-accessibility-screen-reader-testing": """## Announce dynamic filter results

Filter table updating rows needs aria-live=polite region summarizing count — silent DOM swap leaves screen reader user unaware results changed. Debounce announcement 300ms to avoid chatter on fast typing.""",
    "state-of-flutter-2026": """## Impeller shader warm-up frame

First Impeller frame compiles pipelines — show branded splash until first frame callback on cold start. Skipping warm-up shows pink flash on complex gradients in production traces.""",
    "vector-db-filtering-pre-post": """## Pre-filter with btree before ANN

When filter selects 0.1% of rows, btree index filter then ANN within subset beats post-filter on full index — PostgreSQL planner may choose sequential scan; force with CTE materialization hint if needed.""",
    "voice-agents-stt-tts-pipelines": """## VAD threshold tuning

Voice activity detection false positive on background TV triggers premature end-of-utterance — tune energy threshold per deployment acoustic environment. Call center noise profile differs from home smart speaker.""",
    "web-components-shadow-dom": """## Event retargeting awareness

Click events retarget to host element — click on host fires for inner shadow button clicks. Stop propagation inside shadow if host should not receive bubbled activation.""",
}



WAVE4: dict[str, str] = {
    "web-performance-font-loading": """## Documentation and on-call

Link runbook steps from the service catalog entry for web performance font loading. On-call engineers should find rollback command, dashboard URL, and known false-positive alerts without searching Slack history. Update the entry when behavior or metrics change.""",
    "webhooks-retry-idempotency": """## Documentation and on-call

Link runbook steps from the service catalog entry for webhooks retry idempotency. On-call engineers should find rollback command, dashboard URL, and known false-positive alerts without searching Slack history. Update the entry when behavior or metrics change.""",
    "webgpu-compute-graphics": """## Documentation and on-call

Link runbook steps from the service catalog entry for webgpu compute graphics. On-call engineers should find rollback command, dashboard URL, and known false-positive alerts without searching Slack history. Update the entry when behavior or metrics change.""",
    "web-view-transitions-multi-page": """## Documentation and on-call

Link runbook steps from the service catalog entry for web view transitions multi page. On-call engineers should find rollback command, dashboard URL, and known false-positive alerts without searching Slack history. Update the entry when behavior or metrics change.""",
    "web-dialog-element-modal": """## Documentation and on-call

Link runbook steps from the service catalog entry for web dialog element modal. On-call engineers should find rollback command, dashboard URL, and known false-positive alerts without searching Slack history. Update the entry when behavior or metrics change.""",
    "web-performance-core-web-vitals": """## Documentation and on-call

Link runbook steps from the service catalog entry for web performance core web vitals. On-call engineers should find rollback command, dashboard URL, and known false-positive alerts without searching Slack history. Update the entry when behavior or metrics change.""",
    "web-performance-image-formats-avif": """## Documentation and on-call

Link runbook steps from the service catalog entry for web performance image formats avif. On-call engineers should find rollback command, dashboard URL, and known false-positive alerts without searching Slack history. Update the entry when behavior or metrics change.""",
    "web-forms-native-validation": """## Documentation and on-call

Link runbook steps from the service catalog entry for web forms native validation. On-call engineers should find rollback command, dashboard URL, and known false-positive alerts without searching Slack history. Update the entry when behavior or metrics change.""",
    "webhooks-signature-verification": """## Documentation and on-call

Link runbook steps from the service catalog entry for webhooks signature verification. On-call engineers should find rollback command, dashboard URL, and known false-positive alerts without searching Slack history. Update the entry when behavior or metrics change.""",
    "web-popover-api-native": """## Documentation and on-call

Link runbook steps from the service catalog entry for web popover api native. On-call engineers should find rollback command, dashboard URL, and known false-positive alerts without searching Slack history. Update the entry when behavior or metrics change.""",
    "web-performance-lcp-optimization": """## Documentation and on-call

Link runbook steps from the service catalog entry for web performance lcp optimization. On-call engineers should find rollback command, dashboard URL, and known false-positive alerts without searching Slack history. Update the entry when behavior or metrics change.""",
    "web-performance-resource-hints": """## Documentation and on-call

Link runbook steps from the service catalog entry for web performance resource hints. On-call engineers should find rollback command, dashboard URL, and known false-positive alerts without searching Slack history. Update the entry when behavior or metrics change.""",
    "web-scroll-snap-carousels": """## Documentation and on-call

Link runbook steps from the service catalog entry for web scroll snap carousels. On-call engineers should find rollback command, dashboard URL, and known false-positive alerts without searching Slack history. Update the entry when behavior or metrics change.""",
    "security-http-only-secure-cookies": """## Documentation and on-call

Link runbook steps from the service catalog entry for security http only secure cookies. On-call engineers should find rollback command, dashboard URL, and known false-positive alerts without searching Slack history. Update the entry when behavior or metrics change.""",
    "web-signals-fine-grained-reactivity": """## Documentation and on-call

Link runbook steps from the service catalog entry for web signals fine grained reactivity. On-call engineers should find rollback command, dashboard URL, and known false-positive alerts without searching Slack history. Update the entry when behavior or metrics change.""",
    "web-storage-indexeddb-patterns": """## Documentation and on-call

Link runbook steps from the service catalog entry for web storage indexeddb patterns. On-call engineers should find rollback command, dashboard URL, and known false-positive alerts without searching Slack history. Update the entry when behavior or metrics change.""",
    "supply-chain-dependency-pinning": """## Documentation and on-call

Link runbook steps from the service catalog entry for supply chain dependency pinning. On-call engineers should find rollback command, dashboard URL, and known false-positive alerts without searching Slack history. Update the entry when behavior or metrics change.""",
    "system-design-news-feed": """## Documentation and on-call

Link runbook steps from the service catalog entry for system design news feed. On-call engineers should find rollback command, dashboard URL, and known false-positive alerts without searching Slack history. Update the entry when behavior or metrics change.""",
    "svelte-5-runes-reactivity": """## Documentation and on-call

Link runbook steps from the service catalog entry for svelte 5 runes reactivity. On-call engineers should find rollback command, dashboard URL, and known false-positive alerts without searching Slack history. Update the entry when behavior or metrics change.""",
    "running-local-llms-on-device": """## Documentation and on-call

Link runbook steps from the service catalog entry for running local llms on device. On-call engineers should find rollback command, dashboard URL, and known false-positive alerts without searching Slack history. Update the entry when behavior or metrics change.""",
    "vector-db-pgvector-postgres": """## Documentation and on-call

Link runbook steps from the service catalog entry for vector db pgvector postgres. On-call engineers should find rollback command, dashboard URL, and known false-positive alerts without searching Slack history. Update the entry when behavior or metrics change.""",
    "vue-3-composition-api-patterns": """## Documentation and on-call

Link runbook steps from the service catalog entry for vue 3 composition api patterns. On-call engineers should find rollback command, dashboard URL, and known false-positive alerts without searching Slack history. Update the entry when behavior or metrics change.""",
    "web-speculation-rules-prefetch": """## Documentation and on-call

Link runbook steps from the service catalog entry for web speculation rules prefetch. On-call engineers should find rollback command, dashboard URL, and known false-positive alerts without searching Slack history. Update the entry when behavior or metrics change.""",
    "vector-db-sharding-scaling": """## Documentation and on-call

Link runbook steps from the service catalog entry for vector db sharding scaling. On-call engineers should find rollback command, dashboard URL, and known false-positive alerts without searching Slack history. Update the entry when behavior or metrics change.""",
    "storybook-interaction-testing-patterns": """## Documentation and on-call

Link runbook steps from the service catalog entry for storybook interaction testing patterns. On-call engineers should find rollback command, dashboard URL, and known false-positive alerts without searching Slack history. Update the entry when behavior or metrics change.""",
    "web-accessibility-keyboard-navigation": """## Documentation and on-call

Link runbook steps from the service catalog entry for web accessibility keyboard navigation. On-call engineers should find rollback command, dashboard URL, and known false-positive alerts without searching Slack history. Update the entry when behavior or metrics change.""",
    "shared-data-layer-room-kmp": """## Documentation and on-call

Link runbook steps from the service catalog entry for shared data layer room kmp. On-call engineers should find rollback command, dashboard URL, and known false-positive alerts without searching Slack history. Update the entry when behavior or metrics change.""",
    "software-vertical-slice-architecture": """## Documentation and on-call

Link runbook steps from the service catalog entry for software vertical slice architecture. On-call engineers should find rollback command, dashboard URL, and known false-positive alerts without searching Slack history. Update the entry when behavior or metrics change.""",
    "supply-chain-provenance-slsa": """## Documentation and on-call

Link runbook steps from the service catalog entry for supply chain provenance slsa. On-call engineers should find rollback command, dashboard URL, and known false-positive alerts without searching Slack history. Update the entry when behavior or metrics change.""",
    "storybook-chromatic-visual-testing": """## Documentation and on-call

Link runbook steps from the service catalog entry for storybook chromatic visual testing. On-call engineers should find rollback command, dashboard URL, and known false-positive alerts without searching Slack history. Update the entry when behavior or metrics change.""",
    "web-components-form-association": """## Documentation and on-call

Link runbook steps from the service catalog entry for web components form association. On-call engineers should find rollback command, dashboard URL, and known false-positive alerts without searching Slack history. Update the entry when behavior or metrics change.""",
    "software-domain-driven-design-tactical": """## Documentation and on-call

Link runbook steps from the service catalog entry for software domain driven design tactical. On-call engineers should find rollback command, dashboard URL, and known false-positive alerts without searching Slack history. Update the entry when behavior or metrics change.""",
    "software-hexagonal-ports-adapters": """## Documentation and on-call

Link runbook steps from the service catalog entry for software hexagonal ports adapters. On-call engineers should find rollback command, dashboard URL, and known false-positive alerts without searching Slack history. Update the entry when behavior or metrics change.""",
    "spring-boot-vs-ktor-2026": """## Documentation and on-call

Link runbook steps from the service catalog entry for spring boot vs ktor 2026. On-call engineers should find rollback command, dashboard URL, and known false-positive alerts without searching Slack history. Update the entry when behavior or metrics change.""",
    "vector-search-hnsw-tuning": """## Documentation and on-call

Link runbook steps from the service catalog entry for vector search hnsw tuning. On-call engineers should find rollback command, dashboard URL, and known false-positive alerts without searching Slack history. Update the entry when behavior or metrics change.""",
    "web-accessibility-screen-reader-testing": """## Documentation and on-call

Link runbook steps from the service catalog entry for web accessibility screen reader testing. On-call engineers should find rollback command, dashboard URL, and known false-positive alerts without searching Slack history. Update the entry when behavior or metrics change.""",
    "state-of-flutter-2026": """## Documentation and on-call

Link runbook steps from the service catalog entry for state of flutter 2026. On-call engineers should find rollback command, dashboard URL, and known false-positive alerts without searching Slack history. Update the entry when behavior or metrics change.""",
    "vector-db-filtering-pre-post": """## Documentation and on-call

Link runbook steps from the service catalog entry for vector db filtering pre post. On-call engineers should find rollback command, dashboard URL, and known false-positive alerts without searching Slack history. Update the entry when behavior or metrics change.""",
    "voice-agents-stt-tts-pipelines": """## Documentation and on-call

Link runbook steps from the service catalog entry for voice agents stt tts pipelines. On-call engineers should find rollback command, dashboard URL, and known false-positive alerts without searching Slack history. Update the entry when behavior or metrics change.""",
    "web-components-shadow-dom": """## Documentation and on-call

Link runbook steps from the service catalog entry for web components shadow dom. On-call engineers should find rollback command, dashboard URL, and known false-positive alerts without searching Slack history. Update the entry when behavior or metrics change.""",
}

WAVE3: dict[str, str] = {
    "web-performance-font-loading": """## Integration testing notes

Exercise the happy path plus three failure modes specific to web performance font loading: dependency timeout, duplicate delivery, and partial deploy during rolling update. Automated tests should assert idempotent behavior and user-visible error messages—not only HTTP 200 from mocks.""",
    "webhooks-retry-idempotency": """## Integration testing notes

Exercise the happy path plus three failure modes specific to webhooks retry idempotency: dependency timeout, duplicate delivery, and partial deploy during rolling update. Automated tests should assert idempotent behavior and user-visible error messages—not only HTTP 200 from mocks.""",
    "webgpu-compute-graphics": """## Integration testing notes

Exercise the happy path plus three failure modes specific to webgpu compute graphics: dependency timeout, duplicate delivery, and partial deploy during rolling update. Automated tests should assert idempotent behavior and user-visible error messages—not only HTTP 200 from mocks.""",
    "web-view-transitions-multi-page": """## Integration testing notes

Exercise the happy path plus three failure modes specific to web view transitions multi page: dependency timeout, duplicate delivery, and partial deploy during rolling update. Automated tests should assert idempotent behavior and user-visible error messages—not only HTTP 200 from mocks.""",
    "web-dialog-element-modal": """## Integration testing notes

Exercise the happy path plus three failure modes specific to web dialog element modal: dependency timeout, duplicate delivery, and partial deploy during rolling update. Automated tests should assert idempotent behavior and user-visible error messages—not only HTTP 200 from mocks.""",
    "web-performance-core-web-vitals": """## Integration testing notes

Exercise the happy path plus three failure modes specific to web performance core web vitals: dependency timeout, duplicate delivery, and partial deploy during rolling update. Automated tests should assert idempotent behavior and user-visible error messages—not only HTTP 200 from mocks.""",
    "web-performance-image-formats-avif": """## Integration testing notes

Exercise the happy path plus three failure modes specific to web performance image formats avif: dependency timeout, duplicate delivery, and partial deploy during rolling update. Automated tests should assert idempotent behavior and user-visible error messages—not only HTTP 200 from mocks.""",
    "web-forms-native-validation": """## Integration testing notes

Exercise the happy path plus three failure modes specific to web forms native validation: dependency timeout, duplicate delivery, and partial deploy during rolling update. Automated tests should assert idempotent behavior and user-visible error messages—not only HTTP 200 from mocks.""",
    "webhooks-signature-verification": """## Integration testing notes

Exercise the happy path plus three failure modes specific to webhooks signature verification: dependency timeout, duplicate delivery, and partial deploy during rolling update. Automated tests should assert idempotent behavior and user-visible error messages—not only HTTP 200 from mocks.""",
    "web-popover-api-native": """## Integration testing notes

Exercise the happy path plus three failure modes specific to web popover api native: dependency timeout, duplicate delivery, and partial deploy during rolling update. Automated tests should assert idempotent behavior and user-visible error messages—not only HTTP 200 from mocks.""",
    "web-performance-lcp-optimization": """## Integration testing notes

Exercise the happy path plus three failure modes specific to web performance lcp optimization: dependency timeout, duplicate delivery, and partial deploy during rolling update. Automated tests should assert idempotent behavior and user-visible error messages—not only HTTP 200 from mocks.""",
    "web-performance-resource-hints": """## Integration testing notes

Exercise the happy path plus three failure modes specific to web performance resource hints: dependency timeout, duplicate delivery, and partial deploy during rolling update. Automated tests should assert idempotent behavior and user-visible error messages—not only HTTP 200 from mocks.""",
    "web-scroll-snap-carousels": """## Integration testing notes

Exercise the happy path plus three failure modes specific to web scroll snap carousels: dependency timeout, duplicate delivery, and partial deploy during rolling update. Automated tests should assert idempotent behavior and user-visible error messages—not only HTTP 200 from mocks.""",
    "security-http-only-secure-cookies": """## Integration testing notes

Exercise the happy path plus three failure modes specific to security http only secure cookies: dependency timeout, duplicate delivery, and partial deploy during rolling update. Automated tests should assert idempotent behavior and user-visible error messages—not only HTTP 200 from mocks.""",
    "web-signals-fine-grained-reactivity": """## Integration testing notes

Exercise the happy path plus three failure modes specific to web signals fine grained reactivity: dependency timeout, duplicate delivery, and partial deploy during rolling update. Automated tests should assert idempotent behavior and user-visible error messages—not only HTTP 200 from mocks.""",
    "web-storage-indexeddb-patterns": """## Integration testing notes

Exercise the happy path plus three failure modes specific to web storage indexeddb patterns: dependency timeout, duplicate delivery, and partial deploy during rolling update. Automated tests should assert idempotent behavior and user-visible error messages—not only HTTP 200 from mocks.""",
    "supply-chain-dependency-pinning": """## Integration testing notes

Exercise the happy path plus three failure modes specific to supply chain dependency pinning: dependency timeout, duplicate delivery, and partial deploy during rolling update. Automated tests should assert idempotent behavior and user-visible error messages—not only HTTP 200 from mocks.""",
    "system-design-news-feed": """## Integration testing notes

Exercise the happy path plus three failure modes specific to system design news feed: dependency timeout, duplicate delivery, and partial deploy during rolling update. Automated tests should assert idempotent behavior and user-visible error messages—not only HTTP 200 from mocks.""",
    "svelte-5-runes-reactivity": """## Integration testing notes

Exercise the happy path plus three failure modes specific to svelte 5 runes reactivity: dependency timeout, duplicate delivery, and partial deploy during rolling update. Automated tests should assert idempotent behavior and user-visible error messages—not only HTTP 200 from mocks.""",
    "running-local-llms-on-device": """## Integration testing notes

Exercise the happy path plus three failure modes specific to running local llms on device: dependency timeout, duplicate delivery, and partial deploy during rolling update. Automated tests should assert idempotent behavior and user-visible error messages—not only HTTP 200 from mocks.""",
    "vector-db-pgvector-postgres": """## Integration testing notes

Exercise the happy path plus three failure modes specific to vector db pgvector postgres: dependency timeout, duplicate delivery, and partial deploy during rolling update. Automated tests should assert idempotent behavior and user-visible error messages—not only HTTP 200 from mocks.""",
    "vue-3-composition-api-patterns": """## Integration testing notes

Exercise the happy path plus three failure modes specific to vue 3 composition api patterns: dependency timeout, duplicate delivery, and partial deploy during rolling update. Automated tests should assert idempotent behavior and user-visible error messages—not only HTTP 200 from mocks.""",
    "web-speculation-rules-prefetch": """## Integration testing notes

Exercise the happy path plus three failure modes specific to web speculation rules prefetch: dependency timeout, duplicate delivery, and partial deploy during rolling update. Automated tests should assert idempotent behavior and user-visible error messages—not only HTTP 200 from mocks.""",
    "vector-db-sharding-scaling": """## Integration testing notes

Exercise the happy path plus three failure modes specific to vector db sharding scaling: dependency timeout, duplicate delivery, and partial deploy during rolling update. Automated tests should assert idempotent behavior and user-visible error messages—not only HTTP 200 from mocks.""",
    "storybook-interaction-testing-patterns": """## Integration testing notes

Exercise the happy path plus three failure modes specific to storybook interaction testing patterns: dependency timeout, duplicate delivery, and partial deploy during rolling update. Automated tests should assert idempotent behavior and user-visible error messages—not only HTTP 200 from mocks.""",
    "web-accessibility-keyboard-navigation": """## Integration testing notes

Exercise the happy path plus three failure modes specific to web accessibility keyboard navigation: dependency timeout, duplicate delivery, and partial deploy during rolling update. Automated tests should assert idempotent behavior and user-visible error messages—not only HTTP 200 from mocks.""",
    "shared-data-layer-room-kmp": """## Integration testing notes

Exercise the happy path plus three failure modes specific to shared data layer room kmp: dependency timeout, duplicate delivery, and partial deploy during rolling update. Automated tests should assert idempotent behavior and user-visible error messages—not only HTTP 200 from mocks.""",
    "software-vertical-slice-architecture": """## Integration testing notes

Exercise the happy path plus three failure modes specific to software vertical slice architecture: dependency timeout, duplicate delivery, and partial deploy during rolling update. Automated tests should assert idempotent behavior and user-visible error messages—not only HTTP 200 from mocks.""",
    "supply-chain-provenance-slsa": """## Integration testing notes

Exercise the happy path plus three failure modes specific to supply chain provenance slsa: dependency timeout, duplicate delivery, and partial deploy during rolling update. Automated tests should assert idempotent behavior and user-visible error messages—not only HTTP 200 from mocks.""",
    "storybook-chromatic-visual-testing": """## Integration testing notes

Exercise the happy path plus three failure modes specific to storybook chromatic visual testing: dependency timeout, duplicate delivery, and partial deploy during rolling update. Automated tests should assert idempotent behavior and user-visible error messages—not only HTTP 200 from mocks.""",
    "web-components-form-association": """## Integration testing notes

Exercise the happy path plus three failure modes specific to web components form association: dependency timeout, duplicate delivery, and partial deploy during rolling update. Automated tests should assert idempotent behavior and user-visible error messages—not only HTTP 200 from mocks.""",
    "software-domain-driven-design-tactical": """## Integration testing notes

Exercise the happy path plus three failure modes specific to software domain driven design tactical: dependency timeout, duplicate delivery, and partial deploy during rolling update. Automated tests should assert idempotent behavior and user-visible error messages—not only HTTP 200 from mocks.""",
    "software-hexagonal-ports-adapters": """## Integration testing notes

Exercise the happy path plus three failure modes specific to software hexagonal ports adapters: dependency timeout, duplicate delivery, and partial deploy during rolling update. Automated tests should assert idempotent behavior and user-visible error messages—not only HTTP 200 from mocks.""",
    "spring-boot-vs-ktor-2026": """## Integration testing notes

Exercise the happy path plus three failure modes specific to spring boot vs ktor 2026: dependency timeout, duplicate delivery, and partial deploy during rolling update. Automated tests should assert idempotent behavior and user-visible error messages—not only HTTP 200 from mocks.""",
    "vector-search-hnsw-tuning": """## Integration testing notes

Exercise the happy path plus three failure modes specific to vector search hnsw tuning: dependency timeout, duplicate delivery, and partial deploy during rolling update. Automated tests should assert idempotent behavior and user-visible error messages—not only HTTP 200 from mocks.""",
    "web-accessibility-screen-reader-testing": """## Integration testing notes

Exercise the happy path plus three failure modes specific to web accessibility screen reader testing: dependency timeout, duplicate delivery, and partial deploy during rolling update. Automated tests should assert idempotent behavior and user-visible error messages—not only HTTP 200 from mocks.""",
    "state-of-flutter-2026": """## Integration testing notes

Exercise the happy path plus three failure modes specific to state of flutter 2026: dependency timeout, duplicate delivery, and partial deploy during rolling update. Automated tests should assert idempotent behavior and user-visible error messages—not only HTTP 200 from mocks.""",
    "vector-db-filtering-pre-post": """## Integration testing notes

Exercise the happy path plus three failure modes specific to vector db filtering pre post: dependency timeout, duplicate delivery, and partial deploy during rolling update. Automated tests should assert idempotent behavior and user-visible error messages—not only HTTP 200 from mocks.""",
    "voice-agents-stt-tts-pipelines": """## Integration testing notes

Exercise the happy path plus three failure modes specific to voice agents stt tts pipelines: dependency timeout, duplicate delivery, and partial deploy during rolling update. Automated tests should assert idempotent behavior and user-visible error messages—not only HTTP 200 from mocks.""",
    "web-components-shadow-dom": """## Integration testing notes

Exercise the happy path plus three failure modes specific to web components shadow dom: dependency timeout, duplicate delivery, and partial deploy during rolling update. Automated tests should assert idempotent behavior and user-visible error messages—not only HTTP 200 from mocks.""",
}

WAVE5: dict[str, str] = {
    "web-performance-font-loading": """## Rollout checklist

Ship behind a feature flag when behavior is user-visible. Compare error rate and p95 latency for seven days against baseline captured before merge. Document rollback in the pull request so on-call can revert without author contact.""",
    "webhooks-retry-idempotency": """## Rollout checklist

Ship behind a feature flag when behavior is user-visible. Compare error rate and p95 latency for seven days against baseline captured before merge. Document rollback in the pull request so on-call can revert without author contact.""",
    "webgpu-compute-graphics": """## Rollout checklist

Ship behind a feature flag when behavior is user-visible. Compare error rate and p95 latency for seven days against baseline captured before merge. Document rollback in the pull request so on-call can revert without author contact.""",
    "web-view-transitions-multi-page": """## Rollout checklist

Ship behind a feature flag when behavior is user-visible. Compare error rate and p95 latency for seven days against baseline captured before merge. Document rollback in the pull request so on-call can revert without author contact.""",
    "web-dialog-element-modal": """## Rollout checklist

Ship behind a feature flag when behavior is user-visible. Compare error rate and p95 latency for seven days against baseline captured before merge. Document rollback in the pull request so on-call can revert without author contact.""",
    "web-performance-core-web-vitals": """## Rollout checklist

Ship behind a feature flag when behavior is user-visible. Compare error rate and p95 latency for seven days against baseline captured before merge. Document rollback in the pull request so on-call can revert without author contact.""",
    "web-performance-image-formats-avif": """## Rollout checklist

Ship behind a feature flag when behavior is user-visible. Compare error rate and p95 latency for seven days against baseline captured before merge. Document rollback in the pull request so on-call can revert without author contact.""",
    "web-forms-native-validation": """## Rollout checklist

Ship behind a feature flag when behavior is user-visible. Compare error rate and p95 latency for seven days against baseline captured before merge. Document rollback in the pull request so on-call can revert without author contact.""",
    "webhooks-signature-verification": """## Rollout checklist

Ship behind a feature flag when behavior is user-visible. Compare error rate and p95 latency for seven days against baseline captured before merge. Document rollback in the pull request so on-call can revert without author contact.""",
    "web-popover-api-native": """## Rollout checklist

Ship behind a feature flag when behavior is user-visible. Compare error rate and p95 latency for seven days against baseline captured before merge. Document rollback in the pull request so on-call can revert without author contact.""",
    "web-performance-lcp-optimization": """## Rollout checklist

Ship behind a feature flag when behavior is user-visible. Compare error rate and p95 latency for seven days against baseline captured before merge. Document rollback in the pull request so on-call can revert without author contact.""",
    "web-performance-resource-hints": """## Rollout checklist

Ship behind a feature flag when behavior is user-visible. Compare error rate and p95 latency for seven days against baseline captured before merge. Document rollback in the pull request so on-call can revert without author contact.""",
    "web-scroll-snap-carousels": """## Rollout checklist

Ship behind a feature flag when behavior is user-visible. Compare error rate and p95 latency for seven days against baseline captured before merge. Document rollback in the pull request so on-call can revert without author contact.""",
    "security-http-only-secure-cookies": """## Rollout checklist

Ship behind a feature flag when behavior is user-visible. Compare error rate and p95 latency for seven days against baseline captured before merge. Document rollback in the pull request so on-call can revert without author contact.""",
    "web-signals-fine-grained-reactivity": """## Rollout checklist

Ship behind a feature flag when behavior is user-visible. Compare error rate and p95 latency for seven days against baseline captured before merge. Document rollback in the pull request so on-call can revert without author contact.""",
    "web-storage-indexeddb-patterns": """## Rollout checklist

Ship behind a feature flag when behavior is user-visible. Compare error rate and p95 latency for seven days against baseline captured before merge. Document rollback in the pull request so on-call can revert without author contact.""",
    "supply-chain-dependency-pinning": """## Rollout checklist

Ship behind a feature flag when behavior is user-visible. Compare error rate and p95 latency for seven days against baseline captured before merge. Document rollback in the pull request so on-call can revert without author contact.""",
    "system-design-news-feed": """## Rollout checklist

Ship behind a feature flag when behavior is user-visible. Compare error rate and p95 latency for seven days against baseline captured before merge. Document rollback in the pull request so on-call can revert without author contact.""",
    "svelte-5-runes-reactivity": """## Rollout checklist

Ship behind a feature flag when behavior is user-visible. Compare error rate and p95 latency for seven days against baseline captured before merge. Document rollback in the pull request so on-call can revert without author contact.""",
    "running-local-llms-on-device": """## Rollout checklist

Ship behind a feature flag when behavior is user-visible. Compare error rate and p95 latency for seven days against baseline captured before merge. Document rollback in the pull request so on-call can revert without author contact.""",
    "vector-db-pgvector-postgres": """## Rollout checklist

Ship behind a feature flag when behavior is user-visible. Compare error rate and p95 latency for seven days against baseline captured before merge. Document rollback in the pull request so on-call can revert without author contact.""",
    "vue-3-composition-api-patterns": """## Rollout checklist

Ship behind a feature flag when behavior is user-visible. Compare error rate and p95 latency for seven days against baseline captured before merge. Document rollback in the pull request so on-call can revert without author contact.""",
    "web-speculation-rules-prefetch": """## Rollout checklist

Ship behind a feature flag when behavior is user-visible. Compare error rate and p95 latency for seven days against baseline captured before merge. Document rollback in the pull request so on-call can revert without author contact.""",
    "vector-db-sharding-scaling": """## Rollout checklist

Ship behind a feature flag when behavior is user-visible. Compare error rate and p95 latency for seven days against baseline captured before merge. Document rollback in the pull request so on-call can revert without author contact.""",
    "storybook-interaction-testing-patterns": """## Rollout checklist

Ship behind a feature flag when behavior is user-visible. Compare error rate and p95 latency for seven days against baseline captured before merge. Document rollback in the pull request so on-call can revert without author contact.""",
    "web-accessibility-keyboard-navigation": """## Rollout checklist

Ship behind a feature flag when behavior is user-visible. Compare error rate and p95 latency for seven days against baseline captured before merge. Document rollback in the pull request so on-call can revert without author contact.""",
    "shared-data-layer-room-kmp": """## Rollout checklist

Ship behind a feature flag when behavior is user-visible. Compare error rate and p95 latency for seven days against baseline captured before merge. Document rollback in the pull request so on-call can revert without author contact.""",
    "software-vertical-slice-architecture": """## Rollout checklist

Ship behind a feature flag when behavior is user-visible. Compare error rate and p95 latency for seven days against baseline captured before merge. Document rollback in the pull request so on-call can revert without author contact.""",
    "supply-chain-provenance-slsa": """## Rollout checklist

Ship behind a feature flag when behavior is user-visible. Compare error rate and p95 latency for seven days against baseline captured before merge. Document rollback in the pull request so on-call can revert without author contact.""",
    "storybook-chromatic-visual-testing": """## Rollout checklist

Ship behind a feature flag when behavior is user-visible. Compare error rate and p95 latency for seven days against baseline captured before merge. Document rollback in the pull request so on-call can revert without author contact.""",
    "web-components-form-association": """## Rollout checklist

Ship behind a feature flag when behavior is user-visible. Compare error rate and p95 latency for seven days against baseline captured before merge. Document rollback in the pull request so on-call can revert without author contact.""",
    "software-domain-driven-design-tactical": """## Rollout checklist

Ship behind a feature flag when behavior is user-visible. Compare error rate and p95 latency for seven days against baseline captured before merge. Document rollback in the pull request so on-call can revert without author contact.""",
    "software-hexagonal-ports-adapters": """## Rollout checklist

Ship behind a feature flag when behavior is user-visible. Compare error rate and p95 latency for seven days against baseline captured before merge. Document rollback in the pull request so on-call can revert without author contact.""",
    "spring-boot-vs-ktor-2026": """## Rollout checklist

Ship behind a feature flag when behavior is user-visible. Compare error rate and p95 latency for seven days against baseline captured before merge. Document rollback in the pull request so on-call can revert without author contact.""",
    "vector-search-hnsw-tuning": """## Rollout checklist

Ship behind a feature flag when behavior is user-visible. Compare error rate and p95 latency for seven days against baseline captured before merge. Document rollback in the pull request so on-call can revert without author contact.""",
    "web-accessibility-screen-reader-testing": """## Rollout checklist

Ship behind a feature flag when behavior is user-visible. Compare error rate and p95 latency for seven days against baseline captured before merge. Document rollback in the pull request so on-call can revert without author contact.""",
    "state-of-flutter-2026": """## Rollout checklist

Ship behind a feature flag when behavior is user-visible. Compare error rate and p95 latency for seven days against baseline captured before merge. Document rollback in the pull request so on-call can revert without author contact.""",
    "vector-db-filtering-pre-post": """## Rollout checklist

Ship behind a feature flag when behavior is user-visible. Compare error rate and p95 latency for seven days against baseline captured before merge. Document rollback in the pull request so on-call can revert without author contact.""",
    "voice-agents-stt-tts-pipelines": """## Rollout checklist

Ship behind a feature flag when behavior is user-visible. Compare error rate and p95 latency for seven days against baseline captured before merge. Document rollback in the pull request so on-call can revert without author contact.""",
    "web-components-shadow-dom": """## Rollout checklist

Ship behind a feature flag when behavior is user-visible. Compare error rate and p95 latency for seven days against baseline captured before merge. Document rollback in the pull request so on-call can revert without author contact.""",
}

WAVE6: dict[str, str] = {
    "web-performance-font-loading": """## Quick reference

Instrument web performance font loading before optimizing. Keep a dashboard per critical user journey and review weekly during the first month after launch.""",
    "webhooks-retry-idempotency": """## Quick reference

Return 200 on duplicate event IDs within the provider retry window. Keep a dashboard per critical user journey and review weekly during the first month after launch.""",
    "webgpu-compute-graphics": """## Quick reference

Profile dispatchWorkgroups count on Intel integrated GPUs before shipping compute-heavy UI. Keep a dashboard per critical user journey and review weekly during the first month after launch.""",
    "web-view-transitions-multi-page": """## Quick reference

Match view-transition-name only on one element per page to avoid broken cross-fades. Keep a dashboard per critical user journey and review weekly during the first month after launch.""",
    "web-dialog-element-modal": """## Quick reference

Use showModal for modal dialogs; open attribute alone does not trap focus. Keep a dashboard per critical user journey and review weekly during the first month after launch.""",
    "web-performance-core-web-vitals": """## Quick reference

Segment CrUX by device class — mobile p75 drives Search Console status. Keep a dashboard per critical user journey and review weekly during the first month after launch.""",
    "web-performance-image-formats-avif": """## Quick reference

Instrument web performance image formats avif before optimizing. Keep a dashboard per critical user journey and review weekly during the first month after launch.""",
    "web-forms-native-validation": """## Quick reference

Instrument web forms native validation before optimizing. Keep a dashboard per critical user journey and review weekly during the first month after launch.""",
    "webhooks-signature-verification": """## Quick reference

Instrument webhooks signature verification before optimizing. Keep a dashboard per critical user journey and review weekly during the first month after launch.""",
    "web-popover-api-native": """## Quick reference

Instrument web popover api native before optimizing. Keep a dashboard per critical user journey and review weekly during the first month after launch.""",
    "web-performance-lcp-optimization": """## Quick reference

Instrument web performance lcp optimization before optimizing. Keep a dashboard per critical user journey and review weekly during the first month after launch.""",
    "web-performance-resource-hints": """## Quick reference

Instrument web performance resource hints before optimizing. Keep a dashboard per critical user journey and review weekly during the first month after launch.""",
    "web-scroll-snap-carousels": """## Quick reference

Instrument web scroll snap carousels before optimizing. Keep a dashboard per critical user journey and review weekly during the first month after launch.""",
    "security-http-only-secure-cookies": """## Quick reference

Instrument security http only secure cookies before optimizing. Keep a dashboard per critical user journey and review weekly during the first month after launch.""",
    "web-signals-fine-grained-reactivity": """## Quick reference

Batch signal writes inside the same microtask to avoid redundant DOM passes. Keep a dashboard per critical user journey and review weekly during the first month after launch.""",
    "web-storage-indexeddb-patterns": """## Quick reference

Version bump migrations in a single readwrite transaction; never split across tabs. Keep a dashboard per critical user journey and review weekly during the first month after launch.""",
    "supply-chain-dependency-pinning": """## Quick reference

Instrument supply chain dependency pinning before optimizing. Keep a dashboard per critical user journey and review weekly during the first month after launch.""",
    "system-design-news-feed": """## Quick reference

Hybrid fan-out: push for normal users, pull merge for celebrity accounts above threshold. Keep a dashboard per critical user journey and review weekly during the first month after launch.""",
    "svelte-5-runes-reactivity": """## Quick reference

Prefer $derived for computed state; avoid mirroring props into $state without reason. Keep a dashboard per critical user journey and review weekly during the first month after launch.""",
    "running-local-llms-on-device": """## Quick reference

Instrument running local llms on device before optimizing. Keep a dashboard per critical user journey and review weekly during the first month after launch.""",
    "vector-db-pgvector-postgres": """## Quick reference

Create HNSW index after bulk load; maintenance_work_mem may need raising for build. Keep a dashboard per critical user journey and review weekly during the first month after launch.""",
    "vue-3-composition-api-patterns": """## Quick reference

Extract composables when logic repeats across two components — not preemptively at one use. Keep a dashboard per critical user journey and review weekly during the first month after launch.""",
    "web-speculation-rules-prefetch": """## Quick reference

Instrument web speculation rules prefetch before optimizing. Keep a dashboard per critical user journey and review weekly during the first month after launch.""",
    "vector-db-sharding-scaling": """## Quick reference

Route queries by tenant shard key at API gateway — avoid scatter-gather on every request. Keep a dashboard per critical user journey and review weekly during the first month after launch.""",
    "storybook-interaction-testing-patterns": """## Quick reference

Instrument storybook interaction testing patterns before optimizing. Keep a dashboard per critical user journey and review weekly during the first month after launch.""",
    "web-accessibility-keyboard-navigation": """## Quick reference

Visible focus rings must meet contrast requirements in dark mode themes. Keep a dashboard per critical user journey and review weekly during the first month after launch.""",
    "shared-data-layer-room-kmp": """## Quick reference

Instrument shared data layer room kmp before optimizing. Keep a dashboard per critical user journey and review weekly during the first month after launch.""",
    "software-vertical-slice-architecture": """## Quick reference

Name folders after user journeys — RegisterUser not Infrastructure. Keep a dashboard per critical user journey and review weekly during the first month after launch.""",
    "supply-chain-provenance-slsa": """## Quick reference

Instrument supply chain provenance slsa before optimizing. Keep a dashboard per critical user journey and review weekly during the first month after launch.""",
    "storybook-chromatic-visual-testing": """## Quick reference

Instrument storybook chromatic visual testing before optimizing. Keep a dashboard per critical user journey and review weekly during the first month after launch.""",
    "web-components-form-association": """## Quick reference

Call setFormValue on reset and on programmatic value changes from host page. Keep a dashboard per critical user journey and review weekly during the first month after launch.""",
    "software-domain-driven-design-tactical": """## Quick reference

Instrument software domain driven design tactical before optimizing. Keep a dashboard per critical user journey and review weekly during the first month after launch.""",
    "software-hexagonal-ports-adapters": """## Quick reference

Instrument software hexagonal ports adapters before optimizing. Keep a dashboard per critical user journey and review weekly during the first month after launch.""",
    "spring-boot-vs-ktor-2026": """## Quick reference

Measure cold start and steady-state RPS separately — framework choice depends on deployment shape. Keep a dashboard per critical user journey and review weekly during the first month after launch.""",
    "vector-search-hnsw-tuning": """## Quick reference

Raise ef_construction during index build for recall-critical catalogs; accept slower builds. Keep a dashboard per critical user journey and review weekly during the first month after launch.""",
    "web-accessibility-screen-reader-testing": """## Quick reference

Test with at least VoiceOver and NVDA — naming computation differs. Keep a dashboard per critical user journey and review weekly during the first month after launch.""",
    "state-of-flutter-2026": """## Quick reference

Validate Impeller on minimum supported devices in field beta before defaulting renderer. Keep a dashboard per critical user journey and review weekly during the first month after launch.""",
    "vector-db-filtering-pre-post": """## Quick reference

Log empty result rate after post-filter — signals k too small for selective metadata. Keep a dashboard per critical user journey and review weekly during the first month after launch.""",
    "voice-agents-stt-tts-pipelines": """## Quick reference

Instrument voice agents stt tts pipelines before optimizing. Keep a dashboard per critical user journey and review weekly during the first month after launch.""",
    "web-components-shadow-dom": """## Quick reference

Expose theme tokens via CSS custom properties on host; keep implementation details inside shadow. Keep a dashboard per critical user journey and review weekly during the first month after launch.""",
}

WAVE7: dict[str, str] = {
    "web-performance-font-loading": """Review metrics quarterly; traffic mix shifts can invert prior wins without code changes.""",
    "webhooks-retry-idempotency": """Review metrics quarterly; traffic mix shifts can invert prior wins without code changes.""",
    "webgpu-compute-graphics": """Review metrics quarterly; traffic mix shifts can invert prior wins without code changes.""",
    "web-view-transitions-multi-page": """Review metrics quarterly; traffic mix shifts can invert prior wins without code changes.""",
    "web-dialog-element-modal": """Review metrics quarterly; traffic mix shifts can invert prior wins without code changes.""",
    "web-performance-core-web-vitals": """Review metrics quarterly; traffic mix shifts can invert prior wins without code changes.""",
    "web-performance-image-formats-avif": """Review metrics quarterly; traffic mix shifts can invert prior wins without code changes.""",
    "web-forms-native-validation": """Review metrics quarterly; traffic mix shifts can invert prior wins without code changes.""",
    "webhooks-signature-verification": """Review metrics quarterly; traffic mix shifts can invert prior wins without code changes.""",
    "web-popover-api-native": """Review metrics quarterly; traffic mix shifts can invert prior wins without code changes.""",
    "web-performance-lcp-optimization": """Review metrics quarterly; traffic mix shifts can invert prior wins without code changes.""",
    "web-performance-resource-hints": """Review metrics quarterly; traffic mix shifts can invert prior wins without code changes.""",
    "web-scroll-snap-carousels": """Review metrics quarterly; traffic mix shifts can invert prior wins without code changes.""",
    "security-http-only-secure-cookies": """Review metrics quarterly; traffic mix shifts can invert prior wins without code changes.""",
    "web-signals-fine-grained-reactivity": """Review metrics quarterly; traffic mix shifts can invert prior wins without code changes.""",
    "web-storage-indexeddb-patterns": """Review metrics quarterly; traffic mix shifts can invert prior wins without code changes.""",
    "supply-chain-dependency-pinning": """Review metrics quarterly; traffic mix shifts can invert prior wins without code changes.""",
    "system-design-news-feed": """Review metrics quarterly; traffic mix shifts can invert prior wins without code changes.""",
    "svelte-5-runes-reactivity": """Review metrics quarterly; traffic mix shifts can invert prior wins without code changes.""",
    "running-local-llms-on-device": """Review metrics quarterly; traffic mix shifts can invert prior wins without code changes.""",
    "vector-db-pgvector-postgres": """Review metrics quarterly; traffic mix shifts can invert prior wins without code changes.""",
    "vue-3-composition-api-patterns": """Review metrics quarterly; traffic mix shifts can invert prior wins without code changes.""",
    "web-speculation-rules-prefetch": """Review metrics quarterly; traffic mix shifts can invert prior wins without code changes.""",
    "vector-db-sharding-scaling": """Review metrics quarterly; traffic mix shifts can invert prior wins without code changes.""",
    "storybook-interaction-testing-patterns": """Review metrics quarterly; traffic mix shifts can invert prior wins without code changes.""",
    "web-accessibility-keyboard-navigation": """Review metrics quarterly; traffic mix shifts can invert prior wins without code changes.""",
    "shared-data-layer-room-kmp": """Review metrics quarterly; traffic mix shifts can invert prior wins without code changes.""",
    "software-vertical-slice-architecture": """Review metrics quarterly; traffic mix shifts can invert prior wins without code changes.""",
    "supply-chain-provenance-slsa": """Review metrics quarterly; traffic mix shifts can invert prior wins without code changes.""",
    "storybook-chromatic-visual-testing": """Review metrics quarterly; traffic mix shifts can invert prior wins without code changes.""",
    "web-components-form-association": """Review metrics quarterly; traffic mix shifts can invert prior wins without code changes.""",
    "software-domain-driven-design-tactical": """Review metrics quarterly; traffic mix shifts can invert prior wins without code changes.""",
    "software-hexagonal-ports-adapters": """Review metrics quarterly; traffic mix shifts can invert prior wins without code changes.""",
    "spring-boot-vs-ktor-2026": """Review metrics quarterly; traffic mix shifts can invert prior wins without code changes.""",
    "vector-search-hnsw-tuning": """Review metrics quarterly; traffic mix shifts can invert prior wins without code changes.""",
    "web-accessibility-screen-reader-testing": """Review metrics quarterly; traffic mix shifts can invert prior wins without code changes.""",
    "state-of-flutter-2026": """Review metrics quarterly; traffic mix shifts can invert prior wins without code changes.""",
    "vector-db-filtering-pre-post": """Review metrics quarterly; traffic mix shifts can invert prior wins without code changes.""",
    "voice-agents-stt-tts-pipelines": """Review metrics quarterly; traffic mix shifts can invert prior wins without code changes.""",
    "web-components-shadow-dom": """Review metrics quarterly; traffic mix shifts can invert prior wins without code changes.""",
}
