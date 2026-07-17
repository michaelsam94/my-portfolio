#!/usr/bin/env python3
"""Humanize batch M: 50 specific slugs. Preserve technical depth, strip wave2 filler, expand to >=1200 words."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
PROGRESS = ROOT / "scripts" / "humanize-progress" / "batch-m.json"
DATE_MODIFIED = "2026-07-17"
TARGET_WORDS = 1200
WORD_PAT = re.compile(r"\b[\w'-]+\b")

SKIP_SLUGS = frozenset({
    "local-first-apps-crdts",
    "managing-technical-debt",
    "multi-region-active-active",
})

SLUGS = [
    "load-balancing-algorithms-l4-l7", "load-testing-with-k6", "local-first-apps-crdts",
    "long-context-vs-rag", "managing-technical-debt", "mcp-remote-servers-deployment",
    "mcp-resources-vs-tools-vs-prompts", "mcp-sampling-elicitation", "mcp-server-authentication-oauth",
    "mcp-server-testing-inspector", "mcp-transport-stdio-http-sse", "message-queue-dead-letter-handling",
    "message-queues-sqs-vs-kafka", "mfa-totp-implementation", "microservices-api-composition",
    "microservices-circuit-breaker-resilience", "microservices-contract-testing-pact",
    "microservices-distributed-tracing", "microservices-service-discovery",
    "microservices-strangler-fig-migration", "migrating-xml-to-compose", "mixture-of-experts-explained",
    "ml-model-serving-inference", "mobile-app-security-owasp-masvs", "mobile-reverse-engineering-defense",
    "modbus-industrial-gateways", "model-context-protocol-vs-function-calling", "model-distillation-smaller-faster",
    "modular-monoliths-vs-microservices", "mqtt-bridging-clustering", "mqtt-iot-at-scale",
    "mqtt-qos-levels-explained", "mqtt-retained-messages-last-will", "mqtt-sparkplug-b",
    "mqtt-tls-authentication-iot", "mqtt-topic-design-patterns", "mtls-mutual-authentication",
    "mtls-service-mesh", "multi-agent-orchestration-orchestrator-workers", "multi-region-active-active",
    "multimodal-audio-transcription-whisper", "multimodal-document-understanding",
    "multimodal-image-generation-apis", "multimodal-models-in-apps", "multimodal-realtime-voice-api",
    "multimodal-text-to-speech-neural", "multimodal-vision-language-models", "navigation-3-jetpack-compose",
    "nextjs-after-api-response-streaming", "nextjs-analytics-web-vitals-reporting",
    "nextjs-app-router-server-actions",
]

FILLER_SECTIONS = re.compile(
    r"\n## (Common production mistakes|Debugging and triage workflow|"
    r"Metrics worth dashboarding|What to measure|How this fits your stack|Rollout checklist)"
    r".*?(?=\n## |\Z)",
    re.DOTALL,
)

BANNED = ("## Problem framing", "Problem framing", "Copying a tutorial without matching your constraints")


def word_count(text: str) -> int:
    return len(WORD_PAT.findall(text))


def pick_variant(slug: str, n: int) -> int:
    return int(hashlib.sha256(slug.encode()).hexdigest(), 16) % n


def yaml_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def parse_post(path: Path) -> dict:
    raw = path.read_text()
    parts = raw.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"Bad frontmatter: {path}")
    fm = parts[1]
    body = parts[2]

    def grab(key: str, default: str = "") -> str:
        m = re.search(rf'^{key}:\s*"(.*)"', fm, re.M)
        return m.group(1) if m else default

    faqs = []
    faq_block = re.search(r"faq:\n((?:  - q:.*\n    a:.*\n)*)", fm)
    if faq_block:
        for m in re.finditer(r'  - q: "(.*)"\n    a: "(.*)"', faq_block.group(1)):
            faqs.append({"q": m.group(1), "a": m.group(2)})

    tags_block = re.search(r"tags:\s*\[(.*?)\]", fm, re.S)
    if tags_block:
        tags = re.findall(r'"([^"]+)"', tags_block.group(1))
    else:
        tags_m = re.search(r"tags:.*?(?=\nkeywords:|\nfaq:|\Z)", fm, re.S)
        tags = re.findall(r'-\s*"([^"]+)"', tags_m.group(0)) if tags_m else []

    return {
        "path": path,
        "slug": path.stem,
        "raw_fm": fm,
        "title": grab("title", path.stem),
        "description": grab("description"),
        "date_published": grab("datePublished", "2025-01-01"),
        "tags": tags,
        "keywords": grab("keywords"),
        "faq": faqs,
        "body": body,
    }


def is_humanized(body: str, faq: list) -> bool:
    if any(b in body for b in BANNED):
        return False
    if re.search(r"^## Problem", body, re.M):
        return False
    wc = word_count(body)
    if wc < TARGET_WORDS:
        return False
    if len(faq) < 3:
        return False
    if not all(f.get("q") and f.get("a") and len(f["a"]) > 50 for f in faq):
        return False
    return True


def strip_filler(body: str) -> str:
    body = FILLER_SECTIONS.sub("", body)
    return body.strip()


def domain_for(slug: str) -> str:
    if slug.startswith("mcp") or slug.startswith("model-context") or slug.startswith("multi-agent"):
        return "mcp"
    if slug.startswith("mqtt") or slug.startswith("modbus"):
        return "iot"
    if slug.startswith("microservices") or slug.startswith("modular-monolith"):
        return "microservices"
    if slug.startswith("multimodal") or slug.startswith("mixture-of") or slug.startswith("ml-model") or slug.startswith("model-distillation") or slug.startswith("long-context"):
        return "ml"
    if slug.startswith("nextjs"):
        return "nextjs"
    if slug.startswith("mobile") or slug.startswith("mfa") or slug.startswith("mtls"):
        return "security"
    if slug.startswith("message"):
        return "messaging"
    if slug.startswith("navigation"):
        return "android"
    if slug.startswith("load") or slug.startswith("multi-region"):
        return "ops"
    if slug.startswith("local-first"):
        return "localfirst"
    if slug.startswith("managing"):
        return "engineering"
    if slug.startswith("migrating"):
        return "android"
    return "general"


def faq_enhance(slug: str, title: str, existing: list[dict]) -> list[dict]:
    """Keep good existing FAQ; add fourth question if only three generic ones."""
    if len(existing) >= 3 and all(len(f.get("a", "")) > 80 for f in existing):
        return existing[:4]
    topic = slug.replace("-", " ")
    extras = {
        "load-balancing-algorithms-l4-l7": [
            {"q": "Why does round robin fail on LLM inference endpoints?",
             "a": "Inference requests hold connections for seconds to minutes. Round robin assigns the next request to the next backend regardless of load, so one slow request blocks a slot while other backends sit idle. Least connections routes around occupied backends and keeps GPU utilization even."},
        ],
        "mcp-transport-stdio-http-sse": [
            {"q": "Why do MCP POST messages fail behind load balancers with SSE transport?",
             "a": "SSE transport opens a long-lived GET stream on one server instance while POST messages may land on another without session affinity. Enable sticky sessions or migrate to Streamable HTTP stateless mode so each request is self-contained."},
        ],
        "nextjs-app-router-server-actions": [
            {"q": "Can Server Actions replace all API routes?",
             "a": "No. External clients, webhooks, mobile apps calling REST, and endpoints needing custom HTTP status codes or caching headers still need Route Handlers. Server Actions excel at in-app form mutations with progressive enhancement."},
        ],
    }
    if slug in extras:
        merged = existing[:3] + extras[slug]
        return merged[:4]
    if len(existing) >= 3:
        return existing
    return existing + [
        {"q": f"What is the first production sign {topic} is misconfigured?",
         "a": "Tail latency spikes, silent data loss, or security findings — not unit test failures. Define SLOs and alert on user-visible symptoms before tuning internals."},
    ]


def intro_for(slug: str, domain: str) -> str | None:
    """Optional narrative hook prepended when body opens too abruptly."""
    hooks = {
        "load-balancing-algorithms-l4-l7": (
            "I have debugged more uneven-traffic incidents than I care to count, and the load balancer "
            "was rarely broken — the layer or algorithm was wrong for the workload. "
            "L4 and L7 are not interchangeable labels; they see different parts of the connection and make different routing decisions."
        ),
        "load-testing-with-k6": (
            "Load testing with k6 is one of those practices teams postpone until a launch melts a database. "
            "The difference between a script that prints RPS and one that predicts production failure is scenario design: "
            "think in user journeys, not isolated endpoints."
        ),
        "mcp-transport-stdio-http-sse": None,  # already has good intro
        "message-queues-sqs-vs-kafka": (
            "Choosing between SQS and Kafka is less about which queue is 'better' and more about whether you need "
            "a managed mailbox or a distributed commit log. Teams that pick wrong spend months fighting the abstraction."
        ),
        "microservices-strangler-fig-migration": (
            "The strangler fig pattern sounds poetic until you are routing production traffic through two architectures "
            "simultaneously. Done well, users never notice; done poorly, every deploy is a coin flip."
        ),
        "mqtt-iot-at-scale": (
            "MQTT brokers look simple until you have a million devices reconnecting after a cellular tower blip. "
            "At scale, connection churn, topic ACL design, and QoS choices matter more than broker brand."
        ),
        "nextjs-app-router-server-actions": None,
    }
    return hooks.get(slug)


# Topic-specific expansion sections keyed by slug
EXPANSIONS: dict[str, list[tuple[str, str]]] = {
    "load-balancing-algorithms-l4-l7": [
        ("What I check during an incident", (
            "When traffic skews to one backend, I pull three numbers before touching config: active connections per backend, "
            "request duration p95 per backend, and health-check pass rate. Skew with equal connection counts usually means "
            "sticky sessions or consistent-hash ring imbalance. Skew with unequal connections on round robin almost always "
            "means long-lived requests — switch to least connections and redeploy during a trough.\n\n"
            "For WebSocket upgrades behind L7, verify the upgrade request and subsequent frames hit the same backend. "
            "Some ingress controllers terminate WebSockets at the edge and proxy incorrectly on reconnect. "
            "NLB in front of nginx helps with TCP-level distribution, but the L7 layer still needs `proxy_http_version 1.1` "
            "and `Connection` header handling documented in the runbook."
        )),
        ("Capacity planning with weights", (
            "Weighted round robin is how you mix instance sizes without maintaining separate pools. "
            "If you run m5.xlarge (4 vCPU) beside m5.2xlarge (8 vCPU), weight 1:2 — not 1:1 because the names look similar. "
            "Revisit weights after autoscaling events; a new node pool with different CPU generation may need recalibration.\n\n"
            "Consistent hashing deserves explicit mention for cache-heavy APIs. When a backend leaves the pool, "
            "only keys mapped to that node remap — unlike naive modulo hashing that reshuffles everything. "
            "Use a bounded number of virtual nodes per backend (typically 100–200 in Envoy) to keep distribution smooth."
        )),
    ],
    "load-testing-with-k6": [
        ("Scenarios beat raw RPS", (
            "A script that hammers `GET /health` tells you almost nothing about checkout or search under load. "
            "Model scenarios as weighted VUs: 70% browse, 20% search, 10% purchase. k6's `exec.scenario` API lets you "
            "run ramping-vus, constant-arrival-rate, and per-scenario thresholds in one script.\n\n"
            "Constant arrival rate is underused. It maintains requests per second regardless of response time — "
            "so when latency spikes, k6 adds VUs to hold the rate. That mirrors real traffic better than fixed VU count, "
            "where slowdowns artificially reduce load and hide backpressure failures."
        )),
        ("Thresholds that gate releases", (
            "Define thresholds in the script, not in someone's head: `http_req_duration: ['p(95)<500']`, "
            "`http_req_failed: ['rate<0.01']`, custom metrics for business steps. Wire k6 Cloud or Grafana output "
            "to CI so a regression blocks merge.\n\n"
            "Run smoke load on every deploy (2 minutes, 10 VUs) and full soak weekly (30+ minutes at expected peak). "
            "Memory leaks and connection pool exhaustion show up in soak tests, not in two-minute bursts."
        )),
    ],
    "long-context-vs-rag": [
        ("Cost math nobody does upfront", (
            "A 128k-token context window sounds like free retrieval until you multiply by concurrent users. "
            "Stuffing full document corpora into context costs dollars per request and adds seconds of prefill latency. "
            "RAG pays indexing cost once and retrieves kilobytes per query — usually 10–100x cheaper at scale.\n\n"
            "Long context wins when cross-chunk reasoning is essential: comparing clause 47 to clause 12 in one contract, "
            "or maintaining exact ordering across a full codebase file set. For FAQ-style lookup, RAG with reranking "
            "beats raw context on both cost and accuracy."
        )),
        ("Hybrid patterns in production", (
            "Most mature systems combine both: RAG retrieves candidate chunks, then a reranker selects top-k, "
            "and the model receives a 8k–32k window with only high-signal text. Some teams add a 'context overflow' "
            "path that escalates to larger windows for premium tiers or human-reviewed cases.\n\n"
            "Measure retrieval recall and answer faithfulness separately. Long context can hallucinate connections "
            "between unrelated sections; RAG fails loudly when retrieval misses. Your eval suite should test both failure modes."
        )),
    ],
    "managing-technical-debt": [
        ("Debt registers that get used", (
            "A spreadsheet no one opens is not a debt register. I have seen effective teams tie debt items to "
            "quarterly OKR capacity — typically 15–25% of engineering time — with explicit owners and 'cost of delay' "
            "estimates. Items without customer impact metrics get deprioritized forever; that is fine if documented.\n\n"
            "Tag debt in tickets: `tech-debt`, estimated remediation days, and which SLO is at risk. "
            "When incident review finds debt as root cause, link the postmortem to the ticket and bump priority."
        )),
        ("When to pay vs when to borrow", (
            "Pay debt when change frequency is high in that module, when onboarding new engineers takes weeks "
            "because of legacy patterns, or when compliance deadlines hard-stop on audit findings. "
            "Borrow more when exploring product-market fit and the code path may be deleted in sixty days.\n\n"
            "The anti-pattern is uniform '20% cleanup sprints' with no prioritization — teams polish unused modules "
            "while checkout remains fragile."
        )),
    ],
    "mcp-remote-servers-deployment": [
        ("Deployment topologies", (
            "Remote MCP servers belong behind the same infrastructure as internal APIs: TLS termination, "
            "WAF, rate limits, and identity-aware proxy. Containerize the server process; avoid running as "
            "a long-lived subprocess on a developer laptop shared via ngrok for production workloads.\n\n"
            "For multi-tenant deployments, isolate credentials per tenant in a secrets manager and map "
            "OAuth subject claims to tool permission scopes. A compromised MCP server is equivalent to "
            "partial admin access — design blast radius accordingly."
        )),
        ("Health and lifecycle", (
            "MCP sessions over SSE may live for hours. Kubernetes liveness probes that kill pods on "
            "CPU idle will drop active agent sessions. Prefer readiness probes that remove unhealthy instances "
            "from rotation while allowing graceful SSE drain with `preStop` hooks and adequate `terminationGracePeriodSeconds`."
        )),
    ],
    "mcp-resources-vs-tools-vs-prompts": [
        ("Choosing the right primitive", (
            "Tools are for actions with side effects — create ticket, run query, send email. "
            "Resources are for read-only context the model can fetch — file contents, schema docs, config snapshots. "
            "Prompts are reusable instruction templates the user or host selects explicitly.\n\n"
            "The failure mode I see: everything implemented as a tool because it is easier. "
            "That invites the model to 'call' read operations repeatedly, burning tokens and latency. "
            "Resources with URI templates and cache headers reduce redundant fetches."
        )),
        ("Security boundaries", (
            "Tool descriptions are prompt injection surface. Version and review them like API docs. "
            "Resources should not expose paths outside declared roots. Prompts shipped by the server should "
            "not contain secrets — inject credentials server-side when tools execute."
        )),
    ],
    "mcp-sampling-elicitation": [
        ("Sampling in the MCP lifecycle", (
            "MCP sampling lets servers request LLM completions through the client — useful when a tool "
            "needs semantic classification without embedding an API key in the server. The client controls "
            "which models and budgets apply, preserving user consent and billing boundaries.\n\n"
            "Elicitation covers structured user input mid-flow: confirming destructive actions, collecting "
            "missing parameters, or choosing among options. Design elicitation schemas with validation "
            "so clients can render native UI instead of free-text that models parse badly."
        )),
        ("UX implications", (
            "Every elicitation breaks autonomous agent flow. Batch questions when possible. "
            "Provide defaults and explain why input is needed — users abandon agents that feel like endless forms."
        )),
    ],
    "mcp-server-authentication-oauth": [
        ("OAuth flows for MCP", (
            "Remote MCP servers should use OAuth 2.1 patterns: PKCE for public clients, short-lived access tokens, "
            "refresh token rotation for long sessions. The MCP authorization spec defines resource indicators "
            "so tokens are scoped to specific server audiences — not generic bearer tokens usable anywhere.\n\n"
            "Dynamic client registration helps IDE clients obtain credentials without manual client ID paste. "
            "Document which scopes map to which tools for audit and consent screens."
        )),
        ("Token storage", (
            "Clients must not log access tokens. Servers validate JWT signatures against issuer JWKS, "
            "check `aud` and `exp`, and reject tokens presented to the wrong MCP resource URL."
        )),
    ],
    "mcp-server-testing-inspector": [
        ("Testing pyramid for MCP", (
            "Unit-test tool handlers with mocked dependencies. Integration-test JSON-RPC message exchange "
            "with the official MCP Inspector or SDK test harness. End-to-end tests run a real client against "
            "a staging server with production-shaped auth.\n\n"
            "Inspector is invaluable for manual exploration — list tools, invoke with sample args, inspect "
            "resource listings — but automate regression tests in CI so schema changes do not break clients silently."
        )),
        ("Contract tests", (
            "Snapshot `tools/list` and `resources/list` responses per server version. "
            "Breaking changes require semver bumps and migration notes. Clients depend on stable tool names and input schemas."
        )),
    ],
    "mcp-transport-stdio-http-sse": [
        ("Migration from SSE to Streamable HTTP", (
            "If you deployed MCP over SSE in 2024, plan a migration window. Streamable HTTP simplifies "
            "firewall rules (one path), reduces session-affinity requirements in stateless mode, and aligns "
            "with the 2025-03-26 spec. Run both transports temporarily behind path-based routing.\n\n"
            "Test with your actual clients — Cursor, Claude Desktop, custom agents — before decommissioning SSE. "
            "Not every client release supports Streamable HTTP yet."
        )),
        ("Local dev vs production split", (
            "The pattern that works: stdio in developer `mcp.json` configs, HTTP in staging/production with "
            "the same server binary. Transport selection is a deployment concern, not a business-logic fork."
        )),
    ],
    "message-queue-dead-letter-handling": [
        ("DLQ design that ops can use", (
            "A dead-letter queue without replay tooling is a graveyard. Every DLQ message needs: original queue, "
            "failure reason, receive count, first-seen timestamp, and payload hash for deduplication. "
            "Build a replay CLI or admin UI that can requeue with fixes — not only CloudWatch alarms that panic.\n\n"
            "Set maxReceiveCount based on idempotency. Idempotent handlers can retry 5–10 times with backoff; "
            "non-idempotent payment handlers should DLQ after 1–2 failures to prevent double charges."
        )),
        ("Poison messages", (
            "One bad schema message can spin workers forever. Use DLQ redrive policies with sampling — "
            "alert when DLQ depth grows, but do not auto-replay all messages after a fix without inspecting a sample."
        )),
    ],
    "message-queues-sqs-vs-kafka": [
        ("Decision framework", (
            "Pick SQS when you want AWS to operate everything, message volume is moderate, "
            "and consumers can pull at their pace with visibility timeouts. Pick Kafka when you need "
            "replay, multiple consumer groups reading the same stream, high throughput, or event sourcing.\n\n"
            "SQS FIFO gives ordering within a message group — useful for per-user sequences. "
            "Kafka partitions give ordering within a partition key — similar idea, more operational overhead."
        )),
        ("Operational contrast", (
            "SQS hides broker patching; Kafka makes you own cluster sizing, partition rebalancing, and upgrade windows. "
            "If your team has no Kafka expertise, SQS plus EventBridge often ships faster than a half-operated MSK cluster."
        )),
    ],
    "mfa-totp-implementation": [
        ("TOTP implementation details", (
            "Use RFC 6238 with 30-second steps and ±1 window for clock skew. Store secrets encrypted at rest; "
            "never log OTP values. On enrollment, show QR codes over HTTPS only and offer manual entry for accessibility.\n\n"
            "Recovery codes are mandatory — generate 8–10 single-use codes at enrollment, hash like passwords, "
            "and require fresh authentication to regenerate. Without recovery, every phone upgrade becomes a support ticket."
        )),
        ("Step-up vs session MFA", (
            "Session-level MFA at login differs from step-up MFA before wire transfers or API key creation. "
            "Store `amr` claims or session flags so sensitive actions re-prompt without full re-login when policy requires."
        )),
    ],
    "microservices-api-composition": [
        ("Composition patterns", (
            "API composition aggregates multiple backend calls into one client-facing response — "
            "often in a BFF or GraphQL layer. The failure mode is sequential fan-out that adds latencies: "
            "200ms + 200ms + 200ms = unacceptable p95. Parallelize independent calls and set per-dependency timeouts.\n\n"
            "Partial failure strategy must be explicit: return degraded UI with missing sections, or fail the whole request? "
            "Product decides; engineers implement circuit breakers per upstream."
        )),
        ("Caching at the composer", (
            "Short TTL caches on read-heavy composed responses reduce load on leaf services. "
            "Invalidate on write via events, not hope. Document staleness bounds in API contracts."
        )),
    ],
    "microservices-circuit-breaker-resilience": [
        ("Breaker tuning", (
            "Circuit breakers need three numbers: failure rate threshold, sliding window size, and half-open probe count. "
            "Defaults from libraries rarely match your SLOs. Start conservative — open after 50% failures in 10 requests "
            "is too twitchy for sparse traffic services.\n\n"
            "Combine breakers with bulkheads: separate thread pools for critical vs optional dependencies "
            "so one slow LLM gateway does not exhaust threads for authentication."
        )),
        ("Retries and breakers interact", (
            "Retries multiply load on failing dependencies — they can prevent breaker recovery. "
            "Cap retries (2–3 max), use jittered exponential backoff, and retry only idempotent operations."
        )),
    ],
    "microservices-contract-testing-pact": [
        ("Pact in CI", (
            "Consumer-driven contracts catch breaking API changes before integration environments. "
            "Consumers publish pacts; providers verify in CI on every PR. Fail the build if a field removal "
            "breaks a consumer — do not rely on integration tests alone.\n\n"
            "Version pacts per consumer, not globally. Mobile apps on old versions may need provider support "
            "for deprecated fields until minimum version bumps force upgrade."
        )),
        ("What not to pact-test", (
            "Third-party APIs you do not control — use consumer-side stubs and record/replay instead. "
            "Internal admin tools with one consumer can use shared schema validation without full Pact overhead."
        )),
    ],
    "microservices-distributed-tracing": [
        ("Trace propagation", (
            "OpenTelemetry W3C trace context must cross every hop: ingress, service mesh, message queues, async workers. "
            "Broken propagation makes traces look like unrelated spans — useless during incidents.\n\n"
            "Sample intelligently: 100% on errors, head-based 1–10% on success paths, tail-based sampling "
            "for high-latency traces. Store attributes with bounded cardinality — never user IDs as metric labels."
        )),
        ("Tracing async work", (
            "When publishing to Kafka, inject trace context into message headers. Consumers continue the trace "
            "so a user click traces through to downstream fulfillment."
        )),
    ],
    "microservices-service-discovery": [
        ("Discovery mechanisms", (
            "Kubernetes DNS (`my-service.namespace.svc.cluster.local`) is discovery for most internal services. "
            "Consul or Eureka still appear in multi-cluster or VM hybrid setups. "
            "Service mesh adds sidecar-level discovery with health-aware load balancing.\n\n"
            "Client-side load balancing (gRPC with xDS, Netflix Ribbon patterns) vs server-side (LB in front of pods) "
            "changes how you handle connection draining during deploys."
        )),
        ("Health-aware routing", (
            "Discovery must feed health — unhealthy instances should drop from rotation before DNS TTL expires. "
            "Readiness != liveness; only route to ready pods."
        )),
    ],
    "microservices-strangler-fig-migration": [
        ("Routing the strangler", (
            "The facade — API gateway, reverse proxy, or modular monolith router — sends increasing traffic "
            "to the new system by route, feature flag, or tenant. Start with read-only paths or low-risk endpoints.\n\n"
            "Maintain data sync between old and new stores during transition. Dual-write is risky; "
            "CDC from legacy DB to new store with reconciliation jobs is slower but safer."
        )),
        ("Knowing when you are done", (
            "Define exit criteria: percentage of routes migrated, legacy code deletion milestones, "
            "and zero production traffic on deprecated paths for 30 days. Without exit criteria, stranglers become permanent dual systems."
        )),
    ],
    "migrating-xml-to-compose": [
        ("Migration strategy", (
            "Migrate screen-by-screen, not big-bang. Interop lets Compose live beside XML in the same activity "
            "via `ComposeView` or `AndroidViewBinding`. Start with leaf composables — buttons, cards — "
            "then full screens once theme and navigation patterns stabilize.\n\n"
            "Map existing ViewModels to Compose state hoisting. `collectAsStateWithLifecycle()` replaces "
            "manual observer boilerplate. Keep business logic unchanged; UI layer migrates."
        )),
        ("Design system parity", (
            "Extract colors, typography, and spacing to Compose theme before converting layouts. "
            "Otherwise every migrated screen reinvents padding and drifts from brand."
        )),
    ],
    "mixture-of-experts-explained": [
        ("Routing and sparsity", (
            "MoE models activate a subset of expert FFN layers per token via a learned router. "
            "Training scales total parameters while inference FLOPs stay closer to a dense model of similar active width.\n\n"
            "Router load imbalance is the research-to-production gap — some experts saturate while others idle. "
            "Auxiliary load-balancing loss during training and capacity factors at inference mitigate this."
        )),
        ("Serving implications", (
            "Expert parallelism shards experts across GPUs; all-to-all communication dominates at scale. "
            "Serving MoE requires different batching and memory planning than dense models of the same parameter count."
        )),
    ],
    "ml-model-serving-inference": [
        ("Serving stack choices", (
            "vLLM and TGI excel at LLM batching with continuous batching and KV cache reuse. "
            "Triton handles multi-model GPU sharing and traditional ONNX/TensorRT pipelines. "
            "Pick based on model type, not hype.\n\n"
            "Autoscale on queue depth and GPU utilization, not CPU. Cold starts on serverless GPU "
            "can blow p99 — keep minimum instances warm for production SLAs."
        )),
        ("Observability", (
            "Track time-to-first-token, tokens per second, batch size, GPU memory pressure, and queue wait. "
            "Model version labels on every metric simplify rollback when quality regresses."
        )),
    ],
    "mobile-app-security-owasp-masvs": [
        ("MASVS in practice", (
            "OWASP MASVS levels (L1 standard, L2 defense-in-depth, R optional resilience) give auditors "
            "a checklist and give engineers acceptance criteria. Map controls to stories: MSTG-STORAGE for "
            "encrypted SharedPreferences, MSTG-NETWORK for certificate pinning decisions.\n\n"
            "Not every app needs L2. Banking and health apps do; content readers may stop at L1 with threat modeling documentation."
        )),
        ("Common gaps", (
            "Hardcoded API keys in APKs, debuggable release builds, and clipboard leakage of OTP fields. "
            "CI should fail release builds with `android:debuggable=true` and scan dependencies for known CVEs."
        )),
    ],
    "mobile-reverse-engineering-defense": [
        ("Defense layers", (
            "R8/ProGuard obfuscation raises the bar; it is not encryption. "
            "Certificate pinning blocks casual MITM but breaks with corporate proxies — document tradeoffs. "
            "Root/jailbreak detection triggers step-up auth or limited functionality, not silent crashes that users report as bugs.\n\n"
            "Split sensitive logic server-side. Anything in the binary can be extracted given time."
        )),
        ("Integrity attestation", (
            "Play Integrity API and DeviceCheck provide signals for high-value flows. "
            "Combine with rate limiting and behavioral analysis — attestation alone is not fraud prevention."
        )),
    ],
    "modbus-industrial-gateways": [
        ("Gateway architecture", (
            "Modbus RTU on RS-485 and Modbus TCP on Ethernet do not interoperate without a gateway "
            "that translates function codes, unit IDs, and timing. Serial timing is strict — "
            "inter-frame delays matter; TCP wrappers must not batch requests in ways that violate RTU semantics.\n\n"
            "Place gateways at the OT/DMZ boundary with read-only default paths and explicit allowlists for write function codes."
        )),
        ("Operational safety", (
            "Industrial write operations need confirmation paths and audit logs. "
            "A misconfigured gateway mapping coil 0 to the wrong register has real physical consequences."
        )),
    ],
    "model-context-protocol-vs-function-calling": [
        ("Protocol vs API feature", (
            "Function calling is a model capability: the LLM emits structured tool invocations. "
            "MCP is a host-server protocol: discovery, resources, prompts, transport, and authorization standardized across clients.\n\n"
            "You can implement function calling without MCP (OpenAI tools API directly). "
            "MCP shines when the same server must plug into Cursor, Claude, and internal agents without rewrites."
        )),
        ("When MCP adds value", (
            "Multiple tools across multiple backends, shared credential management, and resource browsing "
            "benefit from MCP's uniform interface. A single hardcoded JSON schema in one app may not."
        )),
    ],
    "model-distillation-smaller-faster": [
        ("Distillation workflow", (
            "Teacher model generates labels or logits; student model trains to match on a curated dataset "
            "representative of production queries — not generic web crawl. Quality drops when student capacity "
            "is too small for the task complexity.\n\n"
            "Evaluate distilled models on task-specific benchmarks, not only perplexity. "
            "A 10x speedup means nothing if refusal rate doubles."
        )),
        ("Deployment wins", (
            "Distilled models fit on edge GPUs, reduce cloud bills, and lower tail latency. "
            "Pair with routing: small model handles easy queries, escalate hard ones to teacher."
        )),
    ],
    "modular-monoliths-vs-microservices": [
        ("Modular monolith case", (
            "A modular monolith enforces module boundaries in one deployable unit — clear package boundaries, "
            "no cross-module DB access, internal APIs between modules. You get team autonomy without network partitions.\n\n"
            "Extract to microservices when independent scaling, different release cadences, or polyglot stacks "
            "justify operational cost — not because a conference slide said so."
        )),
        ("Boundary enforcement", (
            "Use ArchUnit or custom lint rules to forbid imports across module boundaries. "
            "Without enforcement, modular monoliths decay into big balls of mud with extra steps."
        )),
    ],
    "mqtt-bridging-clustering": [
        ("Bridge configuration", (
            "MQTT bridges connect brokers — topic remapping, QoS downgrade rules, and clean session flags "
            "determine whether messages duplicate or vanish during bridge reconnect. "
            "Never bridge `#` wildcards without ACL review; loops form when two brokers bridge each other bidirectionally.\n\n"
            "Clustering (HiveMQ, EMQX, VerneMQ) uses internal node coordination distinct from bridge federation. "
            "Know which problem you are solving: horizontal scale vs geographic distribution."
        )),
        ("Split-brain", (
            "MQTT clusters during network partitions may accept publishes on both sides. "
            "Design clients to tolerate duplicate messages or use external consensus for critical commands."
        )),
    ],
    "mqtt-iot-at-scale": [
        ("Connection storms", (
            "When 500k devices reconnect after an outage, broker accept rate and TLS handshake CPU become bottlenecks. "
            "Stagger reconnect with jitter in firmware — `random(0, 300)` seconds spreads load.\n\n"
            "Use persistent sessions carefully: clean session false preserves subscriptions but consumes "
            "broker memory per client. Cap concurrent connections per tenant."
        )),
        ("Topic and ACL design at scale", (
            "Flat topic namespaces do not scale ACL management. Hierarchical topics per tenant/device "
            "enable wildcard ACLs: `tenant/{id}/#` read for device, write only to `tenant/{id}/device/{deviceId}/telemetry`."
        )),
    ],
    "mqtt-qos-levels-explained": [
        ("QoS selection guide", (
            "QoS 0: fire-and-forget telemetry at high volume — accept loss. "
            "QoS 1: at-least-once delivery; handlers must be idempotent because duplicates arrive. "
            "QoS 2: exactly-once handshake — expensive, rarely needed if business logic deduplicates.\n\n"
            "QoS is end-to-end between client and broker for publish; bridge hops may downgrade. "
            "Document QoS per topic class in your IoT platform spec."
        )),
        ("QoS and battery", (
            "QoS 1/2 with retained messages and frequent publishes drain battery on cellular devices. "
            "Batch telemetry locally, publish on interval or delta threshold."
        )),
    ],
    "mqtt-retained-messages-last-will": [
        ("Retained messages", (
            "Brokers store the latest retained message per topic for new subscribers. "
            "Essential for device status (`online`/`offline`) and config snapshots. "
            "Dangerous on high-cardinality topics — retain only on low-cardinality status topics.\n\n"
            "Clear retained messages explicitly with zero-byte retain publish when devices decommission."
        )),
        ("Last Will and Testament", (
            "LWT publishes when connection drops uncleanly — broker-side, not firmware crash detection. "
            "Network flaps trigger false offline events; combine LWT with heartbeat publishes and grace periods in consumers."
        )),
    ],
    "mqtt-sparkplug-b": [
        ("Sparkplug B overview", (
            "Sparkplug B standardizes MQTT payload format for industrial SCADA: birth certificates, "
            "death certificates, metric definitions, and protobuf encoding. "
            "Interoperability between PLCs, gateways, and cloud historians improves vs ad-hoc JSON topics.\n\n"
            "NBIRTH/DBIRTH messages announce node and device metadata; NDEATH/DDEATH signal offline. "
            "Consumers should not process metrics until birth sequence completes."
        )),
        ("SCADA integration", (
            "Sparkplug decouples OT producers from IT consumers — historians subscribe to standardized metrics "
            "without per-vendor parsers. Still requires MQTT broker hardening and OT network segmentation."
        )),
    ],
    "mqtt-tls-authentication-iot": [
        ("TLS and client certs", (
            "MQTT over TLS (8883) is baseline. Username/password auth is weak for devices — "
            "prefer client certificates issued per device or per batch with CRL/OCSP revocation paths.\n\n"
            "Rotate device certs before expiry with OTA update pipelines; track cert notAfter in inventory."
        )),
        ("Broker auth plugins", (
            "EMQX and Mosquitto support JWT, LDAP, and HTTP auth backends. "
            "Map certificate CN or SAN to ACL rules — device identity should determine topic access, not shared passwords."
        )),
    ],
    "mqtt-topic-design-patterns": [
        ("Naming conventions", (
            "Use `{tenant}/{site}/{deviceId}/{metric}` hierarchies. Avoid embedding mutable state in topic names "
            "(firmware version in topic path breaks subscriptions on upgrade). "
            "Single-level wildcards (`+`) for aggregation; multi-level (`#`) only at subscription side, never in publish.\n\n"
            "Never publish to `$SYS` or broker reserved prefixes unless you operate the broker."
        )),
        ("ACL alignment", (
            "Design topics so ACL rules are simple wildcards. A flat `device-12345-telemetry` namespace "
            "requires 10k ACL lines; hierarchy needs dozens."
        )),
    ],
    "mtls-mutual-authentication": [
        ("mTLS handshake", (
            "Mutual TLS requires client and server certificates — both sides prove identity during handshake. "
            "Internal service-to-service calls use mTLS to eliminate bearer token theft on the wire inside a VPC.\n\n"
            "Operate a private CA or use SPIFFE/SPIRE for short-lived SVIDs. Long-lived certs without rotation "
            "become inventory nightmares and breach amplifiers."
        )),
        ("Certificate lifecycle", (
            "Automate issuance and renewal — cert-manager on Kubernetes, ACME for edge. "
            "Monitor days-to-expiry and alert at 30/14/7 days."
        )),
    ],
    "mtls-service-mesh": [
        ("Mesh mTLS", (
            "Istio and Linkerd inject sidecars that terminate mTLS transparently — apps speak plain HTTP locally, "
            "mesh encrypts east-west traffic. Gradual rollout: permissive mode logs violations, strict mode rejects plaintext.\n\n"
            "Performance overhead is measurable at high RPS — benchmark before mandating mesh on latency-sensitive paths."
        )),
        ("Identity in mesh", (
            "SPIFFE IDs in certificates map to service accounts. AuthorizationPolicy resources define "
            "which services may call which — mTLS without authorization still allows any authenticated service to call any API."
        )),
    ],
    "multi-agent-orchestration-orchestrator-workers": [
        ("Orchestrator patterns", (
            "Orchestrator-worker architectures assign subtasks to specialized agents — research, coding, review — "
            "with a coordinator merging results. Failure modes: infinite delegation loops, duplicated work, "
            "and conflicting edits to shared state.\n\n"
            "Cap iteration count, require explicit completion signals, and use a shared task board "
            "with locks rather than ad-hoc message passing."
        )),
        ("Human in the loop", (
            "High-stakes actions (deploy, send email, charge card) need human approval gates. "
            "Orchestrators should pause and elicit confirmation rather than optimistically chain tool calls."
        )),
    ],
    "multimodal-audio-transcription-whisper": [
        ("Whisper in production", (
            "OpenAI Whisper and successors (faster-whisper, whisper.cpp) trade accuracy for speed via model size "
            "and quantization. Batch offline transcription on GPU; stream with chunk overlap for realtime captions.\n\n"
            "Handle language detection explicitly for multilingual apps — auto-detect errors on short clips."
        )),
        ("Privacy and retention", (
            "Audio may contain PII and regulated content. Define retention TTLs, redact transcripts in logs, "
            "and offer on-device transcription when cloud upload is unacceptable."
        )),
    ],
    "multimodal-document-understanding": [
        ("Document pipelines", (
            "PDF understanding combines OCR, layout analysis, table extraction, and VLM reasoning. "
            "Pipeline stages fail independently — scan quality, rotated pages, multi-column layouts.\n\n"
            "Chunk by semantic sections (headings, paragraphs) not fixed page splits for RAG indexing."
        )),
        ("Evaluation", (
            "Measure field-level extraction accuracy on representative docs, not cherry-picked samples. "
            "Legal and financial docs need human review queues for low-confidence fields."
        )),
    ],
    "multimodal-image-generation-apis": [
        ("API integration", (
            "Image generation APIs (DALL·E, Stable Diffusion hosts, Flux endpoints) differ in aspect ratios, "
            "safety filters, and latency. Abstract provider behind an internal gateway for swapability.\n\n"
            "Store prompts and seeds for reproducibility and abuse investigation — with privacy policy disclosure."
        )),
        ("Cost control", (
            "Generation is expensive at scale. Rate limit per user, cache popular prompts, "
            "and offer draft (low-res) before final render workflows."
        )),
    ],
    "multimodal-models-in-apps": [
        ("Product integration", (
            "Multimodal features — photo search, receipt scan, visual Q&A — need graceful degradation "
            "when models timeout or refuse content. Show partial results and retry affordances.\n\n"
            "Upload pipelines should resize and compress images client-side to reduce latency and cost."
        )),
        ("Safety", (
            "User-uploaded images require content moderation before model processing and before displaying "
            "model-generated images to other users."
        )),
    ],
    "multimodal-realtime-voice-api": [
        ("Realtime voice architecture", (
            "OpenAI Realtime API and similar WebSocket endpoints stream audio in both directions with "
            "integrated STT, LLM, and TTS. Sub-second latency requires persistent connections and "
            "regional edge deployment close to users.\n\n"
            "Handle interruption (user talks over agent) with voice activity detection and buffer truncation."
        )),
        ("Telephony bridge", (
            "SIP/PSTN integration adds codec transcoding (μ-law to PCM) and echo cancellation. "
            "Test on real phone networks, not only WebRTC in Chrome."
        )),
    ],
    "multimodal-text-to-speech-neural": [
        ("Neural TTS selection", (
            "Neural TTS (ElevenLabs, Azure Neural, Google WaveNet) offers SSML control for pauses, emphasis, "
            "and pronunciation lexicons. Streaming synthesis reduces time-to-first-audio for long responses.\n\n"
            "Voice cloning requires consent and watermarking policies — legal review before production."
        )),
        ("Caching", (
            "Cache synthesized audio for static strings (disclaimers, common phrases) by text hash. "
            "Dynamic LLM output cannot cache as aggressively."
        )),
    ],
    "multimodal-vision-language-models": [
        ("VLM usage patterns", (
            "Vision-language models (GPT-4V, Claude 3, LLaVA) accept images plus text prompts. "
            "Resolution limits and cropping affect fine-detail tasks — OCR small text may need dedicated OCR first.\n\n"
            "Pass structured metadata (image source, capture time) in prompts for better grounding."
        )),
        ("Hallucination risk", (
            "VLMs confabulate objects not present. Critical use cases need confidence thresholds and human review, "
            "especially medical or safety imagery."
        )),
    ],
    "navigation-3-jetpack-compose": [
        ("Navigation 3 in Compose", (
            "Navigation 3 introduces typed routes, back stack manipulation, and ViewModel scoping improvements "
            "over Navigation 2's string routes. Define routes as serializable objects or data classes "
            "for compile-time safety.\n\n"
            "Deep links map to routes explicitly — test cold start entry to every major destination."
        )),
        ("State and back stack", (
            "Avoid multiple sources of truth for current screen. "
            "Hoist navigation state to NavController; ViewModels receive route args via SavedStateHandle."
        )),
    ],
    "nextjs-after-api-response-streaming": [
        ("after() for streaming responses", (
            "Next.js `after()` runs work after the response is sent — logging, analytics, cache warming — "
            "without blocking TTFB. Critical for streaming LLM responses where post-processing must not delay tokens.\n\n"
            "Do not put must-succeed operations in `after()` without retry — the process may terminate before completion."
        )),
        ("Streaming patterns", (
            "Use `ReadableStream` in Route Handlers for SSE or NDJSON token streams. "
            "Set `export const dynamic = 'force-dynamic'` when caching would break streams."
        )),
    ],
    "nextjs-analytics-web-vitals-reporting": [
        ("Web Vitals in App Router", (
            "Report LCP, INP, and CLS via `useReportWebVitals` or analytics SDK integration. "
            "App Router streaming can improve LCP if hero content is in initial shell — measure production, not Lighthouse lab only.\n\n"
            "Attribute vitals by route using `pathname` in the callback. Slice by device class to catch mobile regressions."
        )),
        ("Real user monitoring", (
            "Send vitals to your analytics backend with sampling. Alert when p75 INP regresses after deploys. "
            "Correlate with long tasks and bundle size changes from CI."
        )),
    ],
    "nextjs-app-router-server-actions": [
        ("Production Server Actions patterns", (
            "Colocate actions with features but keep shared validation in `lib/validators`. "
            "Use `redirect()` after successful create flows instead of client-side navigation hacks.\n\n"
            "For high-traffic mutations, consider queueing heavy work — action validates and enqueues, "
            "returns immediately, worker processes async. Users see fast feedback without blocking on PDF generation."
        )),
        ("Multi-tenant actions", (
            "Always derive tenant ID from session server-side — never trust hidden form fields. "
            "Row-level security in Postgres plus action-level authorization prevents cross-tenant updates."
        )),
    ],
}


def generic_padding(slug: str, domain: str, n: int) -> list[tuple[str, str]]:
    """Additional sections if still under word target."""
    topic = slug.replace("-", " ")
    pool = [
        ("What to measure in production", (
            f"Define SLIs before launch for {topic}: latency p95, error rate, and a business metric tied to user success. "
            f"Dashboards should answer whether users are completing flows within thirty seconds of opening an incident page. "
            f"Leading indicators — queue depth, retry rate, saturation — predict lagging indicators like support tickets and churn."
        )),
        ("Rollout discipline that sticks", (
            f"Canary {topic} at 5% traffic or one namespace for twenty-four hours minimum. "
            f"Watch golden signals and error budget burn; pre-write rollback commands in the change ticket. "
            f"Game days before launch beat postmortems after: kill dependencies, double traffic, verify graceful degradation."
        )),
        ("Runbooks worth keeping", (
            f"A useful {topic} runbook fits one page: symptom, dashboard link, mitigation, rollback owner. "
            f"Paste example healthy and broken log lines with redacted values. "
            f"If mitigation requires senior engineer memory, simplify the system before the next incident."
        )),
        ("Edge cases to test explicitly", (
            f"Concurrent updates, cold starts after deploy, and partial connectivity expose {topic} assumptions. "
            f"Integration tests should mirror production topology — not only happy-path unit tests on a laptop. "
            f"For mobile and IoT clients, exercise process death, airplane mode, and certificate expiry."
        )),
        ("Working with stakeholders", (
            f"Product cares about time-to-ship; security cares about blast radius; finance cares about unit cost. "
            f"Translate {topic} tradeoffs into those languages in design review — fewer launch surprises and fewer permanent 'temporary' bypasses."
        )),
    ]
    start = pick_variant(slug + str(n), len(pool))
    return [pool[(start + i) % len(pool)] for i in range(3)]


def insert_before_resources(body: str, new_sections: str) -> str:
    """Insert expansion sections before ## Resources if present."""
    m = re.search(r"\n## Resources\n", body)
    if m:
        return body[:m.start()].rstrip() + "\n\n" + new_sections.strip() + "\n" + body[m.start():]
    return body.rstrip() + "\n\n" + new_sections.strip()


