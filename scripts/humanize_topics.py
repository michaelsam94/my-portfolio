"""Topic-specific paragraph banks for batch-07 humanization. No shared article skeleton."""
from __future__ import annotations

import hashlib

# Each entry: list of (heading, paragraphs) where paragraphs is list of strings
KEYWORD_BLOCKS: dict[str, list[tuple[str, list[str]]]] = {
    "webauthn": [
        ("Registration ceremony", [
            "WebAuthn registration starts with the server generating a random challenge and sending `publicKey` options to the browser. The authenticator creates a key pair bound to your `rpId` and returns an attestation. Verify challenge expiry, origin, and rpIdHash on the server — a mismatch is an immediate reject, not a warning.",
            "Store credentials with a stable `credentialId`, public key, sign count, and authenticator metadata. Sign count monotonicity catches cloned authenticators. For passkeys synced via iCloud or Google Password Manager, attestation formats differ from hardware keys; your policy should accept both if UX targets consumers.",
        ]),
        ("Authentication ceremony", [
            "Allow-credentials narrows which passkeys the client may use. For usernameless flows, leave it empty and let the platform picker show all passkeys for your rpId. Always verify signature, challenge, origin, and that the credential is not revoked.",
            "AI admin consoles should treat WebAuthn as step zero, not a checkbox. Operators who can change system prompts or export datasets are high-value targets. Pair passkeys with re-auth for destructive actions — deleting a vector index should require a fresh assertion.",
        ]),
    ],
    "passkeys": [
        ("Deployment phases", [
            "Roll out passkeys in three phases: optional enrollment beside passwords, default-on for new users, then password deprecation with escape hatches for break-glass accounts. Communicate device requirements — corporate Windows without Hello needs a fallback.",
            "Measure enrollment funnel: offer → created → used at next login. Drop-off usually means confusing copy or missing cross-device guidance. Link to platform docs for syncing passkeys between phone and laptop.",
        ]),
    ],
    "passwordless": [
        ("Migration path", [
            "Do not flip a boolean and delete passwords overnight. Run dual-mode auth for at least one release: users enroll passkeys or magic links while passwords still work. Track `% logins via passwordless` and support tickets tagged auth.",
            "Magic links introduce mailbox dependency; WebAuthn does not. For B2B AI products, prefer passkeys for admins and magic links only for low-privilege viewers. Session fixation and link replay belong in your threat model either way.",
        ]),
    ],
    "jwt": [
        ("Rotation without downtime", [
            "Publish JWKS with two active keys during rotation. Sign new tokens with key B while accepting validations with A and B. Only retire key A after max access-token TTL plus client clock skew buffer — usually 24–48 hours for conservative mobile clients.",
            "Never embed long-lived secrets in JWTs; they are bearer tokens, not vaults. For LLM gateways, short-lived service JWTs plus mTLS beat month-long HS256 strings copied into twelve microservices.",
        ]),
    ],
    "patch-management": [
        ("Inference fleet windows", [
            "GPU inference nodes cannot reboot like stateless API pods. Drain: stop accepting new sessions, wait for in-flight completions, snapshot model warm-up metrics, then patch. Rehearse on one node pool before fleet-wide maintenance.",
            "Align patches with embedding refresh jobs and training windows — not Friday 4pm. Keep a golden latency test that runs post-patch before re-admitting traffic. Document kernel/NVIDIA driver combos that broke CUDA last quarter.",
        ]),
    ],
    "streaming": [
        ("SSE production details", [
            "Buffer tokens to word boundaries before flushing — 30–80ms batches reduce React re-render churn. Send `: heartbeat\\n\\n` comments every 15s so nginx and ALBs do not kill idle connections during long reasoning traces.",
            "On client disconnect, abort upstream generation immediately. Burning tokens after the user clicked Stop is pure margin loss. Propagate cancellation through async generators and HTTP client close callbacks.",
        ]),
    ],
    "outbox": [
        ("Transactional outbox", [
            "Write business rows and outbox events in one database transaction. A relay process publishes to Kafka or SQS with idempotent consumers downstream. This beats dual-write 'update DB then fire event' which fails open on partial crashes.",
            "LLM pipelines use outbox for audit events: prompt hash logged, retrieval snapshot id, model version. Regulators ask for lineage; outbox gives you ordered, durable records without blocking the user response path.",
        ]),
    ],
    "sealed": [
        ("Exhaustive when", [
            "Sealed hierarchies exist so `when` can be exhaustive without `else`. Adding a branch becomes a compiler-guided refactor across the codebase. Resist `else -> TODO()` — it hides the safety net.",
            "Use `data object` for zero-payload cases so logs read `Loading` not `Loading@3fa2`. Smart casts inside `is` branches remove ceremony; pair with [Kotlin contracts](https://kotlinlang.org/docs/whatsnew1620.html) when custom types need narrowing helpers.",
        ]),
    ],
    "serialization": [
        ("Beyond JSON", [
            "kotlinx.serialization supports ProtoBuf, CBOR, and custom formats. Pick ProtoBuf for service-to-service when schema evolution matters; JSON stays for public HTTP. `@ProtoNumber` and `@SerialName` are how you rename without breaking wire compatibility.",
            "Polymorphic hierarchies need a discriminator strategy — `@JsonClassDiscriminator` or sealed subclass registration. Defaulting to class name leaks package structure; explicit serial names keep payloads stable when you refactor packages.",
        ]),
    ],
    "ksp": [
        ("Symbol processing", [
            "KSP runs Kotlin-aware rounds before code generation — faster than KAPT because it avoids stub compilation. Processors should return unprocessed symbols for invalid inputs so KSP can retry after other processors generate missing types.",
            "Generate narrow APIs: validators, adapters, DI modules. Keep generated code deterministic and idempotent. Log actionable errors at the annotation site, not stack traces in build scans nobody reads.",
        ]),
    ],
    "supervisorjob": [
        ("Structured concurrency", [
            "`SupervisorJob` isolates child failures — one failed coroutine does not cancel siblings. Use it for independent work streams (analytics + recommendations). Use plain `Job` when all children must fail together.",
            "Always attach coroutines to a scope with a defined lifetime — `GlobalScope` is for demos. In Android, `viewModelScope`; on server, request-scoped supervisor tied to the HTTP call or message ack deadline.",
        ]),
    ],
    "gateway-api": [
        ("Gateway API vs Ingress", [
            "Gateway API separates concerns: `GatewayClass` (implementation), `Gateway` (listeners), `HTTPRoute` (rules). Role-oriented RBAC lets app teams own routes without cluster-admin Ingress annotations soup.",
            "Migrate by mirroring hostnames on both Ingress and HTTPRoute, shift DNS or service mesh weights gradually, and compare access logs. TLS termination moves with the Gateway — duplicate certs during cutover.",
        ]),
    ],
    "karpenter": [
        ("Node provisioning", [
            "Karpenter provisions nodes from pending pod specs — faster than cluster-autoscaler when bin-packing matters. Define NodePools with instance category, architecture, and capacity-type (spot vs on-demand) constraints.",
            "Spot interruption handling requires graceful termination hooks and PDBs. Batch inference can live on spot; latency-sensitive chat serving usually needs on-demand baseline with spot overflow.",
        ]),
    ],
    "network-polic": [
        ("Default deny", [
            "Start with deny-all ingress and egress, then allow DNS (kube-system), API dependencies, and telemetry endpoints. Without egress control, a compromised pod exfiltrates embeddings and API keys.",
            "Validate policies with netpol-audit tools — CNI differences bite. Calico, Cilium, and AWS VPC CNI enforce subtly different semantics for namespace selectors and FQDN rules.",
        ]),
    ],
    "prometheus": [
        ("Kubernetes monitoring", [
            "Use kube-state-metrics for object health, node-exporter for saturation, and cAdvisor-derived container metrics. RED on workloads, USE on nodes. High-cardinality labels (`user_id`, `prompt_id`) belong in traces or logs, not Prometheus.",
            "Recording rules pre-aggregate expensive queries dashboards hammer during incidents. Alert on SLO burn rates, not static thresholds on CPU that page at 3am for no user impact.",
        ]),
    ],
    "helm": [
        ("Helm vs Kustomize", [
            "Helm packages releases with templating and lifecycle hooks — great for third-party charts. Kustomize patches existing YAML without a DSL — great for gitops repos that diff cleanly in PRs.",
            "Hybrid pipelines render Helm then kustomize overlay for environment-specific patches. Pin chart versions; `latest` in production is how you learn about breaking changes live.",
        ]),
    ],
    "kv-cache": [
        ("Serving economics", [
            "KV cache reuse is the difference between profitable and subsidized long-context chat. Prefix caching across users with shared system prompts saves massive compute — measure hit rate per route.",
            "PagedAttention and continuous batching change memory fragmentation tradeoffs. Profile GPU memory before scaling replicas; more smaller GPUs sometimes beat fewer H100s with thrashing cache.",
        ]),
    ],
    "lazy-loading": [
        ("Images and LCP", [
            "Native `loading=\"lazy\"` defers off-screen images; never lazy-load LCP hero assets. Combine with `fetchpriority=\"high\"` on the one image that matters for Core Web Vitals.",
            "Intersection Observer adds custom root margins — start loading 200px before enter for carousels. Track `element.timing` or web-vitals library to verify LCP wins in field data, not only Lighthouse lab runs.",
        ]),
    ],
    "package-lock": [
        ("Supply chain integrity", [
            "Commit lockfiles for every deployable — npm, pip, poetry, cargo. CI should fail when lockfile is stale relative to manifest. For LLM agent runtimes that install tools dynamically, pin versions in an allowlist registry.",
            "Verify checksums and use private mirrors for air-gapped inference clusters. SBOM export on build artifacts makes incident response faster when a CVE hits a transitive dependency.",
        ]),
    ],
    "idempotency": [
        ("Retry safety", [
            "Clients retry on timeouts; servers must dedupe with idempotency keys stored until TTL exceeds max client retry window. Return the same response body on replay — billing and LLM quota systems depend on this.",
            "Keys should scope to tenant + operation, not global UUIDs that collide across services. Postgres `INSERT ... ON CONFLICT` or Redis SET NX with TTL are common backends.",
        ]),
    ],
    "rag": [
        ("Retrieval quality", [
            "Chunk boundaries split tables and code blocks — use structure-aware chunking. Re-embed incrementally on doc updates; full reindex nightly hides stale content bugs until a user cites wrong numbers.",
            "Hybrid search tuning is not one weight forever — log empty retrievals and low-confidence answers, then adjust sparse/dense blend weekly from production samples, not offline nDCG alone.",
        ]),
    ],
    "ab-test": [
        ("Statistical power", [
            "Pre-register primary metrics and minimum detectable effect before launching. Underpowered tests waste traffic and conclude 'no difference' when the truth is 'not enough sample'.",
            "For LLM UX, power on task completion rate and time-to-success, not click-through on thumbs. Sequential testing without correction inflates false positives — use proper methods or fixed horizons.",
        ]),
    ],
    "opentelemetry": [
        ("GenAI traces", [
            "Instrument model calls as spans: `gen_ai.system`, `gen_ai.request.model`, token counts as attributes. Link retrieval and tool spans as children of the orchestration span — flamegraphs should show where latency lives.",
            "Sample aggressively on high-volume paths but always keep errors. Export cost metrics to the same trace backend so you correlate slow spans with expensive prompts.",
        ]),
    ],
    "audit": [
        ("Immutable audit trails", [
            "Append-only audit logs with hash chaining or WORM storage resist tampering after the fact. Record actor, action, target, timestamp, and correlation id — not raw prompts with customer PII.",
            "Separate audit ingestion from query paths so logging storms during incidents do not starve the primary API. Retention policies should match regulatory minimums, not infinite S3 bills.",
        ]),
    ],
    "enumeration": [
        ("Account enumeration", [
            "Login and reset flows must return identical responses and timing whether or not an email exists. Rate-limit by IP and fingerprint; captcha only after thresholds to avoid punishing mobile NAT users.",
            "LLM signup wizards that confirm 'email already registered' leak your customer list to competitors. Use generic copy and deliver details only via the mailbox.",
        ]),
    ],
    "backpressure": [
        ("Flow control", [
            "When downstream model latency spikes, accept fewer requests at the edge instead of queueing unbounded work. Return 503 with Retry-After or shed load by tenant tier.",
            "Reactive streams, semaphores, and adaptive concurrency limits beat blind retries — retries during overload are positive feedback loops.",
        ]),
    ],
    "canary": [
        ("Progressive delivery", [
            "Route 1–5% of traffic to the new model or prompt template; compare error rate, latency, cost, and task success against baseline. Automate rollback when burn rate exceeds budget.",
            "Flagger or Argo Rollouts integrate with service mesh weights. For LLM changes, offline evals gate entry; online canaries gate scale.",
        ]),
    ],
    "partition": [
        ("Data partitioning", [
            "Partition by tenant or time so queries prune irrelevant data. Sticky assignment keeps related sessions on one shard for cache warmth — but plan rebalancing when shards skew.",
            "LLM conversation stores partition by tenant_id + month to bound index size and simplify GDPR deletes.",
        ]),
    ],
    "materialized": [
        ("View refresh", [
            "Materialized views trade freshness for read speed. CONCURRENTLY refresh where Postgres allows; schedule off-peak for heavy aggregates feeding analytics dashboards.",
            "For RAG analytics, pre-aggregate retrieval hit rates and empty-result counts — ad-hoc scans across billions of log rows do not belong in incident queries.",
        ]),
    ],
    "hybrid-search": [
        ("Weight tuning", [
            "Start with BM25 + dense vectors at equal weight, then adjust from logged failures: keyword-heavy queries need higher sparse weight; paraphrase questions need dense.",
            "Re-tune after corpus updates — embeddings trained on old docs skew retrieval until re-index completes.",
        ]),
    ],
    "chunk": [
        ("Parent-child linking", [
            "Retrieve small chunks for precision but pass parent sections to the model for context. Store parent_id on each chunk and expand after vector search.",
            "Heading-aware splits beat fixed token windows for documentation RAG. Never split mid-table without repeating headers in both chunks.",
        ]),
    ],
    "fraud": [
        ("Realtime scoring", [
            "Feature stores must serve low-latency aggregates — device fingerprint, velocity, geo mismatch. Model scores gate step-up auth, not silent blocks without appeal paths.",
            "LLM billing fraud (token farming, shared API keys) needs per-key quotas and anomaly detection on usage patterns, not only monthly invoices.",
        ]),
    ],
    "gdpr": [
        ("Right to erasure", [
            "Deletion must cascade: user profile, conversations, embeddings, backups with legal holds excepted. Tombstone ids in vector stores prevent re-ingestion from nightly ETL.",
            "Document retention in privacy policy and automate DSAR workflows — manual grep across S3 does not scale past enterprise sales.",
        ]),
    ],
    "oidc": [
        ("Discovery caching", [
            "Cache OIDC discovery documents and JWKS with TTL aligned to provider rotation practices. Stale JWKS causes widespread auth failure when IdP rotates keys hourly.",
            "Validate issuer string exactly — subtle mismatches (`https` vs `https://`) become intermittent login failures only in production.",
        ]),
    ],
    "csrf": [
        ("Double-submit cookie", [
            "Synchronizer tokens or double-submit cookies protect cookie-authenticated LLM admin UIs. SameSite=Lax is not sufficient for all cross-site flows.",
            "State-changing POSTs from browser sessions need CSRF tokens even when APIs also accept bearer tokens from scripts.",
        ]),
    ],
    "dead-letter": [
        ("DLQ handling", [
            "Poison messages belong in a DLQ with original payload, error class, and retry count. Operators need replay tooling with idempotency — blind requeue loops forever.",
            "Alert on DLQ depth growth rate, not static count — bursty failures differ from systemic bugs.",
        ]),
    ],
    "drift": [
        ("Infrastructure drift", [
            "Compare live cloud state to Terraform/Pulumi git revisions daily. Emergency console edits must merge back within 24h or be reverted.",
            "LLM infra drift includes prompt templates outside git, embedding pipelines run manually, and API keys in shared docs.",
        ]),
    ],
    "ebpf": [
        ("Ambient mesh", [
            "eBPF dataplanes reduce sidecar overhead but require kernel compatibility matrices. Roll out on canary nodes before fleet-wide Cilium upgrades.",
            "Observability from eBPF must still export RED metrics your on-call already knows how to read.",
        ]),
    ],
    "wasm": [
        ("Kotlin Wasm interop", [
            "Kotlin/Wasm targets browser and Node with different interop stubs. `@JsExport` boundaries should be narrow — expose stable facades, not entire domain models.",
            "Compose for Web on Wasm still shares sizing and input latency constraints with Canvas backends; profile on mid-tier Android browsers.",
        ]),
    ],
    "typealias": [
        ("Domain language", [
            "Typealiases document intent without wrapper overhead: `typealias UserId = String` beats bare String in public APIs. They do not provide nominal typing — use value classes when mix-ups must be compile errors.",
            "Consistent aliases across modules beat each team inventing `typealias CustomerKey`. Publish a small domain-types artifact.",
        ]),
    ],
    "value-class": [
        ("Inline value classes", [
            "`@JvmInline value class` removes allocation on JVM for wrappers like Email or Meters. Serialization needs explicit kotlinx.serialization support — register contextual serializers where JSON expects primitives.",
            "Do not wrap every string — value classes shine at domain boundaries, not inside hot inner loops with hundreds of distinct wrappers.",
        ]),
    ],
}


