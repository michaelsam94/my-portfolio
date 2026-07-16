---
title: "Idiomatic Error Handling in Go"
slug: "go-error-handling-wrapping"
description: "Go errors are values. fmt.Errorf with %w, errors.Is and errors.As, sentinel errors, and when not to panic in production services."
datePublished: "2025-05-10"
dateModified: "2025-05-10"
tags: ["Backend", "Go", "Errors", "API"]
keywords: "Go error handling, errors.Is, errors.As, fmt.Errorf wrap, sentinel errors Go"
faq:
  - q: "Should Go functions return error or panic?"
    a: "Return error for expected failures—not found, validation, I/O timeouts. Panic for programmer bugs and unrecoverable invariants during development; recover at HTTP middleware boundary if at all. Libraries should almost never panic."
  - q: "What is the difference between errors.Is and errors.As?"
    a: "errors.Is checks equality in error chain including wrapped errors—good for sentinel ErrNotFound. errors.As extracts typed error into target variable—good for structured errors with fields like HTTP status codes."
  - q: "When should I wrap errors with %w?"
    a: "Wrap at boundaries when adding context: query user failed. Use %w to preserve root cause for Is/As. Do not wrap if message alone suffices and callers never inspect chain."
---

`if err != nil` is not ceremony—it is the contract. Go rejects exceptions for control flow; errors return alongside values and compose with wrapping. The mistake I see most is string comparison on `err.Error()` instead of `errors.Is`, which breaks the moment someone adds context with `%w`.

## Basic error returns

```go
func ParsePort(s string) (int, error) {
    port, err := strconv.Atoi(s)
    if err != nil {
        return 0, fmt.Errorf("parse port %q: %w", s, err)
    }
    if port < 1 || port > 65535 {
        return 0, fmt.Errorf("parse port %q: out of range", s)
    }
    return port, nil
}
```

Callers decide severity—log, retry, or return 400.

## Sentinel errors

Package-level variables for stable comparison:

```go
var ErrNotFound = errors.New("not found")

func Find(id string) (*Item, error) {
    item, ok := store[id]
    if !ok {
        return nil, ErrNotFound
    }
    return item, nil
}
```

Check with `errors.Is`:

```go
item, err := Find(id)
if errors.Is(err, ErrNotFound) {
    http.NotFound(w, r)
    return
}
```

Never compare `err == ErrNotFound` if wrapping may occur—use `errors.Is`.

## Custom error types

```go
type ValidationError struct {
    Field   string
    Message string
}

func (e *ValidationError) Error() string {
    return fmt.Sprintf("%s: %s", e.Field, e.Message)
}

func Bind(r *http.Request, dst any) error {
    if err := decode(r, dst); err != nil {
        return &ValidationError{Field: "body", Message: err.Error()}
    }
    return nil
}
```

Extract with `errors.As`:

```go
var verr *ValidationError
if errors.As(err, &verr) {
    writeJSON(w, 422, verr)
    return
}
```

## Wrapping chains

Go 1.13+ `%w`:

```go
if err := repo.Save(ctx, user); err != nil {
    return fmt.Errorf("create user %q: %w", user.Email, err)
}
```

Outer message for logs; inner for classification:

```go
if errors.Is(err, sql.ErrNoRows) {
    return ErrNotFound
}
```

## Joining multiple errors

Go 1.20+ `errors.Join`:

```go
var errs []error
for _, id := range ids {
    if err := delete(id); err != nil {
        errs = append(errs, err)
    }
}
return errors.Join(errs...)
```

Useful for batch operations reporting partial failure.

## HTTP handler mapping

Central error handler:

```go
func handleError(w http.ResponseWriter, err error) {
    switch {
    case errors.Is(err, ErrNotFound):
        http.Error(w, "not found", http.StatusNotFound)
    case errors.As(err, new(*ValidationError)):
        http.Error(w, err.Error(), http.StatusUnprocessableEntity)
    default:
        slog.Error("request failed", "err", err)
        http.Error(w, "internal error", http.StatusInternalServerError)
    }
}
```

