---
title: "Context, Cancellation, and Timeouts in Go"
slug: "go-context-cancellation-timeouts"
description: "context.Context propagates deadlines and cancellation through Go call chains. HTTP handlers, database queries, and goroutines that respect Done()."
datePublished: "2025-05-07"
dateModified: "2025-05-07"
tags: ["Backend", "Go", "Context", "API"]
keywords: "Go context package, context cancellation, context.WithTimeout, Go HTTP timeout, graceful shutdown context"
faq:
  - q: "Should context be the first parameter in Go functions?"
    a: "Yes—idiom is func(ctx context.Context, ...). Never store context in structs long-term; pass per request so cancellation and deadlines stay scoped to operation lifetime."
  - q: "What happens if I ignore context cancellation in a database query?"
    a: "The query runs to completion even if client disconnected—wasting connection pool slots and CPU. Pass ctx to QueryContext/ExecContext so driver cancels when ctx.Done() fires, subject to driver support."
  - q: "WithTimeout vs WithDeadline?"
    a: "WithTimeout(duration) creates deadline now+duration. WithDeadline(time.Time) sets explicit instant. Both cancel context afterward and should call cancel() to release timer resources even if operation finished early."
---

Production incident: clients timed out at the load balancer but Go handlers kept running—thousands of DB queries for nobody. We passed `context.Background()` everywhere instead of the request context. Wiring `r.Context()` through and using `QueryContext` dropped idle load 40% the same deploy.

The `context` package carries deadlines, cancellation signals, and request-scoped values across API boundaries and goroutines.

## Creating contexts

```go
ctx := context.Background() // root — tests, main, init only
ctx, cancel := context.WithCancel(parent)
defer cancel()

ctx, cancel := context.WithTimeout(parent, 3*time.Second)
defer cancel()

ctx, cancel := context.WithDeadline(parent, time.Now().Add(3*time.Second))
defer cancel()
```

Always `defer cancel()` for timeout/deadline contexts—releases internal timer even on success.

## HTTP server integration

```go
func handler(w http.ResponseWriter, r *http.Request) {
    ctx := r.Context() // cancels when client disconnects

    result, err := service.Fetch(ctx, r.URL.Query().Get("id"))
    if errors.Is(err, context.Canceled) {
        return // client gone, skip writing response
    }
    if err != nil {
        http.Error(w, err.Error(), http.StatusInternalServerError)
        return
    }
    json.NewEncoder(w).Encode(result)
}
```

Set server timeouts:

```go
srv := &http.Server{
    Addr:         ":8080",
    Handler:      router,
    ReadTimeout:  5 * time.Second,
    WriteTimeout: 10 * time.Second,
    IdleTimeout:  120 * time.Second,
}
```

Handler context deadline may combine client disconnect and WriteTimeout.

## Propagating through layers

```go
func (s *Service) Fetch(ctx context.Context, id string) (*Item, error) {
    return s.repo.Get(ctx, id)
}

func (r *Repo) Get(ctx context.Context, id string) (*Item, error) {
    row := r.db.QueryRowContext(ctx, "SELECT ... WHERE id = $1", id)
    ...
}
```

Every I/O boundary accepts ctx.

## select on Done

Long loops and goroutines:

```go
func poll(ctx context.Context, interval time.Duration) error {
    ticker := time.NewTicker(interval)
    defer ticker.Stop()

    for {
        select {
        case <-ctx.Done():
            return ctx.Err()
        case <-ticker.C:
            if err := work(); err != nil {
                return err
            }
        }
    }
}
```

Return `ctx.Err()` — `context.Canceled` or `context.DeadlineExceeded`.

## Graceful shutdown

```go
ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
defer stop()

go func() { srv.ListenAndServe() }()

<-ctx.Done()
shutdownCtx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
defer cancel()
srv.Shutdown(shutdownCtx)
```

`Shutdown` stops new requests and waits for in-flight with separate timeout context—do not reuse already-cancelled signal context for shutdown grace period.

