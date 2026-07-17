#!/usr/bin/env python3
"""Generate unique deep-dive rewrites for remaining batch-01 template posts.
Each article uses topic-specific sections/FAQs — not a shared boilerplate template.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLOG = ROOT / "content/blog"
PROGRESS = ROOT / "scripts/humanize-progress/batch-01.json"

ALREADY_REWRITTEN = {
    "agent-session-fixation-prevention",
    "agent-settlement-cutoff-windows",
    "agent-short-lived-credentials-rotation",
    "agent-sidecar-resource-overhead",
    "agent-slot-filling-dialogue",
    "agent-slowly-changing-dimensions",
    "agent-sparse-dense-hybrid",
    "agent-speculation-rules-prerender",
    "agent-spiffe-spire-identity",
    "agent-spot-instance-interruption-handling",
    "agent-sso-saml-metadata-rotation",
    "agent-star-schema-normalization",
}


def words(text: str) -> int:
    return len(re.findall(r"\w+", text))


def titleize(slug: str) -> str:
    s = slug
    for p in ("agent-", "android-", "llm-", "rag-"):
        if s.startswith(p):
            s = s[len(p) :]
            break
    return s.replace("-", " ").title()


# Topic-specific content packs: unique FAQs, hooks, sections, code, resources
PACKS: dict[str, dict] = {}


def pack(
    slug: str,
    *,
    title: str,
    desc: str,
    tags: list[str],
    keywords: str,
    faq: list[tuple[str, str]],
    hook: str,
    sections: list[tuple[str, str]],
    resources: list[tuple[str, str]],
    pub: str = "2025-06-15",
):
    PACKS[slug] = {
        "title": title,
        "desc": desc,
        "tags": tags,
        "keywords": keywords,
        "faq": faq,
        "hook": hook,
        "sections": sections,
        "resources": resources,
        "pub": pub,
    }


# --- Define all remaining packs (unique structures) ---

pack(
    "agent-state-store-rocksdb",
    title="RocksDB State Stores for Agent Stream Processors",
    desc="Use RocksDB as local state for agent stream jobs: keyed session state, changelog recovery, TTL, and when to prefer remote Redis over embedded RocksDB.",
    tags=["AI Agents", "Streaming", "Infrastructure", "Backend"],
    keywords="RocksDB state store agents, Flink RocksDB agent state, Kafka Streams state store",
    faq=[
        (
            "Why use RocksDB for agent stream state?",
            "RocksDB gives stream processors durable keyed state on local disk with changelog recovery. Agent jobs that maintain per-session counters or watermarked aggregates can keep large state without fitting in heap.",
        ),
        (
            "RocksDB vs Redis for agent session state?",
            "RocksDB shines inside stream jobs with exactly-once changelog semantics. Redis fits low-latency orchestrators needing shared state across replicas. RocksDB is embedded per task — not a remote shared DB.",
        ),
        (
            "How do you bound RocksDB growth?",
            "Set state TTL on session keys, cap list lengths, store pointers to object storage instead of transcripts, and monitor SST size plus changelog lag.",
        ),
        (
            "What breaks on task migration?",
            "State restores from changelog; large state means long recovery. Keep state lean, enable incremental checkpoints, and size timeouts for millions of session keys.",
        ),
    ],
    hook="Agent stream jobs that count tool failures per tenant or maintain sliding-window toxicity scores need keyed state. Heap maps die at scale; remote Redis adds a network hop on every record. Embedded RocksDB state stores put durable state on local SSD next to the operator, with Kafka changelogs for recovery.",
    sections=[
        (
            "Where RocksDB sits",
            """```
Kafka topic → stream operator
                 ├─ local RocksDB (keyed state)
                 └─ changelog topic (durability)
```

On failure, a new task restores from checkpoint + changelog, not from empty memory. That model matches agent metering and feature-generation topologies better than ad-hoc cache writes.""",
        ),
        (
            "State types agents actually need",
            """| State | Example | Notes |
|-------|---------|-------|
| ValueState | last intent per session | TTL 24h |
| ListState | last 20 tool names | Cap length |
| MapState | per-tool error counts | Periodic emit |
| Window state | 5-min usage | Allowed lateness |

Do not store full prompt text in RocksDB — cardinality and PII explode. Store hashes or object-storage URIs when audit needs content.""",
        ),
        (
            "Flink TTL configuration",
            """```java
ValueStateDescriptor<SessionFeatures> desc =
  new ValueStateDescriptor<>("sess", SessionFeatures.class);
desc.enableTimeToLive(StateTtlConfig.newBuilder(Time.hours(24))
  .setUpdateType(StateTtlConfig.UpdateType.OnCreateAndWrite)
  .build());
```

