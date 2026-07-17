---
title: "AI Agents: Git Leaks Prevention"
slug: "agent-git-leaks-prevention"
description: "Stop API keys, MCP configs, and eval datasets from entering git history—pre-commit hooks, CI depth scans, secret rotation playbooks, and agent-repo patterns that survive monorepos."
datePublished: "2025-10-26"
dateModified: "2025-10-26"
tags: ["AI", "Agent", "Git"]
keywords: "git leaks, secrets scanning, gitleaks, pre-commit, agent API keys, MCP config, detect-secrets, trufflehog"
faq:
  - q: "Why do agent repos leak secrets more often than typical application code?"
    a: "Agent repos accumulate .env examples, notebook outputs, MCP server configs, prompt files with embedded URLs, and eval fixtures that mirror production payloads. Contributors paste sk- keys into debug scripts. CI logs print truncated tokens during failed auth. The attack surface is wider because experimentation is encouraged and git history is forever."
  - q: "Should we scan only staged files or the full repository?"
    a: "Both. Pre-commit hooks scan staged diffs to block commits before push. CI scans full history on every PR and nightly because secrets enter via force-push, amended commits, and imported forks. A secret in an old commit is as exploitable as one on main today."
  - q: "How do we handle false positives from high-entropy strings in eval data?"
    a: "Use baselines (detect-secrets, gitleaks allowlists) checked into the repo with review. Never blanket-ignore entire directories—scope allowlists to file path plus line hash. Re-baseline only via PR with security reviewer approval."
  - q: "What is the rotation playbook when a leak is confirmed?"
    a: "Revoke the credential immediately, scan git history for all occurrences including forks, notify affected services, rotate downstream dependencies that trusted the key, and run a post-incident review on why pre-commit or CI missed it. Do not rely on 'delete the commit'—assume the secret is burned."
---
An OpenAI key committed in `eval_runner.py` rotated three staging environments when GitHub secret scanning fired at 2 a.m. The developer had copied `.env.local` into a "temporary" debug branch six weeks earlier; squash-merge preserved the blob. Pre-commit was optional. CI scanned only the default branch on Sundays.

Agent repositories leak differently from CRUD apps. You have MCP JSON with bearer tokens, LangSmith URLs with embedded keys, notebook cells that `print(os.environ)`, and prompt YAML where someone pasted a webhook for Slack alerts. Git history is immutable; scanners that only watch `main` miss the damage already sitting in feature branches waiting for merge.

This post covers defense in depth for git leak prevention in agent stacks: hooks that developers cannot bypass casually, CI that scans history depth, custom rules for LLM provider formats, and the rotation playbook when prevention fails.

## The agent-repo secret surface

Beyond `.env` files, watch these paths:

| Path pattern | Typical leak |
|--------------|--------------|
| `mcp.json`, `.cursor/mcp.json` | OAuth tokens, API keys in server args |
| `**/prompts/*.yaml` | Webhook URLs with secrets |
| `notebooks/*.ipynb` | Cell output containing keys |
| `eval/fixtures/*.json` | Production-shaped payloads with real tokens |
| `docker-compose*.yml` | Inline env vars "for local dev" |
| `.github/workflows/*.yml` | `${{ secrets.X }}` echoed in debug steps |

Treat `**/*.md` code blocks as scan targets—README examples often contain real-looking `sk-proj-` strings copied from dashboards.

## Pre-commit: block before history exists

Pre-commit must run on **staged** content and fail the commit. Make installation mandatory via `core.hooksPath` in CI bootstrap scripts, not documentation alone.

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.4
    hooks:
      - id: gitleaks
        args: ["--staged", "--redact"]
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args: ["--baseline", ".secrets.baseline"]
  - repo: local
    hooks:
      - id: agent-provider-keys
        name: Scan for LLM provider key patterns
        entry: python scripts/scan_provider_keys.py
        language: python
        files: \.(py|ts|yaml|json|ipynb|md)$
```

Custom rules catch formats generic scanners miss:

```python
# scripts/scan_provider_keys.py
import re, sys, pathlib

PATTERNS = [
    (r"sk-[a-zA-Z0-9]{20,}", "OpenAI-style key"),
    (r"sk-ant-[a-zA-Z0-9-]{20,}", "Anthropic key"),
    (r"hf_[a-zA-Z0-9]{30,}", "Hugging Face token"),
    (r"xox[baprs]-[0-9a-zA-Z-]{10,}", "Slack token"),
    (r"https://hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[a-zA-Z0-9]+", "Slack webhook"),
]

def scan_file(path: pathlib.Path) -> list[str]:
    text = path.read_text(errors="ignore")
    hits = []
    for pattern, label in PATTERNS:
        for match in re.finditer(pattern, text):
            hits.append(f"{path}:{label} at offset {match.start()}")
    return hits

if __name__ == "__main__":
    errors = []
    for f in sys.argv[1:]:
        errors.extend(scan_file(pathlib.Path(f)))
    if errors:
        print("\n".join(errors), file=sys.stderr)
        sys.exit(1)
```

## CI: full history and PR depth

Pre-commit fails open when developers use `--no-verify` or commit from GUIs that skip hooks. CI is the backstop:

```yaml
# .github/workflows/secrets-scan.yml
name: Secrets scan
on: [pull_request, push]
jobs:
  gitleaks:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # full history
      - uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITLEAKS_CONFIG: .gitleaks.toml