def blocks_for_slug(slug: str) -> list[tuple[str, list[str]]]:
    matched: list[tuple[str, list[str]]] = []
    for kw, blocks in KEYWORD_BLOCKS.items():
        if kw.replace("-", "") in slug.replace("-", ""):
            matched.extend(blocks)
    return matched


def kotlin_blocks(topic: str, slug: str) -> list[tuple[str, list[str]]]:
    return blocks_for_slug(slug) + [
        ("Practical conventions", [
            f"Keep {topic} visible in code review: one module owns the closed set, tests cover every branch, and public APIs document which variants callers must handle.",
            "Reach for IDE inspections and detekt rules to ban `else` branches on sealed `when` in internal modules — exceptions should be rare and documented.",
        ]),
        ("Performance and interop", [
            "Sealed dispatch is inexpensive on JVM; allocations are not. Avoid creating new wrapper objects on animation frames or per-token hot paths.",
            "Java callers need explicit KDoc because exhaustiveness is a Kotlin compile-time feature. Narrow entry points reduce misuse at mixed-language boundaries.",
        ]),
        ("Team adoption", [
            "Introduce patterns in one service boundary with measurable bug reduction before mandating repo-wide. Brownfield codebases need migration maps, not big-bang rewrites.",
            "Pair with serialization and API versioning — sealed types change when you add variants; clients on old contracts need forward-compatible defaults.",
        ]),
    ]