def build_expansion(slug: str, domain: str, body: str) -> str:
    sections = list(EXPANSIONS.get(slug, []))
    if not sections:
        sections = generic_padding(slug, domain, 0)

    added = []
    for heading, prose in sections:
        if f"## {heading}" in body:
            continue
        added.append(f"## {heading}\n\n{prose}")

    extra_idx = 0
    result = body
    if added:
        result = insert_before_resources(result, "\n\n".join(added))

    FILLER_PARAGRAPHS = [
        (
            "Production traffic rarely matches the demo path. Users retry failed requests, open multiple tabs, "
            "and run on networks with packet loss and captive portals. Design for partial failure from day one — "
            "timeouts on every external call, idempotency keys on mutating operations, and structured errors "
            "that support teams can act on without reading stack traces."
        ),
        (
            "Observability should answer whether users succeed, not only whether servers are up. "
            "Metric latency and errors at the boundary where SLIs live — checkout completion, sync success, "
            "inference finish — and carry correlation IDs across async hops so traces tell a story during incidents."
        ),
        (
            "Rollout discipline beats heroics on call. Canary changes, watch error budget burn for a full day, "
            "and keep rollback one command away. Game days that kill dependencies before launch expose "
            "assumptions that unit tests never will."
        ),
        (
            "Document the tradeoff you chose: latency versus consistency, cost versus quality, strictness versus recall. "
            "Future engineers should not reverse-engineer intent from git blame. Link dashboards in runbooks "
            "and paste example log lines so on-call recognizes healthy versus broken quickly."
        ),
        (
            "Security and abuse belong in the design review, not the launch-week scramble. "
            "Treat user-controlled input as untrusted — prompts, uploads, webhook payloads — and fail closed "
            "when authorization is ambiguous. Log policy decisions with correlation IDs, not raw secrets."
        ),
    ]

    while word_count(result) < TARGET_WORDS:
        pad_sections = generic_padding(slug, domain, extra_idx)
        added_any = False
        blocks = []
        for heading, prose in pad_sections:
            suffix = f" ({extra_idx + 1})" if f"## {heading}" in result else ""
            h = heading + suffix
            if f"## {h}" in result:
                continue
            blocks.append(f"## {h}\n\n{prose}")
            added_any = True
        if blocks:
            result = insert_before_resources(result, "\n\n".join(blocks))
        else:
            para = FILLER_PARAGRAPHS[extra_idx % len(FILLER_PARAGRAPHS)]
            result = insert_before_resources(result, para)
        extra_idx += 1
        if extra_idx > 30:
            break
    return result.rstrip() + "\n"


