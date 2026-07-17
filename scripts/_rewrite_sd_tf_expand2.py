#!/usr/bin/env python3
"""Second expansion pass for posts still under 1200 words."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
WORD_PAT = re.compile(r"\b[\w'-]+\b")
TARGET = 1200

EXTRA: dict[str, str] = {
    "system-design-search-autocomplete": r'''
## Observability and SLO definition

Define SLO on `suggest_latency_p95 < 100ms` and `empty_suggestion_rate < 5%` excluding blocked prefixes. Dashboard panels: cache hit ratio by prefix length, index lag seconds behind catalog CDC, CTR by suggestion position. Alert when CTR at position 1 drops week-over-week — often signals ranking regression or stale sponsored weights.

Trace exemplars link slow requests to specific ES shard or cold Redis key. Sampling 1% is enough at autocomplete QPS.

## Security: prefix enumeration and data leakage

Attackers scrape prefixes to reconstruct catalog or harvest private SKU names before public launch. Rate limit aggressively; require authentication for unpublished catalog namespaces; return generic suggestions for unauthenticated API keys on sensitive product lines.
''',

    "system-design-ticketing-booking": r'''
## Inventory auditing and fraud detection

Nightly reconciliation job compares `COUNT(seats WHERE status='sold')` to `COUNT(tickets WHERE status='valid')` per event. Mismatch pages finance and ops. Secondary market integration requires voiding barcodes on refund with propagation delay under 60 seconds to gate scanners.

Velocity limits: max 6 holds per account per hour, max 2 concurrent holds per payment fingerprint. Graph analysis links accounts sharing device IDs blocking cart farms.

## Multi-event cart and season packages

Festival passes span multiple events — holds become transactional across event shards using two-phase commit or saga pattern: hold all seats in `preparing` state, commit all on payment, release all on any failure. Cross-shard deadlock rare but catastrophic without timeout coordinator.
''',

    "system-design-video-streaming": r'''
## Content protection beyond DRM

Forensic watermarking embeds invisible per-session identifiers in video frames — leaks trace to account. Studio contracts may require it for pre-release screeners. Watermarking adds transcode stage CPU cost.

Geo-blocking via CDN geo headers and license policy — sports blackout regions require accurate IP geolocation with VPN detection heuristics.

## Edge computing for manifest personalization

Signed URLs with short TTL force manifest fetches through origin API — bottleneck at Super Bowl scale. Edge workers validate JWT at CDN and assemble manifest without origin round trip, shaving 200ms off startup. Worker code must stay deterministic and audited.

## Storage lifecycle policies

Delete source mezzanine files 30 days after successful transcode to cold archive — keep only encoded ladder and poster frames hot. Glacier retrieval for compliance replay only. Lifecycle rules automated via S3 Intelligent-Tiering transitions.
''',

    "system-design-notification-system": r'''
## Device token lifecycle

APNs returns `410` when token invalid — immediately delete from registry. FCM `NotRegistered` same treatment. Stale token table bloat causes wasted provider calls and inflated bill. Weekly sweep tokens with no successful delivery in 90 days.

## Attachment and rich push

Email supports attachments from virus-scanned object storage URLs. Push rich media (images) size-limited; fall back to text if payload exceeds 4KB. MIME multipart generation isolated in sandboxed renderer — template injection into HTML email is XSS to recipients.

## Cross-channel deduplication UX

User should not get push AND SMS AND email for same `order_shipped` unless they explicitly want triple redundancy. Default cascade: push first; if undelivered in 5 minutes (no app open), send email. Configurable per notification type.
''',

    "system-design-payment-system": r'''
## Webhook signature verification

Every processor webhook must verify HMAC signature before state transition. Reject replayed events by `event_id` dedup store with 7-day TTL. Clock skew tolerance ±5 minutes on timestamp header.

## Testing payments in CI

Use processor test mode keys and stub webhooks in integration tests. Never run real charges in CI. Contract tests against processor API sandbox validate adapter mapping when processor bumps API version.

## Currency presentment vs settlement reporting

Finance expects settlement CSV in USD while customer charged EUR. Ledger stores both `presentment_amount` and `settlement_amount` with FX rate and `settlement_date`. Reconciliation matches bank deposit totals, not authorization totals.
''',

    "system-design-ride-sharing": r'''
## Map matching and GPS fraud

Raw GPS drifts off-road; map-match to street graph before fare distance calculation. Drivers spoofing GPS to inflate distance — compare GPS path length to routing API shortest path; flag discrepancies >15% for manual review.

## Regulatory data retention

Many cities require trip records retained 7 years with driver/rider identity — separate compliance warehouse from operational trip DB with TTL. GDPR erasure requests conflict — legal defines retention exceptions.

## Offline and tunnel scenarios

Driver in tunnel stops sending location — rider sees last known with uncertainty halo. Matching service excludes drivers with `updated_at` stale >30s automatically. Resume stream triggers catch-up ETA recalculation.
''',

    "system-design-news-feed": r'''
## Graph expansion and suggested follows

Candidate generation may inject posts from friends-of-friends or topical clusters — clearly label "Suggested for you" distinct from organic follow graph. Ranking model separate to avoid polluting relationship signal.

## Feed integrity during incidents

Kill switch disables fan-out worker when moderation detects coordinated spam attack — posts queue in pending state rather than polluting millions of feeds. Replay fan-out after clearance with rate limit.
''',

    "system-design-metrics-monitoring": r'''
## Histogram bucket design

Choose histogram buckets matching SLO thresholds — if SLO is 300ms, include buckets at 100, 200, 300, 500, 1000ms. Misaligned buckets make `histogram_quantile` statistically meaningless for your actual target.

## Agent resource limits

Prometheus scrape too many targets per shard — horizontal sharding by `shard=0/1/2` label federation. Thanos Query fans out to shards. Plan shard count from target count growth forecast.
''',

    "terraform-drift-detection": r'''
## Drift budgets and risk scoring

Not all drift equal — security group opening port 22 is P0; tag drift is P3. Classify plan diffs automatically: `drift_risk_score` based on resource type and attribute. Route high-score alerts to security channel, low-score to weekly digest.
''',

    "terraform-state-management-backends": r'''
## State file size management

`terraform state pull | jq '.resources | length'` trending up signals resource sprawl. `removed` block (Terraform 1.7+) cleanly removes resources from state without destroy when adopting new resource address.

## Encryption key rotation

S3 SSE-KMS key rotation automatic; ensure IAM policies reference alias not raw key ID. Terraform backend block `kms_key_id` update requires init reconfiguration — document runbook.
''',

    "terraform-testing-policy-as-code": r'''
## Negative test fixtures

Maintain `testdata/bad_plan_public_s3.json` that must fail specific policies — regression test when Rego refactors. Positive fixture `good_plan.json` must pass all deny rules.

## Developer override workflow

Break-glass `policy_waiver` label on PR requires two approvers from security; Conftest skips deny rules only for labeled plans; waivers expire in 7 days if not applied.
''',
}


def wc(text: str) -> int:
    return len(WORD_PAT.findall(text))


def main() -> None:
    counts = {}
    for slug, extra in EXTRA.items():
        path = BLOG / f"{slug}.md"
        raw = path.read_text(encoding="utf-8")
        parts = raw.split("---", 2)
        body = parts[2]
        insert_before = "## Synthesis"
        if insert_before in body:
            head, tail = body.split(insert_before, 1)
            body = head.rstrip() + "\n" + extra.strip() + "\n\n" + insert_before + tail
        else:
            body = body.rstrip() + "\n" + extra
        path.write_text(parts[0] + "---" + parts[1] + "---" + body, encoding="utf-8")
        counts[slug] = wc(body)

    print("After second expansion:")
    for slug in sorted(counts):
        flag = "OK" if counts[slug] >= TARGET else "SHORT"
        print(f"  {slug}: {counts[slug]} [{flag}]")

    # verify all 12 target slugs
    all_slugs = [
        "system-design-search-autocomplete",
        "system-design-ticketing-booking",
        "system-design-video-streaming",
        "system-design-notification-system",
        "system-design-payment-system",
        "system-design-ride-sharing",
        "system-design-news-feed",
        "system-design-metrics-monitoring",
        "terraform-drift-detection",
        "terraform-modules-composition",
        "terraform-state-management-backends",
        "terraform-testing-policy-as-code",
    ]
    final = {}
    for slug in all_slugs:
        raw = (BLOG / f"{slug}.md").read_text(encoding="utf-8")
        body = raw.split("---", 2)[2]
        final[slug] = wc(body)
    print("\nFinal counts:")
    short = []
    for slug in sorted(final):
        flag = "OK" if final[slug] >= TARGET else "SHORT"
        print(f"  {slug}: {final[slug]} [{flag}]")
        if final[slug] < TARGET:
            short.append(slug)
    if short:
        raise SystemExit(f"Still short: {short}")


if __name__ == "__main__":
    main()