## Context values — use sparingly

```go
type ctxKey struct{}

func WithRequestID(ctx context.Context, id string) context.Context {
    return context.WithValue(ctx, ctxKey{}, id)
}
```

Use unexported key types to avoid collisions. Pass explicit parameters for business data—context values for cross-cutting observability (trace ID, auth claims) only.

## errgroup with context

```go
g, ctx := errgroup.WithContext(ctx)
g.Go(func() error { return fetchA(ctx) })
g.Go(func() error { return fetchB(ctx) })
if err := g.Wait(); err != nil {
    // ctx cancelled on first error
}
```

First failure cancels sibling goroutines when they respect ctx.

## Anti-patterns

- `context.TODO()` in production paths — temporary only
- Storing ctx in struct fields — stale cancellation
- Ignoring `ctx.Err()` distinction — log Canceled vs DeadlineExceeded differently
- Passing nil context — panic in some stdlib calls

## gRPC and context

gRPC Go passes metadata from incoming ctx—propagate to outgoing calls:

```go
resp, err := client.Fetch(ctx, req)
```

Client-side deadline:

```go
ctx, cancel := context.WithTimeout(ctx, 2*time.Second)
defer cancel()
```

## Database transactions

```go
tx, err := db.BeginTx(ctx, nil)
```

Rollback on ctx cancel during long migration scripts—avoid holding locks after client disconnect.

## Testing cancellation

```go
ctx, cancel := context.WithCancel(context.Background())
cancel()
err := svc.Operation(ctx)
require.ErrorIs(t, err, context.Canceled)
```

## Never use context value for optional params

Function parameters express API; context values for request-scoped telemetry only—overloading ctx with business params hides dependencies.


## http.Client and context

Go 1.13+ `http.NewRequestWithContext` mandatory—never `http.Get(url)` without context in production code paths.

## Graceful degradation on timeout

Return partial results if some parallel fetches succeed before ctx deadline—document UX for incomplete dashboard vs error page.

## Context in tests

Use `context.Background()` in pure unit tests; integration tests use timeout context mirroring production deadlines.

## Anti-pattern: context in struct

Storing ctx in `Service` struct creates stale cancellation—pass per method call; linter rule custom if needed.

## context.WithTimeout leak

Always defer cancel() immediately after WithTimeout assignment—even when returning early on error—staticcheck SA1029 enforces in CI golangci-lint config.

## Rollout guidance

Context timeout defaults centralized config struct loaded environment variables—change timeout one deploy not scattered magic number duration literals forty files.

## Team practices

Shipping Go Context Cancellation Timeouts in production taught our team that documentation beats hero demos. We wrote runbooks covering failure modes, on-call steps, and rollback triggers before the second release, not after the first outage.

When reviewing PRs touching Go Context Cancellation Timeouts, we ask for measurable outcomes: latency, crash rate, or support ticket volume—not subjective feels faster. If metrics are unavailable, the PR includes a DevTools trace or load test snippet proving the change.

Onboarding engineers paste a checklist into their first Go Context Cancellation Timeouts PR description: environment setup verified, tests added or updated, accessibility spot-checked, and release notes drafted for user-visible changes.

We keep a living FAQ in the repo wiki for Go Context Cancellation Timeouts questions repeated in Slack more than twice. FAQ entries link to source files and Slack threads, reducing tribal knowledge and repeated explanations in code review.

Cross-functional review includes design for UX-facing work, security for auth or storage, and platform for native bridges. Go Context Cancellation Timeouts spans layers; skipping reviewers recreated bugs we fixed months ago.

## Resources

- [context package documentation](https://pkg.go.dev/context)
- [Go blog — context](https://go.dev/blog/context)
- [net/http Server timeouts](https://pkg.go.dev/net/http#Server)
- [database/sql QueryContext](https://pkg.go.dev/database/sql#DB.QueryContext)
- [Graceful shutdown example (Go docs)](https://pkg.go.dev/net/http#example-Server-Shutdown)
