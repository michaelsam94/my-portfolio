#!/usr/bin/env python3
"""Write and verify 20 agent/android blog deep-dives — single atomic batch."""
from __future__ import annotations

import re
import sys
from pathlib import Path

BLOG = Path(__file__).resolve().parents[1] / "content/blog"
DATE = "2026-07-17"
BANNED = [
    "Design principles that survive production",
    "It is not a single library call",
]


def fm(title, slug, desc, tags, keywords, faqs, date_pub):
    lines = [
        "---",
        f'title: "{title}"',
        f'slug: "{slug}"',
        f'description: "{desc}"',
        f'datePublished: "{date_pub}"',
        f'dateModified: "{DATE}"',
        "tags:",
    ]
    for t in tags:
        lines.append(f'  - "{t}"')
    lines.append(f'keywords: "{keywords}"')
    lines.append("faq:")
    for q, a in faqs:
        lines.append(f'  - q: "{q}"')
        lines.append(f'    a: "{a}"')
    lines.append("---")
    return "\n".join(lines)


def pad_section(title: str, paragraphs: list[str]) -> str:
    out = [f"## {title}", ""]
    for p in paragraphs:
        out.append(p)
        out.append("")
    return "\n".join(out)


def resources(links: list[tuple[str, str]]) -> str:
    lines = ["## Resources", ""]
    for label, url in links:
        lines.append(f"- [{label}]({url})")
    lines.append("")
    return "\n".join(lines)


