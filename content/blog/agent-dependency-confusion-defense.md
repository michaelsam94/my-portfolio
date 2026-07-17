---
title: "AI Agents: Dependency Confusion Defense"
slug: "agent-dependency-confusion-defense"
description: "Dependency Confusion Defense: production patterns for ai teams — design, implementation, testing, security, and operations."
datePublished: "2025-10-30"
dateModified: "2025-10-30"
tags: ["AI", "Agent", "Dependency"]
keywords: "agent, dependency, confusion, defense, ai, production, engineering, architecture"
faq:
  - q: "What is dependency confusion in agent and ML projects?"
    a: "An attacker publishes a public package with the same name as your internal private package—often at a higher semver—so package managers resolve the malicious public version during CI or local installs. Agent repos are high-value targets because they contain API keys, model endpoints, and tool execution sandboxes."
  - q: "Which package ecosystems affect agent stacks most?"
    a: "Python (pip/Poetry/uv) and npm (LangChain, Vercel AI SDK, MCP servers) dominate. Also watch Docker base images tagged `:latest`, Hugging Face model repos with typosquatted names, and PyPI packages mimicking internal names like `company-agent-tools`."
  - q: "Does pinning versions eliminate dependency confusion?"
    a: "Pinning helps but does not fully protect. Attackers can still publish higher versions on public indexes if your resolver checks public before private. You need private registry priority, namespace controls, and lockfile integrity verification—not pins alone."
  - q: "How should CI defend agent repos specifically?"
    a: "Use scoped private indexes first, block install from public PyPI/npm unless allowlisted, verify lockfile package URLs point to approved registries, scan for typosquats on new dependencies, and run builds in ephemeral environments without persistent credential caches."
---
A CI pipeline for the customer-support agent started failing intermittently on Tuesday—then passing on re-run. By Thursday, security found outbound connections from build containers to an unknown PyPI package named `acme-agent-sdk` at version `99.0.0`. The team's internal SDK was also called `acme-agent-sdk`, hosted on a private Artifactory instance, pinned internally at `2.4.1`. pip resolved the public typosquat because an engineer's laptop had a misconfigured `.pip.conf` that listed PyPI before the private index. The malicious package exfiltrated `OPENAI_API_KEY` and `LANGCHAIN_API_KEY` from environment variables during `pip install`.

Dependency confusion attacks exploit **name collisions between private and public package registries**. Agent repositories are especially attractive: they bundle LLM credentials, MCP server configs, retrieval index URLs, and sometimes customer data in eval fixtures. Defense requires registry policy, CI hardening, and supply-chain verification—not hope that semver pins save you.

## How the attack works

Classic sequence (Alex Birsan, 2021):

1. Attacker discovers internal package names via leaked `package.json`, `requirements.txt`, JS bundle source maps, or public GitHub repos.
2. Attacker publishes same name to npm/PyPI with very high version.
3. Developer or CI resolver prefers public high version over private lower version—or checks public first.
4. Malicious `setup.py` / `postinstall` script runs with CI secrets in environment.

Agent-specific variants:

- **Hugging Face model typosquats** — `meta-llama/Llama-3.1-8B` vs `meta-llama/Llama-3.1-8B-Instruct-official`
- **MCP server npm packages** — `@company/mcp-internal-tools` vs `@company-tools/mcp`
- **Docker `FROM`** pulling public image with internal naming convention

```
Developer/CI
     │
     ▼
 pip / npm resolver ──▶ checks PUBLIC index first (misconfig)
     │                        │
     │                        ▼
     │              acme-agent-sdk@99.0.0 (MALICIOUS)
     │
     └── should resolve ──▶ private.registry/acme-agent-sdk@2.4.1
```

## Defense in depth

### Registry and resolver configuration

**Python (pip / uv / Poetry)**

