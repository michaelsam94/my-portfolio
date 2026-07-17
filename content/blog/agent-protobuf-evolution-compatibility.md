---
title: "AI Agents: Protobuf Evolution Compatibility"
slug: "agent-protobuf-evolution-compatibility"
description: "How to evolve agent event schemas, tool RPC payloads, and streaming token frames in Protocol Buffers without breaking consumers mid-rollout."
datePublished: "2025-02-12"
dateModified: "2025-02-12"
tags: ["AI", "Agent", "Protobuf"]
keywords: "protobuf schema evolution, field numbers, backward compatibility, buf breaking changes, agent event schema, gRPC versioning"
faq:
  - q: "Can I rename a protobuf field without breaking wire compatibility?"
    a: "Yes, if the field number stays the same and you only change the name in .proto source. Generated code changes, but on-the-wire bytes are unchanged. Renumbering a field is a breaking change—old binaries will misinterpret payloads."
  - q: "What is the safest way to add a new field to an agent ToolRequest message?"
    a: "Assign the next unused field number, mark it optional (proto3 optional or explicit presence), default safely, and deploy consumers before producers if the field is required for new behavior. Never reuse a retired field number; reserve it with a comment or reserved statement."
  - q: "How do oneof fields affect evolution?"
    a: "Adding a new oneof variant is backward compatible if clients ignore unknown fields. Changing which fields share a oneof, or moving an existing field into a oneof, is breaking. Agent tool argument unions often start as oneof—plan variant additions as additive only."
  - q: "Should agent teams use JSON or protobuf for external webhooks?"
    a: "JSON over HTTP for third-party integrators who cannot compile schemas; protobuf internally between your services. If you expose JSON mapped from proto, document that unknown JSON fields are ignored and never rely on JSON field name changes without version bumps."
---
The deploy looked innocent: add `retrieval_context_id` to `AgentTurnEvent` so downstream eval pipelines could join retrieval logs with generation logs. Within twenty minutes, the Rust ingestion service panicked on parse—except protobuf parsers do not panic on unknown fields. The panic came from application code that matched on `event.payload` as a closed enum and hit `UNRECOGNIZED` after someone renumbered an existing field to "make room" for the new ID. Wire compatibility survived in theory. Team discipline did not.

Protocol Buffers encode a contract optimized for evolution—if you follow the rules. Agent platforms generate enormous schema surface area quickly: tool definitions, streaming token frames, human feedback envelopes, embedding job batches. JSON-first prototypes harden into gRPC services under traffic. This piece is a field guide to evolving those schemas without coordinated big-bang deploys.

## Mental model: tags, not names

On the wire, a protobuf message is a sequence of `(field_number, wire_type, value)` triples. Field **names** exist for humans and code generators; field **numbers** are the real API.

```
AgentTurnEvent (conceptual on-wire)
  [1] string session_id = "abc"
  [2] int32 turn_index = 7
  [5] ToolInvocation tool = { ... }   // note gap: 3,4 unused or reserved
  [6] string retrieval_context_id = "ctx-9f2"
```

A consumer compiled against an older `.proto` ignores field 6 entirely—stored as unknown fields in many runtimes. A consumer that **requires** field 6 before producers send it gets default empty string—usually fine if your logic treats empty as "legacy event."

Breaking changes re-use numbers, change wire types, or move fields between oneofs in ways old code cannot interpret.

## Safe changes (do these freely)

| Change | Compatible? | Notes |
|--------|-------------|-------|
| Add new field with new number | Yes | Old code ignores it |
| Add `optional` / explicit presence | Yes | Proto3 optional is evolution-friendly |
| Add enum value (at end) | Yes* | *Old clients may drop unrecognized enum on serialize—test |
| Add message to a oneof | Yes | New variant only |
| Reserve deleted field numbers | Yes | Prevents accidental reuse |
| Rename field or message | Yes | Number unchanged |

## Breaking changes (require version bump or new message)

| Change | Why it breaks |
|--------|---------------|
| Change field number | Wrong slot on wire |
| Change field type (e.g. int32 → string) | Wire type mismatch |
| Delete field without reservation | Number may be reused later |
| Rename enum numeric values | Same wire, semantic shift |
| Move existing field into oneof | Old layout incompatible |

When you must break, ship `AgentTurnEventV2` on a new topic or RPC method and run dual-write until consumers migrate. Do not "just fix" the original message in place.

## A concrete agent schema evolution

Start with a minimal turn event:

```protobuf
syntax = "proto3";

package agent.v1;

message AgentTurnEvent {
  string session_id = 1;
  uint32 turn_index = 2;
  string model_id = 3;
  repeated ToolInvocation tools = 4;
}

message ToolInvocation {
  string name = 1;
  bytes arguments_json = 2;  // deferred JSON for flexibility
  ToolStatus status = 3;
}

enum ToolStatus {
  TOOL_STATUS_UNSPECIFIED = 0;
  TOOL_STATUS_OK = 1;
  TOOL_STATUS_ERROR = 2;
}
```

Phase 2: add retrieval join key without breaking Rust, Go, and Python consumers:

```protobuf
message AgentTurnEvent {
  reserved 5;              // if you deleted an experimental field
  reserved "debug_blob";

  string session_id = 1;
  uint32 turn_index = 2;
  string model_id = 3;
  repeated ToolInvocation tools = 4;
  optional string retrieval_context_id = 6;  // skip 5 if reserved
}
```

