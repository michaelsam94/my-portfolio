---
title: "AI Agents: Function Concurrency Limits"
slug: "agent-function-concurrency-limits"
description: "Controlling parallel tool and function execution in agent runtimes — semaphores, per-tenant quotas, Lambda reserved concurrency, bulkhead patterns, and backpressure for LLM orchestrators."
datePublished: "2026-04-19"
dateModified: "2026-04-19"
tags: ["AI", "Agent", "Function"]
keywords: "function concurrency, agent tool limits, semaphore, bulkhead, Lambda reserved concurrency, rate limiting, backpressure, parallel tool calls"
faq:
  - q: "Why do agent platforms need function concurrency limits beyond LLM rate limits?"
    a: "LLM rate limits cap tokens and requests; they do not cap downstream tool fan-out. A single agent turn can invoke five tools in parallel, each hitting databases, payment APIs, or sandboxed code runners. Without function-level limits, one chat session can exhaust connection pools, trigger partner API bans, or spawn runaway sub-agent trees."
  - q: "Should concurrency limits apply per user, per tenant, or globally?"
    a: "All three, layered. Global limits protect shared infrastructure. Per-tenant limits enforce plan tiers and noisy-neighbor isolation. Per-session or per-user limits prevent a single runaway agent loop from monopolizing a tenant's quota. Expose remaining capacity in API responses so clients can backoff gracefully."
  - q: "How do you handle tools with different latency profiles under one limit?"
    a: "Use weighted semaphores or separate bulkheads per tool class: fast read tools (search, cache) get higher concurrency; slow or expensive tools (code execution, external API) get lower caps. A single global semaphore unfairly blocks quick lookups when one sandbox compile occupies the slot."
  - q: "What happens when an agent hits a concurrency limit mid-turn?"
    a: "Queue with timeout, return a structured 'resource_exhausted' tool result the model can reason about, or degrade to sequential execution for non-critical tools. Never fail silently or hang indefinitely — the LLM will retry aggressively and amplify load."
---
The first production incident I traced to missing function concurrency limits did not involve the LLM at all. A support agent with parallel tool calling enabled fired six database lookups, three HTTP fetches, and a sandboxed Python execution in one turn. Each sub-call was "within limits" individually. Together they saturated the connection pool, tripped a partner API's abuse detector, and left five hundred unrelated sessions timing out on auth checks. Token rate limits on GPT-4 were fine. **Function concurrency** — how many tool invocations run at once, for whom, and with what backpressure — was undefined.

Agent runtimes expose tools to the model: search, calculators, CRM writes, code interpreters, sub-agent delegation. Modern models eagerly parallelize independent tool calls. That parallelism is a feature until your infrastructure treats every tool as free. Concurrency limits are the bulkhead between model enthusiasm and platform survival.

## The concurrency stack for agent systems

Think in layers, each with distinct counters and reset windows:

| Layer | What it limits | Example cap |
|-------|----------------|-------------|
| Global platform | Total in-flight tool executions | 2,000 |
| Tenant / plan tier | Concurrent tools per organization | 50 (Pro), 10 (Free) |
| Session / run | Parallel tools per agent invocation | 5 |
| Tool class bulkhead | Per-tool-type slots | 20 search, 3 sandbox |
| Downstream dependency | External API in-flight | 100 req to Stripe |

Limits compose: a tool call must acquire tenant slot AND tool-class slot AND optional dependency slot before execution. Release in `finally` blocks — crashed tools that leak semaphores are a classic outage source.

## Semaphore implementation at the orchestrator

The orchestrator sits between the LLM response parser and tool executors. When the model returns multiple `tool_calls`, the orchestrator schedules them — not the model.

