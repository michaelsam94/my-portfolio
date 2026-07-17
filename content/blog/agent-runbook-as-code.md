---
title: "AI Agents: Runbook As Code"
slug: "agent-runbook-as-code"
description: "Runbook-as-code for AI agent operations — executable incident steps, versioned remediation in git, parameterized playbooks, and game-day tests that keep LLM outages boring."
datePublished: "2026-03-22"
dateModified: "2026-03-22"
tags: ["AI", "Agent", "Runbook"]
keywords: "runbook as code, executable runbooks, incident automation, Rundeck, Temporal workflows, AI ops, LLM incident response, game day drills"
faq:
  - q: "What makes a runbook 'as code' instead of a wiki page?"
    a: "The steps are executable artifacts in version control — scripts, workflow definitions, or parameterized job specs — with the same review, testing, and rollback expectations as application code. Prose explains intent; code performs the action."
  - q: "Which agent incidents benefit most from runbook-as-code?"
    a: "Repeatable mitigations: disabling a toxic tool, rolling back a prompt version, draining a bad model endpoint, purging poisoned RAG index segments, and scaling inference replicas. If you have done it twice manually at 2 AM, codify it."
  - q: "How do you keep runbooks from becoming dangerous automation?"
    a: "Require explicit parameters (tenant ID, model version), dry-run mode, approval gates for destructive steps, and idempotent operations. Runbooks should default to read-only diagnostics; write actions need confirmation or break-glass roles."
  - q: "How often should runbooks be tested?"
    a: "Quarterly game days for Tier-1 agent paths, plus CI smoke tests that execute diagnostic-only runbooks against staging. Any runbook not executed in six months gets archived or refreshed — stale steps are worse than no runbook."
---
The PagerDuty alert said `agent_completion_p99 > 12s`. The on-call engineer opened the wiki, searched "LLM latency," and found a runbook last edited fourteen months ago. Step 4 said "restart the inference pod." Step 7 referenced a Grafana dashboard that no longer existed. Step 9 said "ask Sarah." Sarah left the company in 2024.

Forty minutes later the team had manually rolled back a prompt template — the correct fix — but only after someone remembered the change from a Slack thread.

Wiki runbooks decay. Agent systems change weekly: models, tools, retrieval indices, rate limits. Runbook-as-code treats operational knowledge like software — versioned, tested, reviewable, and executable under stress.

## Why wikis fail for agent incidents

Agent outages have distinctive shapes:

- **Provider degradation** — OpenAI/Anthropic latency spikes; your app queues explode
- **Prompt regression** — a merged JSON template doubles token usage
- **RAG poisoning** — bad chunk sync causes confident wrong answers
- **Tool cascade** — CRM API 429s trigger agent retry storms
- **Cost runaway** — runaway loop calling expensive tools

Each mitigation is a sequence of **known commands**: flip feature flag, drain queue, pin model version, invalidate cache key pattern. Wikis describe these in prose humans must interpret. Runbooks-as-code run them with typed parameters and guardrails.

## Anatomy of a runbook repository

I structure agent ops repos like this:

```
runbooks/
  README.md                    # index + severity routing
  lib/
    kubectl_helpers.sh
    llm_provider.py
  diagnostics/
    agent-trace-sample.yaml    # read-only
    rag-index-health.yaml
  mitigations/
    rollback-prompt-version.yaml
    disable-agent-tool.yaml
    drain-inference-queue.yaml
  game-days/
    2026-q1-provider-outage.md
```

Each runbook YAML specifies inputs, steps, rollback, and ownership — not a Markdown essay.

## Runbook spec: machine-readable steps