Phase 3: structured tool args alongside JSON for gradual migration:

```protobuf
message ToolInvocation {
  string name = 1;
  bytes arguments_json = 2;
  ToolStatus status = 3;
  oneof typed_args {
    CalendarArgs calendar = 4;
    BillingArgs billing = 5;
  }
}

message CalendarArgs {
  string event_title = 1;
  int64 start_unix_ms = 2;
}
```

Consumers that only read `arguments_json` keep working. New orchestrators populate `typed_args` for type-safe validation. This dual representation costs bytes—acceptable in audit topics, questionable in per-token streaming frames where you want slim binary.

## Streaming frames need extra discipline

Token streaming messages often arrive at kilohertz aggregate rates. Prefer **additive** fields and fixed framing:

```protobuf
message StreamFrame {
  uint64 sequence = 1;
  oneof payload {
    TokenDelta token = 2;
    ToolCallStart tool_start = 3;
    ToolCallEnd tool_end = 4;
    Heartbeat heartbeat = 5;
  }
}
```

Adding `ToolCallProgress` as variant 6 is safe. Splitting `TokenDelta` into separate message types on the same field number is not.

For WebSocket clients using proto-json, enable `json_name` annotations once and never rename without a version bump—JavaScript clients often bind to JSON keys, not proto names.

## Automate compatibility checks in CI

Human review of field numbers does not scale. **Buf** (or prototool) breaking-change detection against main:

```yaml
# buf.yaml
version: v2
modules:
  - path: proto
breaking:
  use:
    - FILE
lint:
  use:
    - DEFAULT
```

```bash
# In CI before merge
buf breaking --against '.git#branch=main'
```

FILE-level breaking rules catch field renames that change JSON casing integrations rely on, not just wire tags. For agent monorepos, pin generated stubs in the same PR as `.proto` changes so code review sees both.

## Unknown fields and application logic

Protobuf guarantees parsing survives unknown fields; your **business logic** might not:

```go
// Fragile — breaks when proto adds TOOL_STATUS_PENDING = 3
switch inv.Status {
case agentv1.ToolStatus_TOOL_STATUS_OK:
    // ...
case agentv1.ToolStatus_TOOL_STATUS_ERROR:
    // ...
default:
    panic("unexpected tool status")
}
```

Prefer open handling:

```go
if inv.Status != agentv1.ToolStatus_TOOL_STATUS_OK {
    metrics.ToolNonOK.Inc()
    // handle or skip; do not panic on unrecognized enum
}
```

Same for `oneof` switches in Rust and TypeScript—always include a fallback arm that logs and continues.

## JSON, GraphQL, and the impedance mismatch

Teams expose agent tool schemas to no-code builders as JSON Schema converted from proto. Conversion is lossy around `oneof`, `map`, and `Timestamp`. Document round-trip rules:

- Never expose internal field numbers in public docs.
- Version public JSON schemas (`toolSchemaVersion: 2`).
- When proto adds fields, JSON Schema `additionalProperties: false` integrations break—prefer `true` for extensibility on public surfaces.

## Migration playbook for live traffic

1. **Add** fields in proto; release consumers (ignore new data).
2. **Deploy** producers writing new fields (dual-write optional legacy).
3. **Migrate** readers to use new fields when present.
4. **Deprecate** legacy paths; `reserved` old fields after traffic at zero.
5. **Delete** dead code paths—not just proto comments.

For Kafka topics, use subject compatibility (Confluent Schema Registry with PROTOBUF) or embed `schema_version` in message headers if you manage schemas in Git.

```protobuf
// Header: schema_version=3
message AgentTurnEvent { ... }
```

Consumers read header first and dispatch to parser v3 or v2. Heavyweight but explicit when Buf breaking checks cannot cover all runtimes.

## Field number allocation discipline

Agent repos often sprawl across ten services generating stubs from the same proto tree. Assign number ranges per domain to reduce merge conflicts:

| Range | Owner | Example messages |
|-------|-------|------------------|
| 1–99 | Core session | `AgentTurnEvent`, `StreamFrame` |
| 100–199 | Tools | `ToolInvocation`, `ToolResult` |
| 200–299 | Retrieval | `RetrievalQuery`, `ChunkHit` |
| 300–399 | Human feedback | `Rating`, `Correction` |

Publish the registry in `proto/README.md`. CI rejects PRs that allocate outside range without platform review.

Never set `json_name` to camelCase in proto3 then switch to snake_case in public REST—the wire is unchanged but mobile clients desync. Pick a JSON convention and lint it.

## Closing thought

Protobuf evolution compatibility is a social contract enforced by integers. Agent systems change fast; field numbers change never—or only with a numbered migration plan. Treat `.proto` files like database migrations: additive by default, breaking changes get a new table name, not a silent ALTER.

## Resources

- [Protocol Buffers — Updating a Message Type](https://protobuf.dev/programming-guides/proto3/#updating)
- [Buf breaking change detection rules](https://buf.build/docs/breaking/rules/)
- [Google API Improvement Guide — Compatibility](https://cloud.google.com/apis/design/compatibility)
- [Confluent Schema Registry — Protobuf](https://docs.confluent.io/platform/current/schema-registry/fundamentals/serdes-develop/serdes-protobuf.html)
- [gRPC versioning guidance](https://grpc.io/docs/guides/versioning/)