```ini
# pip.conf — private index FIRST, explicit index-url
[global]
index-url = https://artifactory.company.com/api/pypi/pypi/simple
extra-index-url = https://pypi.org/simple

# Better: disable public entirely in CI
# index-url = https://artifactory.company.com/api/pypi/pypi/simple
# no extra-index-url
```

```toml
# pyproject.toml — Poetry: explicit source priority
[[tool.poetry.source]]
name = "company"
url = "https://artifactory.company.com/api/pypi/pypi/simple"
priority = "primary"

[[tool.poetry.source]]
name = "pypi"
priority = "explicit"  # only if explicitly referenced
```

**npm**

```ini
# .npmrc in repo root — scope internal packages to private registry
@acme:registry=https://npm.company.com/
//npm.company.com/:_authToken=${NPM_TOKEN}

# Block default registry for scoped packages
registry=https://npm.company.com/
```

Enforce with `npm config list` in CI preflight; fail if public registry appears for `@acme` scope.

### Namespace ownership

Register your internal package names on public registries as **empty placeholder packages** published by the company account. Controversial but effective for names that ever leaked. Document in security policy; legal may prefer trademark claims instead.

Prefer **scoped names** impossible to confuse: `@acme-internal/agent-sdk` on npm, `com.acme.internal.agent-sdk` Maven-style for Python via private index only.

### Lockfile integrity

Lockfiles must record **resolved registry URL**, not only version:

```python
# ci/verify_lockfile_sources.py
import json
import sys

ALLOWED_REGISTRIES = {
    "https://artifactory.company.com/api/pypi/pypi/simple",
    "https://npm.company.com/",
}

def verify_poetry_lock(path: str) -> list[str]:
    errors = []
    # Poetry lock parsing — check [[package]] source urls
    with open(path) as f:
        content = f.read()
    for line in content.splitlines():
        if "url = " in line and "pypi.org" in line:
            pkg_context = content[max(0, content.index(line) - 200): content.index(line)]
            if "acme-" in pkg_context or "company" in pkg_context.lower():
                errors.append(f"Internal-looking package resolves from public: {line.strip()}")
    return errors

if __name__ == "__main__":
    errors = verify_poetry_lock("poetry.lock")
    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    print("Lockfile source verification passed")
```

Run on every PR touching lockfiles.

### CI pipeline hardening

```yaml
# .github/workflows/agent-ci.yml (excerpt)
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Verify registry config
        run: |
          pip config list | grep -q "artifactory.company.com" || exit 1
          ! pip config list | grep -q "extra-index-url.*pypi.org" || \
            echo "WARNING: public PyPI in extra-index-url"

      - name: Install with locked deps only
        run: uv sync --locked --no-dev
        env:
          UV_INDEX_URL: https://artifactory.company.com/api/pypi/pypi/simple
          PIP_NO_INDEX: "false"

      - name: Verify no post-install network
        run: |
          # Run import smoke test; network policy blocks egress in k8s CI
          python -c "import acme_agent_sdk; print(acme_agent_sdk.__file__)"
          python ci/verify_lockfile_sources.py
```

Additional CI controls:

- Ephemeral runners with no persistent home directory
- Secrets scoped to minimal jobs—not global `env` on install steps
- `pip install --require-hashes` where feasible
- Dependabot/Renovate configured to use private registry credentials

### Pre-commit and dependency review

Block new dependencies without review:

```yaml
# .github/dependabot.yml — route through private mirror
registries:
  company-artifactory:
    type: python-index
    url: https://artifactory.company.com/api/pypi/pypi/simple
    username: ${{ secrets.ARTIFACTORY_USER }}
    password: ${{ secrets.ARTIFACTORY_PASS }}
```

Human review for any new package name in PR. Typosquat detectors (Socket.dev, Snyk, OSSF Scorecard) flag `python-dateutil` vs `python_dateutil`.

## Agent-specific supply chain surfaces

