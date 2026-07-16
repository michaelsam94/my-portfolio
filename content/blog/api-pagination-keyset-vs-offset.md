---
title: "Keyset vs Offset Pagination"
slug: "api-pagination-keyset-vs-offset"
description: "Choose between keyset (cursor) and offset pagination for APIs: performance at scale, stable results, implementation patterns, and client guidance."
datePublished: "2026-07-16"
dateModified: "2026-07-16"
tags: ["Backend", "API", "Databases", "Architecture"]
keywords: "keyset pagination, cursor pagination, offset pagination, API pagination, seek method pagination, stable pagination"
faq:
  - q: "What is the difference between offset and keyset pagination?"
    a: "Offset pagination uses LIMIT/OFFSET (or page/pageSize) to skip rows — simple but slow on large offsets because the database scans and discards skipped rows. Keyset pagination uses a cursor (typically the last seen ID or timestamp) to fetch the next page — faster at any depth because it seeks directly to the cursor position using an index."
  - q: "When should I use keyset pagination?"
    a: "Use keyset pagination for large datasets (millions of rows), real-time feeds where items are inserted during browsing, and APIs where performance at deep pages matters. Use offset pagination for small datasets, admin UIs with page numbers, or when users need to jump to arbitrary pages."
  - q: "What are the downsides of keyset pagination?"
    a: "Keyset pagination can't jump to arbitrary pages (no 'page 47'), requires a stable sort column (usually indexed ID or timestamp), and cursors are opaque to clients. Duplicate or missed items can occur if the sort column values change between requests."
---

If your API uses `?page=500&size=20`, your database is scanning and throwing away 9,980 rows on every request — and getting slower as the table grows. Offset pagination is fine for admin panels with 200 rows. It's a performance trap for feeds, search results, and any list that users scroll deeply. Keyset (cursor) pagination seeks directly to the last seen position using an index, keeping query time constant regardless of depth. I've migrated APIs from offset to keyset at the 100K-row mark every time; the query time drop from 2 seconds to 5 milliseconds at deep pages is consistent across Postgres, MySQL, and SQLite.

## Offset pagination

```sql
SELECT id, title, created_at
FROM posts
ORDER BY created_at DESC
LIMIT 20 OFFSET 9800;  -- page 491
```

```json
GET /api/posts?page=491&size=20

{
  "items": [...],
  "page": 491,
  "pageSize": 20,
  "totalCount": 150000
}
```

Problems at scale:
- `OFFSET 9800` scans 9800 rows and discards them — O(n) per page
- Insertions during browsing cause duplicates or skips
- `totalCount` requires a full table scan or approximate count

Works fine when: total rows < 10K, users rarely go past page 5, you need page numbers.

## Keyset pagination

```sql
-- First page
SELECT id, title, created_at
FROM posts
ORDER BY created_at DESC, id DESC
LIMIT 20;

-- Next page (cursor = last item's created_at + id)
SELECT id, title, created_at
FROM posts
WHERE (created_at, id) < ('2026-01-15T10:30:00', 'post-uuid-123')
ORDER BY created_at DESC, id DESC
LIMIT 20;
```

```json
GET /api/posts?cursor=eyJjcmVhdGVkQXQiOiIyMDI2-...

{
  "items": [...],
  "nextCursor": "eyJjcmVhdGVkQXQiOiIyMDI2-...",
  "hasMore": true
}
```

The cursor encodes the last seen sort values (base64 JSON or signed token). Query time is constant — the index seeks directly to the cursor position.

## Implementation

Encode/decode cursors:

```python
import base64, json

def encode_cursor(created_at: str, item_id: str) -> str:
    return base64.urlsafe_b64encode(
        json.dumps({"createdAt": created_at, "id": item_id}).encode()
    ).decode()

def decode_cursor(cursor: str) -> tuple[str, str]:
    data = json.loads(base64.urlsafe_b64decode(cursor))
    return data["createdAt"], data["id"]
```

```python
@app.get("/api/posts")
def list_posts(cursor: str | None = None, limit: int = 20):
    query = "SELECT id, title, created_at FROM posts"
    params = []

    if cursor:
        created_at, item_id = decode_cursor(cursor)
        query += " WHERE (created_at, id) < (%s, %s)"
        params.extend([created_at, item_id])

    query += " ORDER BY created_at DESC, id DESC LIMIT %s"
    params.append(limit + 1)  # fetch one extra to detect hasMore

    rows = db.execute(query, params)
    has_more = len(rows) > limit
    items = rows[:limit]

    next_cursor = encode_cursor(items[-1].created_at, items[-1].id) if has_more else None
    return {"items": items, "nextCursor": next_cursor, "hasMore": has_more}
```

Fetch `limit + 1` to detect `hasMore` without a separate count query.

## Required index

Keyset pagination requires a composite index matching the sort order:

```sql
CREATE INDEX idx_posts_created_id ON posts (created_at DESC, id DESC);
```

Without this index, keyset queries degrade to sequential scans — worse than offset.

## Comparison

| Factor | Offset | Keyset |
|--------|--------|--------|
| Deep page performance | Degrades O(n) | Constant O(1) |
| Jump to page N | Yes | No |
| Stable during inserts | No (duplicates/skips) | Mostly stable |
| Total count | Easy (expensive) | Hard (skip or approximate) |
| Client complexity | Simple (page number) | Cursor management |
| Implementation | Trivial | Moderate |

## Hybrid approach

Many APIs offer both:

```
GET /api/posts?page=3&size=20          ← offset (admin, small datasets)
GET /api/posts?cursor=abc&limit=20     ← keyset (feeds, mobile scroll)
```

Default to keyset for public/mobile APIs. Offer offset for admin dashboards where page numbers matter and datasets are filtered.

## Client guidance

Mobile clients should always use cursor pagination:

```kotlin
class PostPagingSource(private val api: PostApi) : PagingSource<String, Post>() {
    override suspend fun load(params: LoadParams<String>): LoadResult<String, Post> {
        val response = api.getPosts(cursor = params.key, limit = params.loadSize)
        return LoadResult.Page(
            data = response.items,
            prevKey = null,
            nextKey = if (response.hasMore) response.nextCursor else null
        )
    }
    // ...
}
```

See [Paging 3 with Compose](https://blog.michaelsam94.com/android-paging3-compose/) for the Android client side.

Document cursor format as opaque to clients — exposing internal sort keys lets callers construct invalid cursors that skip or duplicate rows.

## Keyset pagination SQL pattern

```sql
SELECT * FROM orders
WHERE (created_at, id) < ($cursor_ts, $cursor_id)
ORDER BY created_at DESC, id DESC
LIMIT 20;
```

Offset pagination `LIMIT 20 OFFSET 100000` scans 100K rows — keyset stays O(page size) at any depth.

## Common production mistakes

Teams get pagination keyset vs offset wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

API design for pagination keyset vs offset frustrates clients when pagination cursors expire silently, error bodies lack stable machine-readable codes, and rate limits return 429 without `Retry-After` headers.

## Debugging and triage workflow

When pagination keyset vs offset misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Use the Index, Luke — pagination](https://use-the-index-luke.com/no-offset)
- [GitHub REST API cursor pagination](https://docs.github.com/en/rest/guides/using-pagination-in-the-rest-api)
- [Stripe API pagination](https://docs.stripe.com/api/pagination)
- [SQL cursor pagination (PlanetScale)](https://planetscale.com/blog/mysql-pagination)
- [Rate limiting algorithms](https://blog.michaelsam94.com/api-rate-limiting-algorithms/)
