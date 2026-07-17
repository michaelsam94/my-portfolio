---
title: "System Design: File Storage Like Dropbox"
slug: "system-design-file-storage-dropbox"
description: "Design cloud file storage: chunking, deduplication, metadata indexing, sync protocol, conflict resolution, and CDN delivery at scale."
datePublished: "2026-02-18"
dateModified: "2026-07-17"
tags: ["System Design", "Storage", "Architecture", "Distributed Systems"]
keywords: "dropbox system design, file chunking, content deduplication, sync protocol, cloud storage architecture"
faq:
  - q: "Why chunk files instead of storing them as single blobs?"
    a: "Chunking (4–8 MB blocks) enables deduplication — identical blocks across users and versions upload once. Delta sync sends only changed chunks after local edits. Parallel uploads improve throughput on high-latency links. Metadata tracks which chunks compose each file version without re-uploading unchanged data."
  - q: "How does Dropbox-style sync detect remote changes?"
    a: "Clients maintain a local cursor (sync token). Periodic long-poll or WebSocket notifications signal changes; client fetches delta API listing modified paths since cursor. Conflict detection compares revision IDs; simultaneous edits create conflict copies rather than silent overwrites."
  - q: "What storage backend suits chunk blobs versus metadata?"
    a: "Object storage (S3, GCS) for immutable chunk blobs with content-addressed keys (SHA-256). Relational or distributed SQL for namespace metadata, ACLs, and share links. Separate hot metadata path from cold blob path so listing directories stays fast even when total stored bytes is petabytes."
---

Uploading a 2 GB video over hotel Wi-Fi taught our team why Dropbox chunks. After chunking at 4 MB with rolling hash boundaries, a single subtitle edit uploaded 12 MB. Content-addressed deduplication meant three teammates sharing the same asset stored one copy. Metadata service tracked names and paths; blob store held anonymous blocks.

## Two-layer architecture: namespace vs blobs

```
Client path: /Projects/demo/video.mp4
     ↓
Metadata DB: file_id, parent_folder, owner, revision, chunk_list[]
     ↓
Object store: blobs/sha256/ab/cd/abcd... (immutable)
```

Metadata queries need low latency and ACID for rename, move, and permission changes. Blobs are append-only and immutable — perfect for S3.

| Layer | Store | Operations |
| --- | --- | --- |
| Namespace | Postgres/CockroachDB | list, rename, ACL |
| Chunks | S3/GCS | put, get |
| Cache | CDN + Redis | hot chunk delivery |

## Content-defined chunking

Fixed-size chunks shift when bytes insert at file start. **Content-defined chunking** (Rabin fingerprint) keeps boundaries stable across small edits:

```python
def chunk_stream(stream, min_size=2*MB, avg_size=4*MB, max_size=8*MB):
    buffer = bytearray()
    for data in stream:
        buffer.extend(data)
        while len(buffer) >= avg_size:
            cut = find_rabin_cut(buffer, mask=0xFFF)
            if cut >= min_size or len(buffer) >= max_size:
                yield hash_chunk(buffer[:cut]), bytes(buffer[:cut])
                del buffer[:cut]
```

Variable chunk sizes complicate capacity planning but dramatically improve delta sync for documents and SQLite databases.

## Deduplication and encryption

Hash each chunk (SHA-256). Store once per hash — reference count tracks how many file versions point to each blob. Client-side encryption removes server-side dedup visibility but maximizes privacy. Enterprise products often offer both modes.

## Upload pipeline: check, upload, commit

1. Client splits file into chunks, hashes locally
2. `POST /chunks/check` — server returns which hashes already exist
3. Client uploads missing chunks in parallel
4. `POST /files/commit` registers metadata atomically

Commit is atomic — partial uploads garbage-collect via TTL on unreferenced chunks. Background sweeper deletes blobs with zero refcount after grace period.

## Sync protocol and cursor-based deltas

```json
GET /sync/delta?cursor=cursor_v4821
{
  "cursor": "cursor_v4823",
  "entries": [
    { "path": "/notes.txt", "rev": "rev_9a", "op": "modified" },
    { "path": "/old.zip", "rev": null, "op": "deleted" }
  ]
}
```

Long-polling reduces empty polling. Mobile clients batch notifications to save battery.

## Conflict resolution

Last-writer-wins loses data. **Conflict copies** preserve both versions. Revision numbers monotonically increase per file — compare revision, not wall-clock mtime.

## Sharing, permissions, and presigned access

Permission check on every metadata operation before returning chunk hashes. Presigned URLs expire in 15 minutes — client requests batch presign for delta download list.

## Scale: sharding, hot files, and garbage collection

Metadata sharding by `user_id`. CDN cache for hot chunks. GC deletes blobs with zero refcount after grace period for undo support.

## Bandwidth optimization

Delta sync using rolling hash identifies changed byte ranges inside large chunks. LAN sync allows direct device-to-device transfer on same network — metadata still flows through server for ACL enforcement.

## Enterprise: legal hold and audit

Legal hold prevents delete propagation. Retention policies auto-delete after N years except hold-flagged content. Audit log records every metadata mutation.

