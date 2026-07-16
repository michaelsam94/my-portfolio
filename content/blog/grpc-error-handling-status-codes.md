---
title: "gRPC Error Handling"
slug: "grpc-error-handling-status-codes"
description: "Handle errors correctly in gRPC: status codes, rich error details, client-side retry logic, and mapping gRPC errors to HTTP for gateways."
datePublished: "2025-06-22"
dateModified: "2025-06-22"
tags: ["Backend", "gRPC", "API", "Architecture"]
keywords: "gRPC error handling, gRPC status codes, grpc-status-details-bin, gRPC retry, error details protobuf, DEADLINE_EXCEEDED"
faq:
  - q: "What gRPC status codes should I use for common errors?"
    a: "INVALID_ARGUMENT for bad client input, NOT_FOUND for missing resources, ALREADY_EXISTS for duplicate creation, PERMISSION_DENIED for authorization failures, UNAUTHENTICATED for missing/invalid credentials, INTERNAL for unexpected server bugs, UNAVAILABLE for transient failures worth retrying, and DEADLINE_EXCEEDED for timeouts."
  - q: "How do I attach structured error details to gRPC errors?"
    a: "Use google.rpc.Status with google.rpc.ErrorInfo, BadRequest, or custom protobuf messages packed into Any details. Clients extract details from the trailing metadata header grpc-status-details-bin. This gives clients machine-readable error context beyond a plain string message."
  - q: "Which gRPC errors are safe to retry?"
    a: "Retry UNAVAILABLE and sometimes DEADLINE_EXCEEDED on idempotent operations. Never retry INVALID_ARGUMENT, NOT_FOUND, PERMISSION_DENIED, or ALREADY_EXISTS — the result won't change. Use exponential backoff with jitter. For non-idempotent calls, use idempotency keys before retrying anything."
---

HTTP gives you status codes everyone knows. gRPC gives you 16 status codes most developers can't name without looking them up — and a binary protocol that hides the message unless you decode it properly. Bad gRPC error handling shows up as clients that retry everything (duplicate writes) or retry nothing (fragile services). The fix is consistent status code usage, structured error details, and explicit retry policies.

## The 16 status codes you'll actually use

| Code | When | Retry? |
|------|------|--------|
| `OK` | Success | — |
| `CANCELLED` | Client cancelled | No |
| `INVALID_ARGUMENT` | Bad input (validation) | No |
| `NOT_FOUND` | Resource doesn't exist | No |
| `ALREADY_EXISTS` | Duplicate create | No |
| `PERMISSION_DENIED` | Not authorized | No |
| `UNAUTHENTICATED` | Missing/invalid auth | No (re-auth first) |
| `RESOURCE_EXHAUSTED` | Rate limited | Yes, with backoff |
| `FAILED_PRECONDITION` | State doesn't allow action | No |
| `ABORTED` | Concurrency conflict | Maybe (optimistic retry) |
| `OUT_OF_RANGE` | Value out of bounds | No |
| `UNIMPLEMENTED` | RPC not built yet | No |
| `INTERNAL` | Server bug | No (alert on-call) |
| `UNAVAILABLE` | Transient failure | Yes |
| `DEADLINE_EXCEEDED` | Timeout | Maybe (if idempotent) |

The rest (`UNKNOWN`, `DATA_LOSS`) should be rare and alarming.

## Returning errors on the server

Go:

```go
import (
    "google.golang.org/grpc/codes"
    "google.golang.org/grpc/status"
)

func (s *Server) CreateOrder(ctx context.Context, req *pb.CreateOrderRequest) (*pb.Order, error) {
    if req.GetCustomerId() == "" {
        return nil, status.Error(codes.InvalidArgument, "customer_id is required")
    }

    existing, _ := s.repo.FindByIdempotencyKey(ctx, req.GetIdempotencyKey())
    if existing != nil {
        return nil, status.Error(codes.AlreadyExists, "order already created")
    }

    order, err := s.repo.Create(ctx, req)
    if err != nil {
        return nil, status.Errorf(codes.Internal, "create order: %v", err)
    }
    return order, nil
}
```

Never return internal error details (stack traces, SQL errors) to clients. Log them server-side; return a generic `INTERNAL` message.

## Rich error details

For validation errors, attach structured details:

```go
import (
    "google.golang.org/genproto/googleapis/rpc/errdetails"
    "google.golang.org/grpc/status"
    "google.golang.org/protobuf/types/known/anypb"
)

st := status.New(codes.InvalidArgument, "validation failed")
br := &errdetails.BadRequest{
    FieldViolations: []*errdetails.BadRequest_FieldViolation{
        {Field: "email", Description: "must be a valid email address"},
        {Field: "quantity", Description: "must be greater than 0"},
    },
}
st, _ = st.WithDetails(br)
return nil, st.Err()
```

Client extraction (Go):

```go
st, ok := status.FromError(err)
if !ok { return err }

for _, detail := range st.Details() {
    if br, ok := detail.(*errdetails.BadRequest); ok {
        for _, v := range br.FieldViolations {
            fmt.Printf("%s: %s\n", v.Field, v.Description)
        }
    }
}
```

This is how gRPC APIs return field-level validation errors without cramming JSON into the status message string.

## Client-side error handling

```go
resp, err := client.CreateOrder(ctx, req)
if err != nil {
    st, ok := status.FromError(err)
    if !ok {
        return fmt.Errorf("unknown error: %w", err)
    }

    switch st.Code() {
    case codes.InvalidArgument:
        return handleValidation(st)
    case codes.AlreadyExists:
        return fetchExistingOrder(ctx, req.IdempotencyKey)
    case codes.Unavailable, codes.DeadlineExceeded:
        return retryWithBackoff(ctx, req)
    default:
        return fmt.Errorf("rpc failed: %s", st.Message())
    }
}
```

Always use `status.FromError()` — don't string-match error messages.

## Retry with backoff

```go
func retryWithBackoff(ctx context.Context, req *pb.CreateOrderRequest) (*pb.Order, error) {
    backoff := 100 * time.Millisecond
    for attempt := 0; attempt < 3; attempt++ {
        resp, err := client.CreateOrder(ctx, req)
        if err == nil {
            return resp, nil
        }
        st, _ := status.FromError(err)
        if st.Code() != codes.Unavailable && st.Code() != codes.DeadlineExceeded {
            return nil, err
        }
        select {
        case <-ctx.Done():
            return nil, ctx.Err()
        case <-time.After(backoff):
        }
        backoff *= 2
    }
    return nil, fmt.Errorf("exhausted retries")
}
```

For production, use gRPC's built-in retry policy in service config or a library like `github.com/grpc-ecosystem/go-grpc-middleware/retry`.

## gRPC → HTTP mapping for gateways

If you expose gRPC services through grpc-gateway or Envoy:

| gRPC Code | HTTP Status |
|-----------|-------------|
| OK | 200 |
| INVALID_ARGUMENT | 400 |
| UNAUTHENTICATED | 401 |
| PERMISSION_DENIED | 403 |
| NOT_FOUND | 404 |
| ALREADY_EXISTS | 409 |
| RESOURCE_EXHAUSTED | 429 |
| INTERNAL | 500 |
| UNAVAILABLE | 503 |
| DEADLINE_EXCEEDED | 504 |

grpc-gateway handles this automatically. Custom error handlers can include the structured details in the HTTP response body.

## Logging and alerting

- Log `INTERNAL` errors at ERROR with full context
- Log `INVALID_ARGUMENT` at WARN (client bug or bad integration)
- Alert on `INTERNAL` rate spikes, not on `NOT_FOUND`
- Include trace ID in error metadata for support correlation

```go
st := status.New(codes.Internal, "internal error")
st, _ = st.WithDetails(&errdetails.ErrorInfo{
    Reason:   "DB_CONNECTION_FAILED",
    Domain:   "orders.example.com",
    Metadata: map[string]string{"trace_id": traceID},
})
```

Treat production rollout as a measured change: ship with observability, validate rollback, and review metrics 24 hours after deploy — patterns that look obvious in docs fail when skipped under release pressure.

## Common production mistakes

Teams get error handling status codes wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of error handling status codes fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When error handling status codes misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [gRPC Status Codes reference](https://grpc.io/docs/guides/status-codes/) — official definitions and usage guidance
- [google.rpc.ErrorDetails](https://github.com/googleapis/googleapis/blob/master/google/rpc/error_details.proto) — structured error detail protobuf definitions
- [gRPC Go status package](https://pkg.go.dev/google.golang.org/grpc/status) — server and client error APIs
- [grpc-gateway error handling](https://grpc-ecosystem.github.io/grpc-gateway/docs/mapping/customizing_your_gateway/) — mapping gRPC errors to HTTP responses