```

Configure `.gitleaks.toml` with agent-specific allowlists—narrow, not broad:

```toml
[allowlist]
paths = [
  '''^eval/fixtures/synthetic/''',  # known fake keys only
]
regexes = [
  '''sk-fake-[0-9a-f]{32}''',       # documented test keys
]
```

Run TruffleHog or GitHub Advanced Security in parallel for entropy-based detection gitleaks rules miss.

## Baselines without becoming Swiss cheese

`detect-secrets` baselines track known false positives by file and line hash. Workflow:

1. Initial scan generates `.secrets.baseline`
2. New findings fail CI until baselined via explicit PR
3. Security reviews every baseline addition—reject "ignore whole file" requests

```bash
# Refresh baseline after removing real secrets (not to hide them)
detect-secrets scan --baseline .secrets.baseline
detect-secrets audit .secrets.baseline  # interactive review
```

Never commit `.env`, `.env.local`, or `credentials.json`. Use `.env.example` with placeholder values and document `direnv` or 1Password inject for local dev.

## Notebook and MCP-specific hygiene

Jupyter notebooks store outputs in JSON—keys hide in cell outputs after a successful API call:

```python
# nbstripout in pre-commit — strip outputs before commit
# .pre-commit-config.yaml addition:
  - repo: https://github.com/kynan/nbstripout
    rev: 0.7.1
    hooks:
      - id: nbstripout
```

For MCP configs, use environment variable references instead of inline secrets:

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_PERSONAL_ACCESS_TOKEN}"
      }
    }
  }
}
```

Commit `mcp.example.json`; add `mcp.json` to `.gitignore`. CI validates example files contain no high-entropy strings.

## Monorepo and fork considerations

Agent tooling often lives in monorepos alongside unrelated services. Scope scans per changed paths in CI for speed, but run full-repo scans nightly. When importing open-source agent frameworks:

```bash
# Before merging external repo
gitleaks detect --source ./vendor/agent-framework --verbose
trufflehog git file://./vendor/agent-framework
```

Forks inherit secret history—scan before `git subtree add`. Enable GitHub secret scanning push protection on org repos; it blocks pushes containing known provider patterns.

## When a leak is confirmed

Assume compromise. Sequence:

1. **Revoke** the credential at the provider within minutes
2. **Search** full history: `gitleaks detect --source . --log-opts="--all"`
3. **Notify** security and affected downstream systems
4. **Rotate** dependent secrets (webhooks, DB passwords derived from same pattern)
5. **Scrub** is not deletion—use BFG or filter-repo only after rotation; old commits remain in clones
6. **Post-incident**: why did hooks miss it? `--no-verify`? Path not in hook config? New key format?

```bash
# Find all commits touching a known leaked prefix
git log -S 'sk-proj-REDACTED_PREFIX' --all --oneline
```

Document in runbook: never paste live keys into Slack, tickets, or incident channels—use provider console revocation links.

## Metrics and governance

Track:

- `secret_scan_ci_failures` per week (should be low; investigate spikes)
- `pre_commit_bypass_rate` if you log `--no-verify` via wrapper scripts
- `time_to_revoke_minutes` from alert to provider revocation in game days
- `baseline_additions` per month (rising count signals hygiene debt)

Assign a DRI in the service catalog. New hires should pass a game day: "here is a branch with a fake key—walk through detection and rotation."

## Common mistakes

**Optional pre-commit.** Documented but not enforced equals absent.

**CI scans HEAD only.** Misses secrets in PR commits that get squashed away from view but remain reachable.

**Example keys that match real formats.** Use obviously fake prefixes documented in CONTRIBUTING.md.

**Logging secrets in CI.** Mask `sk-`, `hf_`, and bearer tokens in workflow output; never `echo ${{ secrets.X }}` for debugging.

**Ignoring `.gitignore`d files in local scans.** Developers still push after `git add -f`. Educate; scan staged content regardless.

## Developer experience without bypass culture

Scanning fails when it feels punitive. Reduce friction:

**Fast hooks.** Staged-only scans should finish in under two seconds on typical diffs. Full-repo scans belong in CI, not every commit.

**Clear remediation.** When gitleaks fires, print file, line, and rule ID—not a generic "secret detected." Link to internal docs on 1Password inject and `.env.example` setup.

**Local parity.** `make precommit` runs the same hooks as CI so surprises happen on laptop, not in PR checks.

**Grandfathered history.** Teams importing legacy repos need a bounded remediation sprint: scan, rotate, baseline only after real secrets are gone—not a blanket baseline on day one to greenwash CI.

```makefile
# Makefile — one command for new contributors
precommit:
	pre-commit install --install-hooks
	pre-commit run --all-files
```

Security owns the rules; platform owns hook performance. Product teams should not disable hooks for "just this once" without a ticket that expires.

## Supply chain and third-party agent packages

Agent repos depend on prompt libraries, MCP server packages, and vendored eval harnesses published to npm and PyPI. Those packages can contain secrets from upstream maintainer mistakes. Pin dependencies with lockfiles and run secret scans on `node_modules` and `.venv` only in CI nightly—too slow for pre-commit, but catches supply-chain leaks before production deploy.

When copying prompt templates from public GitHub repos, assume they contain real keys until proven otherwise. Run gitleaks on import, not after merge.

## The takeaway

Git leak prevention for agent repos is a pipeline: pre-commit on staged diffs, custom provider rules, full-history CI, notebook output stripping, and MCP config templates. Prevention reduces frequency; rotation readiness limits blast radius. Treat every confirmed leak as burned—history does not forget, and neither do attackers scraping public GitHub.

## Resources

- [Gitleaks documentation](https://github.com/gitleaks/gitleaks)
- [detect-secrets baseline workflow](https://github.com/Yelp/detect-secrets)
- [GitHub secret scanning and push protection](https://docs.github.com/en/code-security/secret-scanning)
- [TruffleHog](https://github.com/trufflesecurity/trufflehog)
- [BFG Repo-Cleaner (post-rotation history rewrite)](https://rtyley.github.io/bfg-repo-cleaner/)
