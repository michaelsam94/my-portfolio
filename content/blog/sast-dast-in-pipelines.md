---
title: "SAST and DAST in Pipelines"
slug: "sast-dast-in-pipelines"
description: "Integrate SAST and DAST into CI/CD: tool selection, gating policy, false positive triage, and shift-left without blocking merges forever."
datePublished: "2025-05-07"
dateModified: "2026-07-17"
tags: ["Security", "CI/CD", "DevSecOps", "SAST"]
keywords: "SAST DAST pipeline, static analysis CI, dynamic application security testing, DevSecOps, Semgrep, OWASP ZAP, security gates"
faq:
  - q: "Should SAST block pull requests on every finding?"
    a: "Block only on severity thresholds you can sustain—typically critical and high on default branches, advisory on feature branches. New findings introduced by the diff should fail the build; legacy baseline findings should be tracked separately until burned down. Blocking on thousands of historical issues guarantees developers disable the scanner."
  - q: "Where does DAST fit if we already run SAST?"
    a: "SAST analyzes source without running the app; DAST probes a deployed instance like an attacker. DAST catches misconfigurations, auth bypasses, and runtime-only issues SAST cannot see. Run DAST against staging on a schedule and after deploy, not on every commit if startup is slow."
  - q: "How do we handle false positives at scale?"
    a: "Maintain suppression files with ticket references and expiry dates. Require security review for global rule disables. Tune rules per language framework—generic SQLi rules flag ORM code constantly until scoped. Measure false positive rate weekly; if triage exceeds capacity, narrow rules before adding tools."
---
Security scanned once before SOC2 audit found 400 criticals in JavaScript dependencies and a SQL injection in staging that SAST flagged six months ago but nobody triaged. Bolt-on scanning fails; pipeline-integrated scanning with sane gates survives. Static Application Security Testing (SAST) reads code and dependencies; Dynamic Application Security Testing (DAST) hits running URLs. Together they cover different failure modes—but only if CI policy matches what your team can actually fix per sprint.

## SAST in pull request workflows

Run fast linters on every push:

```yaml
# .github/workflows/security.yml
jobs:
  sast:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Semgrep
        run: |
          pip install semgrep
          semgrep scan --config p/ci --error --baseline-commit ${{ github.event.pull_request.base.sha }}
```

`--baseline-commit` reports only new issues on PRs, keeping feedback relevant. Store SARIF output and upload to GitHub Advanced Security or DefectDojo for trending.

Language-specific tools complement generic rules: `cargo audit` / `cargo deny` for Rust, `npm audit` or OSV-Scanner for Node, CodeQL for deep taint analysis on default branch nightly.

## Policy tiers

| Tier | When | Action |
|------|------|--------|
| Advisory | Feature PR | Comment only |
| Blocking | Default branch | Fail on new Critical/High |
| Nightly | Scheduled | Full repo, no baseline |

Adjust severities with CVSS plus exploitability context—a path traversal in an internal admin tool is not equal to one on the public signup form.

## DAST against staging

Spin ephemeral environment or target long-lived staging:

```yaml
  dast:
    needs: deploy-staging
    steps:
      - name: OWASP ZAP baseline
        uses: zaproxy/action-baseline@v0.12.0
        with:
          target: https://staging.example.com
          rules_file_name: .zap/rules.tsv
```

Authenticate DAST with service accounts and crawl depth limits so you test real flows without deleting data. Seed staging with synthetic users; never point ZAP at production without read-only scope and rate limits.

## Secrets and supply chain

Add secret scanning (Gitleaks, TruffleHog) pre-commit and in CI—credentials in git history bypass both SAST and DAST. SBOM generation on build artifacts feeds vulnerability matching when CVEs drop mid-week.

## Triage workflow

Every suppressed finding links to JIRA with owner and revisit date. Weekly security office hours review top SARIF deltas. Developers fix or dispute within SLA; disputes require coded proof or test demonstrating safety.

## Metrics that matter

Track mean time to remediate by severity, new findings per 1000 LOC, and percentage of PRs failing security checks. Leadership cares about trend lines, not absolute scanner scores.

Weekly security office hours review top SARIF deltas. Developers fix or dispute within SLA; disputes require proof or tests demonstrating safety. Leadership cares about MTTR trend lines, not absolute scanner scores.

Nightly full-repo scans without baseline on default branch catch drift when teams bypass PR checks. SBOM generation on build artifacts feeds mid-week CVE matching when advisories drop between releases.