TTL is mandatory for session-keyed agent state. Without it, abandoned chats become immortal keys.""",
        ),
        (
            "Operational knobs",
            """Enable managed memory for RocksDB, size block cache vs write buffer from metrics, turn incremental checkpoints on, and place RocksDB on NVMe — network disks add latency that shows up as checkpoint backpressure. Watch checkpoint duration, state size, and catch-up lag after restart.""",
        ),
        (
            "When Redis wins instead",
            """Online orchestrators needing `GET session:{id}` from any replica should use Redis. RocksDB state is local to a stream task. Hybrid works well: stream job with RocksDB computes features, writes to a feature store, online agent reads the store.""",
        ),
        (
            "Anti-patterns",
            """Putting RocksDB on undersized EBS without IOPS headroom; a single global key for all tenants; disabling changelogs in prod; storing embeddings as values. Also avoid treating RocksDB as a debugging scratchpad — anything you put there must be reconstructable from the changelog or you will lose it on rescale.""",
        ),
    ],
    resources=[
        ("Flink RocksDB state backend", "https://nightlies.apache.org/flink/flink-docs-stable/docs/ops/state/state_backends/"),
        ("Kafka Streams memory management", "https://kafka.apache.org/documentation/streams/"),
        ("RocksDB tuning guide", "https://github.com/facebook/rocksdb/wiki/RocksDB-Tuning-Guide"),
    ],
    pub="2025-07-09",
)

pack(
    "agent-status-page-communication",
    title="Status Page Communication During Agent Outages",
    desc="Write status page updates that help customers during agent outages: component taxonomy, incident phases, avoiding empty 'investigating' posts, and linking impact to chat vs admin vs APIs.",
    tags=["AI Agents", "SRE", "Communications", "Operations"],
    keywords="status page agent outage, incident communication LLM, statuspage components agents",
    faq=[
        (
            "What components should an agent status page list?",
            "Split user-visible surfaces: Chat/Completions API, Tool execution, Retrieval/RAG, Admin dashboard, SSO/Login, Billing webhooks. A single 'API' blob forces customers to guess whether their chat outage matches your incident.",
        ),
        (
            "How often should you update during an agent incident?",
            "Every 20–30 minutes while investigating, immediately on impact change, and when mitigated. Empty 'still investigating' updates without new facts train customers to ignore you — add what you ruled out and current workaround.",
        ),
        (
            "Should you mention model provider outages?",
            "Yes when material, without blaming theater. 'Elevated errors from upstream model provider; failing over to backup model' is better than silence or vague 'degraded performance.' Customers correlate with Downdetector anyway.",
        ),
        (
            "What belongs in a postmortem vs status page?",
            "Status page: impact, ETA/workaround, resolve time. Postmortem: root cause, timeline, action items. Do not dump internal Slack speculation onto the public page.",
        ),
    ],
    hook="When the agent returns 503s, customers open two tabs: your chat UI and status.example.com. If the status page still says 'All Systems Operational' while Twitter fills with screenshots, you have a communications failure layered on an engineering one. Agent platforms need componentized status pages and disciplined incident writing.",
    sections=[
        (
            "Component taxonomy that matches user mental models",
            """Map infrastructure to what customers experience. Orchestrator pods dying is not a component name — 'Agent chat responses' is. Keep the list short (5–8). Include a separate component for 'Enterprise SSO' because login outages look like total product death even when APIs are fine.""",
        ),
        (
            "Incident phase language",
            """Use a consistent ladder: Investigating → Identified → Monitoring → Resolved. For each update include: impact (which component, error rates/%), scope (regions/tenants if known), workaround, next update time. Example: 'Chat completions elevated 5xx (~18% of requests) in us-east since 14:12 UTC. Tool execution unaffected. Workaround: retry; we are failing over model routing. Next update by 14:45 UTC.'""",
        ),
        (
            "Avoiding harmful vagueness",
            """Banned phrases without facts: 'some users may be affected,' 'intermittent issues,' 'slowness.' Prefer measured impact from your SLOs. If you lack numbers yet, say what you're measuring and what you already ruled out ('Not a scheduled deploy; auth path healthy').""",
        ),
        (
            "Automation and authenticity",
            """Auto-open incidents from SLO burn — but require a human to publish the first customer-facing sentence within 5 minutes. Pure machine status pages feel abandoned. Subscribe hooks: Slack #incidents → Statuspage API with templated fields your IC fills.""",
        ),
        (
            "Maintenance vs incident",
            """Schedule maintenance for model migrations and index rebuilds with 48h notice when possible. Never relabel an ongoing outage as maintenance. Agent eval downtime can be maintenance; chat 500s cannot.""",
        ),
        (
            "After resolve",
            """Post a short resolve note with duration and impact summary. Link to public postmortem if you write one (or 'detailed follow-up within 72h'). Update components to Operational deliberately — flapping green/red destroys trust.""",
        ),
    ],
    resources=[
        ("Atlassian Statuspage best practices", "https://www.atlassian.com/software/statuspage"),
        ("Google SRE — managing incidents", "https://sre.google/sre-book/managing-incidents/"),
        ("Incident response guides (PagerDuty)", "https://response.pagerduty.com/"),
    ],
    pub="2025-04-18",
)

print(f"packs so far: {len(PACKS)}")