```yaml
# mitigations/rollback-prompt-version.yaml
apiVersion: runbooks.agent/v1
kind: Runbook
metadata:
  name: rollback-prompt-version
  owner: team-agent-platform
  severity: [SEV2, SEV3]
  tags: [prompts, latency, quality]
description: >
  Pin agent system prompt to last known-good version from object storage.
inputs:
  agent_id:
    type: string
    required: true
    description: Agent identifier in config service
  target_version:
    type: string
    required: false
    description: Semver; defaults to previous production version
  dry_run:
    type: boolean
    default: true
steps:
  - id: fetch-current
    run: python lib/prompt_admin.py get --agent-id ${agent_id} --json
    save: current
  - id: resolve-target
    run: python lib/prompt_admin.py resolve-previous --agent-id ${agent_id}
    when: ${target_version} == ""
    save: target
  - id: apply
    run: python lib/prompt_admin.py set --agent-id ${agent_id} --version ${target_version || target.version} --dry-run ${dry_run}
  - id: verify
    run: python lib/prompt_admin.py eval-smoke --agent-id ${agent_id}
    unless: ${dry_run} == true
rollback:
  - run: python lib/prompt_admin.py set --agent-id ${agent_id} --version ${current.version}
```

Reviewers see diffs in git. CI validates schema and runs dry-run against staging.

## Executors: Rundeck, Temporal, or plain Make

Pick an executor matching your maturity:

**Make / shell** — smallest start; good for teams already living in terminals

```makefile
# Makefile excerpt
rollback-prompt:
	@test -n "$(AGENT_ID)" || (echo "AGENT_ID required" && exit 1)
	python lib/prompt_admin.py set --agent-id $(AGENT_ID) \
	  --version $(or $(VERSION),$$(python lib/prompt_admin.py resolve-previous --agent-id $(AGENT_ID))) \
	  --dry-run $(or $(DRY_RUN),true)
```

**Rundeck / StackStorm** — RBAC, audit logs, web UI for on-call without kubectl access

**Temporal / Argo Workflows** — long-running remediations with automatic retry and saga compensation

For agent incidents, I favor **read diagnostics in Rundeck, write mitigations in Temporal** when steps span multiple services with wait conditions.

Example Temporal workflow fragment for disabling a runaway tool:

```python
@workflow.defn
class DisableAgentTool:
    @workflow.run
    async def run(self, agent_id: str, tool_name: str, actor: str) -> str:
        config_before = await workflow.execute_activity(
            snapshot_agent_config,
            agent_id,
            start_to_close_timeout=timedelta(seconds=30),
        )
        await workflow.execute_activity(
            patch_agent_config,
            args=[agent_id, {"tools": {"deny": [tool_name]}}],
            start_to_close_timeout=timedelta(seconds=30),
        )
        await workflow.execute_activity(
            notify_slack,
            f"{actor} disabled {tool_name} on {agent_id}",
            start_to_close_timeout=timedelta(seconds=15),
        )
        return config_before  # stored for rollback workflow
```

## Linking alerts to runbooks

Alerts should deep-link to a runbook ID, not a wiki space:

```yaml
# alertmanager/agent-p99-latency.yaml
- alert: AgentCompletionP99High
  expr: histogram_quantile(0.99, rate(agent_completion_duration_seconds_bucket[5m])) > 12
  for: 10m
  labels:
    severity: sev2
    runbook: rollback-prompt-version
  annotations:
    summary: "Agent {{ $labels.agent_id }} P99 latency elevated"
    runbook_url: "https://runbooks.internal/agents/rollback-prompt-version?agent_id={{ $labels.agent_id }}"
```

On-call clicks through with parameters prefilled. No searching.

## Agent-specific runbooks worth writing first

If you are starting from zero, codify these five before exotic scenarios:

1. **Sample production traces** — pull last N traces for agent_id + error class
2. **Pin / rollback model version** — switch routing weight in inference gateway
3. **Disable single tool** — patch config deny list without full agent shutdown
4. **Purge RAG collection segment** — delete by source URI pattern after bad sync
5. **Enable safe mode** — respond with static fallback, no tools, 503 on writes

```bash
#!/usr/bin/env bash
# diagnostics/agent-trace-sample.sh
set -euo pipefail
AGENT_ID="${1:?agent id required}"
LIMIT="${2:-20}"
curl -s -H "Authorization: Bearer ${OPS_TOKEN}" \
  "https://trace-api.internal/v1/agents/${AGENT_ID}/traces?status=error&limit=${LIMIT}" \
  | jq '[.traces[] | {id, error, tools: [.steps[].tool_name], latency_ms}]'
```

