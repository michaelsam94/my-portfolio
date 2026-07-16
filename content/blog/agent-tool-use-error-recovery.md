---
title: "Tool-Use Error Recovery for Agents"
slug: "agent-tool-use-error-recovery"
description: "Build resilient agent tool error recovery: structured error messages, retry policies, fallback tools, and preventing infinite retry loops."
datePublished: "2026-07-06"
dateModified: "2026-07-06"
tags: ["AI Agents", "LLM", "Architecture", "Backend"]
keywords: "agent error recovery, tool use errors LLM, agent retry logic, tool failure handling, resilient AI agents"
faq:
  - q: "How should agents handle tool failures?"
    a: "Return structured error information to the model — error type, message, and suggested recovery action — rather than generic failure text. Let the model decide whether to retry with corrected arguments, try an alternative tool, or tell the user what's wrong. Cap retries at 2–3 per tool call to prevent loops."
  - q: "Should agents automatically retry failed tool calls?"
    a: "Auto-retry transient failures (timeouts, 503s) with exponential backoff in the executor layer — the model doesn't need to know about infra blips. For logical failures (404, validation error, permission denied), return the error to the model and let it decide how to proceed. Never auto-retry errors that modify state."
  - q: "How do you prevent agents from retrying the same failed call indefinitely?"
    a: "Track retry count per tool call signature (tool name + args hash). After 2–3 identical failures, halt and return a user-facing error. Also detect when the model calls the same tool with the same args across turns — that's a loop, not recovery."
---

Tools fail. APIs timeout, return 404, reject malformed arguments, and rate-limit at the worst moment. The difference between a fragile agent demo and a production agent is what happens next — does it retry intelligently, try an alternative, explain the problem to the user, or loop the same failing call until the budget runs out? I've seen agents burn $4 retrying a misspelled order ID eleven times because the error message was `"Error: failed"` and the model had nothing to work with. Structured error recovery is not optional infrastructure.

## Structured error responses

Never return opaque errors to the model:

```python
@dataclass
class ToolError:
    tool_name: str
    error_type: Literal["not_found", "validation", "timeout", "permission", "rate_limit", "internal"]
    message: str
    recoverable: bool
    suggestion: str | None = None

def format_error_for_llm(error: ToolError) -> str:
    return json.dumps({
        "status": "error",
        "type": error.error_type,
        "message": error.message,
        "recoverable": error.recoverable,
        "suggestion": error.suggestion,
    })
```

Example the model can act on:

```json
{
  "status": "error",
  "type": "not_found",
  "message": "Order 4521 not found for user u-123",
  "recoverable": true,
  "suggestion": "Verify the order ID with the user or search orders by date range"
}
```

Compare that to `"Tool execution failed."` — one enables recovery, the other enables looping.

## Two-layer retry strategy

**Executor layer** — automatic, invisible to the model:

```python
RETRYABLE = {"timeout", "rate_limit", "internal"}

async def execute_with_retry(tool_name, args, max_retries=2):
    for attempt in range(max_retries + 1):
        try:
            return await execute_tool(tool_name, args)
        except TransientError as e:
            if attempt < max_retries:
                await asyncio.sleep(2 ** attempt)
                continue
            return ToolError(tool_name, "timeout", str(e), recoverable=True,
                           suggestion="The service is temporarily unavailable. Try again or inform the user.")
```

**Model layer** — for logical failures the model must reason about:

The model receives the structured error and decides: fix args and retry, try a different tool, ask the user for clarification, or give up gracefully.

## Fallback tool chains

Define alternatives for critical operations:

```python
FALLBACK_CHAINS = {
    "search_orders": ["search_orders_by_email", "list_recent_orders"],
    "get_weather": ["get_weather_backup_api"],
}

async def execute_with_fallback(tool_name, args):
    result = await execute_tool(tool_name, args)
    if result.is_error and tool_name in FALLBACK_CHAINS:
        for fallback in FALLBACK_CHAINS[tool_name]:
            result = await execute_tool(fallback, args)
            if not result.is_error:
                return result
    return result
```

