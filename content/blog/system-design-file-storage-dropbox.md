---
title: "System Design: File Storage"
slug: "system-design-file-storage-dropbox"
description: "Design a cloud file storage system like Dropbox with upload deduplication, sync, conflict resolution, and metadata management at petabyte scale."
datePublished: "2025-10-21"
dateModified: "2025-10-21"
tags: ["System Design", "Storage", "Architecture", "Backend"]
keywords: "Dropbox system design, file storage architecture, chunk deduplication, file sync system, cloud storage design, metadata service"
faq:
  - q: "How does Dropbox-style deduplication work?"
    a: "Files are split into fixed-size chunks (4MB typical). Each chunk is hashed (SHA-256). Before storing, the system checks if a chunk with that hash already exists — if yes, increment a reference counter instead of storing a duplicate. Two users uploading the same file, or one user uploading a slightly modified file, share unchanged chunks. This reduces storage by 40-70% for typical user data."
  - q: "How do you handle sync conflicts when two devices edit the same file offline?"
    a: "Last-writer-wins is simplest but loses data. Better approach: detect conflict on sync (both devices modified since last sync version), keep both versions — rename the loser as 'conflicted copy' — and notify the user. Operational transformation or CRDTs work for text files but are complex. Most consumer file sync uses version branching with user-visible conflict files."
  - q: "What storage backend should a file system use?"
    a: "Object storage (S3, GCS, Azure Blob) for chunk data — it's cheap, durable (11 nines), and scales infinitely. A relational or NoSQL database for metadata (file names, paths, permissions, chunk manifests, versions). Never store file content in a database. Hot metadata (recent files, active syncs) benefits from caching in Redis."
---

Dropbox stores over 700 billion files for 700 million users. The insight that makes this economical: users rarely upload truly unique content. The same PDF, installer, or photo gets uploaded by thousands of people. Even within one user's account, successive versions of a document share 90%+ identical chunks. File storage at scale is a deduplication problem wrapped in a metadata and sync problem.

## Architecture overview

```
Client ←→ Sync API ←→ Metadata Service (PostgreSQL)
   ↓                        ↓
Upload/Download         Chunk Index (hash → location)
   ↓                        ↓
Chunk Storage (S3)     Notification Service (WebSocket/long poll)
```

Clients talk to a sync API for metadata operations (list files, create folders, get changes) and directly to object storage for chunk upload/download via pre-signed URLs.

## Chunking and deduplication

Split files into fixed-size chunks with content-defined boundaries (rolling hash) so insertions don't shift all subsequent chunk boundaries:

```python
def chunk_file(file_data: bytes, target_size: int = 4_194_304) -> list[Chunk]:
    chunks = []
    offset = 0
    while offset < len(file_data):
        # Content-defined boundary: find next hash point near target_size
        boundary = find_boundary(file_data, offset, target_size)
        chunk_data = file_data[offset:boundary]
        chunks.append(Chunk(
            hash=sha256(chunk_data),
            size=len(chunk_data),
            data=chunk_data
        ))
        offset = boundary
    return chunks
```

On upload, check each chunk hash against the chunk index:

```python
async def upload_file(user_id: str, path: str, file_data: bytes):
    chunks = chunk_file(file_data)
    chunk_refs = []

    for chunk in chunks:
        existing = await chunk_index.lookup(chunk.hash)
        if existing:
            await chunk_index.increment_ref(chunk.hash)
            chunk_refs.append(chunk.hash)
        else:
            await s3.upload(f"chunks/{chunk.hash[:2]}/{chunk.hash}", chunk.data)
            await chunk_index.register(chunk.hash, location=f"s3://chunks/{chunk.hash}")
            chunk_refs.append(chunk.hash)

    file_version = FileVersion(
        file_id=await metadata.get_or_create_file(user_id, path),
        version=await metadata.next_version(path),
        chunks=chunk_refs,
        size=len(file_data),
        modified_at=now()
    )
    await metadata.save_version(file_version)
```