## Safety rails on write actions

Runbooks that mutate production need:

- **Dry-run default** — first execution prints diff only
- **Break-glass role** — `ops-break-glass` MFA session for write mode
- **Blast radius params** — max percentage of traffic affected
- **Automatic rollback timer** — if eval smoke fails post-change, revert

```python
def patch_agent_config(agent_id: str, patch: dict, dry_run: bool = True) -> dict:
    current = config_service.get(agent_id)
    merged = deep_merge(current, patch)
    diff = json_diff(current, merged)
    if dry_run:
        return {"dry_run": True, "diff": diff}
    if not auth.has_role("ops-break-glass"):
        raise PermissionError("write runbooks require break-glass role")
    config_service.set(agent_id, merged, audit={"runbook": ctx.runbook_id})
    return {"applied": True, "diff": diff}
```

## Testing runbooks in CI and game days

**CI smoke** — run diagnostic runbooks against staging on every merge to `runbooks/`:

```yaml
# .github/workflows/runbook-smoke.yml
jobs:
  smoke:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install -r runbooks/requirements.txt
      - run: make -C runbooks agent-trace-sample AGENT_ID=staging-support DRY_RUN=true
      - run: python runbooks/ci/validate_schemas.py
```

**Game days** — inject provider latency, prompt bug, or RAG bad chunk in staging; on-call executes runbooks under time pressure; debrief updates steps.

Measure **time-to-mitigate** per scenario quarter over quarter. That metric matters more than runbook page count.

## Documentation that stays in sync

Keep one paragraph of human context at the top of each YAML — **why this runbook exists, when not to use it**. Everything else should be executable or deleted.

Anti-pattern: 800-word narrative with copy-paste commands. That duplicates the wiki problem inside git.

Good pattern:

```yaml
description: |
  Use when P99 latency spikes after a prompt deploy but provider dashboards are green.
  Do NOT use for CRM 429 errors — see drain-tool-retries runbook instead.
```

## Observability for runbook executions

Treat runbook runs as first-class events — same as deploys:

```python
def emit_runbook_metric(runbook_id: str, status: str, duration_ms: int, dry_run: bool):
    statsd.increment("runbook.execution", tags=[
        f"runbook:{runbook_id}",
        f"status:{status}",
        f"dry_run:{dry_run}",
    ])
    statsd.histogram("runbook.duration_ms", duration_ms, tags=[f"runbook:{runbook_id}"])
```

Dashboard panels worth building:

- Executions per runbook (detect runbooks nobody uses)
- Failure rate by step ID (identify brittle commands)
- Median time-to-complete vs game-day targets
- Ratio of dry-run to live executions (on-call should dry-run first during ambiguous pages)

Correlate runbook executions with agent SLO recovery timestamps. If `rollback-prompt-version` runs but P99 stays elevated, the runbook is stale or the diagnosis was wrong — update the alert routing, not just the agent code.

## Ownership and deprecation

Every runbook has `owner` in metadata. Quarterly bot opens issues for runbooks with no execution logs in 180 days. Owners either refresh or archive.

When agents are decommissioned, delete their runbooks in the same PR that removes production config. Orphan runbooks cause panic clicks during unrelated incidents.

## Closing thought

The goal is not automation for its own sake. The goal is that a tired engineer at 2 AM performs the same correct sequence a well-rested team would choose at 2 PM — without relying on memory, Slack archaeology, or Sarah.

Put the steps in git. Test them. Link them from alerts. Agent incidents will still happen; they do not have to be adventures.

## Resources

- [Google SRE: Managing Incidents (Chapter 14)](https://sre.google/sre-book/managing-incidents/)
- [Rundeck Runbook Automation documentation](https://docs.rundeck.com/docs/manual/runbooks/)
- [Temporal.io documentation — workflows as code](https://docs.temporal.io/workflows)
- [PagerDuty Runbook documentation best practices](https://support.pagerduty.com/docs/runbooks)
- [AWS Well-Architected Operational Excellence pillar](https://docs.aws.amazon.com/wellarchitected/latest/operational-excellence-pillar/welcome.html)