## Read path latency

Target sub-100ms p99 for folder listing. Denormalize child counts, cache hot directory listings in Redis, paginate delta responses. Thumbnail generation runs async on commit.

## Failure modes

| Issue | Mitigation |
| --- | --- |
| Partial upload | Resume from last confirmed chunk hash |
| Metadata/blob inconsistency | GC detects orphaned chunks |
| Hot keys on viral file | CDN + metadata read replicas |

File storage at scale separates the fast metadata path from the cold blob path. Get chunking, deduplication, and sync protocol right; block storage is commodity S3 with content-addressed keys.

## Metadata schema deep dive

```sql
CREATE TABLE files (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    path TEXT NOT NULL,
    current_version INT DEFAULT 1,
    created_at TIMESTAMPTZ,
    UNIQUE(user_id, path)
);

CREATE TABLE file_versions (
    file_id UUID REFERENCES files(id),
    version INT,
    chunk_hashes TEXT[] NOT NULL,
    size_bytes BIGINT,
    modified_at TIMESTAMPTZ,
    device_id TEXT,
    PRIMARY KEY (file_id, version)
);

CREATE TABLE chunk_index (
    hash TEXT PRIMARY KEY,
    s3_key TEXT NOT NULL,
    size_bytes INT,
    ref_count INT DEFAULT 1
);
```

Path lookups use `(user_id, path)` B-tree index. Sync compares version numbers — never mtime alone.

## Mobile offline queue

Mobile clients queue upload commits when offline. On reconnect, client pushes pending commits and reconciles server delta — conflicts surface as copies rather than blocking sync. SQLite local index mirrors server metadata for offline browse.

## Thumbnail and preview pipeline

Commit succeeds immediately; preview generation runs async. Delta entry arrives when rendering completes. Store derived chunk hashes linked from metadata so folder listing shows preview availability without downloading originals.

## Cross-region replication

Metadata replicates synchronously within region; blob storage uses cross-region replication for durability. Metadata service routes read requests to nearest replica; writes go to primary. Failover promotes read replica — document RPO/RTO for metadata vs blobs separately.

## Security: presigned URL constraints

Presigned URLs include content-hash constraint where S3 supports it — client cannot swap chunk content after presign. Short expiry (15 min) limits exposure if URL leaks. Rate-limit presign requests per user to prevent abuse as free CDN.

## Cost modeling

Storage cost = unique chunks × average chunk size. Egress cost dominates at scale — LAN sync and delta sync directly reduce cloud egress bills. Monitor ref_count distribution — long tail of single-reference chunks indicates poor dedup or many unique uploads.

## Petabyte-scale GC

GC job processes chunks in batches with rate limiting against S3 DELETE API. Soft-delete grace period (7 days) before physical delete supports undo. Legal hold flag on file prevents refcount decrement on delete — enterprise compliance requirement.

## Sync cursor consistency

Server assigns monotonic cursor tokens — clients never generate cursors locally. Cursor gap detection triggers full reconcile when delta entries missing — indicates client fell too far behind or server compaction deleted history.

## Selective sync and selective download

Enterprise clients sync subset of folders. Metadata index supports partial namespace subscription — client cursor scoped to folder subtree. Reduces mobile battery and bandwidth for large accounts.

## Virus scanning on upload

Scan committed files async before marking shareable. Quarantine chunk set if malware detected — metadata flag prevents share link generation until cleared.

## Bandwidth fairness

Per-user upload rate limiting prevents one client saturating ingress. Chunk upload check endpoint is cheap — abuse as free storage probe requires auth and rate limits.

## Version history and restore

File versions retained per retention policy — user restore selects historical version, creates new version pointing at old chunk list. Chunk refcounts increment on restore; GC respects minimum version retention before decrementing refs.

## Team shared folders

Shared folder links multiple user namespaces to same file IDs. Permission inheritance on subfolders requires materialized path table for efficient ACL evaluation — avoid recursive tree walks on every list operation.

## Chunk size tuning

Target 4 MB average chunk size balances dedup effectiveness against metadata overhead. Smaller chunks improve dedup for similar files but increase metadata row count. Monitor chunks-per-file distribution — documents cluster around 50-200 chunks; video files may have thousands.

## Client-side hash verification

After download, client re-hashes chunks and compares to metadata manifest — detects corruption in transit or storage bit rot before user opens file.

## Monitoring sync health

Track sync latency p99, conflict rate, and orphaned chunk count. Alert when GC queue depth exceeds threshold — indicates metadata/blob inconsistency or failed commits accumulating.

## Upload resume protocol

Clients resume partial uploads from last confirmed chunk hash in commit manifest — network interruption mid-upload does not restart from byte zero.

## Resources

- [Dropbox engineering blog](https://dropbox.tech/)
- [LBFS: A Low-Bandwidth File System](https://www.usenix.org/event/osdi01/full_papers/maeda/maeda.pdf)
- [AWS S3 presigned URLs](https://docs.aws.amazon.com/AmazonS3/latest/userguide/PresignedUrlUploadObject.html)
- [Conflict-free Replicated Data Types (CRDTs)](https://crdt.tech/)
