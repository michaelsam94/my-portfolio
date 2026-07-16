---
title: "Parallel Tool Calls in Function Calling"
slug: "llm-function-calling-parallel-tools"
description: "Execute LLM tool calls in parallel: provider parallel function calling, dependency analysis, error handling, and latency patterns that cut agent response time in half."
datePublished: "2024-12-06"
dateModified: "2024-12-06"
tags: ["AI", "LLM", "AI Agents", "Architecture"]
keywords: "parallel tool calls LLM, function calling parallel, OpenAI parallel tools, agent tool execution, concurrent LLM tools"
faq:
  - q: "When can tool calls run in parallel?"
    a: "When they have no data dependencies — looking up weather and stock price for the same user query, searching two databases, fetching multiple URLs. Sequential is required when tool B needs tool A's output (get user ID, then fetch orders). The model often requests parallel calls correctly if your tool descriptions are clear about independence."
  - q: "Does parallel execution confuse the model?"
    a: "No — you execute in parallel on the backend but return all results in one tool response message. The model receives structured results together and synthesizes. What confuses the model is partial failures without clear error messages per tool call."
  - q: "How do I handle partial failures in parallel tool execution?"
    a: "Return per-tool success/failure in the tool response message. Include error details for failed tools and results for successful ones. Let the model decide whether to retry, proceed with partial data, or tell the user. Never fail the entire batch because one tool timed out."
---

The agent needed weather in Tokyo, exchange rates for JPY, and the user's saved travel preferences. The model correctly returned three tool calls in one response. Your orchestrator ran them sequentially — 2.4 seconds total. Parallel execution finished in 0.8 seconds. Same answer, three times faster. Parallel tool calling is one of the highest-ROI latency optimizations in LLM agents, and most teams leave it on the table because their tool runner is a for-loop.

## Provider support

OpenAI and Anthropic both support multiple tool calls per response:

```python
response = await client.chat.completions.create(
    model="gpt-4o",
    messages=messages,
    tools=TOOLS,
    parallel_tool_calls=True,  # OpenAI default since 2024
)
tool_calls = response.choices[0].message.tool_calls
# May contain 1-N calls
```

The model decides how many tools to invoke. Your job is executing them efficiently.

## Parallel execution pattern

```python
async def execute_tool_calls(
    tool_calls: list[ToolCall],
    registry: ToolRegistry,
) -> list[ToolResult]:
    async def run_one(call: ToolCall) -> ToolResult:
        handler = registry.get(call.function.name)
        try:
            args = json.loads(call.function.arguments)
            result = await asyncio.wait_for(
                handler(**args),
                timeout=handler.timeout,
            )
            return ToolResult(tool_call_id=call.id, content=result, error=None)
        except Exception as e:
            return ToolResult(tool_call_id=call.id, content=None, error=str(e))

    return await asyncio.gather(*[run_one(c) for c in tool_calls])
```

Return all results in one message:

```python
tool_messages = [
    {"role": "tool", "tool_call_id": r.tool_call_id,
     "content": r.content if r.error is None else f"Error: {r.error}"}
    for r in results
]
messages.extend(tool_messages)
```

## Dependency-aware scheduling

Not everything can parallelize. Build a dependency graph when the model chains tools:

```python
@dataclass
class ToolCall:
    id: str
    name: str
    args: dict
    depends_on: list[str] = field(default_factory=list)

async def execute_dag(calls: list[ToolCall]) -> list[ToolResult]:
    results = {}
    remaining = list(calls)
    while remaining:
        ready = [c for c in remaining if all(d in results for d in c.depends_on)]
        if not ready:
            raise CyclicDependency(remaining)
        batch_results = await asyncio.gather(*[run(c, results) for c in ready])
        for call, result in zip(ready, batch_results):
            results[call.id] = result
        remaining = [c for c in remaining if c.id not in results]
    return list(results.values())
```

Most model-generated parallel calls are independent — the DAG path handles explicit chains.

## Rate limiting parallel calls

Three parallel calls to the same API can hit rate limits:

```python
class RateLimitedExecutor:
    def __init__(self):
        self.semaphores = defaultdict(lambda: asyncio.Semaphore(5))

    async def run(self, call: ToolCall) -> ToolResult:
        async with self.semaphores[call.name]:
            return await execute(call)
```

Per-tool semaphores prevent thundering herd on shared backends.

## Idempotency and side effects

Parallelizing mutating tools is risky:

| Tool type | Parallel safe? |
|-----------|---------------|
| Read/search | Yes |
| Create (different entities) | Usually yes |
| Update same resource | No — race condition |
| Delete | No |
| Payment/charge | Never parallel |

Tag tools with `read_only: true` in schema. Only parallelize read-only by default; require explicit opt-in for writes.

```python
READ_ONLY = {"search", "get_weather", "fetch_url", "list_orders"}

async def execute_tool_calls(calls: list[ToolCall]) -> list[ToolResult]:
    reads = [c for c in calls if c.name in READ_ONLY]
    writes = [c for c in calls if c.name not in READ_ONLY]
    read_results = await asyncio.gather(*[run(c) for c in reads])
    write_results = []
    for w in writes:  # sequential for writes
        write_results.append(await run(w))
    return read_results + write_results
```

## Timeouts and partial results

Set per-tool timeouts shorter than the overall request timeout:

```python
TOOL_TIMEOUTS = {
    "search": 5,
    "fetch_url": 10,
    "database_query": 15,
}
```

If one of three parallel calls times out, return the other two results with an error for the third. The model can often answer with partial data.

## Observability

Trace each tool call as a separate span under the LLM turn span:

```
llm.turn (800ms)
  ├── tool.search (120ms)
  ├── tool.get_weather (450ms)  ← bottleneck
  └── tool.get_preferences (80ms)
```

Parallel wall-clock = max(individual), not sum. Dashboards should show both per-tool latency and batch latency.

## Provider API differences

| Provider | Parallel support | Notes |
|----------|------------------|-------|
| OpenAI | Yes, `parallel_tool_calls` | Default true |
| Anthropic | Yes, multiple tool_use blocks | Same turn |
| Gemini | Function calling parallel | Check model version |
| Local models | Varies | Often sequential only |

Disable parallel when tools have implicit ordering:

```python
response = client.chat.completions.create(
    model="gpt-4o",
    messages=messages,
    tools=tools,
    parallel_tool_calls=False,  # force sequential
)
```

## Dependency-aware parallelization

Build execution DAG when tools depend on each other:

```python
# Model returned: search_orders(user), get_order_details(order_id from ???)
# Can't parallelize — second depends on first result

async def execute_with_dependencies(calls, prior_results):
    independent = [c for c in calls if not c.depends_on(prior_results)]
    if not independent:
        return sequential_execute(calls)
    return await asyncio.gather(*[run(c) for c in independent])
```

Most LLMs don't declare dependencies — your orchestrator detects from argument references or executes writes sequentially by default.

Pair with [agent parallel tool execution](https://blog.michaelsam94.com/agent-parallel-tool-execution/) and [tool use error recovery](https://blog.michaelsam94.com/agent-tool-use-error-recovery/) for production agent tool pipelines.

## Common production mistakes

Teams get function calling parallel tools wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

LLM features around function calling parallel tools break in production when prompts assume deterministic output, context windows are sized for dev datasets, or token costs are never budgeted per user session. Always log prompt hash, model version, and latency—not raw prompts with PII.

## Resources

- [OpenAI parallel function calling](https://platform.openai.com/docs/guides/function-calling#parallel-function-calling)
- [Anthropic tool use documentation](https://docs.anthropic.com/en/docs/build-with-claude/tool-use)
- [Python asyncio.gather patterns](https://docs.python.org/3/library/asyncio-task.html#asyncio.gather)
- [LangGraph parallel node execution](https://langchain-ai.github.io/langgraph/how-tos/parallel/)
- [OpenTelemetry tracing for async operations](https://opentelemetry.io/docs/languages/python/instrumentation/)