Map domain errors to HTTP once—not scattered status codes.

## Logging vs returning

Libraries return errors; applications log at boundary with context:

```go
if err := svc.Process(ctx, req); err != nil {
    slog.ErrorContext(ctx, "process failed",
        "request_id", requestID(ctx),
        "err", err,
    )
    handleError(w, err)
}
```

Avoid log-and-return same error up stack—duplicate noise.

## Panic and recover

```go
func middleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        defer func() {
            if rec := recover(); rec != nil {
                slog.Error("panic", "recover", rec, "stack", debug.Stack())
                http.Error(w, "internal error", 500)
            }
        }()
        next.ServeHTTP(w, r)
    })
}
```

Last resort—not error handling strategy.

## Testing errors

```go
if !errors.Is(err, ErrNotFound) {
    t.Fatalf("got %v, want ErrNotFound", err)
}

var verr *ValidationError
if !errors.As(err, &verr) || verr.Field != "email" {
    t.Fatalf("unexpected error: %v", err)
}
```

## %v vs %w

Use `%w` when callers need `errors.Is/As`; use `%v` when wrapping external errors you intentionally hide from inspection ( rare—document why).

## Multi-error aggregation

Go 1.20 `errors.Join` for parallel step failures—return combined error listing all failed IDs.

## Sentry and error reporting

Report only non-cancelled errors at HTTP 5xx boundary—`context.Canceled` is noise in Sentry.

## Domain error catalog

Maintain table of sentinel errors and HTTP mappings in one package—handlers import catalog instead of string matching.


## pkg/errors historical note

Legacy `github.com/pkg/errors` wrap still in old codebases—migrate to fmt.Errorf %w during touch; do not mix Is/As behavior inconsistently across packages.

## Client-facing messages

Map internal wrapped errors to safe user messages—log full chain server-side, return generic "try again" client-side unless ValidationError.

## Retry classification

```go
func retryable(err error) bool {
    return errors.Is(err, ErrTemporary) || errors.Is(err, context.DeadlineExceeded)
}
```

Central retry helper avoids duplicate policy in every caller.

## Error monitoring sampling

High-volume expected errors (404) sample at 1% in Sentry—prevent quota burn; always capture 5xx unwrapped chain.

## errors.Is vs == for sentinel

Wrapped sentinel compared with == fails—onboarding doc example shows correct errors.Is pattern; code review checklist item for Go newcomers first month.

## Rollout guidance

Error handling style guide published internal backlink from go.mod README new contractor onboarding day one—reduces review comment duplication senior engineers tired repeating wrap with percent w.

## Team practices

Shipping Go Error Handling Wrapping in production taught our team that documentation beats hero demos. We wrote runbooks covering failure modes, on-call steps, and rollback triggers before the second release, not after the first outage.

When reviewing PRs touching Go Error Handling Wrapping, we ask for measurable outcomes: latency, crash rate, or support ticket volume—not subjective feels faster. If metrics are unavailable, the PR includes a DevTools trace or load test snippet proving the change.

Onboarding engineers paste a checklist into their first Go Error Handling Wrapping PR description: environment setup verified, tests added or updated, accessibility spot-checked, and release notes drafted for user-visible changes.

We keep a living FAQ in the repo wiki for Go Error Handling Wrapping questions repeated in Slack more than twice. FAQ entries link to source files and Slack threads, reducing tribal knowledge and repeated explanations in code review.

## Resources

- [Working with Errors in Go 1.13](https://go.dev/blog/go1.13-errors)
- [errors package](https://pkg.go.dev/errors)
- [fmt.Errorf wrapping](https://pkg.go.dev/fmt#Errorf)
- [Go FAQ — exceptions](https://go.dev/doc/faq#exceptions)
- [Upsert: Don’t just check errors, handle them gracefully (Rob Pike)](https://go.dev/blog/error-handling-and-go)
