# Sixth expansion — last mile to 1200

EXPAND6: dict[str, str] = {
    "system-design-metrics-monitoring": r'''
## Dashboard review ritual

Weekly 15-minute metrics review per service owner: compare this week's p99 to four-week baseline, scan new high-cardinality labels, confirm alert thresholds still match SLO. Ritual prevents slow metric rot where dashboards lie confidently while production degrades.
''',
    "system-design-news-feed": r'''
## Feed session stickiness

Persist `last_cursor` server-side for logged-in users — resume scroll position across devices. Stale cursor older than 24 hours resets to top with "new posts" marker separating fresh from already-seen batch.
''',
    "system-design-notification-system": r'''
## Bounce handling

Hard bounces immediately suppress email channel for address; soft bounces retry three times over 24 hours then suppress. SendGrid webhook drives suppression list shared across all sending products.
''',
    "system-design-payment-system": r'''
## Partial capture for shipped goods

Ship 3 of 5 line items — partial capture authorized amount proportional to shipped SKUs, release remainder authorization hold. State machine tracks per-line-item capture status linked to fulfillment events.
''',
    "system-design-ride-sharing": r'''
## Driver offline detection

No location ping for 60 seconds while `on_trip` triggers automated rider notification and backup driver dispatch workflow — rider should not stare at frozen map indefinitely.
''',
    "terraform-drift-detection": r'''
## Slack plan artifact retention

Upload full `terraform plan` text to S3 on every drift alert with 90-day retention — auditors and incident reviewers need diff even after Terraform Cloud run history expires on free tier.
''',
    "terraform-modules-composition": r'''
## Changelog discipline

Every module tag requires CHANGELOG.md entry: Added, Changed, Deprecated, Removed, Security. Consumers subscribe to GitHub Releases RSS — silent breaking change erodes platform team trust faster than missing feature.
''',
    "terraform-state-management-backends": r'''
## State pull for debug only

`terraform state pull > backup.json` before manual state surgery — mandatory step in runbook. Engineers who skip backup discover S3 versioning restore takes 20 stressful minutes.
''',
    "terraform-testing-policy-as-code": r'''
## Policy version pinning

Pin Conftest policy bundle git SHA in CI workflow, not floating main — infrastructure deploy pipeline must not change compliance rules mid-apply without explicit policy repo release.
''',
}
