---
title: "Collaborative Editing with CRDTs"
slug: "realtime-collaborative-editing-crdt"
description: "How CRDTs enable conflict-free collaborative text editing: LWW registers, sequence CRDTs, Yjs and Automerge in practice, and when OT is still the better choice."
datePublished: "2026-01-06"
dateModified: "2026-01-06"
tags: ["Real-Time", "Distributed Systems", "IoT", "Architecture"]
keywords: "CRDT collaborative editing, conflict-free replicated data types, Yjs, Automerge, operational transform, real-time sync"
faq:
  - q: "What is a CRDT and why use one for collaborative editing?"
    a: "A Conflict-free Replicated Data Type is a data structure designed so concurrent updates from multiple users always merge to a consistent state without coordination. For collaborative editing, sequence CRDTs (like Yjs's Y.Text or Automerge's Text) let each client apply local edits instantly and merge remote edits deterministically — no central server deciding winner/loser on every keystroke."
  - q: "How do CRDTs differ from Operational Transform?"
    a: "OT transforms operations against each other relative to a shared document revision, usually requiring a central server or strict ordering. CRDTs embed causality in the data structure itself, so peers can merge offline and out-of-order. OT tends to be more compact for plain text; CRDTs tolerate partition and decentralization better."
  - q: "What are the main downsides of CRDT-based editors?"
    a: "CRDTs carry metadata overhead — tombstones, unique IDs, or fractional indices — that grows with edit history unless compacted. Large documents with years of edits can become heavy. Debugging merge behavior is harder than a single authoritative server log. For many products, a hosted service (Liveblocks, PartyKit with Yjs) abstracts this cost."
---

Google Docs made real-time co-editing feel magic. Under the hood, that magic is a convergence algorithm — either Operational Transform or Conflict-free Replicated Data Types — that guarantees two people typing in the same paragraph never permanently diverge. CRDTs have become the default choice for new collaborative products because they merge without a single point of coordination, which means offline editing, peer-to-peer sync, and simpler mental models when the network misbehaves.

I shipped a notes app with Yjs last year. The product requirement was "works in a subway tunnel." CRDTs made that achievable without inventing a custom offline queue and replay protocol.

## The convergence problem in one paragraph

Alice and Bob both edit the word "hello" at the same time. Alice inserts "!" at the end; Bob deletes the second "l." What is the document state after both operations arrive? A convergence algorithm must give every replica the same answer, regardless of delivery order. CRDTs achieve this by designing the data structure so merges are associative, commutative, and idempotent — math words that translate to "apply updates in any order, get the same result."

## Sequence CRDTs for text

Plain text is an ordered sequence of characters. Sequence CRDTs assign each character (or insert) a unique position identifier that determines sort order when merging:

- **Fractional indexing** — positions like `1.5` between `1` and `2`. Simple but identifiers grow unboundedly with edits.
- **Lamport + unique ID** — `(clock, nodeId)` pairs totally order inserts from different replicas.
- **Tree-based (RGA, YATA)** — linked structures with tombstones for deletes.

Deletes are almost always **tombstones** — mark removed, do not physically erase — because erasing would let a late-arriving insert resurrect in the wrong place. Compaction strategies (snapshots, garbage collection of old tombstones) are essential for long-lived documents.

```javascript
import * as Y from "yjs";
import { WebsocketProvider } from "y-websocket";

const doc = new Y.Doc();
const ytext = doc.getText("content");

// Local edit — instant, no round trip
ytext.insert(0, "Hello");

// Sync over WebSocket
const provider = new WebsocketProvider("wss://sync.example.com", "room-1", doc);

ytext.observe(() => {
  console.log(ytext.toString());
});
```

Yjs handles the CRDT mechanics; you handle persistence, auth, and UI binding.

## Yjs vs Automerge — practical comparison

Both are production-grade. The choice is usually ecosystem fit:

| Factor | Yjs | Automerge |
| --- | --- | --- |
| Wire format | Binary, compact | Binary (Automerge 2.x) |
| Bindings | ProseMirror, TipTap, CodeMirror, Monaco | Custom integrations |
| Persistence | y-leveldb, y-indexeddb | automerge-repo |
| Learning curve | Lower with editor bindings | Lower for JSON-like docs |

For rich text with ProseMirror or TipTap, Yjs is the path of least resistance. For JSON-shaped app state (forms, whiteboards, design tools), Automerge's document model maps cleanly.

## Architecture for a production CRDT editor

A typical stack:

1. **Client** — Yjs doc bound to editor (TipTap + y-prosemirror).
2. **Sync server** — WebSocket relay (y-websocket, Hocuspocus, Liveblocks). The server forwards updates; it does not need to understand text.
3. **Persistence** — Store Yjs state vectors or update blobs in Postgres/S3. On join, send missing updates since client's state vector.
4. **Auth** — Room-level tokens; validate before WebSocket upgrade.

The sync server is not authoritative for conflict resolution — CRDTs merge on the client. The server is a message bus and persistence layer. This is different from OT systems where the server transforms every operation.

Offline flow: edits apply locally, updates queue in IndexedDB (y-indexeddb), replay on reconnect. CRDT merge handles any overlap with remote edits during the offline window.

## When OT still wins

CRDTs are not universally superior:

- **Massive plain-text documents with tight bandwidth** — OT history can be more compact if you accept central coordination.
- **Strict server audit requirements** — a single OT log is easier to replay for compliance than distributed CRDT state.
- **Existing OT infrastructure** — Google Docs is not switching. Neither should you if OT works.

For greenfield collaborative features in 2026, CRDT libraries have matured past the "research prototype" stage. The engineering work shifts from algorithm correctness to persistence, compaction, and access control.

## Compaction and document hygiene

Unbounded tombstone growth kills performance. Production systems need:

- **Periodic snapshots** — serialize compact state, discard ancient update history.
- **Retention policy** — drop tombstones older than N days if business rules allow.
- **Document size monitoring** — alert when binary state exceeds thresholds.

I snapshot on a timer and on last-client-leave for a room. That keeps cold-start load bounded without losing recent merge capability.

Treat production rollout as a measured change: ship with observability, validate rollback, and review metrics 24 hours after deploy — patterns that look obvious in docs fail when skipped under release pressure.

## Common production mistakes

Teams get collaborative editing crdt wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of collaborative editing crdt fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When collaborative editing crdt misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Yjs documentation](https://docs.yjs.dev/)
- [Automerge documentation](https://automerge.org/docs/)
- [CRDT.tech — papers and implementations](https://crdt.tech/)
- [Hocuspocus — collaborative backend for Yjs](https://tiptap.dev/hocuspocus)
- [Conflict-free Replicated Data Types (Shapiro et al.)](https://hal.science/hal-01269388/document)
