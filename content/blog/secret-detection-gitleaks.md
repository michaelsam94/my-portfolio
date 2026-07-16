---
title: "Secret Detection with Gitleaks"
slug: "secret-detection-gitleaks"
description: "Detect committed secrets with Gitleaks: pre-commit hooks, CI scanning, baselines, and remediation when keys hit git history."
datePublished: "2025-06-24"
dateModified: "2025-06-24"
tags: ["Security", "Secrets", "CI/CD", "Git"]
keywords: "Gitleaks secret detection, git secrets scanning, pre-commit gitleaks, leaked API keys, trufflehog alternative, secret scanning CI"
faq:
  - q: "Does Gitleaks scan git history or only latest commit?"
    a: "Both modes exist. CI on pull requests typically scans diff from base branch to HEAD for speed. Nightly jobs scan full history or depth-limited log to catch legacy leaks. Pre-commit hooks scan staged files before commit. Full history scans belong on schedule—they are slow on large repos."
  - q: "What do I do when Gitleaks finds a live secret?"
    a: "Rotate the credential immediately—removing the commit does not revoke a key already in clones or forks. Then rewrite history or accept baseline suppression only after rotation proof. Notify security if secret had production scope; check cloud audit logs for unauthorized use since leak timestamp."
  - q: "How do I reduce false positives?"
    a: "Use allowlist files for test fixtures with fake keys matching patterns. Tune custom rules for your org's key prefixes. Require entropy thresholds for generic API key rules. Never blanket-disable rules—scope suppressions to file path and line with ticket ID."
---

A contractor pushed `.env.production` with AWS keys. GitHub notified you seventeen minutes later—after a bot cloned the public fork. Secret scanners like Gitleaks regex and entropy-scan files and commits for patterns: `AKIA`, `ghp_`, private key PEM headers, high-entropy strings beside `password=`. Finding secrets before push is ideal; finding them in CI beats learning from cryptocurrency miners in your account.


## Local pre-commit

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.4
    hooks:
      - id: gitleaks
```

Developers fix locally without CI round trip. Pair with `.gitignore` for `.env*`—scanner catches what ignore misses.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## CI on pull requests

```yaml
- name: Gitleaks
  uses: gitleaks/gitleaks-action@v2
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

Scan PR diff only to keep feedback fast. Fail build on new findings; block merge.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Custom rules for org keys

```toml
# gitleaks.toml
[[rules]]
id = "company-api-key"
description = "Internal API key"
regex = '''sk_live_[A-Za-z0-9]{32}'''
```

Commit config to repo so all pipelines share ruleset version.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Baseline for legacy debt

```bash
gitleaks detect --report-path baseline.json --baseline-path baseline.json
```

First run generates baseline of accepted historical findings with expiry review dates. New leaks still fail. Burn down baseline quarterly—rotate and rewrite history for high-risk entries.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## History rewrite caution

`git filter-repo` removes secrets from history but force-pushes disrupt teams. Coordinate freeze windows. Prefer rotation over rewrite when secret was short-lived test key in private repo with limited exposure.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Beyond Gitleaks

Layer GitHub secret scanning, GitLab secret detection, and cloud provider hooks (AWS GitHub integration). Different tools catch different patterns.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.


Fake secrets in docs should use obvious placeholders (`sk_test_xxxxxxxx`). Provide `gitleaks protect` in Makefile target. Incident retros include how secret entered repo—process fix, not blame.

Baseline legacy findings with expiry review—never blanket disable rules. First full history scan belongs on schedule; PR scans use diff for speed.

Coordinate history rewrite with team freeze when rotation proves leak in private repo. Prefer rotation over rewrite when exposure was limited and key short-lived.

Layer GitHub secret scanning and cloud provider hooks. Different tools catch different patterns; one tool is not sufficient.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

Document the decision, owner, and rollback path in your team wiki the same week you ship. Future you will not remember which environment variable toggled the behavior unless it is written next to the runbook entry and linked from the alert. That habit costs ten minutes per change and saves hours when pagination or auth misbehaves under a single large tenant.



Run the change through your standard PR checklist: tests, observability, and a two-minute rollback drill in staging. Small operational habits accumulate into systems that survive on-call nights without heroics.


Share a short write-up in your engineering channel after rollout: what shipped, what metric you watch, and who owns follow-up. That closes the loop for teammates who were not in the PR and surfaces gaps in docs before the next person repeats the same investigation.


Prefer boring, repeatable process over one heroic migration weekend.


Treat operational readiness as part of definition-of-done: dashboards, alerts, runbook links, and a named owner. Skipping those steps ships code that works in demo and fails quietly in production until a customer or auditor finds the gap.

## Resources

- [Gitleaks GitHub repository](https://github.com/gitleaks/gitleaks)
- [GitHub secret scanning](https://docs.github.com/en/code-security/secret-scanning)
- [OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
- [git-filter-repo documentation](https://github.com/newren/git-filter-repo)
- [TruffleHog scanner](https://github.com/trufflesecurity/trufflehog)
