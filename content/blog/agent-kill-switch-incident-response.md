---
title: "Agent Kill Switches and Incident Response Playbooks"
slug: "agent-kill-switch-incident-response"
description: "Design layered kill switches for production agent systems—global halt, tenant freeze, tool blocks, model routing fallback—and wire them into incident response with audit trails and measured recovery."
datePublished: "2026-03-13"
dateModified: "2026-03-13"
tags: ["AI Agents", "Incident Response", "Safety", "Operations"]
keywords: "agent kill switch, incident response, AI safety halt, feature flags, circuit breaker, run cancellation, blast radius"
faq:
  - q: "What is the difference between a kill switch and a circuit breaker for agents?"
    a: "A kill switch is an intentional operator control that stops some or all agent behavior immediately—human-initiated, audited, often via flag or admin API. A circuit breaker is automatic: error rates, cost spikes, or guardrail violations trip it without waiting for a human. Production stacks need both; breakers buy minutes, kill switches stop bleeding during incidents."
  - q: "At what granularity should agent kill switches operate?"
    a: "Layer them: global platform halt, per-tenant freeze, per-agent definition disable, per-tool block, and per-model route off. Incidents rarely need global halt—misconfigured tool in one agent should not take down unrelated tenants. Each layer needs an owner, TTL, and automatic expiry reminder so you don't forget the switch is on."
  - q: "How fast should a kill switch propagate to all workers?"
    a: "Target under 30 seconds p99 for hard blocks on new runs; in-flight runs may take longer to cancel gracefully. Use a central flag store with pub/sub (Redis, LaunchDarkly, etcd watch) plus edge cache with max 5–10s TTL and a 'version' header workers check every request. Run game days to measure actual propagation, not config intent."
  - q: "What should incident response do after activating a kill switch?"
    a: "Follow a fixed sequence: assign incident commander, activate narrowest effective switch, preserve logs and traces with incident ID, notify affected tenants if user-visible, root-cause without re-enabling blindly, re-enable via canary with enhanced monitoring, and publish blameless postmortem with switch effectiveness metrics."
---

The shopping agent sent 12,000 refund emails in nine minutes. Guardrails flagged anomaly at email 400, but the alert routed to a Slack channel nobody watched on a holiday. Engineering toggled "maintenance mode" in the admin UI—which only blocked the marketing site, not the agent worker pool. The actual stop required SSH and scaling a deployment to zero. Total damage: six figures and a board question about "AI kill switches."

If you ship agents that touch money, inboxes, or infrastructure, you ship **kill switches** before you ship the demo. Incident response for agents is not generic ITIL with a chatbot skin—it is stopping unbounded loops, cutting tool access, preserving forensic evidence, and recovering without re-triggering the failure mode.

## Kill switch layers

Design concentric rings of control:

| Layer | Scope | Effect | Typical trigger |
|-------|-------|--------|-----------------|
| L0 Global | Platform | No new runs; cancel optional | Catastrophic model compromise |
| L1 Tenant | Customer | Freeze tenant runs | Abuse, billing dispute |
| L2 Agent | Agent definition | Disable one agent version | Bad prompt deploy |
| L3 Tool | Tool registry | Block tool invocation | Leaked API key, bad SQL |
| L4 Model route | Inference | Fallback model or reject | Provider outage, cost runaway |
| L5 Spend | Budget | Hard cap per hour | Token burn anomaly |

Each layer maps to a flag key, admin API, and runbook section. Narrowest effective layer first—L0 is last resort.

Flag schema example:

```json
{
  "platform_halt": false,
  "tenant_freeze": {
    "acme-corp": { "until": "2026-03-13T18:00:00Z", "reason": "INC-4421" }
  },
  "disabled_agents": ["shopping-v3"],
  "blocked_tools": ["send_email", "stripe_refund"],
  "model_overrides": {
    "gpt-4o": "disabled"
  },
  "max_parallel_runs_global": 500
}
```

Store in durable KV with revision numbers; workers subscribe to changes.

## Control plane implementation

Central service exposes authenticated break-glass API:

```typescript
// POST /internal/v1/kill-switch
interface KillSwitchRequest {
  layer: "global" | "tenant" | "agent" | "tool" | "model";
  target?: string;
  action: "enable" | "disable";
  incident_id: string;
  actor: string;
  ttl_minutes?: number;
}

async function applyKillSwitch(req: KillSwitchRequest): Promise<void> {
  await authz.assertBreakGlass(req.actor, req.layer);
  const revision = await flags.patch(req);
  await audit.log({
    event: "kill_switch",
    ...req,
    revision,
    at: new Date().toISOString(),
  });
  await bus.publish("flags.updated", { revision });
  await pager.notifyIncidentChannel(req.incident_id, `Kill switch ${req.action} ${req.layer}:${req.target ?? "*"}`);
}
```

Workers check flags at **run start** and **tool invoke**—not once at boot:

```python
def assert_run_allowed(ctx: RunContext) -> None:
    flags = flag_client.get(version=ctx.flag_version)  # poll every N sec or push
    if flags.platform_halt:
        raise RunBlockedError("platform_halt", incident=flags.incident_id)
    if ctx.tenant_id in flags.tenant_freeze:
        raise RunBlockedError("tenant_frozen")
    if ctx.agent_id in flags.disabled_agents:
        raise RunBlockedError("agent_disabled")
```

