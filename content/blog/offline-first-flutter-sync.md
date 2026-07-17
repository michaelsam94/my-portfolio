---
title: "Offline-First Flutter Apps with Local Sync"
slug: "offline-first-flutter-sync"
description: "Build offline-first Flutter apps for flaky networks: a local Drift database as source of truth, an outbox sync queue, and pragmatic conflict resolution."
datePublished: "2026-05-21"
dateModified: "2026-07-17"
tags: ["Flutter", "Offline-First", "Sync", "Drift"]
keywords: "offline-first Flutter, local sync, Flutter offline, data sync, conflict resolution, Drift"
faq:
  - q: "What does offline-first mean in a Flutter app?"
    a: "Offline-first means the local database is the source of truth for the UI. Reads and writes hit local storage instantly, and a background sync process reconciles with the server when connectivity allows. The network becomes an enhancement, not a requirement."
  - q: "Which local database should I use for offline-first Flutter?"
    a: "Drift (SQLite) is my default because it gives typed queries, reactive streams the UI can watch, and full SQL for the reconciliation logic sync needs. Isar and Hive are lighter options, but sync-heavy apps benefit from SQL's querying power."
  - q: "How do you handle sync conflicts in an offline-first app?"
    a: "Pick a strategy per data type. Last-write-wins with server timestamps is simplest and fine for most fields; use per-field merging or CRDTs for collaborative data. Always keep an outbox of local changes with idempotency keys so retries never duplicate writes."
---

Offline-first is a shift in where truth lives. Instead of the UI calling the network and waiting, the **local database becomes the source of truth**: every read and write hits local storage instantly, and a background process syncs with the server whenever the connection allows. The network stops being a prerequisite for the app working and becomes an enhancement. For anything used on the move — field service, logistics, an EV app in a parking garage with one bar of signal — this is the difference between an app people trust and one they curse.

I have built this pattern in Flutter more than once. Here is an architecture that holds up, using Drift for local storage and an outbox for reliable sync.

## The core idea: UI never waits for the network

Draw the boundary clearly. The UI talks only to the local store. It never `await`s an HTTP call to show data or to accept an edit.

```
┌────────────┐   watch/query   ┌──────────────┐   sync   ┌──────────┐
│  Flutter   │ ◀────────────── │  Drift (SQLite)│ ◀──────▶ │  Server  │
│  UI/State  │  write locally  │  = source of   │  outbox  │   API    │
└────────────┘ ──────────────▶ │     truth      │  queue   └──────────┘
                               └──────────────┘
```

A user taps "save." You write to Drift, the UI's reactive stream updates immediately, and the change lands in an outbox table to be pushed later. If the app is offline, nothing about the experience changes — the write succeeded locally. When connectivity returns, the sync engine drains the outbox.

## Why Drift as the local store

