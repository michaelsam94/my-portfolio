---
title: "gRPC Interceptors and Middleware"
slug: "grpc-interceptors-middleware"
description: "Build cross-cutting gRPC concerns with interceptors: authentication, logging, tracing, rate limiting, and recovery — for Go, Java, and Kotlin servers."
datePublished: "2025-06-25"
dateModified: "2025-06-25"
tags: ["Backend", "gRPC", "Architecture", "Security"]
keywords: "gRPC interceptors, gRPC middleware, unary interceptor, stream interceptor, gRPC authentication, OpenTelemetry gRPC tracing"
faq:
  - q: "What are gRPC interceptors?"
    a: "Interceptors are middleware for gRPC — functions that wrap RPC handlers to run logic before and after each call. Unary interceptors wrap single request/response RPCs. Stream interceptors wrap streaming RPCs. They handle cross-cutting concerns (auth, logging, metrics) without polluting business logic."
  - q: "What's the interceptor execution order?"
    a: "Interceptors chain like HTTP middleware. The first registered interceptor runs first on inbound (server) and last on outbound. Order matters: recovery should be outermost, then tracing, then auth, then logging, then your handler."
  - q: "Can interceptors modify requests and responses?"
    a: "Yes. A unary server interceptor receives the request, can modify it or reject it (return an error), call the handler, then modify the response before returning. This is how auth interceptors reject unauthenticated calls before they reach business logic."
---

Business logic shouldn't know about JWT validation, trace ID injection, or panic recovery. In HTTP APIs, that's middleware. In gRPC, it's interceptors — same concept, different API surface. Once you extract auth and observability into interceptors, your service handlers shrink to the actual work and every RPC gets consistent behavior without copy-paste.

## Unary server interceptor (Go)

```go
func AuthInterceptor(ctx context.Context, req interface{}, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (interface{}, error) {
    md, ok := metadata.FromIncomingContext(ctx)
    if !ok {
        return nil, status.Error(codes.Unauthenticated, "missing metadata")
    }

    tokens := md.Get("authorization")
    if len(tokens) == 0 {
        return nil, status.Error(codes.Unauthenticated, "missing token")
    }

    claims, err := validateJWT(strings.TrimPrefix(tokens[0], "Bearer "))
    if err != nil {
        return nil, status.Error(codes.Unauthenticated, "invalid token")
    }

    ctx = context.WithValue(ctx, userKey, claims)
    return handler(ctx, req)
}
```

Register on server creation:

```go
server := grpc.NewServer(
    grpc.ChainUnaryInterceptor(
        recoveryInterceptor,
        otelgrpc.UnaryServerInterceptor(),
        AuthInterceptor,
        loggingInterceptor,
    ),
)
```

`ChainUnaryInterceptor` runs them in order: recovery → tracing → auth → logging → handler.

## Logging interceptor

```go
func loggingInterceptor(ctx context.Context, req interface{}, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (interface{}, error) {
    start := time.Now()
    resp, err := handler(ctx, req)
    code := codes.OK
    if err != nil {
        code = status.Code(err)
    }
    log.Info("rpc",
        "method", info.FullMethod,
        "code", code.String(),
        "duration_ms", time.Since(start).Milliseconds(),
    )
    return resp, err
}
```

Log method name, status code, and duration on every RPC. Never log request/response payloads by default — they contain PII.

## Recovery interceptor

An unhandled panic in a gRPC handler kills the stream and returns `UNKNOWN` to the client with no useful info:

```go
func recoveryInterceptor(ctx context.Context, req interface{}, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (resp interface{}, err error) {
    defer func() {
        if r := recover(); r != nil {
            log.Error("panic recovered", "method", info.FullMethod, "panic", r, "stack", debug.Stack())
            err = status.Error(codes.Internal, "internal error")
        }
    }()
    return handler(ctx, req)
}
```

Put recovery outermost so it catches panics from any inner interceptor too.

## Client interceptors

Attach auth tokens and trace context on outbound calls:

```go
func clientAuthInterceptor(ctx context.Context, method string, req, reply interface{}, cc *grpc.ClientConn, invoker grpc.UnaryInvoker, opts ...grpc.CallOption) error {
    md, ok := metadata.FromOutgoingContext(ctx)
    if !ok {
        md = metadata.New(nil)
    }
    if token := getTokenFromContext(ctx); token != "" {
        md.Set("authorization", "Bearer "+token)
    }
    ctx = metadata.NewOutgoingContext(ctx, md)
    return invoker(ctx, method, req, reply, cc, opts...)
}

conn, err := grpc.Dial("localhost:50051",
    grpc.WithUnaryInterceptor(clientAuthInterceptor),
)
```

## Stream interceptors

Streaming RPCs need separate interceptors:

```go
func streamAuthInterceptor(srv interface{}, ss grpc.ServerStream, info *grpc.StreamServerInfo, handler grpc.StreamHandler) error {
    ctx := ss.Context()
    // validate auth from ctx metadata
    return handler(srv, &wrappedStream{ServerStream: ss, ctx: ctx})
}

type wrappedStream struct {
    grpc.ServerStream
    ctx context.Context
}

func (w *wrappedStream) Context() context.Context { return w.ctx }
```

Stream interceptors wrap the `ServerStream` to inject context values — the stream's `Context()` method is the only way to pass auth claims to the handler.

## Java / Kotlin interceptors

Java uses `ServerInterceptor`:

```java
public class AuthInterceptor implements ServerInterceptor {
    @Override
    public <ReqT, RespT> ServerCall.Listener<ReqT> interceptCall(
            ServerCall<ReqT, RespT> call,
            Metadata headers,
            ServerCallHandler<ReqT, RespT> next) {

        String token = headers.get(AUTH_KEY);
        if (token == null || !validate(token)) {
            call.close(Status.UNAUTHENTICATED.withDescription("invalid token"), headers);
            return new ServerCall.Listener<>() {};
        }
        return next.startCall(call, headers);
    }
}

Server server = ServerBuilder.forPort(50051)
    .intercept(new AuthInterceptor())
    .intercept(new LoggingInterceptor())
    .addService(new OrderServiceImpl())
    .build();
```

## OpenTelemetry tracing

The `otelgrpc` instrumentation handles trace propagation automatically:

```go
import "go.opentelemetry.io/contrib/instrumentation/google.golang.org/grpc/otelgrpc"

server := grpc.NewServer(
    grpc.StatsHandler(otelgrpc.NewServerHandler()),
)
```

This creates spans for each RPC, propagates trace context via metadata, and records status codes. Pair with a logging interceptor that reads the trace ID from context for correlation.

## Rate limiting interceptor

```go
func rateLimitInterceptor(limiter *rate.Limiter) grpc.UnaryServerInterceptor {
    return func(ctx context.Context, req interface{}, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (interface{}, error) {
        if !limiter.Allow() {
            return nil, status.Error(codes.ResourceExhausted, "rate limit exceeded")
        }
        return handler(ctx, req)
    }
}
```

For per-client rate limiting, key the limiter by client identity from the auth interceptor's context value.

## Testing interceptors

Write unit tests that verify interceptor behavior without starting a full server:

```go
func TestAuthInterceptor_RejectsMissingToken(t *testing.T) {
    handler := func(ctx context.Context, req interface{}) (interface{}, error) {
        t.Fatal("handler should not be called")
        return nil, nil
    }

    _, err := AuthInterceptor(context.Background(), struct{}{},
        &grpc.UnaryServerInfo{FullMethod: "/test.Test/Call"}, handler)

    st, _ := status.FromError(err)
    assert.Equal(t, codes.Unauthenticated, st.Code())
}
```

Test the rejection path, the happy path, and panic recovery independently. Interceptors are security boundaries — they deserve the same test coverage as auth handlers.

## Common production mistakes

Teams get interceptors middleware wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of interceptors middleware fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [gRPC Go interceptors documentation](https://github.com/grpc/grpc-go/blob/master/Documentation/interceptors.md) — unary and stream interceptor APIs
- [go-grpc-middleware](https://github.com/grpc-ecosystem/go-grpc-middleware) — production-ready interceptors for logging, auth, recovery, and retry
- [OpenTelemetry gRPC instrumentation](https://pkg.go.dev/go.opentelemetry.io/contrib/instrumentation/google.golang.org/grpc/otelgrpc) — automatic trace propagation
- [gRPC Java ServerInterceptor](https://grpc.io/docs/languages/java/server-side-observability/) — Java interceptor patterns