Cache flags locally with 5s TTL max; accept occasional stale allow for 5s vs 5-minute stale cache disasters.

## Cancelling in-flight runs

New-run blocks are insufficient for runaway loops. Support **run cancellation**:

```sql
UPDATE agent_runs
SET status = 'cancel_requested', cancel_reason = 'INC-4421'
WHERE tenant_id = 'acme-corp' AND status = 'running';
```

Workers poll or subscribe:

```typescript
async function executeRun(runId: string) {
  for await (const step of orchestrator.steps(runId)) {
    if (await runs.isCancelRequested(runId)) {
      await orchestrator.compensate(runId);
      return;
    }
    await step.run();
  }
}
```

Compensation may reverse partial tool effects—design tools idempotently where possible. Email already sent cannot un-send; kill switch limits **future** sends.

## Automatic circuit breakers

Trip breakers before humans wake up:

```yaml
# prometheus alertmanager → webhook → auto-freeze tenant
groups:
  - name: agent-safety
    rules:
      - alert: AgentToolErrorBurst
        expr: rate(agent_tool_errors_total[5m]) > 50
        for: 2m
        labels:
          severity: critical
        annotations:
          action: auto_block_tool
```

Auto-actions require:

- Max duration (auto-expire in 60m unless human extends)
- Page on-call simultaneously—automation assists, not replaces
- Audit trail linking alert fingerprint to flag change

```python
def auto_block_tool(tool_name: str, alert_id: str):
    flags.block_tool(tool_name, ttl_minutes=60, reason=f"auto:{alert_id}")
    incidents.create_draft(alert_id, suggested_action=f"blocked tool {tool_name}")
```

## Incident response timeline

Standard playbook (adjust to your org):

**T+0 — Detect**  
Alerts: spend rate, tool error burst, user reports, guardrail model score.

**T+5 min — Triage**  
Incident commander assigned. Severity set. Comms channel opened.

**T+10 min — Contain**  
Activate narrowest kill switch. Screenshot flag state. Do not deploy unrelated fixes concurrently.

**T+30 min — Diagnose**  
Trace exemplars, prompt version diff, tool schema changes, deployment correlation.

**T+60 min — Eradicate**  
Fix root cause on branch; do not re-enable production until verified in staging.

**T+2h — Recover**  
Canary re-enable: 1% traffic → 10% → 100% with elevated monitoring.

**T+1 week — Postmortem**  
Blameless doc: timeline, switch effectiveness, action items.

Runbook one-pager template:

```markdown
## Agent incident quick reference
1. Dashboard: /ops/agents/overview
2. Kill switch UI: /admin/break-glass (requires Okta break-glass group)
3. Narrow containment order: tool → agent → tenant → global
4. Preserve: export runs where tool_name=X since T-1h
5. Comms: status.example.com template "agent-degraded"
6. Recovery: flag canary script `./scripts/flags-canary.sh --layer tool --target send_email`
```

## Observability during incidents

Metrics to watch while switch is active:

- `agent.runs.blocked_total` by reason
- `agent.runs.in_flight` — should decay after cancel
- `agent.tool.invocations` — should hit zero for blocked tools
- `agent.spend.rate` — should drop within one billing window

Logs must include `incident_id`, `flag_revision`, `run_id`, `tool_name`. Avoid deleting logs during incident—legal hold may apply.

## Access control and abuse of kill switches

Break-glass is attractive to attackers and rogue insiders:

- MFA + short-lived elevation to toggle L0/L1
- Two-person rule for global halt in some enterprises
- All changes append-only audited
- Alert on any kill switch API call—success or failure

Test that compromised admin JWT cannot call kill switch without break-glass group.

## Customer communication

Tenant freeze is user-visible. Pre-write templates:

- "Agent automation paused for your account—manual support available"
- Not: "We killed your AI" or silent failure

Surface banner in product when `tenant_freeze` active, with support link.

## Game days

Quarterly exercises:

1. Inject runaway tool mock in staging
2. On-call finds alert, activates L3 tool block
3. Measure time-to-stop new invocations
4. Practice canary recovery

Track MTTR and switch propagation p99. Improve what you measure.

## Relationship to model safety classifiers

Guardrail models (prompt injection, PII leak) complement kill switches—they reduce incident frequency. They do not replace halt controls when classifier fails open or latency spikes. Architecture:

```
Request → classifier → orchestrator → tools
              ↓ fail closed on high risk
         kill switch check at orchestrator + each tool
```

Redundant gates at run and tool boundaries contain blast radius when one layer fails.

## The takeaway

Agent kill switches are layered, audited, fast-propagating controls—not a hidden env var. Pair human break-glass with automatic circuit breakers, cancel in-flight runs, and incident playbooks that default to narrow containment. Rehearse in game days, expire flags automatically, and recover via canary. The email blast incident is cheaper as a drill than as a holiday surprise.

## Resources

- [Google SRE — Managing incidents](https://sre.google/sre-book/managing-incidents/)
- [LaunchDarkly — Kill switches documentation](https://docs.launchdarkly.com/home/observability/kill-switch)
- [NIST SP 800-61 — Computer security incident handling guide](https://csrc.nist.gov/publications/detail/sp/800-61/rev-2/final)
- [OpenAI — Safety best practices for API deployments](https://platform.openai.com/docs/guides/safety-best-practices)
- [OWASP — LLM Top 10 (unbounded consumption)](https://owasp.org/www-project-top-10-for-large-language-model-applications/)