def kubernetes_blocks(topic: str, slug: str) -> list[tuple[str, list[str]]]:
    return blocks_for_slug(slug) + [
        ("Platform baseline", [
            f"Treat {topic} as a platform capability with a named owner, SLO, and exception process. Ad-hoc cluster tweaks without git commits are how drift becomes outages.",
            "Document assumed CNI features, ingress controller version, and cloud quota limits beside every runbook — tutorials rarely match your fleet.",
        ]),
        ("Rollout discipline", [
            "Canary one node pool or namespace; compare golden signals for 24 hours before fleet-wide enablement. Keep rollback one apply away.",
            "Game-day exercises: drain nodes, revoke tokens, fail a dependency — validate {topic} behavior before peak season.".format(topic=topic),
        ]),
        ("Cost and capacity", [
            "Rightsize requests from measured usage, not copy-pasted YAML. Autoscaling saves money only when workloads declare honest CPU/memory needs.",
        ]),
    ]


def supplement_paragraphs(slug: str, topic: str, domain: str) -> list[str]:
    """Additional topic-colored paragraphs to reach word target without duplicate headings."""
    base = [
        f"When {topic} fails in production, the trigger is usually a config change — flag flip, chart upgrade, or credential rotation — not the original feature launch. "
        f"Build dashboards that compare canary vs baseline during every rollout.",
        f"Security reviews for {topic} should ask about least privilege, data retention, and blast radius. "
        f"If the answer is 'we trust internal callers,' revisit network policy and service identity.",
        f"Documentation for {topic} needs worked examples: one success trace, one failure trace, and the exact command or flag that rolls back. "
        f"Wiki prose without commands does not help on-call.",
        f"Testing {topic} requires failure injection — timeout downstream, duplicate requests, permission denied mid-flow. "
        f"Happy-path CI alone guarantees surprise on the first holiday traffic spike.",
        f"Cross-team contracts matter: product defines acceptable degradation, platform defines enforcement, security defines audit evidence. "
        f"{topic.title()} sits at that intersection — schedule a 30-minute review before GA.",
        f"Version skew between clients and servers exposes {topic} bugs months later. Publish compatibility matrices and test N-1 client versions in staging.",
        f"Capacity planning for {topic} ties to cost: measure peak QPS, payload sizes, and fan-out. "
        f"Synthetic hello-world load tests miss queue backlogs that appear only with production payload shapes.",
    ]
    if domain == "kotlin":
        base.extend([
            f"Refactors touching {topic} should compile-first: let the compiler list every `when` branch to update. "
            f"That is cheaper than production `IllegalStateException` after a missed case.",
            "Binary compatibility: adding sealed variants is source-breaking for exhaustive consumers — semver major or provide adapter layers for external SDK consumers.",
        ])
    if domain == "kubernetes":
        base.extend([
            f"Helm values and Kustomize overlays for {topic} must live in git — emergency kubectl edits need backfill within 24 hours or revert.",
            "Multi-cluster fleets need consistent policy baselines; document which clusters have exceptions and when those exceptions expire.",
        ])
    if domain == "llm_platform":
        base.extend([
            f"LLM-specific risk for {topic}: non-deterministic outputs mask regressions — track model version, prompt hash, and retrieval corpus snapshot on every request.",
            "Unit economics: token usage and GPU seconds should appear on the same dashboard as error rate — finance and on-call then share one truth.",
        ])
    # rotate order per slug for variety
    v = int(hashlib.sha256(slug.encode()).hexdigest(), 16)
    rotated = base[v % len(base):] + base[: v % len(base)]
    return rotated


