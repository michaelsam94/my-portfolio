---
title: "Go Concurrency: Goroutines and Channels"
slug: "go-concurrency-goroutines-channels"
description: "Goroutines and channels are Go's concurrency model. Patterns for worker pools, fan-out/fan-in, and avoiding leaks with context cancellation."
datePublished: "2025-05-04"
dateModified: "2025-05-04"
tags: ["Backend", "Go", "Concurrency", "Performance"]
keywords: "Go goroutines, Go channels, concurrency patterns Go, worker pool Go, fan-in fan-out"
faq:
  - q: "When should I use a channel vs sync.Mutex?"
    a: "Channels coordinate goroutines and pass ownership of data—good for pipelines and signaling. Mutexes protect shared state in place—good for caches and counters. Prefer clear ownership; do not use channels as a mutex replacement for simple increments."
  - q: "How many goroutines is too many?"
    a: "Goroutines are cheap (kilobyte stacks) but not free. Millions of blocked goroutines consume memory. Use worker pools for CPU-bound work; unbounded goroutines per incoming request can exhaust RAM under load."
  - q: "What causes goroutine leaks?"
    a: "Blocked sends/receives on unbuffered channels nobody reads, missing context cancellation, WaitGroups with wrong Add/Done counts. Always tie long-lived goroutines to context.Context cancellation."
---

I shipped a Go service that spawned a goroutine per incoming webhook—fine at 100 RPS, OOM at 10,000. Goroutines are not threads you allocate like candy; they are cooperative workers that need lifecycle boundaries. Channels carry data and signals between them; used together they replace most callback spaghetti.

Go runs concurrent work with **goroutines**—functions executing independently on the runtime scheduler. **Channels** are typed conduits for sending values between goroutines with synchronization.

## Starting goroutines

```go
go func() {
    if err := processJob(job); err != nil {
        log.Printf("job failed: %v", err)
    }
}()
```

Always know how the goroutine exits. Fire-and-forget without supervision leaks under error paths.

## Channels basics

```go
ch := make(chan Result)        // unbuffered — sync handoff
buffered := make(chan Task, 10) // async up to capacity

go func() { ch <- compute() }()
result := <-ch
```

Unbuffered send blocks until receive—rendezvous semantics.

Close channels when no more sends—receivers drain with `for v := range ch`:

```go
close(jobs)
```

Only sender closes. Receiving from closed channel yields zero value and `ok == false`.

## Worker pool pattern

```go
func workerPool(ctx context.Context, jobs <-chan Job, n int) <-chan Result {
    out := make(chan Result)

    var wg sync.WaitGroup
    wg.Add(n)

    worker := func() {
        defer wg.Done()
        for {
            select {
            case <-ctx.Done():
                return
            case job, ok := <-jobs:
                if !ok {
                    return
                }
                out <- process(ctx, job)
            }
        }
    }

    for i := 0; i < n; i++ {
        go worker()
    }

    go func() {
        wg.Wait()
        close(out)
    }()

    return out
}
```

Fixed workers bound parallelism—CPU count or small multiple for I/O.

## Fan-out, fan-in

Fan-out: multiple goroutines read same channel (Go distributes). Fan-in: merge outputs with one goroutine per input channel or `sync.WaitGroup` + single writer.

```go
func merge(ctx context.Context, cs ...<-chan int) <-chan int {
    out := make(chan int)
    var wg sync.WaitGroup

    output := func(c <-chan int) {
        defer wg.Done()
        for v := range c {
            select {
            case out <- v:
            case <-ctx.Done():
                return
            }
        }
    }

    wg.Add(len(cs))
    for _, c := range cs {
        go output(c)
    }

    go func() {
        wg.Wait()
        close(out)
    }()

    return out
}
```

## select for multiplexing

```go
select {
case msg := <-messages:
    handle(msg)
case err := <-errors:
    return err
case <-ctx.Done():
    return ctx.Err()
case <-time.After(5 * time.Second):
    return fmt.Errorf("timeout")
}
```

Default case makes non-blocking attempts—use sparingly to avoid busy loops.

## Context cancellation

Pass `context.Context` into goroutines; exit on `<-ctx.Done()`:

```go
go func() {
    for {
        select {
        case <-ctx.Done():
            return
        default:
            tick()
        }
    }
}()
```

HTTP handlers inherit request context—cancel propagates on client disconnect.

## sync package when channels fit poorly

```go
var mu sync.Mutex
mu.Lock()
cache[key] = val
mu.Unlock()
```

`sync.WaitGroup` waits for goroutine batches. `errgroup.Group` combines wait + first error return—excellent for parallel steps with shared cancel.

```go
g, ctx := errgroup.WithContext(ctx)
g.Go(func() error { return step1(ctx) })
g.Go(func() error { return step2(ctx) })
if err := g.Wait(); err != nil { ... }
```

## Common mistakes

- Sending on closed channel — panic
- Leaked goroutine blocked on send — use buffer or cancel
- Sharing memory without synchronization — data race; run `go test -race`
- Ignoring `WaitGroup` Add before goroutine start race

## Rate limiting with buffered channel

Token bucket via buffered channel of struct{}:

```go
limiter := make(chan struct{}, 10)
for _, req := range requests {
    limiter <- struct{}{}
    go func(r Request) {
        defer func() { <-limiter }()
        handle(r)
    }(req)
}
```

Caps concurrent handlers without unbounded goroutines.

## Pipeline cancellation

Always pass ctx into pipeline stages—cancel closes upstream when downstream fails:

```go
select {
case out <- result:
case <-ctx.Done():
    return ctx.Err()
}
```

## Debugging races

```bash
go test -race ./...
```

CI must run race detector on packages with concurrency—flakes indicate real bugs.

## GOMAXPROCS

Go scheduler respects `GOMAXPROCS`—in Kubernetes, align with CPU limits; avoid oversubscription causing thrashing on CPU-bound worker pools.


## semaphore pattern with context

```go
func acquire(ctx context.Context, sem chan struct{}) error {
    select {
    case sem <- struct{}{}:
        return nil
    case <-ctx.Done():
        return ctx.Err()
    }
}
```

Combine with worker pool for bounded concurrency respecting cancellation.

## Closing channels safely

Only close from sender side; receivers use `for range`—closing twice panics. Use `sync.Once` to close output channel when all workers done.

## Production incident patterns

Goroutine leak from blocked channel send—metrics on `runtime.NumGoroutine()` alert when growth monotonic over hours.

## Testing concurrency

Use deterministic channel sizes in tests to force ordering; `-race` on CI mandatory for packages importing sync and goroutines.

## context.AfterFunc Go 1.21

Use context.AfterFunc for cleanup when ctx cancelled instead of separate goroutine select in simple cases—reduces boilerplate in connection watchdog code.

## Rollout guidance

Goroutine leak detector metric alert threshold tuned after two weeks baseline production—avoid alert fatigue day one threshold zero goroutines impossible production idle state.

## Team practices

Shipping Go Concurrency Goroutines Channels in production taught our team that documentation beats hero demos. We wrote runbooks covering failure modes, on-call steps, and rollback triggers before the second release, not after the first outage.

When reviewing PRs touching Go Concurrency Goroutines Channels, we ask for measurable outcomes: latency, crash rate, or support ticket volume—not subjective feels faster. If metrics are unavailable, the PR includes a DevTools trace or load test snippet proving the change.

Onboarding engineers paste a checklist into their first Go Concurrency Goroutines Channels PR description: environment setup verified, tests added or updated, accessibility spot-checked, and release notes drafted for user-visible changes.

We keep a living FAQ in the repo wiki for Go Concurrency Goroutines Channels questions repeated in Slack more than twice. FAQ entries link to source files and Slack threads, reducing tribal knowledge and repeated explanations in code review.

## Resources

- [Go Concurrency Patterns (talk)](https://go.dev/blog/pipelines)
- [Effective Go — concurrency](https://go.dev/doc/effective_go#concurrency)
- [Go memory model](https://go.dev/ref/mem)
- [golang.org/x/sync/errgroup](https://pkg.go.dev/golang.org/x/sync/errgroup)
- [Share Memory By Communicating](https://go.dev/blog/codelab-share)
