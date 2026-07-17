---
title: "AI Agents: Chaos Monkey Game Days"
slug: "agent-chaos-monkey-game-days"
description: "Random prod failures teach little about agent systems—structured game days that kill LLM providers, vector indexes, and tool sandboxes in staging reveal retry storms and silent degradation before users do."
datePublished: "2026-04-03"
dateModified: "2026-04-03"
tags: ["AI", "Agent", "Chaos"]
keywords: "chaos engineering, game day, LLM failure injection, agent resilience, fault injection, retry storms, graceful degradation, staging drills"
faq:
  - q: "How is a game day different from running Chaos Monkey in production?"
    a: "Game days are scheduled, scoped exercises with explicit hypotheses, observers, and stop conditions. Chaos Monkey randomly terminates instances; game days inject domain-specific faults—429 bursts from the LLM API, empty retrieval results, tool timeout loops—and measure whether agents degrade gracefully."
  - q: "Should we run agent chaos drills in production or staging?"
    a: "Start in staging with production-shaped traffic replay and synthetic agent sessions. Graduate to limited production game days only after runbooks exist, blast radius is tenant-scoped, and you can abort via a central kill switch within seconds."
  - q: "What faults matter most for LLM agent stacks?"
    a: "Provider rate limits, embedding service saturation, vector DB partial outage, tool sandbox OOM, stale cache returning wrong chunks, and cascading retries that multiply token spend 10× while user-visible latency stays flat."
  - q: "How do we score a successful game day?"
    a: "Define pass criteria upfront: max error budget burn, no unbounded retry loops, fallback model engaged within N seconds, incident bot pages fired once (not 400 times), and post-drill action items with owners—not whether everything stayed green."
---
The team had circuit breakers on paper and retries everywhere in code. During a game day nobody remembered to schedule, a staging inject killed the primary embedding endpoint for ninety seconds. Agent sessions did not fail—they **succeeded expensively**. Each retrieval miss triggered three alternate index queries, two reranker calls, and a fallback to a larger model. Spend graphs spiked while success rate stayed at 99.1%. Users would have noticed latency; finance would have noticed the invoice.

Chaos Monkey popularized random failure in microservices. Agent systems need **hypothesis-driven game days** because failure is rarely a dead pod—it is wrong context, runaway tool loops, and silent model substitution. This post covers how to design, run, and learn from chaos drills aimed at LLM orchestration—not just infrastructure.

## What agent failures actually look like

Traditional chaos experiments terminate instances and watch Kubernetes reschedule. Agent pipelines fail differently:

| Fault injected | User-visible symptom | Hidden damage |
|----------------|---------------------|---------------|
| LLM 429 burst | Slow replies | Retry storm, 5× token cost |
| Vector DB read timeout | "I don't know" | Empty context, confident hallucination |
| Tool sandbox hang | Spinner forever | Worker pool exhaustion |
| Stale RAG cache | Wrong answer | High confidence, no error flag |

Game day hypotheses should name the failure mode you fear, not the infrastructure knob you turn.

Example hypothesis: *When the reranker is unavailable for two minutes, the agent serves cached top-3 chunks and surfaces a low-confidence banner within five seconds, without more than two LLM round-trips per user message.*

## Scaffolding a safe game day

Before injecting faults, assemble four controls:

1. **Kill switch** — single flag disables all injectors and restores baseline routes
2. **Blast radius** — staging tenant, synthetic users, or 1% canary cohort only
3. **Observers** — SRE, ML platform, and product on-call in a war room channel
4. **Budget caps** — max spend and max concurrent sessions during the drill

```yaml
# chaos/agent-game-day.yaml
gameDay:
  id: gd-2026-04-embedding-outage
  environment: staging
  durationMinutes: 45
  abortOn:
    - metric: agent.token_spend.rate
      threshold: 3.0  # 3x baseline
      window: 5m
    - metric: agent.session.error_rate
      threshold: 0.15
  injectors:
    - name: embedding-unavailable
      target: embedding-service
      fault: connection_refused
      startAfterMinutes: 10
      durationMinutes: 3
    - name: llm-throttle
      target: llm-gateway
      fault: http_429
      rate: 0.4
      startAfterMinutes: 20
      durationMinutes: 5
  successCriteria:
    - fallback_model_activated_within_seconds: 8
    - max_llm_calls_per_session_p99: 6
    - chatops_incident_created: exactly_once
```

Store game day configs in git. Re-run the same injectors after refactors to detect resilience regressions.

## Injectors tailored to agent paths

Build injectors at **semantic boundaries**, not only network layers:

**Provider throttle.** Return 429 with `Retry-After` headers matching your largest vendor's behavior. Verify client respects backoff and does not fan out to three backup keys simultaneously.

**Retrieval empty set.** Force vector search to return zero rows. Assert the agent admits missing context rather than inventing policy answers.

**Tool latency staircase.** Add 0s, 5s, 30s delays to sandboxed tool calls. Catch orchestrators that parallelize ten tools without a global deadline.

**Context truncation.** Silently drop middle chunks from assembled prompts. Tests whether citations still align with claims—many agents fail this silently.

