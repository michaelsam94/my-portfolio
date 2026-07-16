---
title: "Bidirectional Streaming with gRPC"
slug: "grpc-streaming-bidirectional"
description: "Build bidirectional gRPC streams for real-time communication: chat, live sync, and device telemetry — with flow control, error handling, and Go/Java examples."
datePublished: "2025-06-28"
dateModified: "2025-06-28"
tags: ["Backend", "gRPC", "Architecture", "Performance"]
keywords: "gRPC bidirectional streaming, bidi stream, gRPC streaming RPC, real-time gRPC, stream flow control, gRPC chat example"
faq:
  - q: "When should I use bidirectional streaming instead of unary RPCs?"
    a: "Use bidi streaming when both client and server need to send multiple messages over a single long-lived connection — chat, live device command/response, collaborative editing, or real-time sync. If the client sends one request and gets one response, use unary. If only the server sends multiple messages, use server streaming."
  - q: "How does flow control work in gRPC streams?"
    a: "HTTP/2 flow control applies under the hood — the receiver advertises window size and the sender pauses when the window is exhausted. In application code, check stream context cancellation and handle backpressure by reading/writing in separate goroutines with bounded channels rather than unbounded buffering."
  - q: "What happens when a bidi stream breaks mid-conversation?"
    a: "The stream returns an error (UNAVAILABLE, CANCELLED, or DEADLINE_EXCEEDED). Neither side can send more messages on that stream. Clients must open a new stream and reconcile state — typically by fetching missed messages since a sequence number or timestamp before resuming the stream."
---

Unary RPCs are request-response. Server streaming is a firehose from server to client. Bidirectional streaming is a conversation — both sides talk when they have something to say, over one HTTP/2 connection. I used bidi streams for a device command channel where chargers send telemetry while the backend pushes configuration updates on the same socket. Trying to do that with polling or two separate streams was worse in every dimension.

## Four RPC types

| Type | Client sends | Server sends | Example |
|------|-------------|-------------|---------|
| Unary | 1 message | 1 message | GetOrder |
| Server streaming | 1 message | N messages | DownloadFile |
| Client streaming | N messages | 1 message | UploadFile |
| Bidirectional | N messages | N messages | Chat, live sync |

All four are defined in the `.proto` file:

```protobuf
service ChatService {
  rpc SendMessage (stream ChatMessage) returns (stream ChatMessage);
  rpc GetOrder (OrderRequest) returns (OrderResponse);
  rpc WatchPrices (PriceRequest) returns (stream PriceUpdate);
  rpc UploadLogs (stream LogEntry) returns (UploadSummary);
}
```

The `stream` keyword on both sides makes it bidirectional.

## Proto definition

```protobuf
syntax = "proto3";

message ChatMessage {
  string room_id = 1;
  string sender_id = 2;
  string text = 3;
  int64 sequence = 4;
}

message JoinRequest {
  string room_id = 1;
  string user_id = 2;
}

service Chat {
  rpc JoinRoom (stream ChatMessage) returns (stream ChatMessage);
}
```

## Server implementation (Go)

The server reads and writes on the same stream concurrently:

```go
func (s *ChatServer) JoinRoom(stream pb.Chat_JoinRoomServer) error {
    ctx := stream.Context()
    incoming := make(chan *pb.ChatMessage, 32)

    // Read goroutine
    go func() {
        for {
            msg, err := stream.Recv()
            if err != nil {
                close(incoming)
                return
            }
            incoming <- msg
        }
    }()

    // Broadcast to room subscribers
    for {
        select {
        case <-ctx.Done():
            return status.FromContextError(ctx.Err()).Err()
        case msg, ok := <-incoming:
            if !ok {
                return nil
            }
            s.broadcast(msg.RoomId, msg)
            if err := stream.Send(msg); err != nil {
                return err
            }
        }
    }
}
```

Separate read and write paths. Blocking `Recv()` in the main loop prevents you from sending.

A cleaner pattern uses two goroutines with errgroup:

```go
func (s *ChatServer) JoinRoom(stream pb.Chat_JoinRoomServer) error {
    ctx := stream.Context()
    g, ctx := errgroup.WithContext(ctx)

    g.Go(func() error {
        for {
            msg, err := stream.Recv()
            if err == io.EOF {
                return nil
            }
            if err != nil {
                return err
            }
            s.handleIncoming(ctx, msg)
        }
    })

    g.Go(func() error {
        for update := range s.subscribe(ctx, roomId) {
            if err := stream.Send(update); err != nil {
                return err
            }
        }
        return nil
    })

    return g.Wait()
}
```

## Client implementation (Go)

```go
stream, err := client.JoinRoom(ctx)
if err != nil {
    return err
}

// Send goroutine
go func() {
    for msg := range outgoing {
        if err := stream.Send(msg); err != nil {
            log.Error("send failed", "err", err)
            return
        }
    }
    stream.CloseSend()
}()

// Receive loop
for {
    msg, err := stream.Recv()
    if err == io.EOF {
        break
    }
    if err != nil {
        return err
    }
    handleMessage(msg)
}
```

Always call `CloseSend()` when done sending — it signals half-close so the server knows no more messages are coming.

## Error handling on streams

Stream errors differ from unary:

- **`io.EOF`** on `Recv()` — the other side closed cleanly
- **`CANCELLED`** — context cancelled or client disconnected
- **`UNAVAILABLE`** — connection dropped, retry with new stream
- Send after close — returns error immediately

Never ignore send errors in the write goroutine — propagate them to cancel the read side:

```go
g.Go(func() error {
    defer close(outgoing)
    for msg := range outgoing {
        if err := stream.Send(msg); err != nil {
            return err // cancels ctx, stops read goroutine
        }
    }
    return stream.CloseSend()
})
```

## Backpressure

Unbounded channels between read and write goroutines will OOM under load:

```go
// Bad — unbounded
incoming := make(chan *pb.ChatMessage)

// Good — bounded with drop or block policy
incoming := make(chan *pb.ChatMessage, 64)
```

When the channel is full, either block the reader (applying backpressure to the network) or drop with a metric increment. Blocking is usually correct for command channels; dropping may be acceptable for telemetry.

## When bidi isn't the answer

- **Request-response with occasional server push** — server streaming is simpler
- **Client uploads a file** — client streaming
- **Millions of short messages** — message queue (Kafka, NATS) with unary ack RPCs
- **Browser clients** — gRPC-Web has limited bidi support; use WebSocket or SSE for browsers

Bidi streams shine for long-lived, low-latency, two-way conversations between services or devices.

Treat production rollout as a measured change: ship with observability, validate rollback, and review metrics 24 hours after deploy — patterns that look obvious in docs fail when skipped under release pressure.

## Common production mistakes

Teams get streaming bidirectional wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of streaming bidirectional fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When streaming bidirectional misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [gRPC Streaming Guide](https://grpc.io/docs/languages/go/basics/#bidirectional-streaming-rpc) — official Go streaming tutorial
- [gRPC Flow Control](https://grpc.io/docs/guides/flow-control/) — HTTP/2 flow control under the hood
- [Go errgroup package](https://pkg.go.dev/golang.org/x/sync/errgroup) — coordinating read/write goroutines
- [gRPC Performance Best Practices](https://grpc.io/docs/guides/performance/) — connection management and stream tuning
