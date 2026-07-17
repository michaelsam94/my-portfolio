---
title: "IndexedDB Patterns"
slug: "web-storage-indexeddb-patterns"
description: "Use IndexedDB effectively in web applications: schema design, idb wrapper library, transactions, indexing, migration, and when IndexedDB beats localStorage or Cache API."
datePublished: "2026-05-18"
dateModified: "2026-07-17"
tags: ["Web", "JavaScript", "Storage", "Frontend"]
keywords: "IndexedDB, browser storage, idb library, offline storage, web storage, database migration"
faq:
  - q: "When should I use IndexedDB instead of localStorage?"
    a: "Use IndexedDB when you need to store structured data larger than 5MB, query records by fields other than a single key, store binary data (files, images), or handle concurrent read/write operations. localStorage is limited to string key-value pairs, typically capped at 5-10MB, and blocks the main thread on every access. IndexedDB is asynchronous, supports indexes for fast lookups, handles objects and binary data natively, and scales to hundreds of megabytes or more."
  - q: "What is the best way to work with IndexedDB without callback hell?"
    a: "Use the idb library by Jake Archibald, which wraps IndexedDB's verbose API with Promise-based methods. It reduces a 40-line transaction with callbacks to a 5-line async/await call. For TypeScript projects, idb supports typed schemas that provide autocomplete and type checking on database operations. Avoid the raw IndexedDB API in application code — the wrapper eliminates the most common sources of bugs."
  - q: "How do I handle IndexedDB schema migrations?"
    a: "IndexedDB migrations happen in the onupgradeneeded event, which fires when you open the database with a higher version number. In the upgrade callback, use createObjectStore for new stores, createIndex for new indexes, and deleteObjectStore for removed stores. You cannot modify existing stores outside this event. Increment the version number for each schema change and handle each version transition explicitly in the upgrade function."
---
I built an offline-first task manager that stored 50,000 tasks in localStorage. Parsing the JSON string on every page load took 800ms and blocked the main thread. Switching to IndexedDB with an index on `projectId` brought load time to 40ms and let me query "all tasks in project X" without loading everything into memory. IndexedDB is the browser's structured database — async, indexed, and capable of storing hundreds of megabytes. Most developers avoid it because the raw API is verbose and callback-heavy. With the right patterns and the `idb` wrapper, it's straightforward.

## IndexedDB vs other storage

| Feature | localStorage | IndexedDB | Cache API |
|---|---|---|---|
| Capacity | 5-10 MB | 100+ MB | 100+ MB |
| Data types | Strings only | Objects, binary | HTTP responses |
| Querying | Key only | Indexes, cursors | URL match |
| Async | No (blocks main thread) | Yes | Yes |
| Transactions | No | Yes | No |
| Best for | Preferences, tokens | Structured app data | Offline assets |

## Setup with idb

```bash
npm install idb
```

```typescript
import { openDB, type DBSchema, type IDBPDatabase } from 'idb';

interface TaskDB extends DBSchema {
  tasks: {
    key: string;
    value: {
      id: string;
      title: string;
      projectId: string;
      status: 'todo' | 'doing' | 'done';
      createdAt: number;
    };
    indexes: {
      'by-project': string;
      'by-status': string;
      'by-created': number;
    };
  };
  projects: {
    key: string;
    value: {
      id: string;
      name: string;
    };
  };
}

let db: IDBPDatabase<TaskDB>;

async function getDB() {
  if (db) return db;

  db = await openDB<TaskDB>('task-manager', 2, {
    upgrade(database, oldVersion, newVersion, transaction) {
      if (oldVersion < 1) {
        const taskStore = database.createObjectStore('tasks', { keyPath: 'id' });
        taskStore.createIndex('by-project', 'projectId');
        taskStore.createIndex('by-status', 'status');
        taskStore.createIndex('by-created', 'createdAt');

        database.createObjectStore('projects', { keyPath: 'id' });
      }
      if (oldVersion < 2) {
        // Migration: add by-status index in v2
        const taskStore = transaction.objectStore('tasks');
        if (!taskStore.indexNames.contains('by-status')) {
          taskStore.createIndex('by-status', 'status');
        }
      }
    },
  });

  return db;
}
```

## CRUD operations