```typescript
import { Semaphore, withTimeout } from "./concurrency";

interface ToolCall {
  id: string;
  name: string;
  args: unknown;
}

interface ConcurrencyConfig {
  sessionMax: number;
  tenantMax: number;
  toolBulkheads: Record<string, number>;
  acquireTimeoutMs: number;
}

class AgentToolExecutor {
  private tenantSemaphores = new Map<string, Semaphore>();
  private toolBulkheads: Record<string, Semaphore>;

  constructor(private config: ConcurrencyConfig) {
    this.toolBulkheads = Object.fromEntries(
      Object.entries(config.toolBulkheads).map(([k, n]) => [k, new Semaphore(n)]),
    );
  }

  private tenantSem(tenantId: string): Semaphore {
    if (!this.tenantSemaphores.has(tenantId)) {
      this.tenantSemaphores.set(tenantId, new Semaphore(this.config.tenantMax));
    }
    return this.tenantSemaphores.get(tenantId)!;
  }

  async executeParallel(
    tenantId: string,
    calls: ToolCall[],
    sessionSem: Semaphore,
  ): Promise<ToolResult[]> {
    const capped = calls.slice(0, this.config.sessionMax);
    return Promise.all(
      capped.map((call) => this.executeOne(tenantId, call, sessionSem)),
    );
  }

  private async executeOne(
    tenantId: string,
    call: ToolCall,
    sessionSem: Semaphore,
  ): Promise<ToolResult> {
    const bulkhead = this.toolBulkheads[call.name] ?? this.toolBulkheads.default;
    const acquired =
      (await withTimeout(sessionSem.acquire(), this.config.acquireTimeoutMs)) &&
      (await withTimeout(this.tenantSem(tenantId).acquire(), this.config.acquireTimeoutMs)) &&
      (await withTimeout(bulkhead.acquire(), this.config.acquireTimeoutMs));

    if (!acquired) {
      return {
        toolCallId: call.id,
        status: "resource_exhausted",
        error: `Concurrency limit reached for ${call.name}. Retry sequentially or backoff.`,
      };
    }

    try {
      const result = await this.runTool(call);
      return { toolCallId: call.id, status: "ok", output: result };
    } finally {
      bulkhead.release();
      this.tenantSem(tenantId).release();
      sessionSem.release();
    }
  }
}
```

Structured `resource_exhausted` responses give the model something actionable. Models that see opaque timeouts often re-issue the same parallel batch, making overload worse.

## Serverless and Lambda reserved concurrency

For tools implemented as Lambda functions, **reserved concurrency** per function prevents one agent tool from consuming the entire account concurrency pool. Unreserved functions compete for the remainder; a viral sandbox tool can starve login webhooks.

```yaml
# serverless.yml excerpt — bulkhead per tool
functions:
  agentWebSearch:
    handler: handlers/search.handler
    reservedConcurrency: 100

  agentCodeSandbox:
    handler: handlers/sandbox.handler
    reservedConcurrency: 10   # expensive; strict cap
    timeout: 60

  agentCrmWrite:
    handler: handlers/crm.handler
    reservedConcurrency: 25
    events:
      - sqs:
          arn: !GetAtt ToolQueue.Arn
          batchSize: 1            # avoid double parallelism (SQS batch × tool parallel)
```

When Lambda throttles (`TooManyRequestsException`), map it to the same structured exhaustion response. Consider SQS-backed tool queues for burst absorption — concurrency becomes `reserved × pollers` with visible backlog metrics.

## Sub-agent delegation multiplies concurrency

Agents that spawn sub-agents multiply tool concurrency exponentially. A parent with five parallel tools, each invoking a sub-agent with five tools, creates twenty-five downstream executions without nested limits.

Apply **depth budgets** and **multiplicative caps**:

```python
@dataclass
class RunContext:
    tenant_id: str
    depth: int = 0
    max_depth: int = 3
    inherited_session_budget: int = 5

def remaining_parallel_budget(ctx: RunContext) -> int:
    # Each depth level splits the session budget
    return max(1, ctx.inherited_session_budget // (2 ** ctx.depth))

async def delegate_subagent(ctx: RunContext, task: str) -> str:
    if ctx.depth >= ctx.max_depth:
        raise DelegationLimitExceeded(f"max depth {ctx.max_depth}")
    child = RunContext(
        tenant_id=ctx.tenant_id,
        depth=ctx.depth + 1,
        inherited_session_budget=remaining_parallel_budget(ctx),
    )
    return await run_agent(child, task)
```