def generic_llm_blocks(topic: str) -> list[tuple[str, list[str]]]:
    return [
        ("Production framing", [
            f"{topic.title()} in AI platforms is not a library import — it is a contract between product, security, and infra. Define SLOs, failure modes, and ownership before the feature flag goes to 100%.",
            "Demo paths hide retries, partial permissions, and cost ceilings. Design for double-clicks, stale mobile tabs, and operators running ad-hoc scripts against your API.",
        ]),
        ("Observability", [
            f"Metric {topic} with correlation IDs across retrieval, model, and tool hops. Alert on symptom burn — error rate, p95 latency, cost per successful task — not vanity CPU graphs.",
            "Log decisions, not secrets. Prompt templates hash stably; raw PII in logs becomes tomorrow's compliance ticket.",
        ]),
        ("Rollout", [
            "Canary by tenant cohort. Keep a kill switch that disables the feature path without redeploying weights. Rollback rehearsed in staging monthly — muscle memory beats improvisation at 2am.",
        ]),
        ("Incident readiness", [
            f"Runbooks for {topic} should fit one page: symptoms, dashboards, mitigation, rollback owner. If mitigation requires tribal knowledge, the design is not operable yet.",
            "Post-incident, update tests and alerts — not only the wiki. The next failure should be louder and cheaper.",
        ]),
    ]
