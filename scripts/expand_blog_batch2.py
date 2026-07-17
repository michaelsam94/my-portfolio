#!/usr/bin/env python3
from pathlib import Path

EXPANSIONS = {
"agent-step-functions-saga-retries": """
## Standard vs Express workflow choice matrix

| Pattern | Standard | Express |
| --- | --- | --- |
| Human wait 24h | yes | no |
| Exactly-once feel with idempotent tasks | yes | best-effort |
| Sync API return <200ms | no | yes |
| Visual execution history audit | yes | limited |

Hybrid: Express validates input and starts Standard execution asynchronously — mobile clients poll run status instead of holding HTTP connection through three LLM calls.

## Map state fan-out for tool batches

When agent plans five independent read-only tools, `Map` state with `MaxConcurrency` caps provider thundering herd. Write Map results to S3 array; `MergeResults` Lambda reads pointers only. Map iteration failure policy: `ToleratedFailurePercentage` for optional enrichment tools, zero tolerance for payment tools.

## CloudWatch alarm wiring

Alarm on `ExecutionsFailed` with metric math comparing failed/start > 0.05 for 10m. Separate alarm on `ExecutionThrottled` — account concurrency limits hit during Black Friday agent traffic. SNS to Slack with execution ARN in payload template for one-click Step Functions console link.

## Versioning and rollback

Publish state machine `RefundAgent:3` alias `live` — rollback means pointing alias to `:2` without redeploying Lambdas. Keep Lambda versions aligned in alias — state machine rollback with new Lambda breaking schema is worse than old state machine.

## Integration test harness

LocalStack Step Functions limited — use dev account namespace `sf-qa-*` with cleanup Lambda deleting executions older than 7 days. Fixture tests: inject `States.TaskFailed` in mock Lambda for each compensation path.
""",
"agent-step-up-authentication-risk": """
## Device binding without fingerprinting users

Light device signals (app attestation, refresh token family) augment risk score without storing raw fingerprint. Step-up on new refresh family plus sensitive tool is reasonable; step-up on every login from same device annoys power users. Document in privacy policy.

## Break-glass and support impersonation

Support "view as customer" must not inherit customer elevation — read-only by default. Destructive tools blocked even with support SSO. If break-glass write enabled, four-eyes approval ticket id in audit row.

## OIDC acr_values negotiation failures

Some IdPs ignore acr step-up request — fallback WebAuthn challenge hosted on your domain within 500ms or fail closed on sensitive tool. Don't loop endless login redirects.

## Rate limit step-up attempts

Brute forcing WebAuthn or OTP after stolen session — cap challenges per session (5/hour) with lockout message. Separate from API rate limits.

## Regulatory mappings

PSD2 SCA for payment initiation tools — map step-up methods to SCA evidence stored 18 months. Export format for auditors: JSON list of `{tool, method, auth_time}` not chat logs.
""",
"agent-storybook-visual-regression": """
## Interaction tests vs visual snapshots

Storybook `play` functions click approve button — interaction test catches logic; Chromatic catches color. Run both on `ToolApprovalCard`. Don't snapshot every hover state — snapshot default + hover via pseudo-state addon if needed.

## Monorepo story composition

Agent design system in package `@acme/agent-ui` — Chromatic project per package or monolithic build with `--only-changed` on Turborepo graph. Shared `preview.tsx` sets i18n and theme for all packages.

## Baseline review SLAs

Design review within 4h on PRs touching `approval/**` CODEOWNERS — Chromatic blocking merge without approval on protected components. Emergency hotfix: accept baseline with security ticket if purely copy change invisible to pixels.

## Accessibility snapshot pairing

Add `@storybook/addon-a11y` fail on critical violations in CI separate from Chromatic — color contrast regression may pass pixels but fail WCAG.

## Local Loki for air-gapped

Teams without Chromatic cloud use Loki Docker against static Storybook build in CI — store diffs as artifacts 30 days. Slower but no external data egress for classified agent UIs.
""",
"agent-stream-processing-windowing": """
## Joining agent traces with usage windows

Stream-stream join conversation `start` and `end` events with session window to compute duration — watermark both sides with same skew. Orphan ends without starts go to side output for debugging client bugs.

## Suppression during deploys

During Kafka broker rolling restart, spike late events — temporarily widen allowed lateness via dynamic config rather than paging on false billing anomaly. Automate revert after cluster healthy.

## Exactly-once Kafka Streams

Enable exactly-once v2 processing guarantee for token counters if finance accepts Streams EOS semantics — still reconcile with batch because EOS doesn't cover external Stripe API idempotency.

## Flink savepoints before redeploy

Take savepoint before changing window duration — cannot restore 1m windows to 5m state without recomputation job. Document incompatible state changes in changelog.

## Observability panels

Grafana row: watermark lag, late event rate, window emit count, dedupe drop count. Correlate late spike with mobile app version release — often SDK bug not infra.
""",
"agent-subresource-integrity-hashes": """
## Subresource Integrity with service workers

If agent PWA uses service worker caching JS, ensure SW fetches respect integrity on install — stale SW serving old JS without matching HTML integrity breaks load. Version SW with build id; skip waiting on security patch releases.

## CDN cache key and SRI interaction

CDN must not transform bytes (minify on edge) if integrity computed on origin artifact — disable edge JS minification or recompute hash post-transform in deploy pipeline.

## Third-party script allowlist process

New analytics vendor requires security review ticket: pinned URL, hash, CSP update, expiry review date. Automated CI fails if unknown script URL appears in built HTML.

## Report-only CSP migration

Ship `Content-Security-Policy-Report-Only` with `require-sri-for script` before enforcing — collect violations from prod without breaking enterprise customers on old browsers.
""",
"agent-subscription-billing-dunning": """
## Payment method update deep links

Stripe Customer Portal return URL must land in-app with deep link verifying session — agent chat resumes with system message "Billing updated" from server, not LLM invention. Handle portal cancel gracefully without clearing past_due incorrectly.

## Tax and invoice timing during dunning

Past_due tenants may still accrue metered usage — decide if usage invoices combine with subscription retry or separate. Finance often wants usage billed even when subscription pauses — document in dunning emails to avoid surprise.

## Cohort analysis on recovery

Segment recovery rate by tenant size, payment method type (card vs ACH), and day of month invoice — optimize email timing per cohort. ACH failures need longer grace than card.

## Webhook ordering

`invoice.paid` may arrive before `customer.subscription.updated` — handle idempotently regardless of order. State machine for billing account, not sequential webhook assumptions.
""",
"agent-summarization-map-reduce": """
## Incremental map on document edits

When single doc changes in corpus, re-map only affected chunks and re-run reduce from that doc's branch in reduce tree — don't re-map 2000 docs nightly. Dependency graph: doc_id → chunk_ids → map artifact keys in object storage.

## Language and encoding in map chunks

PDF extraction may mojibake — detect encoding before map; garbage map outputs poison reduce. Language-specific map prompts for non-English corpora; single English reduce on multilingual bullets loses nuance — consider language-aware reduce tiers.

## Human QA sampling protocol

Sample 2% of map outputs weekly stratified by doc type — reviewers flag hallucinated bullets. Feed false bullets into fine-tune negative set or prompt "do not invent" reinforcement.

## Cost caps per tenant

Kill map job when projected token cost exceeds tenant daily budget — return partial hierarchical summary with "truncated due to budget" flag. Agent narrates honestly.

## Storage lifecycle

Map artifacts in S3 IA after 30 days, delete after 90 unless legal hold — lifecycle policy tagged by corpus_id.
""",
"agent-synonym-graph-expansion": """
## Negative edges and antonyms

Graph edges typed `antonym` prevent expansion across "hot" ↔ "cold" in HVAC domain confusion with emotional sense. Query expansion filters antonym neighbors unless domain context explicitly HVAC.

## Synonym approval workflow

Slack bot posts weekly "proposed synonym pairs" mined from zero-result queries — linguist approves in Notion synced to graph JSON in git. Reject "windows" ↔ "Microsoft Windows" without disambiguation node.

## Elasticsearch synonym_graph filter reload

Changing synonym file requires closing/reopening index or using reload API — plan maintenance window. For zero-downtime, new index alias swap with reindex.

## Embedding drift monitoring

When embedding model retrains, synonym graph may become redundant or harmful — eval expansion on/off after model change; temporarily disable query-time expansion if MRR drops.
""",
"agent-synthetic-media-labeling": """
## Platform-specific export presets

YouTube upload API fields for "altered content" — agent export pipeline sets metadata before handoff. TikTok and Instagram policies change — legal subscription to platform developer policy updates.

## Voice cloning disclosure

If TTS uses cloned voice, additional consent and labeling beyond generic AI-generated — some jurisdictions require explicit voice replica permission from subject.

## Batch relabeling historical assets

Migration job: scan S3 for pre-C2PA assets, embed manifest with `c2pa.edited` from archive metadata — prioritize customer-facing CDN paths first. CPU-bound signing queue with rate limit to avoid HSM throttle.

## Accessibility of visible labels

Screen readers should announce "AI-generated image" via contentDescription on Image composable — visible badge alone insufficient.
""",
"agent-table-bloat-vacuum-tuning": """
## Connection pool interaction with vacuum

Long idle connections in pool hold snapshots — PgBouncer transaction mode reduces idle in transaction but autovacuum still blocked by long queries from analytics replica. Route heavy reporting to replica with hot_standby_feedback on — understand primary bloat impact.

## pg_repack operational checklist

Schedule during low traffic; monitor replication lag during repack; verify disk space 2× table size free; run ANALYZE after. Agent message tables with JSONB — repack duration correlates with toast table size.

## ORM batch insert vs bloat

Hibernate/JPA saveAll flushing every row creates bloat — JDBC batch inserts 500 rows per transaction, single commit. SQLAlchemy `bulk_save_objects` patterns for agent event ingest.

## Monitoring dashboards

Grafana postgres_exporter: `pg_stat_user_tables_n_dead_tup`, autovacuum duration, last autovacuum age. Alert if last_autovacuum > 24h on tier-1 tables.
""",
"agent-tax-calculation-vat-gst": """
## Marketplace facilitator rules

If platform is deemed marketplace for third-party sellers, tax calculation splits by seller nexus — agent quoting must know seller_id and call tax API with marketplace facilitator flags. Wrong facilitator flag misstates VAT on cross-border B2C.

## Currency conversion timing

Tax API returns tax in presentation currency — FX rate timestamp must match invoice PDF rate source. Agent display uses formatted money from API; never float math in JS.

## Exemption certificates

B2B US exempt customers upload certificate — tax API customer profile includes exemption id with expiry. Agent must not assume exempt without validated cert on file.

## Audit sample monthly

Finance samples 20 agent-generated quotes vs tax API audit log — mismatch investigation before month close.
""",
"agent-timeseries-anomaly-alerting": """
## Cardinality explosion guards

Never label Prometheus metrics with unbounded `conversation_id` — use logs for drill-down. `tenant_id` OK if <10k tenants; above that sample or top-N only for anomaly by tenant.

## Holiday calendars

US Thanksgiving drops B2B agent usage — exclude holidays in seasonal comparison or use `days_offset` calendar table in recording rules. Grafana annotations for known launches prevent false positive on marketing spike.

## Composite alerts

Fire page only when token anomaly AND error rate elevated — reduces alert on benign marketing burst with healthy success rate. Document composite in runbook with boolean logic.

## Post-incident alert tuning

After false page, ticket to adjust threshold with expiry review date — don't permanently widen without owner.
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
