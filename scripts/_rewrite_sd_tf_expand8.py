# Eighth expansion — final four posts

EXPAND8: dict[str, str] = {
    "system-design-payment-system": r'''
## Refund reason codes

Attach structured `refund_reason` (duplicate, fraudulent, requested_by_customer) to every refund ledger entry — finance reporting and chargeback defense require reason distribution, not aggregate refund dollars alone.

## Processor version pinning

Pin payment processor API version in adapter config — silent Stripe API version bumps have changed idempotency behavior in production for teams who floated on account default.

Treat payment adapter upgrades as production releases with canary — 1% traffic before full cutover.
''',
    "terraform-modules-composition": r'''
## Consumer contract tests

Downstream roots snapshot expected `module.vpc` outputs in `tests/fixtures/expected_outputs.json` — CI fails when module minor version removes output field platform apps depend on.

## README worked example required

Module PRs without updated `examples/complete` diff rejected in CODEOWNERS review — documentation drift is the leading cause of module misconfiguration.

Platform office hours weekly for module upgrade questions — office hours reduce rogue inline forks.

Semantic version tags signed with git tag GPG optional but recommended for supply chain audit trail.

Breaking changes without migration guide do not get major version tag — platform council blocks release. Consumers deserve semver that means something in production plans.
''',
    "terraform-state-management-backends": r'''
## State encryption KMS grants

Lambda or ECS tasks running Terraform need `kms:Decrypt` on state bucket key — "access denied" on init during outage recovery is worst timing; document KMS grants in platform onboarding checklist.

## Versioning lifecycle on state bucket

Noncurrent version transition to Glacier after 90 days — balances ransomware recovery (recent versions hot) against storage cost of thousand-applies-per-month state churn.

Test state bucket restore from version ID quarterly — untested backup is wishful thinking.

Document which workspaces use `terraform_remote_state` vs native stack outputs — migration guides depend on accurate inventory.

State access audit log reviewed monthly — who read prod state and why. Unexplained reads trigger access review within five business days every quarter at minimum.
''',
    "terraform-testing-policy-as-code": r'''
## Checkov skip comments audit

`checkov:skip` comments require ticket ID in same line — monthly grep finds skips without tickets; silent security debt accumulates in modules copied across dozens of roots.

## Plan JSON schema validation

Validate `tfplan.json` against Terraform plan schema before Conftest — malformed plan from provider crash should fail CI loudly, not produce empty policy pass.

Publish policy rule coverage report monthly — rules never triggered may be obsolete or bypassed.

Run Conftest locally via pre-commit hook — developers fix violations before waiting on CI queue.

Policy PRs require security reviewer — two-person rule prevents accidental deny rule deletion.
''',
}