Secret scanning pre-commit and in CI catches credentials that bypass both SAST and DAST. Combine tools—generic Semgrep plus ecosystem-specific cargo audit or npm audit—for defense in depth without duplicate noise if policies are tuned.

## Rollout and ownership

Teams shipping this capability should wire observability before calling the work done: metrics on the user-visible outcome the control protects, alerts linked to runbook steps, and at least one automated test covering the last incident class you care about. Slice dashboards by region and device during rollout because global averages hide bad canaries. When vendors, routes, or org structure change, revisit assumptions from launch week—they age faster than code. Document rollback commands in the runbook header so on-call does not rediscover steps during pagination. Cross-functional review after major traffic shifts keeps product, platform, and security aligned on the leading metric.

## Rollout and ownership

Teams shipping this capability should wire observability before calling the work done: metrics on the user-visible outcome the control protects, alerts linked to runbook steps, and at least one automated test covering the last incident class you care about. Slice dashboards by region and device during rollout because global averages hide bad canaries. When vendors, routes, or org structure change, revisit assumptions from launch week—they age faster than code. Document rollback commands in the runbook header so on-call does not rediscover steps during pagination. Cross-functional review after major traffic shifts keeps product, platform, and security aligned on the leading metric.

## Rollout and ownership

Teams shipping this capability should wire observability before calling the work done: metrics on the user-visible outcome the control protects, alerts linked to runbook steps, and at least one automated test covering the last incident class you care about. Slice dashboards by region and device during rollout because global averages hide bad canaries. When vendors, routes, or org structure change, revisit assumptions from launch week—they age faster than code. Document rollback commands in the runbook header so on-call does not rediscover steps during pagination. Cross-functional review after major traffic shifts keeps product, platform, and security aligned on the leading metric.

## Rollout and ownership

Teams shipping this capability should wire observability before calling the work done: metrics on the user-visible outcome the control protects, alerts linked to runbook steps, and at least one automated test covering the last incident class you care about. Slice dashboards by region and device during rollout because global averages hide bad canaries. When vendors, routes, or org structure change, revisit assumptions from launch week—they age faster than code. Document rollback commands in the runbook header so on-call does not rediscover steps during pagination. Cross-functional review after major traffic shifts keeps product, platform, and security aligned on the leading metric.

## How I operate sast dast in pipelines in production

Treat sast dast in pipelines as a product capability with an owner, a dashboard, and a rollback plan. Define the user-visible success metric before debating tools.

### Delivery

Ship behind a flag when blast radius is high. Prefer managed services for undifferentiated heavy lifting. Document the escape hatch for teams that cannot adopt sast dast in pipelines yet — and review escape hatches quarterly.

### Operability

Alerts should page on symptoms users feel, not on every internal retry. Link runbooks from alerts. After incidents involving sast dast in pipelines, add one test or one alert that would have shortened detection.

### Knowledge

Keep a short FAQ in frontmatter synchronized with reality. Outdated answers are worse than none. Point to primary sources (RFCs, vendor docs) in Resources rather than secondary blog summaries when behavior is subtle.

## Validation scenarios for sast dast in pipelines

Before calling sast dast in pipelines done, exercise these scenarios in a staging environment that mirrors production identity, data volume, and failure injection:

1. **Happy path** with production-like payload sizes.
2. **Auth failure** — expired token, missing scope, revoked session.
3. **Dependency down** — timeout the primary collaborator; confirm degraded mode or clear error.
4. **Replay / duplicate** — submit the same event or request twice; confirm idempotency.
5. **Rollback** — disable the flag or revert the deploy; confirm state converges.

Capture traces for each scenario and store them next to the runbook for sast dast in pipelines.

## Ownership and interfaces

Name the producing and consuming teams for sast dast in pipelines. Publish the API/event contract with versioning rules. If you need a breaking change, run dual-write or dual-read long enough for consumers to migrate. Silent breakages erode trust faster than slow features.

## Resources

- [OWASP Source Code Analysis Tools](https://owasp.org/www-community/Source_Code_Analysis_Tools)
- [OWASP ZAP documentation](https://www.zaproxy.org/docs/)
- [Semgrep CI documentation](https://semgrep.dev/docs/semgrep-ci/overview/)
- [GitHub SARIF support](https://docs.github.com/en/code-security/code-scanning/integrating-with-code-scanning/sarif-support-for-code-scanning)
- [NIST SP 800-218 SSDF](https://csrc.nist.gov/publications/detail/sp/800-218/final)