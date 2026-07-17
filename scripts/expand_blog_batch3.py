#!/usr/bin/env python3
from pathlib import Path

EXPANSIONS = {
"agent-state-store-rocksdb": """
## Backup encryption and key rotation

Checkpoint uploads to S3 should use SSE-KMS with per-tenant context keys where compliance requires — bucket policy denies unencrypted PutObject. Rotate KMS keys annually; old checkpoints remain decryptable with grant. Never store RocksDB OPTIONS file with paths leaking hostnames in shared bucket — sanitize manifest.

## Multi-tenant isolation on shared host

If one pod serves multiple tenants via shard key, separate RocksDB column family prefix or instance per tenant for noisy neighbor isolation — compaction on tenant A shouldn't stall tenant B. Cap disk per tenant; evict LRU session keys when quota hit.

## Read-only followers

RocksDB doesn't natively replicate — for read scaling use event stream projector to read replicas opening read-only DB snapshots refreshed every N minutes — accept staleness for analytics queries, not for live session head.

## Compaction priority during incidents

Manual `CompactRange` on idempotency CF during incident recovery after bulk session purge — runbook step before declaring all-clear. Measure `rocksdb.pending-compaction-bytes` pre/post.

## Migration from Redis

Dual-write phase: write both Redis and RocksDB; read Redis with fallback RocksDB; compare hashes in shadow mode. Cut read to RocksDB; remove Redis after 72h clean metrics.
""",
"agent-status-page-communication": """
## Stakeholder pre-write approval matrix

| Severity | Approver before post |
| --- | --- |
| Sev1 customer impact | IC + comms lead |
| Sev2 partial | IC |
| Internal-only component | On-call |

Pre-approved template blocks for retrieval vs inference vs billing reduce 2am cognitive load — but IC must fill scope fields, not empty merge.

## Social media coordination

Twitter status separate from formal status page — assign social comms to avoid contradictory messages. Agent incidents attract AI hype tweets — stick to facts, link status page.

## Postmortem customer summary

Within 5 days publish customer-safe summary: duration, impact percentage, remediations without blame. Link from resolved status incident — SEO picks up stale "major outage" if not updated.

## SLA credit automation edge cases

Credits apply to subscription component only — metered overage credits separate policy. Enterprise custom SLA JSON overrides default thresholds — status system reads contract table before auto-credit flag.
""",
"agent-tls-certificate-pinning-mobile": """
## Certificate transparency monitoring

Complement pinning with CT log alerts for unauthorized certs issued for your API domain — catches misissue before users update pins. Doesn't replace pinning but adds early warning for rotation planning.

## Pin rotation in app release train

Coordinate backend cert renewals with mobile release cadence — if emergency cert compromise requires new pin without backup pre-shipped, use remote config `allowed_pins` array updatable OTA while App Store review pending hotfix.

## mTLS plus pinning

Enterprise agents using client certs still pin server SPKI — mutual TLS doesn't remove server authentication need on untrusted networks.

## Debug builds

Disable pinning only in debuggable builds with manifest flag — CI ensures release builds never ship with `PINNING_DISABLED`. Pen test tries to bypass via re-signed debug APK sideload.
""",
"agent-toil-reduction-automation": """
## Runbook as code reviews

Quarterly diff runbooks against actual automation — stale runbook step "run SQL manually" when janitor exists trains new hires wrong. Delete or update within same PR as automation merge.

## Ownership rotation

Each automation has named owner in CODEOWNERS — orphaned cron becomes alert when owner team disbanded. Deprecation date on temporary scripts.

## Measuring toil reduction ROI

Track hours logged in ticket category "manual ops" quarter over quarter — target 20% reduction after janitor + self-service ship. If flat, automation unused or new toil added faster.

## Safe defaults on self-service

Quota bump capped at 20% without manager approval in workflow tool — prevents support accidentally doubling tenant cost unbounded.
""",
"agent-token-budget-compression": """
## Placement of compressed state in context

Put `COMPRESSED_STATE` after system policy but before recent raw turns — "lost in the middle" research suggests models attend to start and end. Keep last 2 raw turns verbatim for conversational coherence.

## Tool-specific compression profiles

SQL results compress to row count + sample 5 rows; JSON API compress to schema outline; markdown docs compress to outline headings only. Profile table in config YAML versioned.

## User-visible compression notice

Optional subtle UI "Earlier context summarized" when compression ran — transparency without alarming. Enterprise may disable notice per contract.

## Token counting on multimodal

Image tokens in GPT-4V count separately — compression budget subtracts image tokens first; don't truncate text while leaving huge images.

## A/B test compression aggressiveness

Experiment 70% vs 80% trigger on task success metric — roll back if human escalation rate rises.
""",
"agent-tokenization-payment-vault": """
## Network token lifecycle webhooks

Listen for `payment_method.automatically_updated` when network token refreshes — agent saved-card tool uses latest payment_method_id without user re-entry.

## 3DS and agent-initiated charges

Off-session charges may require SCA — agent tool returns `requires_action` with hosted authentication URL, not retry loop. Step-up auth article pairs here.

## PCI log scanning in CI

TruffleHog or custom Luhn scan on test log fixtures — fail build if sample PAN appears in golden logs.

## Vault per environment

Separate Stripe accounts test/prod — never test tokens in prod agent dev tools; misconfigured API key charges real cards in staging disaster.
""",
"agent-toxicity-classifier-threshold": """
## Locale-specific models

Deploy `classifier-de` for German support queue — English classifier misses compound insults. Routing by `Accept-Language` and conversation locale.

## Appeal workflow

Users appeal false block — queue shows scores + model version for reviewer. Overturn feeds training data with label `false_positive`.

## Red team cadence

Monthly red team prompts attempt to elicit policy violations — measure bypass rate; tune thresholds if bypass rises without raising false positives on golden set.

## Streaming partial output

Block stream on first high-confidence severe category chunk — don't wait for full completion. Buffer first 200 tokens max for classification latency tradeoff.
""",
"agent-translation-memory-cat-tools": """
## TM sync conflict resolution

Linguist edits TM in Phrase while agent ingest adds machine segments — last-write-wins loses work. Lock TM segments under human review; agent queue waits.

## Plural and gender in TM

Languages with plural forms need ICU plural keys in TM lookup — single English "item" maps to plural rules in Slavic languages. TM without plural metadata causes wrong variant selection.

## Offline TM cache

Mobile agent app caches TM subset for offline suggest — sync delta on reconnect. Version header on cache invalidates on TM export bump.

## Quality estimation before auto-apply

MT confidence + TM fuzzy score combined — auto-apply only if TM≥95 OR (TM≥85 AND MT QE≥0.9).
""",
"agent-two-tower-retrieval": """
## Hard negative mining pipeline

Nightly job: top 50 BM25 misses for clicked queries become hard negatives in training JSONL. Cap per query to avoid dominance by head queries.

## Distillation for latency

Teacher cross-encoder reranker labels soft scores; student dual encoder trained to mimic — improves recall without online cross-encoder cost.

## Cold start new documents

New docs without clicks: bootstrap with title BM25 only until min 10 impressions before entering training pairs — avoid noise from low-traffic PDFs.

## ANN index warm on deploy

Pre-warm HNSW with representative query set after index swap — first user queries shouldn't pay cold graph traversal latency spike.
""",
"agent-usage-metering-aggregation": """
## Clock skew in hourly buckets

Events with `event_time` 23:59:59 and processing 00:00:01 land in different billing hours — use consistent bucketing function documented in API. UTC vs tenant timezone for invoice display separate from aggregation bucket.

## Partial failure in exporter

Stripe usage record API 500 — retry with exponential backoff; dead letter queue for manual finance reconciliation. Never double-submit without idempotency key on exporter.

## Real-time dashboard vs billing truth

Dashboard may show 5m delayed stream; invoice uses hourly rollup — footnote on dashboard "subject to final reconciliation."

## Negative adjustments

Credits and refunds emit negative quantity events — aggregation sum handles signed integers; validate no integer overflow on large tenants in load test.
""",
"agent-vector-index-rebuild": """
## Parallel embed workers

Shard corpus by hash mod N workers — coordinate completion barrier before index load. Failed shard blocks cutover — partial index worse than delayed launch.

## Memory sizing for HNSW build

Build phase RAM spikes — scale index builder node vertically for rebuild window only. Cloud cost trade vs longer build on small node.

## User-facing reindex banner

Show "search quality updating" banner during dual-query period if slight recall variance acceptable — support macro explains temporary odd results.

## Post-cutover monitoring

Compare `rag_empty_result_rate` 24h before vs after — auto rollback hook if rate doubles and p-value on binomial test significant.
""",
"agent-view-transitions-spa-mp": """
## SEO and MPA transitions

Cross-document view transitions may affect LCP timing — measure Web Vitals on navigations between marketing MPA pages. Prefetch next page with `<link rel="prefetch">` on hover for desktop.

## React Router data routers

`router.navigate` wrapped in startViewTransition — ensure loader data resolved before transition start or skeleton flashes in old snapshot.

## Print styles

View transitions irrelevant for print — `@media print { * { animation: none } }` always.

## Accessibility focus post-transition

Move focus to h1 after transition completes — `document.startViewTransition` promise `finished` then `h1.focus()`.
""",
"agent-vulnerability-triage-sla": """
## CISA KEV integration

Flag CVEs in CISA Known Exploited Vulnerabilities catalog as automatic Tier 0 candidate even if CVSS moderate — agent internet-facing sandbox RCE in KEV list pages immediately.

## Vendor embargo coordination

Cloud provider security embargo pre-notification — pre-stage patch branch under NDA, deploy within embargo lift window. Agent platforms on shared infra benefit from coordinated release.

## False positive N/A documentation

Closing finding as N/A requires link to code path analysis — audit trail for SOC2. "Not applicable" without evidence fails next audit.

## Pen test finding intake

External pen test CSV import to same queue — dedupe against existing Dependabot issues by CVE id.
""",
"agent-waf-bot-management": """
## LLM-specific WAF signatures

Excessive prompt injection patterns in JSON body — custom rule matching known jailbreak prefixes at edge before GPU cost. Careful false positives on legitimate security agent testing content — allowlist internal pentest IP range.

## Geographic allowlist enterprise

Single-tenant enterprise requires geo fence — WAF rule on `tenant_id` header from JWT after edge termination validates token signature.

## Challenge page branding

CAPTCHA challenge page matches product brand — reduces user confusion on false bot flag.

## Cost attribution

Estimate `$saved` metric from blocked requests times average tokens per request — justify WAF spend to finance quarterly.
""",
"agent-wallet-pass-provisioning": """
## Pass revocation on refund

Cancel booking tool must call pass revoke API — stale boarding pass on lock screen confuses travelers. Apple pass voided web service returns 410; Google object set `state=EXPIRED`.

## Localization of pass fields

Gate label "Gate" vs localized — pass field values from booking API locale, not agent LLM translation.

## Offline pass usage

Passes cached on device offline — updates queue until network; agent message "pass will update when online" if push pending.

## Load testing signing HSM

Black Friday travel surge — batch pass creation load test against signing throughput limit before peak.
""",
"agent-watermark-late-data": """
## Aligning stream and batch numbers

Sunday batch true-up job compares sum(stream windows) vs raw event log — diff >0.1% pages data eng. Finance uses batch number for invoice finalization.

## Out-of-order within same second

Events same event_time second — use event_id tie-break or ingest_time for ordering within window micro-batch.

## Watermark idle injection config

Flink `withIdleness` on source — document duration per source type mobile vs server.

## Testing late events

Chaos test: delay Kafka consumer 20 minutes artificially — verify side output volume and reconciliation patch applied.
""",
"agent-watermarking-outputs": """
## Key rotation without invalidating all history

Multi-key detector tries key ids embedded in payload — rotate annually, retain old keys read-only for 2 years legal hold.

## Paraphrase attack evaluation

Red team paraphrases watermarked text — measure detection rate quarterly; adjust strength if below policy threshold.

## Export formats

PDF text watermark via metadata + visible footer; DOCX different pipeline — don't assume one watermark path covers all agent export tools.
""",
"agent-webhook-signature-verification": """
## Multiple signing secrets during rotation

Accept HMAC with current and previous secret for 24h — providers may sign with either during rotation window. Document rotation runbook synchronized with vendor.

## Webhook IP allowlist optional

Some vendors publish IP ranges — defense in depth behind signature verify, not replacement. Update ranges automatically from vendor JSON monthly.

## Payload size limits

Reject bodies >1MB before HMAC verify — DoS protection. Agent webhooks rarely need huge payloads.

## Async processing signature re-verify

Queue worker re-verify signature or store `verified_at` attestation signed by gateway — don't trust queue message body without verification at ingress.
""",
"agent-workflow-idempotency-keys": """
## Key generation guidance for clients

Document UUID v4 in SDK examples — some clients used timestamp keys colliding on double-click same millisecond. SDK auto-generates key on run builder.

## Partial response replay

Long running run returns 202 with run_id on first POST; replay same key returns same 202 + run_id, not duplicate 201.

## Idempotency store sharding

Redis cluster hash tag `{tenant}:idempotency:{key}` colocate tenant keys — avoid CROSSSLOT errors in cluster mode.

## GDPR deletion

Purge idempotency records containing PII in request body hash mapping — TTL helps but explicit delete on tenant offboarding required.
""",
"agent-workload-identity-federation": """
## Token audience validation

Verify OIDC token `aud` matches cloud provider expected audience — misconfigured trust allows wrong cluster pods assume role.

## Cross-account role assumption

Agent platform in account A assumes role in account B for customer dedicated resources — chain roles with external ID per tenant, session tags for ABAC.

## Local dev federation

Developers use `aws sso login` not static keys — local kind cluster federation via OIDC stub or skip cloud calls with LocalStack clear labeling.

## Federation failure alerts

Alert on spike `AssumeRoleWithWebIdentity` AccessDenied — misconfigured SA annotation after deploy common regression.
""",
"agent-write-through-cache-consistency": """
## Transaction outbox pattern variant

If Redis unavailable after DB commit, write outbox row for async cache refresh — reader loads DB until outbox processor fills Redis. Prevents indefinite stale cache without silent failure.

## Cache warming on deploy

Cold Redis after deploy — optional warm job loads top 10k active session heads before traffic shift. Prevents DB thundering herd on cache empty.

## Serialization format

Use protobuf or msgpack for session head in Redis — JSON float rounding breaks token counts. Version byte prefix for schema migration.

## Read repair

Background job compares random sample Redis vs DB heads — metric `cache_drift_detected`. Auto-repair on drift.
""",
}

def main():
    for slug, extra in EXPANSIONS.items():
        path = Path(f"content/blog/{slug}.md")
        text = path.read_text()
        marker = "\n## Resources\n"
        if marker not in text or extra.strip()[:60] in text:
            print(f"SKIP {slug}")
            continue
        path.write_text(text.replace(marker, extra + marker))
        print(f"OK {slug}")

if __name__ == "__main__":
    main()
