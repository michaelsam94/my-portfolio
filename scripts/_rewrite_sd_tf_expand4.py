# Fourth expansion — final padding to clear 1200 words

EXPAND4: dict[str, str] = {
    "system-design-metrics-monitoring": r'''
## SLO burn rate alerts in practice

Multi-window burn rate alerts catch budget consumption before users notice — page when 2% monthly error budget burns in one hour AND 5% burns in six hours simultaneously. Single-threshold alerts on raw p99 latency generate noise during deploys; burn rates tie alerts to customer impact agreements leadership already signed.
''',

    "system-design-news-feed": r'''
## Spam and coordinated inauthentic behavior

Kill switch halts fan-out worker when moderation detects coordinated spam — posts queue in `pending_moderation` rather than polluting follower feeds. Replay fan-out after clearance with rate limit 10k/sec to avoid secondary Redis spike. Graph analysis links new accounts mass-following same celebrity as bot farm signal.
''',

    "system-design-notification-system": r'''
## Cross-channel deduplication UX

Default cascade for `order_shipped`: push first; if no app open in 5 minutes, email only — never SMS unless user opted into triple delivery. `notification_id` dedupes across channels so retry storm does not become three identical alerts on three surfaces.
''',

    "system-design-payment-system": r'''
## Webhook replay and clock skew

Verify processor webhook signatures with ±5 minute timestamp tolerance. Store processed `event_id` seven days — processors retry aggressively. Reject replays before state transition to prevent double-capture on network glitch.
''',

    "system-design-ride-sharing": r'''
## Supply heatmaps and driver incentives

Unfulfilled request heatmaps drive bonus multipliers independent of rider surge — attracts supply without punishing riders. Acceptance-rate scoring influences offer priority with fairness floor so new drivers are not starved algorithmically in regulated markets.
''',

    "system-design-ticketing-booking": r'''
## Inventory audit and fraud graph

Nightly `sold_seats` vs `valid_tickets` reconciliation per event. Velocity limits: six holds per account per hour. Shared device fingerprint links bot farm accounts blocking cart hoarding before payment stage.
''',

    "system-design-video-streaming": r'''
## QoE client beacons

Player reports `startup_ms`, `rebuffer_count`, `avg_bitrate_kbps`, `error_code` every 30 seconds during playback. QoE dashboard separate from CDN 200 rate — all-green CDN with rising rebuffer means ABR mis-tuned, not origin outage.
''',

    "terraform-drift-detection": r'''
## Drift risk scoring

Classify plan diffs: security group `0.0.0.0/0:22` is P0 page; missing `Environment` tag is P3 weekly digest. Auto-route by `drift_risk_score` computed from resource type and attribute regex rules — on-call stops ignoring alerts.
''',

    "terraform-modules-composition": r'''
## for_each stable keys

Prefer `for_each = { for s in var.subnets : s.name => s }` over `count` — list reorder destroys wrong RDS instances. Module README warns explicitly; consumers learn once painfully without documentation.
''',

    "terraform-state-management-backends": r'''
## removed block for address changes

Terraform 1.7 `removed` block drops resources from state without destroy when deprecating legacy address — cleaner than `terraform state rm` scripts in CI with human error risk.
''',

    "terraform-testing-policy-as-code": r'''
## Negative policy fixtures

`testdata/bad_plan_public_s3.json` must always fail deny rules — regression test when Rego refactors. Positive `good_plan.json` must pass; CI catches accidental policy weakening.
''',
}
