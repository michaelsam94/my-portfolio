---
title: "Building Reliable AI Agents: Retries, Idempotency, Tool Design"
slug: "building-reliable-ai-agents"
description: "How to build reliable AI agents: idempotent tools, safe retries, timeouts, and error handling. Distributed-systems discipline applied to LLM agent loops."
datePublished: "2026-03-11"
dateModified: "2026-03-11"
tags: ["AI Agents", "Reliability", "Distributed Systems", "LLM"]
keywords: "reliable AI agents, agent reliability, tool design, agent retries, idempotent agents, error handling"
faq:
  - q: "What makes an AI agent unreliable?"
    a: "Non-deterministic model output combined with side-effecting tools and naive retries. If a tool call charges a card or sends an email and the agent retries after a timeout, you get duplicate actions. Reliability comes from idempotent tools, bounded retries, and clear error contracts."
  - q: "How do you make agent tools idempotent?"
    a: "Give each side-effecting operation a client-supplied idempotency key so repeated calls with the same key produce one result. The tool checks whether that key was already processed and returns the prior result instead of acting twice, which makes retries safe."
  - q: "Should AI agents retry failed tool calls automatically?"
    a: "Yes, but only for transient, retryable errors, with bounded attempts and backoff. Retrying validation errors or business-rule rejections just wastes tokens and time. The error type must tell the agent whether a retry can possibly succeed."
---

Most "unreliable AI agent" problems have nothing to do with the model. They're the same problems distributed systems engineers have fought for decades — retries, timeouts, partial failures, duplicate side effects — wearing a new hat. The model just makes them worse, because now the thing deciding *when* to call a tool is non-deterministic and occasionally makes things up.

I build agents that touch real systems: charging sessions, payments, work orders. When an agent's tool call has consequences in the physical world, "usually works" isn't good enough. Reliable AI agents come from applying boring, proven engineering discipline to the tool layer, not from a cleverer prompt.

## Design tools like a public API, not a function call

The agent is an untrusted, non-deterministic client of your tools. Treat every tool the way you'd treat an endpoint exposed to the internet: validate inputs, return structured errors, and never assume the caller will behave.