```typescript
// chaos/injectors/retrievalEmpty.ts
import { FaultInjector } from "./types";

export const retrievalEmptyInjector: FaultInjector = {
  name: "retrieval-empty",
  matches: (ctx) => ctx.stage === "vector_search",
  apply: async (ctx) => {
    ctx.span.addEvent("chaos.retrieval_empty");
    return { ...ctx, results: [], injected: true };
  },
  rollback: async (ctx) => ctx,
};
```

Wire injectors through a middleware layer so production code paths execute—avoid separate "chaos branch" binaries that never ship.

## Measuring retry storms

The deadliest agent incidents look healthy on success-rate dashboards. Instrument **work amplification**:

```typescript
// metrics/agentAmplification.ts
metrics.createHistogram("agent.llm.calls_per_session");
metrics.createCounter("agent.retry.reason", { description: "429|timeout|empty_context" });

export function trackSession(sessionId: string) {
  let llmCalls = 0;
  return {
    onLlmCall: () => {
      llmCalls++;
      if (llmCalls > 8) {
        metrics.counter("agent.retry.storm_suspected").add(1, { sessionId });
      }
    },
    flush: () => {
      histogram.record(llmCalls, { sessionId });
    },
  };
}
```

During game days, plot LLM calls per session, tool invocations per turn, and dollars per synthetic user alongside latency percentiles. A pass with 2s p99 and 12× cost is a failure.

## Game day runbook rhythm

A ninety-minute session beats an ad hoc afternoon:

| Phase | Duration | Activity |
|-------|----------|----------|
| Brief | 10 min | Hypotheses, roles, abort criteria |
| Baseline | 10 min | Normal load, confirm metrics |
| Inject A | 15 min | Single fault, observe |
| Recovery | 10 min | Rollback, verify clean state |
| Inject B | 15 min | Compound fault (optional) |
| Retro | 30 min | Timed findings, action items |

Record timeline annotations on dashboards—`T+12m embedding fault start`—so postmortems align logs with injectors.

ChatOps bots should announce inject state to the war room, not page production on-call unless abort thresholds fire. Train the bot during game days; it is part of the system under test.

## From staging to controlled production

Production game days require tighter contracts:

- **Tenant allowlist** — internal dogfood or consenting design partners
- **Synthetic traffic mix** — never experiment on unpaid conversion funnels during peak
- **Financial guardrails** — hard session spend caps and automatic session kill
- **Comms** — status page internal-only banner if user-visible latency shifts

Start with read-path faults (retrieval degradation, cache poison) before write-path faults (tool mutations, billing side effects). The blast radius of a wrong agent action exceeds a slow response.

## Compound faults and agent loop detection

Single-fault drills teach baseline behavior; **compound faults** expose orchestration bugs. Pair embedding outage with LLM throttle—the worst production combo—only after single-fault passes. Watch for agent loops: tool call → empty result → replan → same tool call.

```typescript
// chaos/guards/loopDetector.ts
export function trackToolLoop(sessionId: string, toolName: string): void {
  const key = `${sessionId}:${toolName}`;
  const count = (loopCounts.get(key) ?? 0) + 1;
  loopCounts.set(key, count);
  if (count >= 4) {
    metrics.counter("chaos.agent_tool_loop").add(1, { sessionId, toolName });
    throw new AgentLoopAbortError(sessionId);
  }
}
```

During compound injects, assert the loop detector fires before token spend exceeds 3× baseline. If it does not, your guard is cosmetic. Document expected degradation copy—users should see "search temporarily limited" not a hallucinated answer.

Game day notes should capture **time-to-detect loop** separately from **time-to-recover dependency**. Teams often fix the provider first while loops continue burning budget in the background.

Schedule the first game day before your next major model route change or retrieval index migration. Those deploys multiply failure modes; validating resilience the week after launch is too late to influence architecture decisions.

## Closing the loop

Every game day produces findings; without owners they become trivia. File tickets with severity tied to user impact: retry storm = P1, missing fallback banner = P2, chatops duplicate pages = P3.

Re-run injectors in CI at reduced intensity—five-second embedding fault on each main merge—to catch regressions cheaper than quarterly drills alone.

Chaos Monkey asked whether your instances survive termination. Agent game days ask whether your **orchestration survives intelligence**—ambiguous errors, partial context, and optimistic retries. Schedule the drill before the invoice teaches the lesson.

## Resources

- [Principles of Chaos Engineering](https://principlesofchaos.org/) — hypothesis, blast radius, and production learning culture
- [Netflix Chaos Monkey](https://github.com/Netflix/chaosmonkey) — origin of random instance termination; compare to scoped injectors
- [Gremlin fault injection docs](https://www.gremlin.com/docs/) — scheduling, rollback, and game day tooling patterns
- [Google SRE: Testing for reliability](https://sre.google/sre-book/testing-reliability/) — load tests, disaster drills, and success criteria
- [OpenAI rate limit guidance](https://platform.openai.com/docs/guides/rate-limits) — realistic 429 behavior for provider injectors
