---
title: "Local-First Apps with CRDTs"
slug: "local-first-apps-crdts"
description: "How to build local-first apps with CRDTs: conflict-free offline sync, why CRDTs beat last-write-wins, and using Automerge or Yjs in production without the sharp edges."
datePublished: "2026-06-18"
dateModified: "2026-06-18"
tags: ["Local-First", "CRDTs", "Offline Sync", "Architecture"]
keywords: "local-first, CRDT, offline sync, Automerge, conflict-free replicated data types, Yjs, collaboration"
faq:
  - q: "What is a local-first app?"
    a: "A local-first app stores the authoritative data on the user's device and treats the network as an optional sync channel. The app works fully offline, responds instantly because reads and writes hit local storage, and syncs with the server and other devices in the background when connectivity allows."
  - q: "What is a CRDT and why use one?"
    a: "A CRDT (conflict-free replicated data type) is a data structure that multiple devices can edit independently and merge automatically without conflicts or a central coordinator. It's the piece that makes local-first sync reliable, because concurrent edits from different devices always converge to the same state."
  - q: "When should you not use CRDTs?"
    a: "CRDTs carry metadata overhead and don't enforce global invariants like uniqueness or 'balance must not go negative.' For strong-consistency needs — payments, inventory, anything requiring a single source of truth at write time — a server-authoritative model with transactions is the right tool, not a CRDT."
---

The pitch for local-first is easy to want: an app that opens instantly, works on a plane, and syncs across devices without ever showing a spinner or a merge-conflict dialog. The hard part is the last clause. Two devices edit the same document offline, both come back online — what happens? Last-write-wins silently throws away someone's work. CRDTs are the data structures that make that merge automatic and lossless, and they're the reason local-first is now a practical architecture rather than a research topic.

I've built offline-heavy mobile apps where sync correctness was the entire ballgame, so I want to be concrete about what CRDTs buy you, what they cost, and when *not* to reach for them.

## What "local-first" actually commits you to