Only new chunks hit S3. Duplicate chunks across users or versions cost one storage unit regardless of reference count.

## Metadata model

```sql
CREATE TABLE files (
    id UUID PRIMARY KEY,
    user_id UUID,
    path TEXT,
    current_version INT,
    created_at TIMESTAMP,
    UNIQUE(user_id, path)
);

CREATE TABLE file_versions (
    file_id UUID,
    version INT,
    chunk_hashes TEXT[],  -- ordered list of chunk SHA-256 hashes
    size BIGINT,
    modified_at TIMESTAMP,
    device_id TEXT,
    PRIMARY KEY (file_id, version)
);

CREATE TABLE chunk_index (
    hash TEXT PRIMARY KEY,
    s3_location TEXT,
    size INT,
    ref_count INT DEFAULT 1
);
```

Path-based lookups use `(user_id, path)` index. Sync operations compare version numbers to detect changes.

## Sync protocol

Clients maintain a local state vector (file path → version number). Sync is a delta exchange:

1. Client sends local state vector to sync API.
2. Server compares with authoritative state, returns:
   - **Changes for client:** files the server has that the client doesn't (or has older versions of).
   - **Changes for server:** files the client modified that the server hasn't seen.
3. Client downloads changed files (chunk manifests, then missing chunks from S3).
4. Client uploads local changes (new/changed chunks, updated metadata).

```json
// Client sync request
{
  "cursor": "sync_cursor_abc123",
  "local_changes": [
    { "path": "/docs/report.docx", "version": 5, "action": "modified" },
    { "path": "/photos/new.jpg", "version": 1, "action": "created" }
  ]
}
```

Long polling or WebSocket notifications tell clients when remote changes occur, triggering incremental sync instead of full state comparison.

## Conflict resolution

When two devices modify the same file offline:

```python
async def handle_upload(user_id, path, new_version, device_id):
    current = await metadata.get_current_version(user_id, path)

    if new_version.base_version < current.version:
        # Conflict: server has a newer version
        conflict_path = f"{path} (conflicted copy {device_id})"
        await metadata.save_version(current)  # preserve server version at original path
        await metadata.save_version(new_version, path=conflict_path)
        await notify_user(user_id, f"Conflict detected for {path}")
    else:
        await metadata.save_version(new_version)
```

Both versions are preserved. The user merges manually. For real-time collaborative editing (Google Docs style), operational transformation or CRDTs replace file-level sync — but that's a different architecture.

## Security and access control

- **Pre-signed URLs** for chunk upload/download — clients never hold storage credentials.
- **Encryption at rest** — S3 server-side encryption (SSE-S3 or SSE-KMS). Optional client-side encryption for zero-knowledge storage (Dropbox doesn't do this; SpiderOak does).
- **Sharing links** — generate time-limited, token-based URLs that grant read access without account authentication.
- **Permissions** — folder-level ACLs stored in metadata; checked before returning chunk locations.

## Garbage collection

When files are deleted or chunks are replaced in new versions, decrement reference counts. Chunks with `ref_count = 0` are queued for deletion:

```python
async def gc_chunks():
    orphaned = await chunk_index.find_zero_ref()
    for chunk in orphaned:
        await s3.delete(chunk.s3_location)
        await chunk_index.delete(chunk.hash)
```

Run GC as a background job with rate limiting to avoid S3 API throttling.

## Common production mistakes

Teams get file storage dropbox wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

System design for file storage dropbox breaks at scale when hot keys, thundering herds, and cache stampedes are discovered during launch week instead of load test week.

## Debugging and triage workflow

When file storage dropbox misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Dropbox engineering blog — streamlining sync](https://dropbox.tech/)
- [Linux FastDFS (inspiration for chunk storage)](https://github.com/happyfish100/fastdfs)
- [Content-defined chunking for deduplication](https://en.wikipedia.org/wiki/Rolling_hash)
- [AWS S3 pre-signed URLs](https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html)
- [Designing Data-Intensive Applications — Ch. 3 Storage and Retrieval](https://dataintensive.net/)
