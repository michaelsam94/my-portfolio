---
title: "Reading Flame Graphs"
slug: "performance-profiling-flamegraphs"
description: "Interpret CPU flame graphs for performance debugging: stack frames, width meaning, plateau patterns, and tooling with perf, py-spy, and async-profiler."
datePublished: "2026-02-16"
dateModified: "2026-02-16"
tags: ["Performance", "Profiling", "Observability", "Debugging"]
keywords: "flame graph profiling, CPU flame graph, perf record, py-spy, async profiler Java"
faq:
  - q: "What does width mean in a flame graph?"
    a: "Width represents the proportion of total sampled CPU time spent in that function and its children. Wider bars consumed more CPU during the profiling window. Wider doesn't mean slow per call — a function called millions of times can be wider than a slow function called once."
  - q: "Why are flame graphs upside down compared to call trees?"
    a: "The root (your program entry) is at the bottom; callees stack upward. CPU flows from bottom to top like flames. The y-axis is stack depth; the x-axis is proportional time, not chronological order."
  - q: "How long should you profile to get a useful flame graph?"
    a: "30–60 seconds of wall time under representative load usually suffices. Too short misses rare paths; too long averages away spikes. Profile during load test or production traffic with low overhead samplers (async signal-based profilers)."
---

The API team argued for two weeks about why CPU sat at 80%. Someone ran `py-spy record` for 60 seconds during peak traffic and sent a flame graph. The widest plateau was `json.dumps` inside a logging middleware that serialized entire request bodies on every call. Fifteen minutes to find, two lines to fix. Flame graphs turn "the system feels slow" into "this function ate 40% of your cores."

## Anatomy of a flame graph

```
┌─────────────────────────────────────────────────────────────┐
│                    json.dumps (38%)                         │  ← wide = hot
├──────────────────────┬──────────────────────────────────────┤
│   serialize_log      │         other                        │
├──────────┬───────────┤                                      │
│ middleware│  handler │                                      │
└──────────┴───────────┴──────────────────────────────────────┘
│ main     │           ← bottom = entry / root
```

- **Y-axis:** stack depth (who called whom)
- **X-axis:** alphabetical within a stack level, NOT time sequence
- **Color:** often random or by module — cosmetic, not semantic
- **Width:** cumulative sample count in subtree

Click frames in interactive viewers (speedscope.app, Brendan Gregg's original) to zoom.

## How sampling profilers build the graph

The profiler interrupts the process every N milliseconds (or on CPU clock ticks), captures the call stack, repeats thousands of times, then aggregates identical stacks.

```bash
# Linux perf — Java/C++/Go native code
perf record -F 99 -p $(pgrep myapp) -g -- sleep 60
perf script | stackcollapse-perf.pl | flamegraph.pl > flame.svg

# Python — no code changes, production safe at low rate
py-spy record -o profile.svg --pid $(pgrep gunicorn) --duration 60 --rate 100
```

99 Hz sampling ≈ 1% overhead on most workloads. Always profile under load that reproduces the problem — idle flame graphs show garbage collection and thread pool waits, not request handling.

## Patterns to recognize

**Wide plateau on one function.** The fix target. Often serialization, regex, compression, or accidental sync I/O in hot path.

**Tall skinny tower.** Deep recursion or callback chains — stack overflow risk or inefficient algorithm (O(n²) nested loops show as repeated frames).

**Many medium-width siblings.** Time spread across peers — harder optimization; look for common parent.

**`__libc_start_main` / `runtime.main` heavy.** Not useful — zoom into your code frames.

**Lock contention frames.** `pthread_mutex_lock`, `futex`, `sync.(*Mutex).Lock` wide bars — threading bottleneck, not CPU computation.

## Language-specific tooling

**Java:** async-profiler with `-e cpu,alloc` — allocation flame graphs find GC pressure sources separately from CPU.

```bash
java -agentpath:libasyncProfiler.so=start,event=cpu,file=flame.html,interval=10ms,threads
```

**Node.js:** `--cpu-prof` generates V8 profiles importable to speedscope; clinic.js flame for development.

**Go:** `go tool pprof -http=:8080 cpu.prof` — built-in flame graph view since Go 1.11.

**Browser JS:** Chrome DevTools Performance tab → bottom-up / flame chart (different from server flame graphs but same width = time intuition).

## Async and I/O blind spots

Standard CPU flame graphs miss time blocked on I/O — awaiting Postgres, HTTP clients. The CPU looks idle while latency suffers.

Combine with:
- **Off-CPU flame graphs** (`perf record -e sched:sched_switch`)
- **Wall-time profilers** (OpenTelemetry continuous profiling with wall vs CPU mode)
- **Trace spans** for I/O boundaries

If CPU flame graph looks healthy but p99 is bad, you're I/O bound — profile wait events, not compute.

## From graph to fix

1. Identify widest frame in your code (ignore stdlib unless it's the culprit)
2. Read upward — who called it? Middleware? Specific route handler?
3. Read downward — what inside it is wide? Loop? Library call?
4. Re-profile after fix to confirm bar shrunk — regressions happen

Don't optimize frames under 2% width unless you're at tail latency SLO and scraping for gains.

## Production profiling etiquette

- Sample, don't instrument every call in prod
- Restrict to canary pods or low-traffic windows first
- Redact PII from stack args if profiler captures parameters
- Store profiles as artifacts linked to deploy version for comparison

We tag flame graph captures with Git SHA — comparing pre/post deploy profiles is the fastest regression hunt after a latency spike.

## Continuous profiling in production

Tools like Pyroscope, Parca, and Google Cloud Profiler sample production continuously at low overhead. Compare flame graphs across deploy versions to spot regressions — "this function grew 15% after v2.4" — faster than reproducing in staging.

Annotate profiles with Git SHA and pod name. Without labels, profiling data is unactionable noise.

## Reading flame graphs

Width = time in function. Look for:
- Wide plateaus — optimize that function first
- Unexpected framework frames — allocation hotspots
- Flat tops — CPU-bound, not I/O wait

Compare flame graphs before/after optimization — verify plateaus shrink, not just shift.

## Common production mistakes

Teams get profiling flamegraphs wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Performance work on profiling flamegraphs regresses when optimizations target p50 only, benchmarks run on laptops not production hardware, and flamegraphs are captured once then never compared after refactors.

## Debugging and triage workflow

When profiling flamegraphs misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Brendan Gregg — Flame Graphs](https://www.brendangregg.com/flamegraphs.html)
- [speedscope.app — interactive viewer](https://www.speedscope.app/)
- [py-spy documentation](https://github.com/benfred/py-spy)
- [async-profiler GitHub](https://github.com/async-profiler/async-profiler)
- [Linux perf wiki](https://perf.wiki.kernel.org/index.php/Main_Page)
