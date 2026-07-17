---
title: "AI Agents: Chatops Incident Bots"
slug: "agent-chatops-incident-bots"
description: "Incident bots in Slack fail when they spam threads or hallucinate root cause—reliable ChatOps for agent stacks means structured commands, read-only diagnostics, and LLM summaries gated behind verified telemetry."
datePublished: "2026-03-25"
dateModified: "2026-03-25"
tags: ["AI", "Agent", "Chatops"]
keywords: "ChatOps, incident bot, Slack ops, PagerDuty, runbook automation, LLM incident summary, on-call, agent outage, structured commands"
faq:
  - q: "Should incident bots use LLMs to diagnose outages automatically?"
    a: "Use LLMs to summarize already-fetched metrics and logs, never as the primary probe. Diagnostic commands should call verified APIs—Prometheus, your agent trace store, feature flag service—and the model formats output for humans who still decide action."
  - q: "How do I stop the bot from flooding the incident channel?"
    a: "Route alerts to a dedicated incident thread, dedupe by fingerprint, throttle proactive messages, and require slash commands for expensive queries. One bot message per state transition beats ten partial updates."
  - q: "What permissions should a ChatOps bot have?"
    a: "Read-only on observability and deployment metadata by default. Mutations—scale replicas, flip flags, kill sessions—require explicit slash commands with confirmation, role checks, and audit logs. Never embed admin API keys in LLM tool schemas."
  - q: "How do agent-specific incidents differ from classic service outages?"
    a: "Failures include provider 429 storms, retrieval empty rates, tool sandbox backlog, eval regressions, and cost anomalies—not just HTTP 5xx. Bots need playbooks keyed to agent stages and token spend, not only pod restarts."
---
At 2:14 a.m. the PagerDuty siren was the least noisy thing in `#incidents`. The ChatOps bot had cross-posted forty-seven messages: stack traces, a LLM-generated root cause blaming "database latency," and three duplicate `/status` responses because nobody configured deduplication. The actual issue was an embedding rate limit. The on-call engineer muted the channel and opened Grafana manually—the bot had trained the team to ignore it.

ChatOps incident bots for agent systems sit at the intersection of **alert fatigue** and **automation trust**. Done well, they collapse mean-time-to-context: who is impacted, which model route is hot, what changed in the last deploy. Done poorly, they become another noisy subscriber that hallucinates certainty during outages. This post covers architecture for bots that help without owning the incident.

## Separate signal from conversation

Split responsibilities into three layers:

| Layer | Role | Example |
|-------|------|---------|
| Alert router | Ingest pages, open incident, dedupe | PagerDuty → Slack parent message |
| Command bot | Deterministic slash commands | `/agent status`, `/deploy diff` |
| Summary agent | Optional LLM formatting | "Last 15m: 429 rate 12% on embed route" |

The summary agent **never** runs unless structured data already exists. Prompt it with JSON from commands, not raw Slack scrollback.

```typescript
// chatops/incidentBot.ts
import { App } from "@slack/bolt";
import { fetchAgentHealth } from "./diagnostics";

const app = new App({ token: process.env.SLACK_BOT_TOKEN });

const incidentDedupe = new Map<string, string>(); // fingerprint -> thread_ts

app.command("/agent-status", async ({ ack, respond, body }) => {
  await ack();
  const health = await fetchAgentHealth(); // Prometheus + trace backend
  await respond({
    response_type: "ephemeral",
    blocks: formatHealthBlocks(health), // no LLM here
  });
});

app.event("pagerduty.incident.triggered", async ({ event, client }) => {
  const fp = event.incident.fingerprint;
  if (incidentDedupe.has(fp)) return;

  const parent = await client.chat.postMessage({
    channel: process.env.INCIDENT_CHANNEL!,
    text: `:rotating_light: ${event.incident.title}`,
    metadata: { event_type: "incident_open", fingerprint: fp },
  });
  incidentDedupe.set(fp, parent.ts!);

  await client.chat.postMessage({
    channel: process.env.INCIDENT_CHANNEL!,
    thread_ts: parent.ts,
    text: "Run `/agent-status` and `/deploy-diff 2h` in this thread.",
  });
});
```

Thread-per-incident keeps the main channel readable. Parent message holds status emoji updates only—✅ mitigated, 🔥 active.

## Agent-aware diagnostics

Classic `/health` endpoints miss agent failures. Expose commands that query **stage-level signals**:

```typescript
// chatops/diagnostics/agentHealth.ts
export async function fetchAgentHealth(): Promise<AgentHealthSnapshot> {
  const [llm429, retrievalEmpty, toolP95, spendRate] = await Promise.all([
    promQuery('rate(agent_llm_errors{code="429"}[5m])'),
    promQuery('rate(agent_retrieval_empty[5m])'),
    promQuery('histogram_quantile(0.95, agent_tool_duration_seconds)'),
    promQuery('rate(agent_token_spend_dollars[5m])'),
  ]);

  return {
    llm429Rate: llm429,
    retrievalEmptyRate: retrievalEmpty,
    toolP95Seconds: toolP95,
    spendPerMinute: spendRate,
    degradedRoutes: await listDegradedModelRoutes(),
    lastDeploy: await lastDeployMetadata(),
  };
}
```

Playbooks map symptom clusters to suggested checks:

- 429 spike + flat error rate → check retry config and provider status
- Retrieval empty ↑ + latency flat → index lag or bad embedding deploy
- Spend ↑ + success rate flat → retry storm; link to game day doc
- Tool p95 ↑ → sandbox pool saturation