I default to [Drift](https://drift.simonbinder.eu/) (typed SQLite for Dart) for sync-heavy apps for three reasons:

1. **Reactive queries.** Drift streams query results, so the UI rebuilds automatically when local data changes — exactly what you want when both user edits and incoming sync mutate the same tables.
2. **Real SQL.** Reconciliation needs joins, upserts, and conditional updates. Key-value stores like Hive make that awkward; SQL makes it natural.
3. **Typed and testable.** Compile-time-checked queries and easy in-memory databases for tests.

```dart
// A watchable query — UI rebuilds when rows change, from any source.
Stream<List<Charger>> watchFavorites() =>
    (select(chargers)..where((c) => c.isFavorite.equals(true)))
        .watch();
```

## The outbox: reliable writes that survive restarts

The piece people skip and regret is the **outbox**. Every local mutation that must reach the server gets a row: what changed, an operation type, a client-generated id, and a status. Sync reads pending rows, pushes them, and marks them done. Because the outbox is persisted in SQLite, an app kill mid-sync loses nothing.

```dart
@DataClassName('OutboxEntry')
class Outbox extends Table {
  IntColumn get id => integer().autoIncrement()();
  TextColumn get entityType => text()();          // 'charging_session'
  TextColumn get opType => text()();              // create/update/delete
  TextColumn get payload => text()();             // JSON
  TextColumn get idempotencyKey => text()();      // UUID, generated locally
  DateTimeColumn get createdAt => dateTime()();
  IntColumn get attempts => integer().withDefault(const Constant(0))();
}
```

The `idempotencyKey` is non-negotiable. Retries happen — a request times out, you push again, the server may have already processed the first attempt. A key the server dedupes on turns "double submit" into a no-op. This is the same discipline I leaned on for [idempotency in the EV platform](https://blog.michaelsam94.com/idempotency-distributed-systems/): make retries safe by construction, not by luck.

## Draining the outbox on reconnect

Wire sync to connectivity changes and app lifecycle. On reconnect, drain the outbox in order, with exponential backoff on failure:

```dart
Future<void> drainOutbox() async {
  final pending = await (db.select(db.outbox)
        ..orderBy([(o) => OrderingTerm.asc(o.createdAt)]))
      .get();

  for (final entry in pending) {
    try {
      await api.push(entry); // sends idempotencyKey header
      await db.delete(db.outbox).delete(entry);
    } on ApiException catch (e) {
      if (e.isPermanent) {
        await _moveToDeadLetter(entry); // don't retry forever
      } else {
        await _bumpAttempts(entry);     // backoff, try later
        break;                          // preserve ordering
      }
    }
  }
}
```

Two details that matter: preserve **ordering** so a create is not pushed after its dependent update, and have a **dead-letter** path so a permanently failing item does not block the whole queue.

## Conflict resolution: match the strategy to the data

There is no universal answer, so decide per data type:

| Data type | Strategy |
| --- | --- |
| User profile fields, settings | Last-write-wins on server timestamp |
| Independent records (new sessions) | No conflict — both keep, dedupe by id |
| Counters / balances | Server-authoritative; client requests deltas |
| Collaborative documents | Field-level merge or CRDTs |

Last-write-wins is fine for the majority of fields and is cheap: attach a version or `updatedAt`, and the later write wins. Reach for per-field merging or CRDTs only for genuinely collaborative data — they solve a real problem but add real complexity, so do not pay for them where LWW suffices.

Pulling from the server, I fetch changes since a stored cursor (a `since` timestamp or server change token) and upsert into Drift, letting the reactive queries update the UI. Deletes are usually **soft** (a `deletedAt` column) so a delete on one device propagates cleanly instead of a row silently reappearing.

## Making it feel honest

Offline-first is as much UX as data. Show sync state truthfully: a subtle "pending" marker on unsynced items, a "last synced 3 min ago" line, and never a spinner that blocks input. The pattern I use for real-time apps applies here too — model connectivity as [state the UI reacts to](https://blog.michaelsam94.com/flutter-riverpod-state-management/), so the app can say "saved, will sync" instead of pretending everything is instantly on the server.

Done right, offline-first makes an app feel *faster* even when online, because reads and writes never wait on a round trip. The work is in the plumbing — a local source of truth, a durable outbox with idempotency keys, and conflict rules chosen per data type. Get those three right and flaky networks become a non-event. Want a review of your sync design? [Let's talk](/#contact).

## Schema migrations with Drift offline

Local schema changes are harder than server migrations — users skip app versions. Use Drift's `MigrationStrategy`:

```dart
@override
MigrationStrategy get migration => MigrationStrategy(
  onUpgrade: (m, from, to) async {
    if (from < 3) {
      await m.addColumn(chargers, chargers.syncCursor);
      await backfillSyncCursor();
    }
  },
  beforeOpen: (details) async {
    await customStatement('PRAGMA foreign_keys = ON');
  },
);
```

Never drop columns users still have pending outbox entries for — migrate data first, drain outbox, then compact.

## Sync cursor and incremental pull

Store `lastSyncedAt` or server change tokens per entity type. Pull uses `If-Modified-Since` or cursor APIs:

```dart
Future<void> pullChanges() async {
  final cursor = await db.getSyncCursor('chargers');
  final delta = await api.fetchChargers(since: cursor);
  await db.transaction(() async {
    for (final row in delta.upserts) {
      await db.into(chargers).insertOnConflictUpdate(row);
    }
    for (final id in delta.deletes) {
      await (db.delete(chargers)..where((c) => c.id.equals(id))).go();
    }
    await db.setSyncCursor('chargers', delta.newCursor);
  });
}
```

Push-then-pull ordering prevents overwriting local edits with stale server snapshots — drain outbox first unless server version wins by policy.

## Testing sync without flaky integration tests

Use in-memory Drift databases with a fake API that simulates latency, 409 conflicts, and partial failures. Property-based tests for outbox ordering: create → update → delete same entity should converge to delete on server.

## Conflict resolution for charging session edits

Field apps editing session notes while dispatcher updates status need explicit rules: server `updated_at` wins for status; client wins for local notes until synced. Surface conflict UI — silent overwrite loses trust with field technicians.

## Background sync on mobile OS constraints

iOS suspends background fetch — register `BGAppRefreshTask` and sync on `AppLifecycleState.resumed` with debounce. Android Doze delays WorkManager — use `connectivity` constraint plus expedited work for user-triggered "sync now."

## Resources

- [Drift (SQLite for Dart) documentation](https://drift.simonbinder.eu/)
- [Offline-first patterns on web.dev](https://web.dev/learn/pwa/offline-data)
- [Transactional outbox pattern (microservices.io)](https://microservices.io/patterns/data/transactional-outbox.html)
- [CRDTs explained](https://crdt.tech/)
- [Flutter connectivity_plus package](https://pub.dev/packages/connectivity_plus)
- [Martin Kleppmann on local-first software](https://www.inkandswitch.com/local-first/)