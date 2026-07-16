---
title: "Automating Dependency Audits"
slug: "sec-dependency-audit-automation"
description: "Automate dependency auditing in CI: lockfile discipline, OSV integration, merge gates, and SLA workflows for transitive CVEs."
datePublished: "2025-05-19"
dateModified: "2025-05-19"
tags: ["Security", "Supply Chain", "CI/CD", "Dependencies"]
keywords: "dependency audit automation, npm audit CI, Dependabot, OSV scanner, CVE remediation SLA, lockfile security, supply chain"
faq:
  - q: "Should npm audit block production deploys?"
    a: "Block deploys on new critical CVEs affecting production dependency paths, not on devDependencies unused in shipped artifacts. Use audit-level thresholds and separate jobs for runtime versus development graphs. A blanket fail-on-any-advisory policy trains teams to ignore CI."
  - q: "How do I handle unfixed transitive vulnerabilities?"
    a: "Document risk acceptance with expiry when upstream has no patch—use npm overrides, Gradle resolutionStrategy, or cargo patch crates cautiously. Monitor OSV feeds for the advisory ID and auto-reopen tickets when fixed versions release. VEX documents not_affected when exploit preconditions do not apply to your usage."
  - q: "Dependabot or Renovate?"
    a: "Both automate bump PRs; Renovate offers finer grouping rules and self-hosting. Dependabot integrates natively on GitHub. Either beats manual monthly upgrades. Pair auto-PRs with CI that runs tests and security scan on the updated lockfile before merge."
---

Log4Shell taught teams that transitive dependencies run in production even when application code never mentions them. Manual `npm audit` before releases misses CVEs published Tuesday afternoon. Automated dependency auditing turns advisory feeds into enforced SLAs: detect, assign, patch, verify—on every pull request and nightly against what is actually deployed.


## Lockfiles are the source of truth

Commit lockfiles (`package-lock.json`, `Cargo.lock`, `poetry.lock`). CI must install with frozen resolution:

```bash
npm ci
cargo build --locked
```

Scanning `package.json` ranges without lockfiles imagines versions you might not ship. SBOM tools consume resolved graphs.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## CI scanning with OSV-Scanner

```yaml
- name: OSV scan
  uses: google/osv-scanner-action@v1
  with:
    scan-args: |-
      --lockfile=package-lock.json
      --severity=HIGH,CRITICAL
```

OSV aggregates advisories across ecosystems. Fail only on diff-introduced vulns during PRs using baseline comparison.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Dependabot / Renovate configuration

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: npm
    directory: /
    schedule:
      interval: weekly
    groups:
      production:
        dependency-type: production
        patterns: ["*"]
```

Group minor bumps to reduce PR noise. Auto-merge patch updates when CI is green and coverage is adequate.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Remediation SLAs

| Severity | Merge block | Patch target |
|----------|-------------|--------------|
| Critical (CVSS ≥9, exploitable) | Yes | 48 hours |
| High | Staging block | 7 days |
| Medium | Track | 30 days |

"Exploitable" means reachable from your attack surface—scanner reachability analysis or manual trace.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Overrides with accountability

```json
"overrides": {
  "lodash": "4.17.21"
}
```

Require ticket reference in commit message. Scheduled job checks if override still needed when upstream releases fix.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Deploy-time verification

Promote only artifacts scanned at build SHA. Compare production SBOM to latest scan—drift indicates manual hotfix or registry substitution. Cosign signatures bind image digest to CI run that passed audit.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.


Report MTTR for dependency CVEs monthly. Celebrate burn-down of legacy baseline, not zero findings fantasy—maintainers publish CVEs continuously.

Promote only artifacts scanned at build SHA. Compare production SBOM to latest scan—drift indicates manual hotfix or registry substitution. Cosign signatures bind image to CI run.

Override packages require ticket reference and scheduled re-check when upstream releases fix. Risk acceptance without expiry becomes permanent vulnerability.

Report MTTR for dependency CVEs monthly. Celebrate baseline burn-down, not zero findings fantasy—maintainers publish CVEs continuously. CISA KEV catalog prioritizes exploited issues for immediate action.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

Document the decision, owner, and rollback path in your team wiki the same week you ship. Future you will not remember which environment variable toggled the behavior unless it is written next to the runbook entry and linked from the alert. That habit costs ten minutes per change and saves hours when pagination or auth misbehaves under a single large tenant.



Run the change through your standard PR checklist: tests, observability, and a two-minute rollback drill in staging. Small operational habits accumulate into systems that survive on-call nights without heroics.


Share a short write-up in your engineering channel after rollout: what shipped, what metric you watch, and who owns follow-up. That closes the loop for teammates who were not in the PR and surfaces gaps in docs before the next person repeats the same investigation.

## Resources

- [OSV.dev database](https://osv.dev/)
- [GitHub Dependabot documentation](https://docs.github.com/en/code-security/dependabot)
- [Renovate bot documentation](https://docs.renovatebot.com/)
- [CISA known exploited vulnerabilities catalog](https://www.cisa.gov/known-exploited-vulnerabilities-catalog)
- [OpenSSF Scorecard](https://securityscorecards.dev/)