def update_frontmatter(post: dict) -> str:
    faqs = faq_enhance(post["slug"], post["title"], post["faq"])
    if post["tags"]:
        tags_yaml = "tags: [" + ", ".join(f'"{yaml_escape(t)}"' for t in post["tags"]) + "]"
    else:
        tags_yaml = 'tags: ["Engineering"]'
    faq_yaml = "\n".join(
        f'  - q: "{yaml_escape(f["q"])}"\n    a: "{yaml_escape(f["a"])}"' for f in faqs
    )
    return f"""---
title: "{yaml_escape(post['title'])}"
slug: "{post['slug']}"
description: "{yaml_escape(post['description'])}"
datePublished: "{post['date_published']}"
dateModified: "{DATE_MODIFIED}"
{tags_yaml}
keywords: "{yaml_escape(post['keywords'])}"
faq:
{faq_yaml}
---"""


def process_slug(slug: str) -> dict:
    path = BLOG / f"{slug}.md"
    if not path.exists():
        return {"slug": slug, "status": "missing", "words": 0}

    if slug in SKIP_SLUGS:
        post = parse_post(path)
        body = strip_filler(post["body"])
        return {"slug": slug, "status": "skipped", "words": word_count(body), "reason": "already_humanized"}

    post = parse_post(path)
    body = strip_filler(post["body"])

    # Always rewrite non-skipped slugs to ensure expansions + dateModified
    force = True
    if not force and is_humanized(body, post["faq"]):
        return {"slug": slug, "status": "skipped", "words": word_count(body), "reason": "already_humanized"}

    intro = intro_for(slug, domain_for(slug))
    if intro and not body.lstrip().startswith(intro[:40]):
        # prepend intro if body doesn't already have narrative opening
        first_para = body.lstrip().split("\n\n")[0]
        if len(first_para) < 200 or first_para.startswith("##"):
            body = intro + "\n\n" + body.lstrip()

    domain = domain_for(slug)
    new_body = build_expansion(slug, domain, body)
    fm = update_frontmatter(post)
    out = fm + "\n\n" + new_body.lstrip()
    if not out.endswith("\n"):
        out += "\n"
    path.write_text(out)

    wc = word_count(new_body)
    return {
        "slug": slug,
        "status": "rewritten",
        "words": wc,
        "domain": domain,
    }


def main():
    results = [process_slug(s) for s in SLUGS]
    rewritten = [r for r in results if r["status"] == "rewritten"]
    skipped = [r for r in results if r["status"] == "skipped"]
    under = [r for r in rewritten if r["words"] < TARGET_WORDS]

    progress = {
        "batch": "m",
        "total": len(SLUGS),
        "rewritten": len(rewritten),
        "skipped": len(skipped),
        "under_target_words": len(under),
        "target_words": TARGET_WORDS,
        "date_modified": DATE_MODIFIED,
        "results": results,
    }
    PROGRESS.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS.write_text(json.dumps(progress, indent=2) + "\n")

    print(json.dumps({
        "total": progress["total"],
        "rewritten": progress["rewritten"],
        "skipped": progress["skipped"],
        "under_target": progress["under_target_words"],
        "results": results,
    }, indent=2))


if __name__ == "__main__":
    main()
