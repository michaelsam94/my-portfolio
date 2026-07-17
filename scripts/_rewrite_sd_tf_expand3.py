# Third expansion — unique deep sections (~350+ words each)

EXPAND3: dict[str, str] = {
    "system-design-metrics-monitoring": r'''
## Recording rules and federation at scale

Prometheus recording rules pre-aggregate high-cardinality metrics before they hit long-term storage:

```yaml
groups:
  - name: http_aggr
    interval: 30s
    rules:
      - record: service:http_requests:rate5m
        expr: sum by (service, status) (rate(http_requests_total[5m]))
      - record: service:http_latency:p99_5m
        expr: histogram_quantile(0.99, sum by (le, service) (rate(http_request_duration_seconds_bucket[5m])))
```

Dashboards query `service:http_requests:rate5m`, not raw counters with `pod_name` labels — query time drops from seconds to milliseconds and cardinality stays bounded.

Federation hierarchically rolls up edge Prometheus shards to central Thanos or Cortex:

```
[Edge Prometheus per AZ] --federation--> [Regional aggregator] --remote_write--> [Global store]
```

Edge retention 2 hours; global retention 13 months. Alert evaluation runs at regional tier for AZ-local failures and global tier for cross-region incidents.

## OpenTelemetry collector as universal gateway

Deploy OTel Collector as DaemonSet receiving OTLP from apps, applying tail_sampling for traces, attribute dropping for PII, and exporting to multiple backends simultaneously — vendor A for on-call, self-hosted VictoriaMetrics for cost control. One instrumentation path in application code; routing flexibility in collector config without redeploying microservices.

## On-call runbook integration

Grafana annotations from CI webhooks mark deploy events on latency graphs. Alert template includes deep link to dashboard panel, runbook URL, and `git_sha` of last deploy. PagerDuty auto-enriches with recent changes — on-call should never grep Slack for "who deployed checkout at 3 AM."
''',

    "system-design-news-feed": r'''
## Real-time badge counts without full reload

When a followed user posts, online followers should see badge increment without pulling entire feed. Fan-out worker publishes `feed_update` event to Redis pub/sub channel `user:{id}:live`. Mobile client subscribed via WebSocket inserts post at top if within ranking window. Offline users discover on next open — no push required for non-urgent social posts.

## Hydration cache and stale counts

Batch-hydrate post IDs into JSON documents cached at CDN for public content (`Cache-Control: public, max-age=60`). Like counts denormalized on post row; acceptable 30-second staleness displayed as rounded "1.2k". Private posts bypass CDN entirely — authorization check at hydration API before cache key includes `viewer_id`.

## Cold-start graph for new users

Zero-follower users see `onboarding_feed` curated by editorial or ML — clearly labeled "Popular in your area." Ranker switches to organic graph-only feed when `following_count >= 15`. Prevents empty state churn that kills day-1 retention. Onboarding posts stored separately from main fan-out pipeline to avoid polluting celebrity fan-out queues.
''',

    "system-design-notification-system": r'''
## Unsubscribe and consent audit trail

CAN-SPAM, GDPR, and CASL require provable consent timestamps per channel. Store immutable `consent_events` append-only log: `{user_id, channel, notification_type, action: grant|revoke, ts, ip, source}`. Marketing sends query latest consent before enqueue — not cached preference alone. One-click unsubscribe API updates consent log and preference atomically; next campaign batch respects within 60 seconds.

## Internationalization pipeline

Templates live in CMS with translation workflow — never English hardcoded in orchestrator. RTL email layouts tested separately. Push copy length validated per locale before send; Arabic and German often exceed iOS notification truncation. `estimated_delivery` dates formatted with `Intl.DateTimeFormat` server-side using user's `timezone` preference.

## Priority queue isolation during provider outage

When SendGrid returns sustained 503, circuit breaker opens on marketing email queue only — transactional `password_reset` queue continues on backup SMTP provider with separate credentials. Critical notifications must not sit behind bulk campaign backlog. Monitor queue age p99 per `(priority, channel)` separately.
''',

    "system-design-payment-system": r'''
## Strong Customer Authentication flow

EU PSD2 requires 3DS for many card payments. State machine adds `requires_action` — client completes challenge iframe, webhook confirms `payment_intent.succeeded`. Pending authentication times out after 15 minutes; same idempotency key on retry returns existing intent, never double-authorizes.

## ACH and async settlement rails

Bank debits settle over 3–5 business days with return codes. States: `pending_settlement → succeeded | returned`. Ledger posts on settlement file ingestion, not initiation. Reconciliation matches NACHA/SEPA files to internal `processor_ref` — different timeline than card capture.

## Marketplace seller payouts

Platform captures buyer payment, holds seller portion in ledger liability account, releases via Stripe Connect transfer T+2 after delivery confirmation. Chargeback debits seller balance — may go negative; payout pause until recovered. Idempotency on `transfer_id` prevents duplicate seller payouts on webhook retry.
''',

    "system-design-ride-sharing": r'''
## Map-matched distance and GPS fraud

Fare distance computed on map-matched path, not raw GPS polyline jitter. Compare GPS-integrated distance to routing API shortest path; flag >15% discrepancy for review. Drivers spoofing location to inflate fares is common fraud vector — automatic hold on flagged trips pending manual audit.

## Airport geofencing and venue queues

Airports use polygon geofences with designated pickup pins — GPS error at parking structures causes wrong-zone matches without geofence correction. Virtual driver queue at stadium events orders FIFO within geofence; driver must be inside polygon 5 minutes before match offered.

## Regulatory retention vs GDPR erasure

City regulations require trip records 7 years; GDPR erasure requests conflict. Legal defines retention exceptions — pseudonymize rider PII while retaining trip metrics for compliance warehouse separate from operational DB with 90-day TTL on live trip rows.
''',

    "system-design-ticketing-booking": r'''
## Accessibility and companion seating

ADA and UK Equality Act require accessible seating with linked companion seats — model as seat metadata `accessible=true, companion_seat_id=...`. Screen-reader flow uses structured list alternative to visual seat map. Hold extension policies for assistive checkout documented and fraud-reviewed.

## Season packages and cross-event holds

Festival multi-day passes hold seats across event shards — use saga coordinator: `prepare` holds on all events, `commit` on payment, `abort` releases all on any failure. Two-phase pattern prevents partial booking where day 1 sold but day 2 sold out mid-checkout.

## Resale with rotating barcodes

Secondary market tickets use TOTP barcodes rotating every 30 seconds — screenshot resale ineffective. Transfer API enforces jurisdictional price caps. Gate scanner validates against live entitlement service with 5-second clock skew tolerance.
''',

    "system-design-video-streaming": r'''
## Forensic watermarking and geo-blocking

Studio pre-release screeners need per-session invisible watermark embedding — leaks trace to account. Adds FFmpeg filter stage and 20% transcode CPU. Sports blackout regions require CDN geo headers plus VPN detection heuristics; incorrect geo causes viewer outrage and rights violations.

## Edge manifest personalization

Signed manifest URLs expiring in 60 seconds bottleneck origin during viral events. Cloudflare Workers validate JWT at edge and stitch manifest without origin round trip — startup latency drops 200ms. Worker code audited; deterministic behavior required for debugging playback failures.

## Storage lifecycle for mezzanine files

Delete source mezzanine 30 days post-transcode; retain encoded ladder and poster frames in Intelligent-Tiering. Glacier only for compliance replay requests. Lifecycle misconfiguration leaving 4K sources hot costs petabytes-months on long catalog tail.
''',

    "terraform-drift-detection": r'''
## CloudTrail correlation in alerts

Pipe `aws cloudtrail lookup-events` for drifted resource ARN into Slack alert with principal and source IP. Distinguish console click-ops from `terraform-provider` service account. Kubernetes controllers mutating cloud tags appear as IAM role — check Helm release annotations before reverting.

## Multi-account scan architecture

Delegated `OrganizationAccountAccessRole` per child account; Step Functions map state runs parallel `terraform plan` across 40 accounts. Aggregate drift dashboard by account and workspace — central networking account drift during carrier maintenance is P1 even if app accounts clean.

## Expected drift via lifecycle ignore

Document `lifecycle { ignore_changes = [desired_capacity, tags["LastModified"]] }` for ASG and vendor-managed tags. Without ignore rules, HPA-driven capacity changes page on-call nightly — alert fatigue kills real drift response.
''',

    "terraform-modules-composition": r'''
## Examples directory enforced in CI

`examples/complete/` runs `terraform init -backend=false`, `validate`, and `test` on every PR to module repo. Broken examples block merge before consumers copy broken patterns. Examples use minimum viable inputs — not every optional variable — to stay readable.

## CODEOWNERS and RFC for breaking changes

Platform team owns `modules/vpc/CODEOWNERS`. Major version requires RFC: migration guide, `terraform state mv` commands, deprecation window. Release candidate tags (`v3.0.0-rc1`) tested against three consumer roots before GA.

## Private registry over git sources

Terraform Cloud private registry resolves modules faster than `git::` clone every CI plan. Publish on tag push; consumers pin `version = "2.1.0"` not git ref. Release notes changelog is contract — Renovate opens upgrade PRs with plan diff attached.
''',

    "terraform-state-management-backends": r'''
## State migration runbook

`terraform init -migrate-state` copies local to remote — backup local file first. Backend block changes require coordinated freeze: no applies during migration. Verify lock table permissions in staging before prod migration.

## S3 Object Lock for ransomware defense

Governance mode Object Lock prevents state deletion during retention — protects against compromised CI credentials wiping bucket. Trade-off: cannot delete state until retention expires; plan retention vs recovery requirements.

## OIDC write scope minimization

CI role `terraform-apply-prod` limited to `org-terraform-state/prod/*` prefix. Staging role cannot read prod state — prevents staging pipeline exfiltrating prod resource IDs and secrets.
''',

    "terraform-testing-policy-as-code": r'''
## Mock providers for module CI speed

Terraform 1.7 mock providers enable plan tests without cloud credentials — module CI completes in seconds. Reserve real `apply` tests for weekly integration in ephemeral account.

## Infracost policy gate

Plan JSON through Infracost — deny if monthly delta exceeds `$500` without `cost-approved` PR label. FinOps and security evaluate same artifact; finance blocks expensive instance type changes security missed.

## Signed OPA policy bundles

Cosign-sign policy bundles; CI verifies signature before `conftest test`. Tampered Rego cannot weaken public S3 deny rule without detection.
''',
}
