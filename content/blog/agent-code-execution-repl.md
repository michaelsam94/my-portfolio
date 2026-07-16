---
title: "Giving Agents a Code REPL"
slug: "agent-code-execution-repl"
description: "How to give LLM agents a code REPL for data analysis and automation: sandboxing, state persistence, output limits, and when a REPL beats tool calls."
datePublished: "2026-06-20"
dateModified: "2026-06-20"
tags: ["AI Agents", "LLM", "Architecture", "Security"]
keywords: "agent code REPL, LLM code execution, Python REPL agent, sandboxed code execution, agent data analysis"
faq:
  - q: "When should an agent use a code REPL instead of structured tools?"
    a: "Use a REPL when the task requires ad-hoc data transformation, statistical analysis, or multi-step computation that would require dozens of narrowly scoped tools. A REPL lets the model write Python or SQL once, inspect intermediate results, and iterate. Structured tools are better when operations are fixed, auditable, and must map to specific backend APIs."
  - q: "How do you sandbox an agent REPL safely?"
    a: "Run code in an isolated container or WASM sandbox with no network access, read-only filesystem except a scratch directory, CPU and memory limits, and a hard timeout. Never execute agent-generated code on the host. Strip dangerous imports and use an allowlist of libraries. Treat every REPL session as untrusted input."
  - q: "What output limits should a REPL enforce?"
    a: "Cap stdout at 8–32 KB, truncate large DataFrames to head/tail previews, and return structured summaries instead of raw blobs. Without limits, a single `print(df)` on a million-row dataset will blow your context window and cost you a fortune on the next turn."
---

A code REPL is the single highest-leverage tool you can give a data-analysis agent — and the single easiest way to get code execution wrong. Instead of defining forty tools for "filter CSV," "compute mean," and "plot histogram," you give the model a Python interpreter, a scratch directory, and a library allowlist. It writes three lines, sees the output, adjusts, and finishes. I've replaced entire tool suites with one REPL and watched success rates jump — but only after I stopped treating "run arbitrary code" as a feature and started treating it as a security boundary.

## REPL vs structured tools

Structured tools (`search_orders`, `get_user_profile`) are auditable, typed, and map cleanly to your backend. A REPL is none of those things. The trade-off:

| Dimension | Structured tools | Code REPL |
|-----------|-----------------|-----------|
| Flexibility | Fixed operations only | Arbitrary computation |
| Auditability | Every call logged with params | Must capture source + stdout |
| Safety | Bounded by API permissions | Bounded by sandbox policy |
| Latency | One round-trip per op | One round-trip per script |
| Best for | CRUD, integrations, side effects | Analysis, transforms, prototyping |

My rule: side effects go through tools; computation goes through the REPL. An agent that uses `requests.post()` inside a REPL to call your production API is a design failure — give it a `create_ticket` tool instead.

## Architecture that works in production

```
User query → Agent (LLM) → writes Python → Sandbox executor
                              ↑                    ↓
                         stdout/stderr         timeout + limits
                              ↑                    ↓
                         Agent reads result → next turn or final answer
```

The executor runs in a fresh container per session (or per invocation if you're paranoid). State persists in `/tmp/session/` so the agent can define variables across turns within a conversation, but the container dies when the session ends.

```python
# Minimal executor interface your agent tool wraps
def execute_code(session_id: str, code: str, timeout_s: int = 30) -> ExecutionResult:
    sandbox = get_or_create_sandbox(session_id)
    result = sandbox.run(
        code,
        timeout=timeout_s,
        allowed_imports=["pandas", "numpy", "json", "math", "datetime"],
        max_stdout_bytes=16_384,
    )
    return ExecutionResult(
        stdout=result.stdout,
        stderr=result.stderr,
        error=result.error,
        variables_summary=sandbox.describe_namespace(),  # "df: DataFrame(1000, 12)"
    )
```

The `variables_summary` is critical. After three turns the agent forgets what it named things; a one-line namespace description saves an entire re-read of the dataset.

## Prompting the model to use the REPL well

Models default to narrating what they *would* do instead of writing code. Force execution:

- "Always run code to verify numeric answers. Do not guess."
- "Print intermediate results with `print()` — you cannot see variables otherwise."
- "If code fails, read the traceback, fix, and retry. Max 3 attempts."

Also give it starter snippets for common patterns in your domain. A `load_csv(path)` helper pre-loaded in the sandbox beats watching the model reimplement pandas IO every session.

## The failure modes I've hit

**Unbounded output.** An agent ran `print(json.dumps(huge_dict))` and filled 40K tokens. Fix: truncate stdout server-side and tell the model "output was truncated at 16KB — use `.head()` or aggregate first."

**Stateful surprises.** Turn 1 defined `df`, turn 4 redefined it with different columns, turn 5 assumed old schema. Fix: namespace summaries after every execution, or reset sandbox on topic change.

**Library escape hatches.** `subprocess`, `os.system`, `socket` — block at import level, not just documentation. I've seen models try `import subprocess` when pandas failed; the sandbox should reject it before execution.

**Timeout loops.** Nested loops over large data without vectorization. Fix: 30-second default timeout, suggest `df.groupby()` in the tool description when timeout errors occur.

## When not to use a REPL

Don't give customer-facing agents arbitrary code execution. Don't use a REPL for anything that touches PII without column-level redaction in the sandbox. Don't skip [sandboxing](https://blog.michaelsam94.com/agent-sandboxing-code-execution/) because Docker feels heavy — a compromised REPL on your VPC is worse than no REPL at all.

For agents that need computation *and* side effects, keep both: REPL for analysis, tools for mutations. The [multi-agent orchestration pattern](https://blog.michaelsam94.com/multi-agent-orchestration-orchestrator-workers/) maps well here — an analyst sub-agent gets the REPL, an executor sub-agent gets the write tools, and an orchestrator routes between them.

## Production checklist

- [ ] 30-second execution timeout enforced server-side
- [ ] stdout truncated at 16 KB with model-visible notice
- [ ] `subprocess`, `socket`, `os.system` blocked at import
- [ ] Sandbox runs without network egress by default
- [ ] Every execution logged with session ID and code hash

Treat production rollout as a measured change: ship with observability, validate rollback, and review metrics 24 hours after deploy — patterns that look obvious in docs fail when skipped under release pressure.

## Common production mistakes

Teams get code execution repl wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Agent systems using code execution repl loop infinitely when tool errors are swallowed, subagent budgets have no hard cap, and human-in-the-loop gates are bypassed under latency pressure.

## Debugging and triage workflow

When code execution repl misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [OpenAI Code Interpreter documentation](https://platform.openai.com/docs/assistants/tools/code-interpreter)
- [E2B — cloud sandboxes for AI code execution](https://e2b.dev/docs)
- [Pyodide — Python in WebAssembly](https://pyodide.org/en/stable/)
- [OWASP LLM Top 10 — insecure output handling](https://owasp.org/www-project-top-10-for-large-language-model-applications/)
- [OpenTelemetry GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