| Surface | Risk | Mitigation |
|---------|------|------------|
| LangChain community tools | Arbitrary PyPI deps | Allowlist tool packages |
| MCP server installs | `npx -y unknown-package` | Pin MCP server versions; no `-y` in prod |
| HF `from_pretrained` | Model repo swap | Pin revision hash; verify org |
| Docker agent runtime | Base image drift | Digest-pin `FROM`; scan in CI |
| `.env` in repo | Credential leak to malicious postinstall | Secret scanning; never env in install hooks |

For MCP servers specifically, treat `npx @modelcontextprotocol/server-*` like production dependencies—lock version, verify checksum, run in network-isolated sidecar.

## Detection and response

Monitor for:

- New outbound DNS from CI/build pods to PyPI/npm during install phase
- Package version jumps >10 minor without PR
- Lockfile changes that shift registry URLs

Incident response: rotate **all** secrets reachable from compromised build, audit artifact registry for poisoned wheels published internally, review git history for exfiltration scripts.

## Developer machine hygiene

CI hardening fails if laptops install packages differently. Standardize dev environments:

- **Devcontainers** with the same `pip.conf` / `.npmrc` as CI—checked into repo
- **Pre-commit hook** that rejects lockfile changes resolving internal names from public URLs
- **Onboarding doc** that explains why `pip install package` without lock sync is forbidden

Run occasional spot audits: ask engineers to run `pip debug --verbose` or `npm config list` and paste output to an internal bot that flags public-first resolver config.

## Hugging Face and model supply chain

Agent repos increasingly depend on `transformers`, `from_pretrained`, and LoRA adapters from Hugging Face Hub. Typosquatted model repos can serve malicious `custom_code` in model configs.

Mitigations:

- Pin `revision` commit hash, not only repo name
- Verify `author` org matches expected (`meta-llama`, not `meta-llama-official`)
- Use `trust_remote_code=False` unless explicitly reviewed
- Mirror approved models to internal artifact storage; block runtime download from public hub in prod

```python
# Safe load pattern
from huggingface_hub import hf_hub_download

ALLOWED_MODELS = {
    "meta-llama/Llama-3.1-8B-Instruct": "a1b2c3d4e5f6...",  # revision hash
}

def load_model(repo_id: str):
    if repo_id not in ALLOWED_MODELS:
        raise SecurityError(f"Model {repo_id} not in allowlist")
    path = hf_hub_download(
        repo_id,
        revision=ALLOWED_MODELS[repo_id],
        endpoint="https://hf-mirror.company.com",  # internal mirror
    )
    return path
```

## Organizational policy

Technology controls need policy backing:

- **Package naming standard** — all internal packages use `@company/` scope or `company_` prefix on private index only
- **New dependency review** — security sign-off for packages with postinstall scripts
- **Public placeholder registration** — security team owns squatting known leaked names
- **Quarterly dependency confusion drill** — red team publishes harmless canary package; detect if any CI pipeline resolves it

Publish an internal RFC template for new agent repos that includes a "Supply chain" section checked by security before first prod deploy.

## The takeaway

Dependency confusion defense for agent repos is registry policy plus CI enforcement, not developer diligence alone. Private index first, scoped namespaces, lockfile URL verification, ephemeral builds, and secret minimization during install. The `acme-agent-sdk@99.0.0` incident took one misconfigured `.pip.conf`—make misconfiguration impossible to merge.

## Resources

- [Dependency Confusion: How I Hacked Into Apple, Microsoft (Alex Birsan)](https://medium.com/@alex.birsan/dependency-confusion-4a5dfeafd1cf)
- [Google OSSF — Scorecard](https://github.com/ossf/scorecard)
- [PyPI — Trusted Publishers](https://docs.pypi.org/trusted-publishers/)
- [npm — Scope registry configuration](https://docs.npmjs.com/cli/v10/using-npm/scope)
- [OpenSSF SLSA framework](https://slsa.dev/)
- [Companion: SBOM Generation in CI](/agent-sbom-generation-ci/)
- [Companion: Package Lock Integrity](/agent-package-lock-integrity/)
