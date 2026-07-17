---
title: "Secret Detection with Gitleaks"
slug: "secret-detection-gitleaks"
description: "Detect committed secrets with Gitleaks: pre-commit hooks, CI scanning, baselines, and remediation when keys hit git history."
datePublished: "2025-06-24"
dateModified: "2026-07-17"
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

## CI on pull requests

```yaml
- name: Gitleaks
  uses: gitleaks/gitleaks-action@v2
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

Scan PR diff only to keep feedback fast. Fail build on new findings; block merge.

## Custom rules for org keys

```toml
# gitleaks.toml
[[rules]]
id = "company-api-key"
description = "Internal API key"
regex = '''sk_live_[A-Za-z0-9]{32}'''
```

Commit config to repo so all pipelines share ruleset version.

## Baseline for legacy debt

```bash
gitleaks detect --report-path baseline.json --baseline-path baseline.json
```

First run generates baseline of accepted historical findings with expiry review dates. New leaks still fail. Burn down baseline quarterly—rotate and rewrite history for high-risk entries.

## History rewrite caution

`git filter-repo` removes secrets from history but force-pushes disrupt teams. Coordinate freeze windows. Prefer rotation over rewrite when secret was short-lived test key in private repo with limited exposure.

## Beyond Gitleaks

Layer GitHub secret scanning, GitLab secret detection, and cloud provider hooks (AWS GitHub integration). Different tools catch different patterns.

Fake secrets in docs should use obvious placeholders (`sk_test_xxxxxxxx`). Provide `gitleaks protect` in Makefile target. Incident retros include how secret entered repo—process fix, not blame.

Baseline legacy findings with expiry review—never blanket disable rules. First full history scan belongs on schedule; PR scans use diff for speed.

Coordinate history rewrite with team freeze when rotation proves leak in private repo. Prefer rotation over rewrite when exposure was limited and key short-lived.

Layer GitHub secret scanning and cloud provider hooks. Different tools catch different patterns; one tool is not sufficient.

## Custom rules for internal APIs

Write gitleaks allowlist entries for test fixtures only after security review — blanket allowlists defeat the purpose. Custom regex rules catch internal API key formats that generic rules miss.

## Developer education

First blocked commit should include a one-page doc on where secrets belong — vault references, not literals. Teams that only punish without teaching get `--no-verify` culture.

## Resources

- [Gitleaks GitHub repository](https://github.com/gitleaks/gitleaks)
- [GitHub secret scanning](https://docs.github.com/en/code-security/secret-scanning)
- [OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
- [git-filter-repo documentation](https://github.com/newren/git-filter-repo)
- [TruffleHog scanner](https://github.com/trufflesecurity/trufflehog)

## Operational checklist (1)

Before promoting Secret Detection Gitleaks changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Field validation (2)

Re-baseline Secret Detection Gitleaks after browser upgrades or CDN configuration changes. Mobile share above seventy percent shifts median device class — optimizations tuned on desktop lab profiles may not transfer.

## Coordination (3)

Align with platform and backend owners on cache TTL, deploy windows, and API contracts when Secret Detection Gitleaks touches shared infrastructure — single-layer wins often disappear when another tier invalidates caches.

## Operational checklist (4)

Before promoting Secret Detection Gitleaks changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Field validation (5)

Re-baseline Secret Detection Gitleaks after browser upgrades or CDN configuration changes. Mobile share above seventy percent shifts median device class — optimizations tuned on desktop lab profiles may not transfer.

## Coordination (6)

Align with platform and backend owners on cache TTL, deploy windows, and API contracts when Secret Detection Gitleaks touches shared infrastructure — single-layer wins often disappear when another tier invalidates caches.

## Operational checklist (7)

Before promoting Secret Detection Gitleaks changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Field validation (8)

Re-baseline Secret Detection Gitleaks after browser upgrades or CDN configuration changes. Mobile share above seventy percent shifts median device class — optimizations tuned on desktop lab profiles may not transfer.

## Coordination (9)

Align with platform and backend owners on cache TTL, deploy windows, and API contracts when Secret Detection Gitleaks touches shared infrastructure — single-layer wins often disappear when another tier invalidates caches.

## Operational checklist (10)

Before promoting Secret Detection Gitleaks changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Reviewer checklist for secret detection gitleaks

Ask what happens when the dependency is slow, when authz is skipped on batch jobs, and when clients retry. Those three questions catch most secret detection gitleaks regressions before production.

| Check | Expected for secret detection gitleaks |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 1: inject the failure mode you fear for secret detection gitleaks in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Incident patterns around secret detection gitleaks

Most incidents involving secret detection gitleaks start as a silent drift: a secondary path skips the control, a retry amplifies load, or a config default from a tutorial ships to production. Write the failure story before the happy path.

Concrete probe 2: inject the failure mode you fear for secret detection gitleaks in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Invariants to enforce for secret detection gitleaks

Name three invariants that must hold after every deploy of secret detection gitleaks. Encode at least one in an automated test that fails when the invariant is disabled. Reviewers should reject PRs that only cover the primary UI path.

| Check | Expected for secret detection gitleaks |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 3: inject the failure mode you fear for secret detection gitleaks in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Telemetry and ownership for secret detection gitleaks

Pair a leading operational signal with a lagging user or risk outcome. Page on burn related to secret detection gitleaks, not vanity counters. Keep a named owner and a dashboard link in the service catalog entry.

Concrete probe 4: inject the failure mode you fear for secret detection gitleaks in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Rollout sequence for secret detection gitleaks

Prefer flags, weighted routes, or dual-running configs. Rehearse rollback once in staging. The on-call note for secret detection gitleaks should include the revert command and the expected user-visible effect within five minutes.

| Check | Expected for secret detection gitleaks |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 5: inject the failure mode you fear for secret detection gitleaks in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Cross-team contracts for secret detection gitleaks

Document producers, consumers, timeouts, and idempotency keys. Silent schema or policy changes are how secret detection gitleaks breaks without a clear owner in the incident channel.

Concrete probe 6: inject the failure mode you fear for secret detection gitleaks in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Capacity and cost notes for secret detection gitleaks

Estimate QPS, payload size, cardinality, and downstream saturation. Functionally correct secret detection gitleaks changes still cause outages through pool exhaustion, crawl waste, or CPU amplification.

| Check | Expected for secret detection gitleaks |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 7: inject the failure mode you fear for secret detection gitleaks in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.
