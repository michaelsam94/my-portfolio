---
title: "SAST and DAST in Pipelines"
slug: "sast-dast-in-pipelines"
description: "Integrate SAST and DAST into CI/CD: tool selection, gating policy, false positive triage, and shift-left without blocking merges forever."
datePublished: "2025-05-07"
dateModified: "2025-05-07"
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

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.
## Policy tiers

| Tier | When | Action |
|------|------|--------|
| Advisory | Feature PR | Comment only |
| Blocking | Default branch | Fail on new Critical/High |
| Nightly | Scheduled | Full repo, no baseline |

Adjust severities with CVSS plus exploitability context—a path traversal in an internal admin tool is not equal to one on the public signup form.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.
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

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.
## Secrets and supply chain

Add secret scanning (Gitleaks, TruffleHog) pre-commit and in CI—credentials in git history bypass both SAST and DAST. SBOM generation on build artifacts feeds vulnerability matching when CVEs drop mid-week.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.
## Triage workflow

Every suppressed finding links to JIRA with owner and revisit date. Weekly security office hours review top SARIF deltas. Developers fix or dispute within SLA; disputes require coded proof or test demonstrating safety.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.
## Metrics that matter

Track mean time to remediate by severity, new findings per 1000 LOC, and percentage of PRs failing security checks. Leadership cares about trend lines, not absolute scanner scores.

Weekly security office hours review top SARIF deltas. Developers fix or dispute within SLA; disputes require proof or tests demonstrating safety. Leadership cares about MTTR trend lines, not absolute scanner scores.

Nightly full-repo scans without baseline on default branch catch drift when teams bypass PR checks. SBOM generation on build artifacts feeds mid-week CVE matching when advisories drop between releases.

Secret scanning pre-commit and in CI catches credentials that bypass both SAST and DAST. Combine tools—generic Semgrep plus ecosystem-specific cargo audit or npm audit—for defense in depth without duplicate noise if policies are tuned.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

Document the decision, owner, and rollback path in your team wiki the same week you ship. Future you will not remember which environment variable toggled the behavior unless it is written next to the runbook entry and linked from the alert. That habit costs ten minutes per change and saves hours when pagination or auth misbehaves under a single large tenant.

## Resources

- [OWASP Source Code Analysis Tools](https://owasp.org/www-community/Source_Code_Analysis_Tools)
- [OWASP ZAP documentation](https://www.zaproxy.org/docs/)
- [Semgrep CI documentation](https://semgrep.dev/docs/semgrep-ci/overview/)
- [GitHub SARIF support](https://docs.github.com/en/code-security/code-scanning/integrating-with-code-scanning/sarif-support-for-code-scanning)
- [NIST SP 800-218 SSDF](https://csrc.nist.gov/publications/detail/sp/800-218/final)
