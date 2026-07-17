---
title: "Secret Scanning and Pre-Commit Guardrails"
slug: "secret-scanning-pre-commit"
description: "How secret scanning and pre-commit hooks stop leaked credentials: gitleaks and trufflehog, layered detection in CI, handling the inevitable leak, and cutting false positives."
datePublished: "2026-05-27"
dateModified: "2026-07-17"
tags:
  - "Engineering"
keywords: "secret scanning, pre-commit hooks, gitleaks, trufflehog, leaked credentials, secret detection CI"
faq:
  - q: "What is secret scanning?"
    a: "Automated detection of API keys, tokens, and passwords in code and git history."
  - q: "Why pre-commit?"
    a: "Blocks secrets before they enter history — the cheapest place to stop a leak."
  - q: "Secret already committed?"
    a: "Rotate first, investigate second, rewrite history last."
---

The most expensive line of code I've seen a junior engineer write was a hard-coded AWS key committed to a repo that briefly went public. The key was live for under an hour and it still cost real money and a very long incident review. Secret scanning exists to make that story impossible: it's automated detection of credentials — API keys, tokens, private keys, passwords — that have leaked into source code, and when you wire it into a pre-commit hook, the leak gets stopped on the developer's laptop before it ever becomes part of git history.

The key insight that shapes everything below: **git history is forever.** Once a secret is committed and pushed, deleting it in a later commit does nothing — it still sits in the history and in every clone. So the entire strategy is about layers of defense, with the cheapest, earliest layer catching the most.

## Why pre-commit is the highest-leverage layer

A pre-commit hook runs before the commit object is even created. If the scanner finds a secret in your staged diff, the commit is rejected, and the secret never enters history. Nothing to rotate, nothing to scrub, no incident. That's a fundamentally better position than any downstream check, because downstream means the secret already exists somewhere it shouldn't.

Contrast the cost curve. Catch a secret at pre-commit: 30 seconds of the developer fixing their change. Catch it in CI after a push: rotate the credential, rewrite history, force-push, notify the team. Catch it after it's exploited: a full security incident. The economics make pre-commit the obvious place to invest first.

The catch is that pre-commit hooks live on developer machines and can be bypassed (`git commit --no-verify`). So pre-commit is necessary but not sufficient — you need a server-side backstop too. More on that below.

## Setting up gitleaks with pre-commit

`gitleaks` is my default — fast, single binary, sane rules. The cleanest way to wire it in is through the `pre-commit` framework, which manages the hook lifecycle:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.0
    hooks:
      - id: gitleaks
```

Then each developer runs `pre-commit install` once, and gitleaks scans staged changes on every commit. You can also run it standalone against the full history to find secrets already lurking:

```bash
# Scan the entire git history, not just staged changes
gitleaks detect --source . --verbose

# Scan only what's staged (what the pre-commit hook effectively does)
gitleaks protect --staged --verbose
```

The distinction matters: `detect` walks history (use it once when onboarding a repo to find existing leaks), `protect --staged` checks the pending commit (what the hook uses day to day).

## Two detection strategies, both imperfect

Scanners find secrets two ways, and knowing the difference explains their failure modes:

- **Pattern/regex matching** — looks for known shapes, like an AWS key's `AKIA` prefix or a GitHub token's `ghp_` prefix. High precision for well-formed known credentials, but blind to custom or unrecognized formats.
- **Entropy analysis** — flags high-randomness strings that *look* like secrets regardless of format. Catches novel credentials but generates false positives on legitimate high-entropy strings (hashes, UUIDs, base64 test fixtures).

`trufflehog` leans harder into verification — it can actually *test* whether a found credential is live by calling the relevant API, which slashes false positives because it distinguishes "looks like a secret" from "is an active secret." That verification step is genuinely useful; a verified-live AWS key is a five-alarm fire, while an expired test key is noise.

| Tool | Strength | Best used for |
|---|---|---|
| gitleaks | Fast, easy pre-commit integration | The commit-time gate on every machine |
| trufflehog | Live credential verification | CI scans, prioritizing real leaks |

I run both: gitleaks at pre-commit for speed, trufflehog in CI for verified findings. They complement rather than compete.

## The false-positive problem is the real enemy

Here's the honest failure mode, and it's not technical — it's human. If your scanner cries wolf on every base64 test fixture and example key in the docs, developers start reflexively adding `--no-verify` or blanket-allowlisting, and then the tool catches nothing. A noisy secret scanner is worse than none, because it teaches people to ignore it. This is the same alert-fatigue dynamic that guts vulnerability programs, discussed in [DevSecOps and shifting security left](https://blog.michaelsam94.com/devsecops-shift-left/).

Managing false positives is therefore a first-class task, not an afterthought:

- Maintain an allowlist (gitleaks supports `.gitleaks.toml` with path and regex exclusions) for known-safe fixtures.
- Prefer trufflehog's verification in CI so only *live* credentials block the build.
- Use inline allow comments sparingly and require review when someone adds one.

Tune it until a scanner alert almost always means a real problem. That's what keeps developers trusting the gate.

## The server-side backstop

Because pre-commit is bypassable, you need a check that isn't. Run secret scanning in CI on every push and pull request, and — ideally — enable push protection at the platform level (GitHub, GitLab, and others offer server-side secret scanning that rejects pushes containing recognized secrets). The layers reinforce each other:

1. **Pre-commit** — catches most leaks for free, on the developer's machine.
2. **Pre-push / CI** — catches what bypassed pre-commit, blocks the merge.
3. **Platform push protection** — catches recognized secrets even if CI is misconfigured.
4. **Continuous history scanning** — periodically re-scans for secrets and newly-added detection rules.

No single layer is trustworthy alone; together they make a leak genuinely hard.

## When a secret leaks anyway — and preventing the next one

When (not if) a secret slips through, the order of operations is non-negotiable: **rotate first.** The moment a credential lands in a shared repo, treat it as compromised — attackers scan public git constantly, and even private repos have too many eyes. Revoke and reissue the credential, *then* investigate usage, *then* consider rewriting history to purge it. Rewriting history without rotating is security theater; the leaked value is already out.

The durable fix is to stop putting secrets in code at all. Secret scanning is a safety net, not a strategy — the strategy is proper [secrets management](https://blog.michaelsam94.com/secrets-management/) with a vault and injected runtime credentials, so there's nothing to hard-code in the first place. Scanning catches the mistakes; a real secrets architecture removes the opportunity to make them. Run both, and the class of "credential in git" incidents mostly disappears from your life — which, having lived through the alternative, is exactly where you want to be.

## Resources

- [gitleaks on GitHub](https://github.com/gitleaks/gitleaks)
- [trufflehog on GitHub](https://github.com/trufflesecurity/trufflehog)
- [pre-commit framework](https://pre-commit.com/)
- [GitHub — about secret scanning](https://docs.github.com/en/code-security/secret-scanning/about-secret-scanning)
- [GitLab — secret detection](https://docs.gitlab.com/ee/user/application_security/secret_detection/)
- [OWASP — secrets management cheat sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)

Rotate any secret that ever touched a shared branch even if history rewrite succeeds — bots scan commits within minutes of push.

Review secret scanning pre commit metrics after the next release train on mid-tier mobile devices — regressions that pass lab Lighthouse often fail CrUX field data.

Ship secret scanning pre commit changes with a named owner, dashboard link, and rollback command in the runbook — operational readiness matters as much as the code diff.

Ship secret scanning pre commit changes with a named owner, dashboard link, and rollback command in the runbook — operational readiness matters as much as the code diff. Re-baseline metrics after the next traffic doubling affecting secret routes.