Tell the model about fallbacks in tool descriptions: "If search_orders returns not_found, try search_orders_by_email with the user's email."

## Loop detection

Track call signatures across turns:

```python
class LoopDetector:
    def __init__(self, max_identical=3):
        self.history: list[str] = []
        self.max_identical = max_identical

    def record(self, tool_name: str, args: dict) -> None:
        sig = f"{tool_name}:{hash(json.dumps(args, sort_keys=True))}"
        self.history.append(sig)

    def is_looping(self) -> bool:
        if len(self.history) < self.max_identical:
            return False
        return len(set(self.history[-self.max_identical:])) == 1
```

When looping is detected, inject a system message: "You have called the same tool with the same arguments 3 times. Stop retrying and explain the issue to the user." Hard-stop if it continues.

## Graceful degradation

Not every failure needs a perfect recovery. Teach the agent to partial-succeed:

```
If a non-critical tool fails after one retry, proceed with available data
and note what's missing in your response. Only halt for critical failures
that make the task impossible (e.g., cannot authenticate, cannot find any
orders for this user).
```

Mark tools as critical or optional in their definitions. The orchestrator enforces: critical failure → stop; optional failure → continue with warning.

## Error recovery in eval

Test failure paths explicitly in your [eval dataset](https://blog.michaelsam94.com/agent-evaluation-trajectory-analysis/):

- Tool returns 404 → agent asks user to verify ID
- Tool times out → agent retries once, then explains
- Invalid args → agent corrects and succeeds
- Permission denied → agent explains limitation, doesn't retry

These scenarios catch more production bugs than happy-path evals.

## Error taxonomy for tools

Classify errors before deciding recovery strategy:

| Error type | Example | Recovery |
|------------|---------|----------|
| Transient | 503, timeout | Retry with backoff |
| Client | 400 invalid args | Fix args, retry once |
| Auth | 401, 403 | Stop, ask user to re-auth |
| Not found | 404 | Clarify with user |
| Rate limit | 429 | Backoff, respect Retry-After |
| Permanent | 501 not implemented | Degrade gracefully |

Map HTTP status codes in tool wrappers — don't pass raw JSON errors to the model without classification.

## User-visible error messages

Translate tool failures into actionable user text:

```python
ERROR_MESSAGES = {
    "ORDER_NOT_FOUND": "I couldn't find order {order_id}. Please check the number and try again.",
    "PAYMENT_DECLINED": "The payment was declined. The card may need updating.",
    "RATE_LIMITED": "I'm processing many requests right now. Please wait a moment.",
}

def format_tool_error(error: ToolError) -> str:
    template = ERROR_MESSAGES.get(error.code, "Something went wrong. Our team has been notified.")
    return template.format(**error.context)
```

Never expose internal error codes or stack traces to end users.

## Circuit breaker for flaky tools

After N consecutive failures on an external API, stop calling it:

```python
breaker = CircuitBreaker(fail_max=5, reset_timeout=60)

@breaker
async def call_crm_api(query: str):
    return await crm.search(query)
```

Inject breaker state into agent context: "CRM search is temporarily unavailable." Prevents burning tokens on doomed retries.

Pair with [agent tool selection routing](https://blog.michaelsam94.com/agent-tool-selection-routing/) to exclude broken tools from the routed set automatically.

## Common production mistakes

Teams get tool use error recovery wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Agent systems using tool use error recovery loop infinitely when tool errors are swallowed, subagent budgets have no hard cap, and human-in-the-loop gates are bypassed under latency pressure.

## Resources

- [OpenAI function calling error handling](https://platform.openai.com/docs/guides/function-calling)
- [Anthropic tool use error patterns](https://docs.anthropic.com/en/docs/build-with-claude/tool-use)
- [gRPC retry policy specification](https://grpc.io/docs/guides/retry/)
- [Building reliable AI agents](https://blog.michaelsam94.com/building-reliable-ai-agents/)
- [Deterministic replay for agent tests](https://blog.michaelsam94.com/agent-deterministic-replay-testing/)
