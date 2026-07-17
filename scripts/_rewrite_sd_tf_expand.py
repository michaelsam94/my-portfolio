#!/usr/bin/env python3
"""Expand SD/TF posts to >=1200 words with unique sections."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
WORD_PAT = re.compile(r"\b[\w'-]+\b")
TARGET = 1200

EXPANSIONS: dict[str, str] = {
    "system-design-search-autocomplete": r'''
## Multi-region and locale isolation

Autocomplete indices are rarely global singletons. A query in `de-DE` should not surface English-only SKU aliases; marketplace sellers in India need INR-priced suggestions ranked differently from US defaults. Partition indices by `(locale, marketplace_id)` and route at the edge using GeoDNS or CDN request headers (`Accept-Language`, explicit `X-Market`).

Cross-region replication of hot-prefix caches is eventually consistent — acceptable for suggestions. Authoritative catalog indices follow catalog ownership region; read replicas in APAC shave 80ms off round trips. Never replicate personalized suggestion lists across regions; build them locally from replicated global candidates plus regional profile shards.

## Load testing the suggest path realistically

Synthetic load must mimic prefix distributions from production logs, not uniform random strings. Replay a 24-hour access log sample with timestamps compressed — you'll discover that `"sa"` during holiday sales dwarfs `"zz"` traffic. Warm caches before the test or you will falsely blame Elasticsearch for cold-start latency.

Measure tail latency per dependency: Redis GET, ES completion query, ranking sidecar. A 40ms p99 on ES with 5ms Redis means index redesign, not more API pods.

## Sponsored suggestions without destroying trust

Paid placement belongs at position 1 or 2 with clear "Sponsored" labeling — burying ads at position 9 trains users to ignore them and inflates impression fraud. Cap sponsored density (max 2 of 10). Frequency-cap per user per campaign. Log `sponsored=true` separately in CTR models so organic ranking does not get polluted by ad clicks.
''',

    "system-design-ticketing-booking": r'''
## Accessibility and inclusive booking

Seat maps are visual-first; screen-reader users need equivalent seat selection via structured lists (`Section 104, Row F, Seats 12-13`). Legal requirements (ADA, UK Equality Act) mandate accessible seating inventory with linked companion seats — model these as seat metadata, not afterthought flags.

Hold timers for users requiring assistive checkout flows may need extension — fraud teams hate this; product and legal jointly define policy encoded in hold service rules.

## Resale and transfer mechanics

Secondary markets require ticket barcodes that rotate (TOTP every 30s) to prevent screenshot resale. Transfer API moves entitlement from user A to B with price cap enforcement per jurisdiction. Original purchaser ID may remain on audit trail for dispute resolution.

## Disaster recovery for on-sale events

Pre-scale inventory shards 2× expected peak based on last year's telemetry. Run game days simulating payment provider 503 responses — holds must not mass-expire because webhooks stalled. Feature flag to disable interactive seat map and force GA-only mode is the break-glass lever when Postgres lock wait times exceed SLO.
''',

    "system-design-video-streaming": r'''
## Subtitle, caption, and accessibility tracks

WCAG and regional regulations require closed captions. Store WebVTT alongside HLS renditions as separate `#EXT-X-MEDIA` tracks in master playlist. Burned-in subtitles for languages with complex typography; soft subtitles for user toggle.

Audio description tracks and multi-language audio add manifest complexity — transcode pipeline must produce aligned segment boundaries across tracks or players desync.

## Origin shielding and multi-CDN

Single CDN vendor outage should not black out playback. Primary CDN serves 95% traffic; secondary CDN configured as failover origin pull. Origin shield (CloudFront Origin Shield, Akamai mid-tier) collapses cache miss thundering herds when viral video spikes — without shield, 1M viewers missing cache can DDOS your S3 bucket.

## Analytics pipeline for QoE

Client beacons report startup time, rebuffer count, average bitrate, playback failures with error code. Aggregate into QoE dashboard separate from server metrics — CDN 200s everywhere while players rebuffer means ABR misconfiguration, not origin failure.
''',

    "system-design-notification-system": r'''
## Unsubscribe and regulatory compliance

CAN-SPAM requires physical address in marketing email footers. GDPR requires granular consent records timestamped per channel. CASL requires express consent for commercial email in Canada. Architecture needs `consent_audit_log` immutable store — not just current preference snapshot.

One-click unsubscribe links must hit your API (not mailto) so preference updates propagate before next campaign batch sends.

## Internationalization and timezone rendering

`estimated_delivery` dates render in user locale. RTL templates need separate layout testing. Push character limits differ — Arabic may need shorter copy. Store template strings in CMS with translation workflow; never hardcode English in orchestrator code.

## Load shedding under provider outage

When SendGrid returns 503, notification workers should circuit-break, spill to retry queue with visibility timeout, and **not** block transactional password-reset path — separate queues per priority class. Critical queue gets dedicated worker pool and alternate provider failover domain.
''',

    "system-design-payment-system": r'''
## Strong Customer Authentication (SCA)

EU PSD2 requires 3D Secure for many card payments. Architecture must handle `requires_action` state — client completes challenge, webhook confirms authentication. Pending states timeout with user-friendly retry; do not double-authorize on retry without same idempotency key.

## ACH, SEPA, and async settlement

Bank debits settle over days with return codes (insufficient funds, account closed). State machine adds `pending_settlement → succeeded | returned`. Ledger entries post on settlement confirmation, not initiation. Reconciliation matches NACHA files, not instant webhooks.

## Marketplace payout timing

Sellers expect T+2 payout after delivery confirmation. Hold captured funds in platform ledger sub-account; release via transfer API on schedule. Chargeback on seller transaction debits seller balance — possibly negative; clawback rules in seller agreement.
''',

    "system-design-ride-sharing": r'''
## Pooling and multi-stop trips

UberPOOL-style matching adds combinatorial complexity — pick up rider B while delivering rider A without violating ETA promises. Constraint solver runs after initial match; may reject pool opportunity if detour exceeds threshold.

## Airport and venue geofencing

Airports have designated pickup zones; GPS jitter at parking structures causes wrong-zone matches. Geofenced polygons with manual driver queue at virtual curb pins. Venue events pre-position supply using historical demand curves.

## Driver supply incentives

Heatmap bonuses push drivers to underserved cells without permanent surge — separate budget from rider surge. Acceptance rate and cancellation rate factor into future offer priority — gamification with fairness caps to avoid starving low-rated drivers illegally in regulated markets.
''',

    "system-design-news-feed": r'''
## Real-time updates and badge counts

New post from followed user should increment badge without full feed reload. WebSocket `feed_update` event with `post_id` and rank hint; client inserts if within visible window. Fan-out workers publish to online user's session channel — optional optimization beyond pull-on-open.

## Caching hydrated posts

Post hydration (author, media URLs, counts) is expensive. CDN-cache public post JSON by `post_id` with short TTL; private posts bypass CDN. Like counts stale for 30s acceptable — show approximate "1.2k likes" from denormalized counter.

## Cold start for new users

Users with empty graph see onboarding feed — curated accounts to follow, trending topics. Separate `onboarding_feed` template in ranker until `following_count >= N`. Prevents empty state churn.
''',

    "system-design-metrics-monitoring": r'''
## Recording rules and pre-aggregation

High-cardinality HTTP metrics aggregated via Prometheus recording rules:

```yaml
- record: job:http_requests:rate5m
  expr: sum by (service, status) (rate(http_requests_total[5m]))
```

Downstream dashboards query recording rules, not raw counters — faster queries, lower cardinality in Grafana.

## OpenTelemetry migration path

Dual-publish from apps: Prometheus `/metrics` and OTLP to collector. Collector exports to Prometheus remote_write and vendor backend. Gradual migration without big-bang SDK swap.

## On-call runbook linking

Grafana annotations link deploy events to metric spikes. Alert messages include runbook URL and recent deploy SHA from CI webhook — on-call should not grep git at 3 AM.
''',

    "terraform-drift-detection": r'''
## Integrating drift with incident management

PagerDuty incident for production drift should link to Terraform plan artifact S3 URL and CloudTrail event ID. Resolution criteria: merged PR or documented exception — not merely "acknowledged." SOC2 auditors ask for drift MTTR evidence.

## Terraform Cloud run tasks

Run tasks trigger OPA policy and external drift ticketing on every plan. Drift detection becomes workspace policy: `if plan changes > 0 and vcs_sha == main then open_jira`.

## Handling autoscaler drift separately

ASG desired count changes from HPA are expected drift — exclude `aws_autoscaling_group` `desired_capacity` from alerts via `lifecycle { ignore_changes = [desired_capacity] }` in code, or drift noise overwhelms on-call.
''',

    "terraform-modules-composition": r'''
## Module upgrade cadence

Establish renovate/dependabot for module version bumps in consumer repos. Weekly PR `vpc v2.1.0 → v2.2.0` with plan diff attached. Major version bumps require platform team office hours.

## `for_each` vs `count` pitfalls

`count` shifts indices when list order changes — destroys wrong resources. Prefer `for_each` with stable string keys (`for_each = { for s in var.subnets : s.name => s }`). Document in module README — consumers learn after painful RDS recreation.

## Provider alias patterns

Multi-region modules pass `providers = { aws.replica = aws.west }` explicitly. Module README lists required provider configurations — implicit defaults cause cryptic plan errors in consumer roots.
''',

    "terraform-state-management-backends": r'''
## State migration between backends

```bash
terraform init -migrate-state
```

Interactive migration copies local to S3. Automate in CI carefully — backup first. Backend block changes require team coordination freeze window.

## Object locking and compliance

S3 Object Lock in governance mode prevents state deletion for retention period — protects against ransomware credential abuse deleting state bucket. Trade-off: cannot delete state until retention expires; plan lifecycle policies.

## Team access patterns

Break-glass human read access via SSO role with MFA and session logging. CI OIDC role write access scoped to `org-terraform-state/prod/*` prefix only — staging role cannot touch prod keys.
''',

    "terraform-testing-policy-as-code": r'''
## Mock providers for faster module tests

Terraform 1.7+ mocking enables plan tests without cloud credentials:

```hcl
mock_provider "aws" {
  mock_data "aws_availability_zones" {
    defaults = { names = ["us-east-1a", "us-east-1b"] }
  }
}
```

Module CI runs in milliseconds on every push — reserve real cloud apply for weekly integration.

## Cost estimation in policy

Integrate Infracost or similar on plan JSON — policy denies PR if monthly delta exceeds `$500` without `cost_approved` label. FinOps and security share the same plan artifact gate.

## Supply chain for policy bundles

Sign OPA bundles with cosign; CI verifies signature before `conftest test`. Tampered policy repo cannot silently weaken rules.
''',
}


def wc(text: str) -> int:
    return len(WORD_PAT.findall(text))


def main() -> None:
    slugs = list(EXPANSIONS.keys())
    counts = {}
    for slug in slugs:
        path = BLOG / f"{slug}.md"
        raw = path.read_text(encoding="utf-8")
        parts = raw.split("---", 2)
        if len(parts) < 3:
            raise ValueError(slug)
        body = parts[2]
        if "## Synthesis" in body:
            head, tail = body.split("## Synthesis", 1)
            body = head.rstrip() + "\n" + EXPANSIONS[slug].strip() + "\n\n## Synthesis" + tail
        else:
            body = body.rstrip() + "\n" + EXPANSIONS[slug]
        path.write_text(parts[0] + "---" + parts[1] + "---" + body, encoding="utf-8")
        counts[slug] = wc(body)

    print("After expansion:")
    for slug in sorted(counts):
        flag = "OK" if counts[slug] >= TARGET else "SHORT"
        print(f"  {slug}: {counts[slug]} [{flag}]")
    short = [s for s, c in counts.items() if c < TARGET]
    if short:
        raise SystemExit(f"Still short: {short}")


if __name__ == "__main__":
    main()