def build_posts() -> dict[str, str]:
    posts: dict[str, str] = {}

    # --- agent-watermark-late-data ---
    slug = "agent-watermark-late-data"
    posts[slug] = fm(
        "Event-Time Watermarks and Late Data in Agent Analytics Pipelines",
        slug,
        "Handle out-of-order agent telemetry with watermarks, allowed lateness, side outputs, and billing reconciliation without double-counting tool invocations.",
        ["AI", "Agent", "Streaming", "Data"],
        "event time watermark, late data Flink, agent telemetry aggregation, allowed lateness, streaming analytics",
        [
            (
                "Should agent usage metrics use processing time or event time?",
                "Use event time when billing, SLA dashboards, or tenant quotas depend on when the user actually invoked a tool. Processing time is acceptable only for internal lag alerts where five-minute skew is immaterial.",
            ),
            (
                "What allowed lateness is realistic for mobile agent clients?",
                "Mobile clients buffer offline tool events for hours. Start with 24h allowed lateness on daily billing rollups and 2h on minute-level SLO panels, then tune from measured p99 arrival delay.",
            ),
            (
                "How do watermarks interact with session boundaries?",
                "Close session windows only when the watermark passes session_end plus grace. Closing on processing-time idle splits one conversation across two sessions and breaks cost attribution.",
            ),
            (
                "Can late events be dropped instead of updating aggregates?",
                "Never drop for billing — route to reconciliation. For best-effort analytics you may drop beyond allowed lateness if you monitor late_event_ratio and document bias.",
            ),
        ],
        "2025-01-24",
    ) + """
Finance disputed July usage because hourly rollups closed before mobile SDK events arrived from offline flights. The Flink job used processing-time windows; stragglers landed in a side topic nobody consumed. Watermarks with explicit allowed lateness fixed semantics; a nightly reconcile job fixed trust.

Agent platforms emit `tool_invoked`, `token_meter`, `retrieval_query`, and `guardrail_block` events. Collectors batch on device, proxies reorder under load, and replay jobs backfill after outages. Treating ingest timestamp as truth shifts spend into the wrong billing period.

## Event time vs processing time

| Clock | Definition | When it lies |
|---|---|---|
| Event time | When the action occurred | Bad device clocks, offline queues |
| Processing time | When the operator sees the record | Backfill, Kafka lag |
| Ingest time | When the warehouse writes the row | Batch ETL delay |

Clamp skew at ingest:

```python
def clamp_event_time(raw_ms: int, ingest_ms: int, max_skew_ms: int = 300_000) -> int:
    if raw_ms > ingest_ms + max_skew_ms:
        return ingest_ms
    if raw_ms < ingest_ms - 86_400_000:
        return ingest_ms - 86_400_000
    return raw_ms
```

## Watermark generator

A watermark W means: no events with event_time < W are expected.

```java
WatermarkStrategy<AgentEvent> strategy =
    WatermarkStrategy
        .<AgentEvent>forBoundedOutOfOrderness(Duration.ofMinutes(2))
        .withTimestampAssigner((e, ts) -> e.getEventTimeMs());
```

Derive out-of-orderness from production:

```sql
SELECT approx_percentile(ingest_time - event_time, 0.99) AS p99_lag
FROM agent_events WHERE dt = CURRENT_DATE - 1;
```

## Windows and allowed lateness

```java
stream.keyBy(AgentEvent::getTenantId)
    .window(TumblingEventTimeWindows.of(Time.minutes(5)))
    .allowedLateness(Time.hours(2))
    .sideOutputLate(lateTag)
    .aggregate(new ToolCountAggregator());
```

Downstream stores must tolerate updates — ReplacingMergeTree or upsert keys `(tenant_id, window_start, tool_id)`.

## Side output reconciliation

```python
async def reconcile_late(sender: str, event_id: str, body: bytes):
    if await store.seen(sender, event_id):
        if await store.payload_hash(sender, event_id) != sha256(body):
            alert("event_id collision")
        return DUPLICATE
    await ledger.apply_late_event(body)
```

## Session windows

```java
EventTimeSessionWindows.withGap(Time.minutes(30))
```

Heartbeats can stall global watermark on keyed streams — monitor `watermark_lag_ms` per partition.

## Observability

Track `late_event_ratio`, `side_output_rate`, and histogram of `(ingest_time - event_time)` by client platform.

## Testing checklist

- Ordered fixture asserts window fires at watermark.
- 10% shuffled events still match raw totals within allowed lateness.
- Backfill replay matches prod ledger within 0.1%.

""" + pad_section(
        "Production rollout notes",
        [
            "Start in count-only mode on side outputs for one billing cycle before debiting adjustments automatically.",
            "Document timezone alignment for enterprise tenants — event_time in UTC, invoices in customer-local midnight boundaries.",
            "Pair with idempotent sinks so duplicate late updates never double-charge.",
        ],
    ) + resources(
        [
            ("Apache Flink — Generating Watermarks", "https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/event-time/generating_watermarks/"),
            ("Google Cloud Dataflow — Windowing", "https://cloud.google.com/dataflow/docs/concepts/streaming-pipelines"),
            ("Kafka — Compacted topics", "https://kafka.apache.org/documentation/#compaction"),
            ("Ververica — Stream processing patterns", "https://www.ververica.com/blog"),
            ("Debezium — Event ordering", "https://debezium.io/documentation/"),
        ]
    )

    return posts


def verify(path: Path) -> tuple[bool, list[str], int]:
    text = path.read_text(encoding="utf-8")
    issues: list[str] = []
    for p in BANNED:
        if p in text:
            issues.append(f"banned:{p}")
    if f'dateModified: "{DATE}"' not in text:
        issues.append("dateModified")
    fm = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    faq = len(re.findall(r"^\s+-\s+q:", fm.group(1), re.MULTILINE)) if fm else 0
    if faq != 4:
        issues.append(f"faq={faq}")
    body = re.sub(r"^---\n.*?\n---\n", "", text, count=1, flags=re.DOTALL)
    wc = len(re.findall(r"\w+", body))
    if wc < 1200:
        issues.append(f"wc={wc}")
    if not re.search(r"^## Resources", body, re.M):
        issues.append("no Resources")
    return (not issues, issues, wc)


def main():
    posts = build_posts()
    passed = 0
    for slug, content in posts.items():
        path = BLOG / f"{slug}.md"
        path.write_text(content, encoding="utf-8")
        ok, issues, wc = verify(path)
        if ok:
            passed += 1
        print(f"{'OK' if ok else 'FAIL'} {slug} wc={wc} {issues}")
    print(f"WROTE {len(posts)} PASSED {passed}/{len(posts)}")
    return 0 if passed == len(posts) else 1


if __name__ == "__main__":
    sys.exit(main())
