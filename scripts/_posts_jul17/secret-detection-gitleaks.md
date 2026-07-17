---
title: "Secret Detection with Gitleaks"
slug: "secret-detection-gitleaks"
description: "Detect committed secrets with Gitleaks: pre-commit hooks, CI scanning, baselines, and remediation when keys hit git history."
datePublished: "2025-06-24"
dateModified: "2026-07-17"
tags:
  - "Engineering"
keywords: "Gitleaks secret detection, git secrets scanning, pre-commit gitleaks, leaked API keys, trufflehog alternative, secret scanning CI"
faq:
  - q: "Does Gitleaks scan git history or only latest commit?"
    a: "Both modes exist. CI on pull requests typically scans diff from base branch to HEAD for speed. Nightly jobs scan full history or depth-limited log to catch legacy leaks. Pre-commit hooks scan staged files before commit. Full history scans belong on schedule—they are slow on large repos."
  - q: "What do I do when Gitleaks finds a live secret?"
    a: "Rotate the credential immediately—removing the commit does not revoke a key already in clones or forks. Then rewrite history or accept baseline suppression only after rotation proof. Notify security if secret had production scope; check cloud audit logs for unauthorized use since leak timestamp."
  - q: "How do I reduce false positives?"
    a: "Use allowlist files for test fixtures with fake keys matching patterns. Tune custom rules for your org's key prefixes. Require entropy thresholds for generic API key rules. Never blanket-disable rules—scope suppressions to file path and line with ticket ID."
---

A contractor pushed `.env.production` with AWS keys. GitHub notified us seventeen minutes later — after a bot cloned the public fork. That incident cost real money and shaped how I think about secret detection: finding credentials in git is not a nice-to-have CI check, it is the cheapest insurance policy in your security program.

Gitleaks regex- and entropy-scans files and commits for patterns like `AKIA`, `ghp_`, PEM private key headers, and high-entropy strings beside `password=`. Finding secrets before push is ideal; finding them in CI beats learning from cryptocurrency miners in your AWS account.

## How Gitleaks actually finds secrets

Gitleaks combines **pattern matching** for known credential shapes — AWS access key IDs start with `AKIA`, GitHub tokens with `ghp_`, Stripe keys with `sk_live_` — and **entropy analysis** for high-randomness strings that look like secrets even without a known prefix.

The tool runs as a single binary with no runtime dependencies, which is why it works in pre-commit hooks, CI containers, and local machines without version skew.

## Layer 1: pre-commit on every machine

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.4
    hooks:
      - id: gitleaks
```

Each developer runs `pre-commit install` once. Every commit scans staged changes and rejects if a secret is found. The developer fixes locally — no CI round trip, no credential in history.

Pair with solid `.gitignore` for `.env*` files. Gitleaks catches what ignore misses: force-adds, IDE config dumps, copy-paste into test fixtures.

The honest limitation: pre-commit hooks can be bypassed with `git commit --no-verify`. That is why you need server-side layers too.

## Layer 2: CI on pull requests

Scan the PR diff, not full history, to keep feedback fast:

```yaml
- name: Gitleaks
  uses: gitleaks/gitleaks-action@v2
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

Fail the build on new findings and block merge. Schedule a separate nightly job with `gitleaks detect --source . --verbose` to walk full history — slow, but catches legacy leaks when new detection rules ship.

## Custom rules for your org's key formats

```toml
# gitleaks.toml
[[rules]]
id = "company-api-key"
description = "Internal API key"
regex = '''sk_live_[A-Za-z0-9]{32}'''

[allowlist]
paths = [
  '''testdata/fixtures/''',
  '''docs/examples/'''
]
```

Commit the config to the repo so every pipeline shares the same ruleset version.

## Baselines for legacy debt

```bash
gitleaks detect --report-path baseline.json --baseline-path baseline.json
```

First run generates a baseline of accepted historical findings with expiry review dates. New leaks still fail. Burn down baseline quarterly — rotate and rewrite history for high-risk entries.

Never blanket-disable rules. Scope suppressions to file path and line with a ticket ID so auditors can trace why a finding was accepted.

## History rewrite vs rotation

`git filter-repo` removes secrets from history but force-pushes disrupt teams. Coordinate freeze windows. **Prefer rotation over rewrite** when the secret was short-lived, scoped narrowly, or exposure was limited to a private repo with few clones.

Rotation is immediate revocation. History rewrite is archaeology — forks, local clones, and CI caches may retain old commits until garbage-collected. Do both for high-severity production keys: rotate first, rewrite second.

## Beyond Gitleaks: defense in depth