Store playbooks as markdown the bot links—not LLM-generated guesses.

## LLM summaries with guardrails

When you add summarization, constrain input and output:

```python
# chatops/summary_agent.py
SUMMARY_SYSTEM = """You summarize incident telemetry for on-call engineers.
Rules:
- Only state facts present in the JSON payload.
- If data is missing, say "unknown" — do not infer root cause.
- Max 6 bullet points. Include timestamps from payload.
- Never recommend destructive actions (delete, scale to zero)."""

def summarize_incident(snapshot: dict) -> str:
    return llm.generate(
        system=SUMMARY_SYSTEM,
        user=json.dumps(snapshot),
        temperature=0,
        max_tokens=300,
    )
```

Run summarization on a schedule (every ten minutes during SEV-1) triggered by a human `/summarize` or bot workflow—not on every alert flap. Compare summaries to prior snapshot; post only if materially changed.

## Mutations and blast radius

Bots that scale services or flip feature flags need **two-step confirm** and identity binding:

```typescript
app.command("/agent-disable-model-route", async ({ ack, command, respond }) => {
  await ack();
  if (!hasRole(command.user_id, "incident_commander")) {
    await respond("Requires incident_commander role.");
    return;
  }
  const route = command.text.trim();
  await respond({
    response_type: "ephemeral",
    text: `Confirm: disable route \`${route}\`? React ✅ on this message within 60s.`,
  });
  // confirmation handler calls flags API with audit log
});
```

Audit every mutation: user, incident fingerprint, prior value, new value, correlation ID. Agents processing user traffic should not share the same API token as ChatOps mutations.

## Testing bots before they page you

Incident bots fail silently until the real page. Test harness:

- **Fixture incidents** — replay PagerDuty webhooks into staging Slack
- **Command contract tests** — mock Prometheus; assert block format
- **Load test dedupe** — 100 identical alerts → one thread
- **Summary red-team** — inject misleading metric spikes; assert summary says "unknown" or cites data only

Record golden screenshots of block layouts. Slack rendering regressions break scanning at 3 a.m.

## Security and compliance

Bots read deployment metadata, customer impact counts, and sometimes log excerpts. Minimum controls:

- OAuth with scoped channels, not workspace admin
- Secrets in vault; rotate if posted accidentally to thread
- PII scrubbing before any LLM summary (strip user IDs from exemplar traces)
- Retention policy on incident threads aligned with compliance—export to ticket system, do not rely on Slack search alone

## Metrics for bot usefulness

Measure whether the bot earns its noise:

- Time from page to first **correct** diagnostic command run
- Percent incidents where bot-linked playbook matched actual cause (postmortem tag)
- Channel mute rate during incidents (proxy for fatigue)
- Duplicate message count per incident (target: ≤5 bot posts before human mitigates)

If mute rate climbs, disable proactive LLM summaries before stripping commands.

## Incident lifecycle hooks

Integrate the bot with your incident record system—not only Slack threads. On incident open, create a ticket with fingerprint, severity, and links to the parent message. On `/resolve`, post resolution summary back to the ticket and close PagerDuty only after a human confirms.

```typescript
// chatops/lifecycle.ts
export async function onIncidentResolved(threadTs: string, userId: string) {
  const timeline = await fetchThreadTimeline(threadTs);
  const ticket = await jira.findByFingerprint(timeline.fingerprint);
  await jira.addComment(ticket.id, {
    body: formatPostmortemSeed(timeline), // commands run, deploy diff, no LLM speculation
  });
  await pagerduty.resolve(timeline.incidentId, { resolved_by: userId });
  await slack.postMessage({
    channel: INCIDENT_CHANNEL,
    thread_ts: threadTs,
    text: `:white_check_mark: Incident resolved by <@${userId}>. Postmortem draft seeded in ${ticket.key}.`,
  });
}
```

Status transitions on the parent message—🔥 investigating, 🛠 mitigating, ✅ resolved—should be manual slash commands or emoji reactions from incident commanders, not automatic LLM guesses from metric noise. Automatic state changes train the channel to distrust the header.

For agent cost incidents, add `/agent-spend-top` showing tenants ranked by token burn in the last hour. That command has prevented hours of generic "scale the cluster" responses when one API key was misconfigured in a load test.

Publish bot command documentation in the same repo as runbooks. On-call should not grep Slack history to remember whether `/deploy-diff` accepts hours or commits.

## Closing

ChatOps incident bots for agent stacks should compress telemetry into actionable context—not perform automated root-cause analysis from vibes. Thread per incident, deterministic diagnostics, optional guarded summaries, and mutation gates turn Slack from a scream into a console. The embedding outage at 2:14 a.m. deserved one parent message and a `/agent-status` block—not forty-seven guesses.

## Resources

- [Slack Block Kit Builder](https://app.slack.com/block-kit-builder) — structured incident messages that scan at a glance
- [PagerDuty Slack integration](https://support.pagerduty.com/docs/slack-integration-guide) — parent message and thread patterns
- [Prometheus querying API](https://prometheus.io/docs/prometheus/latest/querying/api/) — backend for deterministic `/agent-status`
- [Google SRE: Incident response](https://sre.google/sre-book/incident-response/) — roles, communication norms, and bot boundaries
- [OpenAI production best practices](https://platform.openai.com/docs/guides/production-best-practices) — provider status and rate-limit playbooks for agent routes