Log `depth`, `parent_run_id`, and `tool_name` on every span. Flame graphs of agent runs without depth tags are unreadable during incidents.

## Backpressure and queueing strategies

When demand exceeds limits, three strategies exist: **reject** (fast fail with retry-after), **queue** ( absorb bursts, risk latency), **shed** (drop low-priority tools). Agent UX generally prefers bounded queues over hard reject for user-initiated turns, but reject is correct for background sync jobs.

Queue depth must be bounded. An unbounded queue masks overload until memory explodes. Expose `queue_depth` and `estimated_wait_ms` to observability; page when p95 wait exceeds conversational tolerance (~2–3 seconds for inline tools).

For **streaming agent UIs**, emit progress events when tools wait on semaphores: "Waiting for available sandbox slot (2 ahead)." Transparency reduces duplicate user submits.

## Fairness across tenants

Noisy-neighbor isolation requires per-tenant semaphores, not just global caps. A enterprise tenant running batch evaluation jobs should not consume all sandbox slots for free-tier interactive users.

**Weighted fair queuing** assigns each tenant a deficit counter — tenants below their fair share get priority when slots free up. Simpler approach: hard tenant caps with overflow to a low-priority queue processed only when global utilization < 70%.

Audit tenant-level concurrency config in plan definitions. Sales promises of "unlimited agents" without engineering caps become platform incidents.

## Security and abuse considerations

Concurrency limits are abuse controls. An attacker triggering parallel code-sandbox tools attempts resource exhaustion or fork bombs. Combine concurrency with:

- Per-user authentication before tool execution
- CPU and memory limits inside sandboxes (cgroups, Firecracker microVMs)
- Egress network policies on tool runners
- Cost attribution per tenant for anomaly detection

A tenant whose tool concurrency constantly pegs at cap may be compromised or misconfigured — alert on sustained 100% utilization, not just errors.

## Testing concurrency behavior

Load tests must include **parallel tool call patterns**, not sequential REST hammering. Simulate a model returning 8 tool calls per turn with 200 concurrent sessions.

Chaos tests: kill tool workers mid-execution and verify semaphores release. Property test: acquired slots never exceed configured maximum under random scheduling.

Integration test case: when sandbox bulkhead is saturated, search tools still succeed — bulkhead isolation verified.

## Observability and SLOs

Metrics to emit: `tool_concurrency_inflight{tool, tenant}`, `tool_acquire_wait_ms`, `tool_resource_exhausted_total`, `semaphore_available{pool}`. Traces should link parent LLM span to child tool spans with concurrency wait events.

SLO example: 99% of read-class tools start execution within 500 ms of schedule time (acquire wait + queue). Sandbox tools may have a looser SLO — document per class.

## Closing

Function concurrency limits are load-bearing infrastructure for any agent that parallelizes tools — which is every modern model default. Layer global, tenant, session, and tool-class bulkheads; return structured exhaustion to the model; cap sub-agent depth; and test with parallel patterns, not sequential load scripts. Token limits protect your OpenAI bill. Concurrency limits protect everything behind the tools.

## Resources

- [AWS Lambda: Reserved Concurrency](https://docs.aws.amazon.com/lambda/latest/dg/configuration-concurrency.html)
- [Microsoft: Bulkhead Pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/bulkhead)
- [OpenAI: Parallel Function Calling](https://platform.openai.com/docs/guides/function-calling/parallel-function-calling)
- [Google Cloud: Concurrency Control for Cloud Run](https://cloud.google.com/run/docs/about-concurrency)
- [Netflix Hystrix (historical bulkhead reference)](https://github.com/Netflix/Hystrix/wiki/How-it-Works#ThreadPool)