```typescript
// Create
async function addTask(task: TaskDB['tasks']['value']) {
  const db = await getDB();
  await db.add('tasks', task);
}

// Read by key
async function getTask(id: string) {
  const db = await getDB();
  return db.get('tasks', id);
}

// Update
async function updateTask(task: TaskDB['tasks']['value']) {
  const db = await getDB();
  await db.put('tasks', task);
}

// Delete
async function deleteTask(id: string) {
  const db = await getDB();
  await db.delete('tasks', id);
}
```

## Indexed queries

The power of IndexedDB — query by field without loading everything:

```typescript
// All tasks in a project
async function getTasksByProject(projectId: string) {
  const db = await getDB();
  return db.getAllFromIndex('tasks', 'by-project', projectId);
}

// All "doing" tasks
async function getDoingTasks() {
  const db = await getDB();
  return db.getAllFromIndex('tasks', 'by-status', 'doing');
}

// Tasks created after a timestamp
async function getRecentTasks(since: number) {
  const db = await getDB();
  const range = IDBKeyRange.lowerBound(since);
  return db.getAllFromIndex('tasks', 'by-created', range);
}
```

## Transactions

Multiple operations in one atomic transaction:

```typescript
async function moveTaskToProject(taskId: string, newProjectId: string) {
  const db = await getDB();
  const tx = db.transaction('tasks', 'readwrite');
  const task = await tx.store.get(taskId);
  if (task) {
    task.projectId = newProjectId;
    await tx.store.put(task);
  }
  await tx.done;
}
```

If any operation fails, the entire transaction rolls back.

## Bulk operations

```typescript
async function importTasks(tasks: Task[]) {
  const db = await getDB();
  const tx = db.transaction('tasks', 'readwrite');

  await Promise.all([
    ...tasks.map(task => tx.store.put(task)),
    tx.done,
  ]);
}
```

## Schema migration pattern

```typescript
const DB_VERSION = 3;

async function getDB() {
  return openDB('app', DB_VERSION, {
    upgrade(db, oldVersion) {
      if (oldVersion < 1) createV1Schema(db);
      if (oldVersion < 2) migrateV1toV2(db);
      if (oldVersion < 3) migrateV2toV3(db);
    },
  });
}

function createV1Schema(db: IDBPDatabase) {
  db.createObjectStore('items', { keyPath: 'id' });
}

function migrateV1toV2(db: IDBPDatabase) {
  const store = db.transaction('items', 'readwrite').store;
  store.createIndex('by-category', 'category');
}

function migrateV2toV3(db: IDBPDatabase) {
  db.createObjectStore('settings', { keyPath: 'key' });
}
```

Each version increment handles only the delta from the previous version.

## Storage limits and cleanup

```typescript
// Check available storage
const estimate = await navigator.storage.estimate();
console.log(`Using ${estimate.usage} of ${estimate.quota} bytes`);

// Request persistent storage (won't be evicted under pressure)
await navigator.storage.persist();
```

Implement cleanup for stale data:

```typescript
async function cleanupOldTasks(maxAge: number) {
  const db = await getDB();
  const cutoff = Date.now() - maxAge;
  const range = IDBKeyRange.upperBound(cutoff);
  const tx = db.transaction('tasks', 'readwrite');

  let cursor = await tx.store.index('by-created').openCursor(range);
  while (cursor) {
    await cursor.delete();
    cursor = await cursor.continue();
  }
  await tx.done;
}
```

## When to use what

- **User preferences** (theme, language) → localStorage
- **Auth tokens** → httpOnly cookies (not IndexedDB or localStorage)
- **Structured app data** (tasks, messages, drafts) → IndexedDB
- **Offline HTML/assets** → Cache API (service worker)
- **Files and images** → IndexedDB (binary Blob storage)
- **Small key-value config** → localStorage

## Conflict resolution

When syncing offline edits, use last-write-wins for simple cases or vector clocks for collaborative editing:

```javascript
async function merge(local, remote) {
  if (local.updatedAt > remote.updatedAt) return local;
  if (remote.updatedAt > local.updatedAt) return remote;
  return mergeFields(local, remote); // field-level merge
}
```

Store `updatedAt` and optionally `deviceId` on every record.

## Storage persistence

Request persistent storage to avoid eviction under disk pressure:

