# Seventh expansion

EXPAND7: dict[str, str] = {
    "system-design-notification-system": r'''
## Quiet hours edge cases

Traveling users crossing timezone mid-flight need quiet hours evaluated at destination timezone after GPS or manual timezone update — not stale profile timezone sending 2 AM push after landing in Tokyo.
''',
    "system-design-payment-system": r'''
## Dispute evidence automation

Chargeback webhook triggers evidence collector: gathers AVS result, delivery tracking, IP geolocation, and customer email thread into processor dispute API automatically — win rate improves when evidence submitted within 24 hours not seven days.

## Network token lifecycle

Card-on-file uses network tokens rotating with issuer updates — stored `payment_method_id` remains stable while underlying PAN token changes. Reduces involuntary churn when physical card reissued without customer re-entering details.
''',
    "system-design-ride-sharing": r'''
## Wheelchair accessible vehicle matching

Filter `vehicle_type=wav` in matching query separate pool — do not assign sedan then cancel when rider requested accessibility. WAV drivers indexed separately with certification expiry checked nightly.
''',
    "terraform-drift-detection": r'''
## Drift SLA on executive dashboard

Monthly report: drift events detected, mean time to reconcile, percent codified vs reverted. Engineering VP visibility drives backport culture more than wiki policy alone.
''',
    "terraform-modules-composition": r'''
## Module deprecation window

`terraform deprecated` attribute (provider feature) plus README banner six months before removing module input — consumers need migration runway for org-wide version bumps.

## Variable validation messages

Validation `error_message` must say how to fix: "az_count must be 2-4 for HA; use 3 for standard prod" not "Invalid value." Plan-time errors are UX for other teams consuming your module.
''',
    "terraform-state-management-backends": r'''
## Workspace naming convention

`{env}-{region}-{domain}` state key paths in S3 — `prod-eu-west-network` not `terraform.tfstate`. On-call finds correct state in panic without opening three nearly identical keys.

## Read-only plan role

CI drift detection uses IAM role without `s3:PutObject` on state bucket — compromised drift scanner cannot corrupt state, only read and plan.
''',
    "terraform-testing-policy-as-code": r'''
## terraform test in consumer repos

Root modules run `terraform test` against pinned child module versions in CI — catches module upgrade breaking consumer assumptions before merge even when module's own tests passed.

## Policy exception audit

`policy_waiver` PRs logged to SIEM with approver identity and expiry — compliance reviews quarterly; expired waivers block merge until resource fixed or waiver renewed.
''',
}