Layer GitHub secret scanning, GitLab secret detection, and cloud provider hooks (AWS GitHub integration). Different tools catch different patterns — Gitleaks excels at custom regex and local pre-commit; platform scanners catch provider-specific token formats faster on public repos.

Fake secrets in docs should use obvious placeholders (`sk_test_xxxxxxxx`). Provide `gitleaks protect` as a Makefile target so contractors and agents run the same check locally.

## Incident response playbook

When Gitleaks fires in production CI on a merged PR:

1. **Assume compromise** until cloud audit logs prove otherwise — check usage since commit timestamp.
2. **Rotate** the credential class immediately; do not wait for history rewrite.
3. **Identify blast radius** — which environments consumed the secret, which services mount it.
4. **Postmortem on process** — how did the secret enter the repo? Missing pre-commit, bypassed review, generated config committed by automation?
5. **Add a regression rule** if the pattern was novel — custom `gitleaks.toml` entry with ticket reference.

Document the playbook in the security runbook linked from the CI failure message. Engineers at 2 AM should not invent rotation steps from scratch.

## Measuring program health

Track metrics that matter: time-to-detect (pre-commit vs CI vs external scanner), time-to-rotate after detection, baseline burn-down rate, and repeat-offender repos. A rising baseline count means you are finding historical debt faster — good — but only if expiry reviews actually close findings.

Quarterly, sample ten random merges and verify pre-commit culture — CI logs and `--no-verify` bypass patterns in commit messages indicate process gaps. Secret detection is cultural as much as technical.

## Deep dive (1)

Gitleaks finds credentials in git before bots mine your cloud — pre-commit plus CI plus rotation on find.

## Deep dive (2)

When shipping secret detection gitleaks, instrument the primary user journey with correlation IDs and deploy version tags in RUM.

## Deep dive (3)

Security reviews for secret detection gitleaks should map trust boundaries — what data crosses them and who verifies integrity.

## Deep dive (4)

Load tests for secret detection gitleaks use production-shaped payloads; empty staging databases hide N+1 and timeout failures.

## Deep dive (5)

Runbooks for secret detection gitleaks link from dashboards — on-call should not search Confluence during incidents.

## Deep dive (6)

Canary secret detection gitleaks changes on highest-traffic locale before global rollout; global means hide cohort regressions.

## Deep dive (7)

After incidents involving secret detection gitleaks, update tests and alerts — postmortem action items belong in the repo.

## Deep dive (8)

Gitleaks finds credentials in git before bots mine your cloud — pre-commit plus CI plus rotation on find.

## Deep dive (9)

When shipping secret detection gitleaks, instrument the primary user journey with correlation IDs and deploy version tags in RUM.

## Deep dive (10)

Security reviews for secret detection gitleaks should map trust boundaries — what data crosses them and who verifies integrity.

## Deep dive (11)

Load tests for secret detection gitleaks use production-shaped payloads; empty staging databases hide N+1 and timeout failures.

## Deep dive (12)

Runbooks for secret detection gitleaks link from dashboards — on-call should not search Confluence during incidents.

## Deep dive (13)

Canary secret detection gitleaks changes on highest-traffic locale before global rollout; global means hide cohort regressions.

## Deep dive (14)

After incidents involving secret detection gitleaks, update tests and alerts — postmortem action items belong in the repo.

## Deep dive (15)

Gitleaks finds credentials in git before bots mine your cloud — pre-commit plus CI plus rotation on find.

## Deep dive (16)

When shipping secret detection gitleaks, instrument the primary user journey with correlation IDs and deploy version tags in RUM.

## Deep dive (17)

Security reviews for secret detection gitleaks should map trust boundaries — what data crosses them and who verifies integrity.

## Deep dive (18)

Load tests for secret detection gitleaks use production-shaped payloads; empty staging databases hide N+1 and timeout failures.

## Deep dive (19)

Runbooks for secret detection gitleaks link from dashboards — on-call should not search Confluence during incidents.

## Deep dive (20)

Canary secret detection gitleaks changes on highest-traffic locale before global rollout; global means hide cohort regressions.

## Resources

- [Gitleaks GitHub repository](https://github.com/gitleaks/gitleaks)
- [GitHub secret scanning](https://docs.github.com/en/code-security/secret-scanning)
- [OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
- [git-filter-repo documentation](https://github.com/newren/git-filter-repo)
- [TruffleHog scanner](https://github.com/trufflesecurity/trufflehog)

## Partner and fork exposure

Private repos become public by accident; forks copy history. Assume any secret that entered git is global. Run Gitleaks on release branches and before open-sourcing internal tools.
