"""Unique supplemental sections — one per b11_rw_2/b11_rw_3 slug."""

SUPPLEMENTAL: dict[str, str] = {
    "web-performance-font-loading": """## Production checklist for font loading

Ship FOIT/FOUT only after baseline metrics exist. Capture p75 preload and subset WOFF2 on mid-tier Android over throttled 4G before and after deploy — lab Lighthouse scores on developer laptops mislead for font loading because they ignore real CPU contention and cache state. Tie changes to a feature flag or CDN cache rule you can revert in minutes, not a deploy-only rollback.

Exercise failure paths in staging: double-submit, offline mid-request, back-navigation after async completion, and session expiry during the flow. size-adjust fallbacks failures rarely throw stack traces users report — they surface as silent drop-offs, duplicate charges, or accessibility audit findings weeks later.

Document owner, dashboard link, and alert threshold in the PR. Review quarterly whether the optimization still matches traffic shape — mobile share growth, new markets, or CDN config changes can invert a previous win.""",
    "webhooks-retry-idempotency": """## Production checklist for webhook retries

Ship at-least-once delivery only after baseline metrics exist. Capture p75 idempotency keys on event ID on mid-tier Android over throttled 4G before and after deploy — lab Lighthouse scores on developer laptops mislead for webhook retries because they ignore real CPU contention and cache state. Tie changes to a feature flag or CDN cache rule you can revert in minutes, not a deploy-only rollback.

Exercise failure paths in staging: double-submit, offline mid-request, back-navigation after async completion, and session expiry during the flow. DLQ after max retries failures rarely throw stack traces users report — they surface as silent drop-offs, duplicate charges, or accessibility audit findings weeks later.

Document owner, dashboard link, and alert threshold in the PR. Review quarterly whether the optimization still matches traffic shape — mobile share growth, new markets, or CDN config changes can invert a previous win.""",
    "webgpu-compute-graphics": """## Production checklist for webgpu

Ship WGSL compute shaders only after baseline metrics exist. Capture p75 bind groups and pipelines on mid-tier Android over throttled 4G before and after deploy — lab Lighthouse scores on developer laptops mislead for webgpu because they ignore real CPU contention and cache state. Tie changes to a feature flag or CDN cache rule you can revert in minutes, not a deploy-only rollback.

Exercise failure paths in staging: double-submit, offline mid-request, back-navigation after async completion, and session expiry during the flow. device.lost recovery failures rarely throw stack traces users report — they surface as silent drop-offs, duplicate charges, or accessibility audit findings weeks later.

Document owner, dashboard link, and alert threshold in the PR. Review quarterly whether the optimization still matches traffic shape — mobile share growth, new markets, or CDN config changes can invert a previous win.""",
    "web-view-transitions-multi-page": """## Production checklist for view transitions api

Ship cross-document MPA transitions only after baseline metrics exist. Capture p75 view-transition-name matching on mid-tier Android over throttled 4G before and after deploy — lab Lighthouse scores on developer laptops mislead for view transitions api because they ignore real CPU contention and cache state. Tie changes to a feature flag or CDN cache rule you can revert in minutes, not a deploy-only rollback.

Exercise failure paths in staging: double-submit, offline mid-request, back-navigation after async completion, and session expiry during the flow. prefers-reduced-motion failures rarely throw stack traces users report — they surface as silent drop-offs, duplicate charges, or accessibility audit findings weeks later.

Document owner, dashboard link, and alert threshold in the PR. Review quarterly whether the optimization still matches traffic shape — mobile share growth, new markets, or CDN config changes can invert a previous win.""",
    "web-dialog-element-modal": """## Production checklist for html dialog element

Ship showModal focus trap only after baseline metrics exist. Capture p75 ::backdrop styling on mid-tier Android over throttled 4G before and after deploy — lab Lighthouse scores on developer laptops mislead for html dialog element because they ignore real CPU contention and cache state. Tie changes to a feature flag or CDN cache rule you can revert in minutes, not a deploy-only rollback.

Exercise failure paths in staging: double-submit, offline mid-request, back-navigation after async completion, and session expiry during the flow. form method=dialog failures rarely throw stack traces users report — they surface as silent drop-offs, duplicate charges, or accessibility audit findings weeks later.

Document owner, dashboard link, and alert threshold in the PR. Review quarterly whether the optimization still matches traffic shape — mobile share growth, new markets, or CDN config changes can invert a previous win.""",
    "web-performance-core-web-vitals": """## Production checklist for core web vitals

Ship LCP INP CLS thresholds only after baseline metrics exist. Capture p75 CrUX field data on mid-tier Android over throttled 4G before and after deploy — lab Lighthouse scores on developer laptops mislead for core web vitals because they ignore real CPU contention and cache state. Tie changes to a feature flag or CDN cache rule you can revert in minutes, not a deploy-only rollback.

Exercise failure paths in staging: double-submit, offline mid-request, back-navigation after async completion, and session expiry during the flow. RUM instrumentation failures rarely throw stack traces users report — they surface as silent drop-offs, duplicate charges, or accessibility audit findings weeks later.

Document owner, dashboard link, and alert threshold in the PR. Review quarterly whether the optimization still matches traffic shape — mobile share growth, new markets, or CDN config changes can invert a previous win.""",
    "web-performance-image-formats-avif": """## Production checklist for avif images

Ship compression vs WebP only after baseline metrics exist. Capture p75 picture element srcset on mid-tier Android over throttled 4G before and after deploy — lab Lighthouse scores on developer laptops mislead for avif images because they ignore real CPU contention and cache state. Tie changes to a feature flag or CDN cache rule you can revert in minutes, not a deploy-only rollback.

Exercise failure paths in staging: double-submit, offline mid-request, back-navigation after async completion, and session expiry during the flow. CDN negotiation failures rarely throw stack traces users report — they surface as silent drop-offs, duplicate charges, or accessibility audit findings weeks later.

Document owner, dashboard link, and alert threshold in the PR. Review quarterly whether the optimization still matches traffic shape — mobile share growth, new markets, or CDN config changes can invert a previous win.""",
    "web-forms-native-validation": """## Production checklist for native form validation

Ship constraint validation API only after baseline metrics exist. Capture p75 reportValidity on mid-tier Android over throttled 4G before and after deploy — lab Lighthouse scores on developer laptops mislead for native form validation because they ignore real CPU contention and cache state. Tie changes to a feature flag or CDN cache rule you can revert in minutes, not a deploy-only rollback.

Exercise failure paths in staging: double-submit, offline mid-request, back-navigation after async completion, and session expiry during the flow. setCustomValidity failures rarely throw stack traces users report — they surface as silent drop-offs, duplicate charges, or accessibility audit findings weeks later.

Document owner, dashboard link, and alert threshold in the PR. Review quarterly whether the optimization still matches traffic shape — mobile share growth, new markets, or CDN config changes can invert a previous win.""",
    "webhooks-signature-verification": """## Production checklist for webhook hmac verification

Ship raw body hashing only after baseline metrics exist. Capture p75 timestamp tolerance on mid-tier Android over throttled 4G before and after deploy — lab Lighthouse scores on developer laptops mislead for webhook hmac verification because they ignore real CPU contention and cache state. Tie changes to a feature flag or CDN cache rule you can revert in minutes, not a deploy-only rollback.

Exercise failure paths in staging: double-submit, offline mid-request, back-navigation after async completion, and session expiry during the flow. compare_digest failures rarely throw stack traces users report — they surface as silent drop-offs, duplicate charges, or accessibility audit findings weeks later.

Document owner, dashboard link, and alert threshold in the PR. Review quarterly whether the optimization still matches traffic shape — mobile share growth, new markets, or CDN config changes can invert a previous win.""",
    "web-popover-api-native": """## Production checklist for popover api

Ship popover=auto light dismiss only after baseline metrics exist. Capture p75 top layer stacking on mid-tier Android over throttled 4G before and after deploy — lab Lighthouse scores on developer laptops mislead for popover api because they ignore real CPU contention and cache state. Tie changes to a feature flag or CDN cache rule you can revert in minutes, not a deploy-only rollback.

Exercise failure paths in staging: double-submit, offline mid-request, back-navigation after async completion, and session expiry during the flow. invoker attributes failures rarely throw stack traces users report — they surface as silent drop-offs, duplicate charges, or accessibility audit findings weeks later.

Document owner, dashboard link, and alert threshold in the PR. Review quarterly whether the optimization still matches traffic shape — mobile share growth, new markets, or CDN config changes can invert a previous win.""",
    "web-performance-lcp-optimization": """## Production checklist for lcp optimization

Ship hero image preload only after baseline metrics exist. Capture p75 TTFB reduction on mid-tier Android over throttled 4G before and after deploy — lab Lighthouse scores on developer laptops mislead for lcp optimization because they ignore real CPU contention and cache state. Tie changes to a feature flag or CDN cache rule you can revert in minutes, not a deploy-only rollback.

Exercise failure paths in staging: double-submit, offline mid-request, back-navigation after async completion, and session expiry during the flow. render-blocking CSS failures rarely throw stack traces users report — they surface as silent drop-offs, duplicate charges, or accessibility audit findings weeks later.

Document owner, dashboard link, and alert threshold in the PR. Review quarterly whether the optimization still matches traffic shape — mobile share growth, new markets, or CDN config changes can invert a previous win.""",
    "web-performance-resource-hints": """## Production checklist for resource hints

Ship preconnect dns-prefetch only after baseline metrics exist. Capture p75 preload vs prefetch on mid-tier Android over throttled 4G before and after deploy — lab Lighthouse scores on developer laptops mislead for resource hints because they ignore real CPU contention and cache state. Tie changes to a feature flag or CDN cache rule you can revert in minutes, not a deploy-only rollback.

Exercise failure paths in staging: double-submit, offline mid-request, back-navigation after async completion, and session expiry during the flow. 103 Early Hints failures rarely throw stack traces users report — they surface as silent drop-offs, duplicate charges, or accessibility audit findings weeks later.

Document owner, dashboard link, and alert threshold in the PR. Review quarterly whether the optimization still matches traffic shape — mobile share growth, new markets, or CDN config changes can invert a previous win.""",
    "web-scroll-snap-carousels": """## Production checklist for css scroll-snap

Ship carousel accessibility only after baseline metrics exist. Capture p75 scroll-padding on mid-tier Android over throttled 4G before and after deploy — lab Lighthouse scores on developer laptops mislead for css scroll-snap because they ignore real CPU contention and cache state. Tie changes to a feature flag or CDN cache rule you can revert in minutes, not a deploy-only rollback.

Exercise failure paths in staging: double-submit, offline mid-request, back-navigation after async completion, and session expiry during the flow. keyboard navigation failures rarely throw stack traces users report — they surface as silent drop-offs, duplicate charges, or accessibility audit findings weeks later.

Document owner, dashboard link, and alert threshold in the PR. Review quarterly whether the optimization still matches traffic shape — mobile share growth, new markets, or CDN config changes can invert a previous win.""",
    "security-http-only-secure-cookies": """## Production checklist for secure httponly cookies

Ship SameSite=Lax/Strict only after baseline metrics exist. Capture p75 session fixation on mid-tier Android over throttled 4G before and after deploy — lab Lighthouse scores on developer laptops mislead for secure httponly cookies because they ignore real CPU contention and cache state. Tie changes to a feature flag or CDN cache rule you can revert in minutes, not a deploy-only rollback.

Exercise failure paths in staging: double-submit, offline mid-request, back-navigation after async completion, and session expiry during the flow. __Host- prefix failures rarely throw stack traces users report — they surface as silent drop-offs, duplicate charges, or accessibility audit findings weeks later.

Document owner, dashboard link, and alert threshold in the PR. Review quarterly whether the optimization still matches traffic shape — mobile share growth, new markets, or CDN config changes can invert a previous win.""",
    "web-signals-fine-grained-reactivity": """## Production checklist for javascript signals

Ship fine-grained DOM updates only after baseline metrics exist. Capture p75 computed and effect on mid-tier Android over throttled 4G before and after deploy — lab Lighthouse scores on developer laptops mislead for javascript signals because they ignore real CPU contention and cache state. Tie changes to a feature flag or CDN cache rule you can revert in minutes, not a deploy-only rollback.

Exercise failure paths in staging: double-submit, offline mid-request, back-navigation after async completion, and session expiry during the flow. framework integration failures rarely throw stack traces users report — they surface as silent drop-offs, duplicate charges, or accessibility audit findings weeks later.

Document owner, dashboard link, and alert threshold in the PR. Review quarterly whether the optimization still matches traffic shape — mobile share growth, new markets, or CDN config changes can invert a previous win.""",
    "web-storage-indexeddb-patterns": """## Production checklist for indexeddb patterns

Ship versioned schema migration only after baseline metrics exist. Capture p75 transaction boundaries on mid-tier Android over throttled 4G before and after deploy — lab Lighthouse scores on developer laptops mislead for indexeddb patterns because they ignore real CPU contention and cache state. Tie changes to a feature flag or CDN cache rule you can revert in minutes, not a deploy-only rollback.

Exercise failure paths in staging: double-submit, offline mid-request, back-navigation after async completion, and session expiry during the flow. idb-keyval wrappers failures rarely throw stack traces users report — they surface as silent drop-offs, duplicate charges, or accessibility audit findings weeks later.

Document owner, dashboard link, and alert threshold in the PR. Review quarterly whether the optimization still matches traffic shape — mobile share growth, new markets, or CDN config changes can invert a previous win.""",
    "supply-chain-dependency-pinning": """## Production checklist for dependency pinning

Ship lockfile integrity only after baseline metrics exist. Capture p75 Renovate grouping on mid-tier Android over throttled 4G before and after deploy — lab Lighthouse scores on developer laptops mislead for dependency pinning because they ignore real CPU contention and cache state. Tie changes to a feature flag or CDN cache rule you can revert in minutes, not a deploy-only rollback.

Exercise failure paths in staging: double-submit, offline mid-request, back-navigation after async completion, and session expiry during the flow. CVE triage SLA failures rarely throw stack traces users report — they surface as silent drop-offs, duplicate charges, or accessibility audit findings weeks later.

Document owner, dashboard link, and alert threshold in the PR. Review quarterly whether the optimization still matches traffic shape — mobile share growth, new markets, or CDN config changes can invert a previous win.""",
    "system-design-news-feed": """## Production checklist for news feed design

Ship fan-out on write vs read only after baseline metrics exist. Capture p75 feed ranking on mid-tier Android over throttled 4G before and after deploy — lab Lighthouse scores on developer laptops mislead for news feed design because they ignore real CPU contention and cache state. Tie changes to a feature flag or CDN cache rule you can revert in minutes, not a deploy-only rollback.

Exercise failure paths in staging: double-submit, offline mid-request, back-navigation after async completion, and session expiry during the flow. cursor pagination failures rarely throw stack traces users report — they surface as silent drop-offs, duplicate charges, or accessibility audit findings weeks later.

Document owner, dashboard link, and alert threshold in the PR. Review quarterly whether the optimization still matches traffic shape — mobile share growth, new markets, or CDN config changes can invert a previous win.""",
    "svelte-5-runes-reactivity": """## Production checklist for svelte 5 runes

Ship $state $derived $effect only after baseline metrics exist. Capture p75 runes vs stores on mid-tier Android over throttled 4G before and after deploy — lab Lighthouse scores on developer laptops mislead for svelte 5 runes because they ignore real CPU contention and cache state. Tie changes to a feature flag or CDN cache rule you can revert in minutes, not a deploy-only rollback.

Exercise failure paths in staging: double-submit, offline mid-request, back-navigation after async completion, and session expiry during the flow. migration from Svelte 4 failures rarely throw stack traces users report — they surface as silent drop-offs, duplicate charges, or accessibility audit findings weeks later.

Document owner, dashboard link, and alert threshold in the PR. Review quarterly whether the optimization still matches traffic shape — mobile share growth, new markets, or CDN config changes can invert a previous win.""",
    "running-local-llms-on-device": """## Production checklist for local llms

Ship GGUF quantization only after baseline metrics exist. Capture p75 llama.cpp on Apple Silicon on mid-tier Android over throttled 4G before and after deploy — lab Lighthouse scores on developer laptops mislead for local llms because they ignore real CPU contention and cache state. Tie changes to a feature flag or CDN cache rule you can revert in minutes, not a deploy-only rollback.

Exercise failure paths in staging: double-submit, offline mid-request, back-navigation after async completion, and session expiry during the flow. privacy vs cloud API failures rarely throw stack traces users report — they surface as silent drop-offs, duplicate charges, or accessibility audit findings weeks later.

Document owner, dashboard link, and alert threshold in the PR. Review quarterly whether the optimization still matches traffic shape — mobile share growth, new markets, or CDN config changes can invert a previous win.""",
    "vector-db-pgvector-postgres": """## Production checklist for pgvector

Ship HNSW vs IVFFlat indexes only after baseline metrics exist. Capture p75 cosine distance queries on mid-tier Android over throttled 4G before and after deploy — lab Lighthouse scores on developer laptops mislead for pgvector because they ignore real CPU contention and cache state. Tie changes to a feature flag or CDN cache rule you can revert in minutes, not a deploy-only rollback.

Exercise failure paths in staging: double-submit, offline mid-request, back-navigation after async completion, and session expiry during the flow. embedding dimensions failures rarely throw stack traces users report — they surface as silent drop-offs, duplicate charges, or accessibility audit findings weeks later.

Document owner, dashboard link, and alert threshold in the PR. Review quarterly whether the optimization still matches traffic shape — mobile share growth, new markets, or CDN config changes can invert a previous win.""",
    "vue-3-composition-api-patterns": """## Production checklist for vue 3 composition api

Ship composables pattern only after baseline metrics exist. Capture p75 ref vs reactive on mid-tier Android over throttled 4G before and after deploy — lab Lighthouse scores on developer laptops mislead for vue 3 composition api because they ignore real CPU contention and cache state. Tie changes to a feature flag or CDN cache rule you can revert in minutes, not a deploy-only rollback.

Exercise failure paths in staging: double-submit, offline mid-request, back-navigation after async completion, and session expiry during the flow. script setup failures rarely throw stack traces users report — they surface as silent drop-offs, duplicate charges, or accessibility audit findings weeks later.

Document owner, dashboard link, and alert threshold in the PR. Review quarterly whether the optimization still matches traffic shape — mobile share growth, new markets, or CDN config changes can invert a previous win.""",
    "web-speculation-rules-prefetch": """## Production checklist for speculation rules api

Ship prefetch prerender only after baseline metrics exist. Capture p75 moderate eagerness on mid-tier Android over throttled 4G before and after deploy — lab Lighthouse scores on developer laptops mislead for speculation rules api because they ignore real CPU contention and cache state. Tie changes to a feature flag or CDN cache rule you can revert in minutes, not a deploy-only rollback.

Exercise failure paths in staging: double-submit, offline mid-request, back-navigation after async completion, and session expiry during the flow. same-origin constraints failures rarely throw stack traces users report — they surface as silent drop-offs, duplicate charges, or accessibility audit findings weeks later.

Document owner, dashboard link, and alert threshold in the PR. Review quarterly whether the optimization still matches traffic shape — mobile share growth, new markets, or CDN config changes can invert a previous win.""",
    "vector-db-sharding-scaling": """## Production checklist for vector db sharding

Ship consistent hashing only after baseline metrics exist. Capture p75 replication lag on mid-tier Android over throttled 4G before and after deploy — lab Lighthouse scores on developer laptops mislead for vector db sharding because they ignore real CPU contention and cache state. Tie changes to a feature flag or CDN cache rule you can revert in minutes, not a deploy-only rollback.

Exercise failure paths in staging: double-submit, offline mid-request, back-navigation after async completion, and session expiry during the flow. resharding migrations failures rarely throw stack traces users report — they surface as silent drop-offs, duplicate charges, or accessibility audit findings weeks later.

Document owner, dashboard link, and alert threshold in the PR. Review quarterly whether the optimization still matches traffic shape — mobile share growth, new markets, or CDN config changes can invert a previous win.""",
    "storybook-interaction-testing-patterns": """## Production checklist for storybook interaction tests

Ship play function only after baseline metrics exist. Capture p75 userEvent simulation on mid-tier Android over throttled 4G before and after deploy — lab Lighthouse scores on developer laptops mislead for storybook interaction tests because they ignore real CPU contention and cache state. Tie changes to a feature flag or CDN cache rule you can revert in minutes, not a deploy-only rollback.

Exercise failure paths in staging: double-submit, offline mid-request, back-navigation after async completion, and session expiry during the flow. CI story tests failures rarely throw stack traces users report — they surface as silent drop-offs, duplicate charges, or accessibility audit findings weeks later.

Document owner, dashboard link, and alert threshold in the PR. Review quarterly whether the optimization still matches traffic shape — mobile share growth, new markets, or CDN config changes can invert a previous win.""",
    "web-accessibility-keyboard-navigation": """## Production checklist for keyboard navigation

Ship focus order and traps only after baseline metrics exist. Capture p75 roving tabindex on mid-tier Android over throttled 4G before and after deploy — lab Lighthouse scores on developer laptops mislead for keyboard navigation because they ignore real CPU contention and cache state. Tie changes to a feature flag or CDN cache rule you can revert in minutes, not a deploy-only rollback.

Exercise failure paths in staging: double-submit, offline mid-request, back-navigation after async completion, and session expiry during the flow. skip links failures rarely throw stack traces users report — they surface as silent drop-offs, duplicate charges, or accessibility audit findings weeks later.

Document owner, dashboard link, and alert threshold in the PR. Review quarterly whether the optimization still matches traffic shape — mobile share growth, new markets, or CDN config changes can invert a previous win.""",
    "shared-data-layer-room-kmp": """## Production checklist for room kmp shared layer

Ship expect/actual drivers only after baseline metrics exist. Capture p75 Flow to UI on mid-tier Android over throttled 4G before and after deploy — lab Lighthouse scores on developer laptops mislead for room kmp shared layer because they ignore real CPU contention and cache state. Tie changes to a feature flag or CDN cache rule you can revert in minutes, not a deploy-only rollback.

Exercise failure paths in staging: double-submit, offline mid-request, back-navigation after async completion, and session expiry during the flow. offline sync failures rarely throw stack traces users report — they surface as silent drop-offs, duplicate charges, or accessibility audit findings weeks later.

Document owner, dashboard link, and alert threshold in the PR. Review quarterly whether the optimization still matches traffic shape — mobile share growth, new markets, or CDN config changes can invert a previous win.""",
    "software-vertical-slice-architecture": """## Production checklist for vertical slice architecture

Ship feature folders only after baseline metrics exist. Capture p75 MediatR handlers on mid-tier Android over throttled 4G before and after deploy — lab Lighthouse scores on developer laptops mislead for vertical slice architecture because they ignore real CPU contention and cache state. Tie changes to a feature flag or CDN cache rule you can revert in minutes, not a deploy-only rollback.

Exercise failure paths in staging: double-submit, offline mid-request, back-navigation after async completion, and session expiry during the flow. slice vs layer failures rarely throw stack traces users report — they surface as silent drop-offs, duplicate charges, or accessibility audit findings weeks later.

Document owner, dashboard link, and alert threshold in the PR. Review quarterly whether the optimization still matches traffic shape — mobile share growth, new markets, or CDN config changes can invert a previous win.""",
    "supply-chain-provenance-slsa": """## Production checklist for slsa provenance

Ship build attestation only after baseline metrics exist. Capture p75 Sigstore cosign on mid-tier Android over throttled 4G before and after deploy — lab Lighthouse scores on developer laptops mislead for slsa provenance because they ignore real CPU contention and cache state. Tie changes to a feature flag or CDN cache rule you can revert in minutes, not a deploy-only rollback.

Exercise failure paths in staging: double-submit, offline mid-request, back-navigation after async completion, and session expiry during the flow. SBOM linkage failures rarely throw stack traces users report — they surface as silent drop-offs, duplicate charges, or accessibility audit findings weeks later.

Document owner, dashboard link, and alert threshold in the PR. Review quarterly whether the optimization still matches traffic shape — mobile share growth, new markets, or CDN config changes can invert a previous win.""",
    "storybook-chromatic-visual-testing": """## Production checklist for chromatic visual testing

Ship baseline snapshots only after baseline metrics exist. Capture p75 UI Review workflow on mid-tier Android over throttled 4G before and after deploy — lab Lighthouse scores on developer laptops mislead for chromatic visual testing because they ignore real CPU contention and cache state. Tie changes to a feature flag or CDN cache rule you can revert in minutes, not a deploy-only rollback.

Exercise failure paths in staging: double-submit, offline mid-request, back-navigation after async completion, and session expiry during the flow. flake management failures rarely throw stack traces users report — they surface as silent drop-offs, duplicate charges, or accessibility audit findings weeks later.

Document owner, dashboard link, and alert threshold in the PR. Review quarterly whether the optimization still matches traffic shape — mobile share growth, new markets, or CDN config changes can invert a previous win.""",
    "web-components-form-association": """## Production checklist for form-associated custom elements

Ship formAssociatedCallback only after baseline metrics exist. Capture p75 ElementInternals on mid-tier Android over throttled 4G before and after deploy — lab Lighthouse scores on developer laptops mislead for form-associated custom elements because they ignore real CPU contention and cache state. Tie changes to a feature flag or CDN cache rule you can revert in minutes, not a deploy-only rollback.

Exercise failure paths in staging: double-submit, offline mid-request, back-navigation after async completion, and session expiry during the flow. participate in submit failures rarely throw stack traces users report — they surface as silent drop-offs, duplicate charges, or accessibility audit findings weeks later.

Document owner, dashboard link, and alert threshold in the PR. Review quarterly whether the optimization still matches traffic shape — mobile share growth, new markets, or CDN config changes can invert a previous win.""",
    "software-domain-driven-design-tactical": """## Production checklist for tactical ddd

Ship aggregates and entities only after baseline metrics exist. Capture p75 value objects on mid-tier Android over throttled 4G before and after deploy — lab Lighthouse scores on developer laptops mislead for tactical ddd because they ignore real CPU contention and cache state. Tie changes to a feature flag or CDN cache rule you can revert in minutes, not a deploy-only rollback.

Exercise failure paths in staging: double-submit, offline mid-request, back-navigation after async completion, and session expiry during the flow. domain events failures rarely throw stack traces users report — they surface as silent drop-offs, duplicate charges, or accessibility audit findings weeks later.

Document owner, dashboard link, and alert threshold in the PR. Review quarterly whether the optimization still matches traffic shape — mobile share growth, new markets, or CDN config changes can invert a previous win.""",
    "software-hexagonal-ports-adapters": """## Production checklist for hexagonal architecture

Ship ports and adapters only after baseline metrics exist. Capture p75 dependency direction on mid-tier Android over throttled 4G before and after deploy — lab Lighthouse scores on developer laptops mislead for hexagonal architecture because they ignore real CPU contention and cache state. Tie changes to a feature flag or CDN cache rule you can revert in minutes, not a deploy-only rollback.

Exercise failure paths in staging: double-submit, offline mid-request, back-navigation after async completion, and session expiry during the flow. fake adapters in tests failures rarely throw stack traces users report — they surface as silent drop-offs, duplicate charges, or accessibility audit findings weeks later.

Document owner, dashboard link, and alert threshold in the PR. Review quarterly whether the optimization still matches traffic shape — mobile share growth, new markets, or CDN config changes can invert a previous win.""",
    "spring-boot-vs-ktor-2026": """## Production checklist for spring boot vs ktor

Ship coroutines vs threads only after baseline metrics exist. Capture p75 startup time on mid-tier Android over throttled 4G before and after deploy — lab Lighthouse scores on developer laptops mislead for spring boot vs ktor because they ignore real CPU contention and cache state. Tie changes to a feature flag or CDN cache rule you can revert in minutes, not a deploy-only rollback.

Exercise failure paths in staging: double-submit, offline mid-request, back-navigation after async completion, and session expiry during the flow. ecosystem maturity failures rarely throw stack traces users report — they surface as silent drop-offs, duplicate charges, or accessibility audit findings weeks later.

Document owner, dashboard link, and alert threshold in the PR. Review quarterly whether the optimization still matches traffic shape — mobile share growth, new markets, or CDN config changes can invert a previous win.""",
    "vector-search-hnsw-tuning": """## Production checklist for hnsw tuning

Ship ef_search ef_construction only after baseline metrics exist. Capture p75 recall vs latency on mid-tier Android over throttled 4G before and after deploy — lab Lighthouse scores on developer laptops mislead for hnsw tuning because they ignore real CPU contention and cache state. Tie changes to a feature flag or CDN cache rule you can revert in minutes, not a deploy-only rollback.

Exercise failure paths in staging: double-submit, offline mid-request, back-navigation after async completion, and session expiry during the flow. index rebuild strategy failures rarely throw stack traces users report — they surface as silent drop-offs, duplicate charges, or accessibility audit findings weeks later.

Document owner, dashboard link, and alert threshold in the PR. Review quarterly whether the optimization still matches traffic shape — mobile share growth, new markets, or CDN config changes can invert a previous win.""",
    "web-accessibility-screen-reader-testing": """## Production checklist for screen reader testing

Ship VoiceOver NVDA only after baseline metrics exist. Capture p75 live regions on mid-tier Android over throttled 4G before and after deploy — lab Lighthouse scores on developer laptops mislead for screen reader testing because they ignore real CPU contention and cache state. Tie changes to a feature flag or CDN cache rule you can revert in minutes, not a deploy-only rollback.

Exercise failure paths in staging: double-submit, offline mid-request, back-navigation after async completion, and session expiry during the flow. accessible name computation failures rarely throw stack traces users report — they surface as silent drop-offs, duplicate charges, or accessibility audit findings weeks later.

Document owner, dashboard link, and alert threshold in the PR. Review quarterly whether the optimization still matches traffic shape — mobile share growth, new markets, or CDN config changes can invert a previous win.""",
    "state-of-flutter-2026": """## Production checklist for flutter 2026

Ship Impeller renderer only after baseline metrics exist. Capture p75 Wasm web target on mid-tier Android over throttled 4G before and after deploy — lab Lighthouse scores on developer laptops mislead for flutter 2026 because they ignore real CPU contention and cache state. Tie changes to a feature flag or CDN cache rule you can revert in minutes, not a deploy-only rollback.

Exercise failure paths in staging: double-submit, offline mid-request, back-navigation after async completion, and session expiry during the flow. Material 3 adoption failures rarely throw stack traces users report — they surface as silent drop-offs, duplicate charges, or accessibility audit findings weeks later.

Document owner, dashboard link, and alert threshold in the PR. Review quarterly whether the optimization still matches traffic shape — mobile share growth, new markets, or CDN config changes can invert a previous win.""",
    "vector-db-filtering-pre-post": """## Production checklist for vector pre/post filtering

Ship metadata filters only after baseline metrics exist. Capture p75 hybrid search on mid-tier Android over throttled 4G before and after deploy — lab Lighthouse scores on developer laptops mislead for vector pre/post filtering because they ignore real CPU contention and cache state. Tie changes to a feature flag or CDN cache rule you can revert in minutes, not a deploy-only rollback.

Exercise failure paths in staging: double-submit, offline mid-request, back-navigation after async completion, and session expiry during the flow. ANN then SQL failures rarely throw stack traces users report — they surface as silent drop-offs, duplicate charges, or accessibility audit findings weeks later.

Document owner, dashboard link, and alert threshold in the PR. Review quarterly whether the optimization still matches traffic shape — mobile share growth, new markets, or CDN config changes can invert a previous win.""",
    "voice-agents-stt-tts-pipelines": """## Production checklist for voice agent pipelines

Ship streaming STT only after baseline metrics exist. Capture p75 TTS latency on mid-tier Android over throttled 4G before and after deploy — lab Lighthouse scores on developer laptops mislead for voice agent pipelines because they ignore real CPU contention and cache state. Tie changes to a feature flag or CDN cache rule you can revert in minutes, not a deploy-only rollback.

Exercise failure paths in staging: double-submit, offline mid-request, back-navigation after async completion, and session expiry during the flow. barge-in handling failures rarely throw stack traces users report — they surface as silent drop-offs, duplicate charges, or accessibility audit findings weeks later.

Document owner, dashboard link, and alert threshold in the PR. Review quarterly whether the optimization still matches traffic shape — mobile share growth, new markets, or CDN config changes can invert a previous win.""",
    "web-components-shadow-dom": """## Production checklist for shadow dom

Ship encapsulated styles only after baseline metrics exist. Capture p75 slot composition on mid-tier Android over throttled 4G before and after deploy — lab Lighthouse scores on developer laptops mislead for shadow dom because they ignore real CPU contention and cache state. Tie changes to a feature flag or CDN cache rule you can revert in minutes, not a deploy-only rollback.

Exercise failure paths in staging: double-submit, offline mid-request, back-navigation after async completion, and session expiry during the flow. ::part and CSS custom properties failures rarely throw stack traces users report — they surface as silent drop-offs, duplicate charges, or accessibility audit findings weeks later.

Document owner, dashboard link, and alert threshold in the PR. Review quarterly whether the optimization still matches traffic shape — mobile share growth, new markets, or CDN config changes can invert a previous win.""",
}