That means tools should have narrow, well-typed inputs and outputs. A tool called `updateOrder(anything)` invites the model to send garbage; a tool called `setOrderStatus(orderId: string, status: "shipped" | "cancelled")` constrains it. Use [structured outputs and function calling](https://blog.michaelsam94.com/structured-outputs-function-calling/) so the model's tool arguments are schema-validated before your code ever runs. Reject invalid arguments with a clear message the model can act on, rather than half-executing.

## Idempotency is the load-bearing wall

Here's the failure that will bite you: the agent calls `chargeCard`, the call succeeds on the server, but the response times out before reaching the agent. The agent, seeing no response, retries. Now you've charged twice.

The fix is the same one payment systems use — **idempotency keys**. The agent (or the orchestration layer) generates a key per logical operation; the tool deduplicates on it.

```python
def charge_card(amount, customer_id, idempotency_key):
    existing = ledger.get(idempotency_key)
    if existing:
        return existing            # already done — return prior result
    result = payment_gateway.charge(amount, customer_id)
    ledger.put(idempotency_key, result)
    return result
```

With this, a retry is safe: the same key returns the same result instead of acting again. Any tool with side effects — sending a message, creating a record, moving money — needs this. Read-only tools (search, fetch) are naturally idempotent and don't. This is exactly the discipline from [idempotency in distributed systems](https://blog.michaelsam94.com/idempotency-distributed-systems/), applied to the agent's hands.

## Retries: bounded, backed off, and only when they can help

Naive agents retry everything, which burns tokens and time on errors that will never succeed. The tool's error contract has to tell the agent whether a retry is worth attempting. I split errors into three kinds:

| Error class | Example | Agent response |
|---|---|---|
| Transient | timeout, 503, rate limit | Retry with backoff, bounded attempts |
| Permanent | validation failure, 404 | Don't retry; change approach or stop |
| Business rule | "insufficient funds" | Don't retry; report to user/escalate |

Encode this in the returned error so the model isn't guessing:

```json
{
  "error": {
    "type": "rate_limit",
    "retryable": true,
    "retry_after_ms": 2000,
    "message": "Provider rate limit hit."
  }
}
```

Cap total attempts (I usually allow 2-3 retries per tool call) and put backoff between them. And crucially, cap the *whole agent loop* — a max step count and a wall-clock deadline — so a confused agent can't spin forever racking up cost. An agent stuck retrying a permanent error is a runaway bill.

## Timeouts and the "did it happen?" problem

Every tool call needs a timeout, because a hung call blocks the whole agent. But a timeout creates ambiguity: you don't know whether the operation completed. This is why idempotency and timeouts are a package deal — the timeout lets you give up waiting, and idempotency lets you safely retry to find out. Where you can, make tools return the current *state* ("order is now shipped") rather than an *event* ("shipped it"), so a retry that reads state is always safe and informative.

## Make the agent's plan inspectable

Reliability isn't only about not breaking things; it's about knowing what happened when something does. Every tool call, its arguments, its result, and every model decision should be traced. When an agent does something wrong at 3am, you need the full trajectory to debug it, and aggregate traces tell you which tools fail most and where loops stall.

This is where [LLM observability with OpenTelemetry](https://blog.michaelsam94.com/llm-observability-opentelemetry-genai/) pays for itself. Emit a span per step with the model's reasoning, the tool called, and the outcome. Without this, "the agent sometimes does the wrong thing" is unfixable; with it, you can see the exact fork where it went sideways.

## Guard the boundary

A reliable agent also refuses to do the wrong thing on purpose. Two layers matter:

- **Input side:** defend against [prompt injection](https://blog.michaelsam94.com/prompt-injection-agent-security/). If a tool returns attacker-controlled text (a web page, a support ticket), that text can try to hijack the agent. Treat tool outputs as untrusted data, not instructions.
- **Action side:** put a human in the loop for high-consequence, irreversible actions. Refunds above a threshold, account deletions, anything you can't undo — the agent proposes, a human confirms. This isn't a lack of trust in the model; it's the same principle as requiring confirmation for `rm -rf`.

## The loop, assembled

Putting it together, a reliable agent loop looks like this:

```text
while step < MAX_STEPS and now < DEADLINE:
    action = model.decide(state)         # non-deterministic, validate it
    if action is final_answer: return it
    validate(action.tool, action.args)   # schema check before executing
    result = call_tool_with(
        timeout, idempotency_key, bounded_retries_on_transient_errors
    )
    trace(step, action, result)          # observability
    state = update(state, result)
```

Nothing here is exotic. It's timeouts, idempotency keys, typed errors, bounded loops, and tracing — the toolkit for [reliable systems](https://blog.michaelsam94.com/designing-for-observability-slos/) generally. The shift in mindset is accepting that the agent is a flaky, creative client you can't fully control, so you make the *tools* and the *loop* robust enough that its mistakes are bounded and recoverable.

## The short version

- Design tools as validated, narrowly-typed APIs; the agent is untrusted.
- Make every side-effecting tool idempotent with a key so retries are safe.
- Classify errors as transient/permanent/business and retry only the transient ones, bounded and backed off.
- Time-box every call and the whole loop.
- Trace everything; gate irreversible actions behind a human.

Do these five things and your agent goes from "impressive demo" to "thing I trust with a production credit card." The model gets the headlines; the reliability comes from the plumbing.

## Resources

- [OpenAI function calling documentation](https://platform.openai.com/docs/guides/function-calling)
- [Anthropic: building effective agents](https://www.anthropic.com/research/building-effective-agents)
- [Stripe: idempotent requests](https://docs.stripe.com/api/idempotent_requests)
- [OpenTelemetry GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
- [AWS: timeouts, retries, and backoff with jitter](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/)