```javascript
if (navigator.storage && navigator.storage.persist) {
  const persisted = await navigator.storage.persist();
  console.log('Storage persisted:', persisted);
}
```

Browsers may evict non-persistent origin data when disk is low.

## Resources

- [idb library (Jake Archibald)](https://github.com/jakearchibald/idb)
- [MDN IndexedDB API](https://developer.mozilla.org/en-US/docs/Web/API/IndexedDB_API)
- [IndexedDB testing with fake-indexeddb](https://github.com/dumbmatter/fakeIndexedDB)
- [Storage for the web (web.dev)](https://web.dev/articles/storage-for-the-web)
- [navigator.storage.estimate()](https://developer.mozilla.org/en-US/docs/Web/API/StorageManager/estimate)

## Operational checklist (1)

Before promoting Web Storage Indexeddb Patterns changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Field validation (2)

Re-baseline Web Storage Indexeddb Patterns after browser upgrades or CDN configuration changes. Mobile share above seventy percent shifts median device class — optimizations tuned on desktop lab profiles may not transfer.

## Coordination (3)

Align with platform and backend owners on cache TTL, deploy windows, and API contracts when Web Storage Indexeddb Patterns touches shared infrastructure — single-layer wins often disappear when another tier invalidates caches.

## Operational checklist (4)

Before promoting Web Storage Indexeddb Patterns changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Field validation (5)

Re-baseline Web Storage Indexeddb Patterns after browser upgrades or CDN configuration changes. Mobile share above seventy percent shifts median device class — optimizations tuned on desktop lab profiles may not transfer.

## Coordination (6)

Align with platform and backend owners on cache TTL, deploy windows, and API contracts when Web Storage Indexeddb Patterns touches shared infrastructure — single-layer wins often disappear when another tier invalidates caches.

## Operational checklist (7)

Before promoting Web Storage Indexeddb Patterns changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Telemetry and ownership for web storage indexeddb patterns

Pair a leading operational signal with a lagging user or risk outcome. Page on burn related to web storage indexeddb patterns, not vanity counters. Keep a named owner and a dashboard link in the service catalog entry.

| Check | Expected for web storage indexeddb patterns |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 1: inject the failure mode you fear for web storage indexeddb patterns in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Rollout sequence for web storage indexeddb patterns

Prefer flags, weighted routes, or dual-running configs. Rehearse rollback once in staging. The on-call note for web storage indexeddb patterns should include the revert command and the expected user-visible effect within five minutes.

Concrete probe 2: inject the failure mode you fear for web storage indexeddb patterns in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Cross-team contracts for web storage indexeddb patterns

Document producers, consumers, timeouts, and idempotency keys. Silent schema or policy changes are how web storage indexeddb patterns breaks without a clear owner in the incident channel.

| Check | Expected for web storage indexeddb patterns |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 3: inject the failure mode you fear for web storage indexeddb patterns in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Capacity and cost notes for web storage indexeddb patterns

Estimate QPS, payload size, cardinality, and downstream saturation. Functionally correct web storage indexeddb patterns changes still cause outages through pool exhaustion, crawl waste, or CPU amplification.

Concrete probe 4: inject the failure mode you fear for web storage indexeddb patterns in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Reviewer checklist for web storage indexeddb patterns

Ask what happens when the dependency is slow, when authz is skipped on batch jobs, and when clients retry. Those three questions catch most web storage indexeddb patterns regressions before production.

| Check | Expected for web storage indexeddb patterns |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 5: inject the failure mode you fear for web storage indexeddb patterns in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Incident patterns around web storage indexeddb patterns

Most incidents involving web storage indexeddb patterns start as a silent drift: a secondary path skips the control, a retry amplifies load, or a config default from a tutorial ships to production. Write the failure story before the happy path.

Concrete probe 6: inject the failure mode you fear for web storage indexeddb patterns in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Invariants to enforce for web storage indexeddb patterns

Name three invariants that must hold after every deploy of web storage indexeddb patterns. Encode at least one in an automated test that fails when the invariant is disabled. Reviewers should reject PRs that only cover the primary UI path.

| Check | Expected for web storage indexeddb patterns |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 7: inject the failure mode you fear for web storage indexeddb patterns in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.