Local-first isn't just "has an offline cache." It's a stance: the copy of the data on the device is authoritative for that device, reads and writes go to local storage first, and the server is a sync peer rather than the source of truth. The payoff is that the UI never waits on the network — the same principle behind [offline-first Flutter with sync](https://blog.michaelsam94.com/offline-first-flutter-sync/), taken to its logical end.

That stance forces one question to the front: when two authoritative copies diverge, how do they reconcile? You have three real options — last-write-wins (lossy), manual conflict resolution (terrible UX), or automatic conflict-free merging. CRDTs are the third.

## Why last-write-wins isn't good enough

Last-write-wins is tempting because it's trivial: tag each field with a timestamp, newest wins. It works until it doesn't. Two users edit different fields of the same record offline; LWW on the whole record discards one user's field entirely even though there was no real conflict. Or two users append items to the same list; LWW keeps one list and drops the other. The data loss is silent, which is the worst kind.

CRDTs solve this by making the *merge* a property of the data structure itself. A CRDT list knows how to combine two concurrent sets of insertions so both survive in a deterministic order. A CRDT map merges per-key. Concurrent edits converge to the same final state on every device, with no coordinator and no lost writes — mathematically guaranteed, not best-effort.

## A concrete look with Automerge

Here's the shape of it with Automerge, which gives you a JSON-like document that merges automatically:

```js
import * as Automerge from "@automerge/automerge";

// Device A
let docA = Automerge.init();
docA = Automerge.change(docA, (d) => {
  d.tasks = [{ title: "Draft proposal", done: false }];
});

// Device B starts from the same doc, edits offline
let docB = Automerge.clone(docA);
docB = Automerge.change(docB, (d) => { d.tasks[0].done = true; });
docA = Automerge.change(docA, (d) => { d.tasks[0].title = "Draft Q3 proposal"; });

// They sync — merge is automatic and lossless
const merged = Automerge.merge(docA, docB);
// merged.tasks[0] === { title: "Draft Q3 proposal", done: true }
```

Device A changed the title, device B marked it done, and the merge keeps both. No conflict dialog, no lost edit. That's the entire value proposition in eight lines. Yjs offers a similar model optimized for text and real-time collaboration — it's what a lot of collaborative editors are built on.

## The costs nobody mentions in the demo

CRDTs are not free, and the demos hide the bill:

- **Metadata overhead.** To merge correctly, CRDTs track causal history — who changed what, when, relative to what. That metadata grows with edit history and can dwarf the actual data for long-lived documents. Automerge and Yjs both have compaction/GC strategies; you need to use them.
- **Document size and memory.** A CRDT document is heavier in memory than the plain object it represents. For large collaborative documents this matters, especially on mobile where memory is tight.
- **No global invariants.** This is the big one. A CRDT guarantees convergence, not correctness of business rules. It cannot enforce "usernames are unique" or "account balance never goes negative," because those require a global view at write time that the local-first model deliberately doesn't have. Two devices can both offline-claim the same username and both merges succeed.
- **Loading and rehydration cost.** Reconstructing a document from its op log on app start can be slow for large histories; you'll want snapshots.

## Where CRDTs fit — and where they don't

The clean rule I use: CRDTs are for **collaborative, user-owned, mergeable data** where eventual consistency is acceptable and every edit should survive. Notes, documents, task lists, drawings, personal data synced across a user's own devices — perfect. The user is editing *their* stuff, and losing an edit is the cardinal sin.

CRDTs are the wrong tool for **contended resources with hard invariants**: payments, inventory counts, seat reservations, unique identifiers. Those need a server that says yes or no authoritatively at write time — a strong-consistency model with transactions, not a merge. Trying to enforce "only 100 tickets" with CRDTs is how you oversell a concert. For that class of problem, keep the server authoritative and use the [idempotency patterns](https://blog.michaelsam94.com/idempotency-distributed-systems/) from distributed systems instead.

Many real apps are hybrids: CRDTs for the collaborative document body, a server-authoritative path for the things that must be globally correct. That's not a cop-out, it's the right decomposition.

## Sync architecture in practice

CRDTs handle the merge, but you still design the transport. A common, robust setup:

1. Each device persists its CRDT document locally (IndexedDB on web, SQLite/file on mobile).
2. Devices exchange *changes*, not whole documents — both Automerge and Yjs produce compact change/update blobs.
3. A relay server (or peer connection) forwards changes between devices and stores them so a device that was offline for a week can catch up.
4. On reconnect, a device sends what it has and requests what it's missing; the CRDT applies incoming changes and converges.

The server here is dumb on purpose — it stores and forwards opaque change blobs and doesn't need to understand or resolve anything. That simplicity is a feature; it's also why this composes well with [running code at the edge](https://blog.michaelsam94.com/edge-computing-functions/), since the relay is stateless-ish and latency-friendly.

## The bottom line

CRDTs turn "sync is a nightmare of conflicts" into "sync just converges," and that's what makes genuinely local-first apps buildable. Reach for Automerge or Yjs when you're syncing a user's own mergeable data across devices or between collaborators, and you want every edit to survive. Don't reach for them when you need one authoritative answer to a contended question — that's a server's job. Get that boundary right and you can build apps that feel instant, work offline, and never lose a keystroke. Get it wrong and you'll either lose data or oversell the concert.

## Resources

- [localfirst.fyi — resources and reading](https://localfirstweb.dev/)
- [Automerge documentation](https://automerge.org/)
- [Yjs — shared editing framework](https://docs.yjs.dev/)
- ["Local-first software" (Ink & Switch essay)](https://www.inkandswitch.com/local-first/)
- [CRDT.tech — the CRDT reference site](https://crdt.tech/)
- [MDN: IndexedDB API](https://developer.mozilla.org/en-US/docs/Web/API/IndexedDB_API)
