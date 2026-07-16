---
title: "Cursor Pagination the Relay Way"
slug: "graphql-pagination-cursor-relay"
description: "Implement stable cursor pagination in GraphQL using the Relay Connection spec: cursors, PageInfo, forward/backward paging, and database strategies."
datePublished: "2025-06-07"
dateModified: "2025-06-07"
tags: ["Backend", "GraphQL", "API", "Architecture"]
keywords: "GraphQL cursor pagination, Relay Connection spec, PageInfo, stable pagination, GraphQL pagination best practices, forward pagination"
faq:
  - q: "Why use cursor pagination instead of offset pagination in GraphQL?"
    a: "Offset pagination (LIMIT/OFFSET) breaks when rows are inserted or deleted during paging — users see duplicates or skip items. Cursor pagination anchors to a stable position (usually a sort key + ID), so pages remain consistent even as the dataset changes. It also scales better because OFFSET scans skip rows expensively on large tables."
  - q: "What is the Relay Connection spec?"
    a: "It's a GraphQL pagination convention defining Connection, Edge, and PageInfo types. A Connection wraps a list of Edges (each with a node and cursor), plus PageInfo (hasNextPage, endCursor). Clients pass after/before cursors and first/last counts to page forward or backward."
  - q: "What should a cursor encode?"
    a: "Encode an opaque, stable sort key — typically base64(sortValue:id) or an encrypted tuple. Never expose raw database IDs alone if sort order can change. The cursor must uniquely identify a position in the sorted result set, not just a row ID."
---

Offset pagination is fine for admin tables nobody scrolls. It's a liability for feeds, chat histories, and any list where rows shift while the user pages. I learned this when a product feed started skipping posts after a deploy introduced concurrent inserts — `OFFSET 40` no longer meant "the next page" because 12 new rows landed at the top. Relay-style cursor pagination fixed it without changing the client API shape much.

## Offset vs cursor, concretely

**Offset:**

```graphql
posts(limit: 20, offset: 40) { title }
```

SQL: `SELECT * FROM posts ORDER BY created_at DESC LIMIT 20 OFFSET 40`

Problems at scale:
- Postgres scans and discards 40 rows on every page
- New rows at the top shift offsets — page 3 might repeat items from page 2
- No stable "resume from here" token for infinite scroll

**Cursor:**

```graphql
posts(first: 20, after: "eyJjcmVhdGVkQXQiOjE3...") {
  edges { node { title } cursor }
  pageInfo { hasNextPage endCursor }
}
```

SQL: `SELECT * FROM posts WHERE (created_at, id) < ($cursor_time, $cursor_id) ORDER BY created_at DESC, id DESC LIMIT 21`

The extra row (21 instead of 20) tells you `hasNextPage` without a COUNT query.

## Relay Connection schema

```graphql
type Query {
  posts(first: Int, after: String, last: Int, before: String): PostConnection!
}

type PostConnection {
  edges: [PostEdge!]!
  pageInfo: PageInfo!
}

type PostEdge {
  node: Post!
  cursor: String!
}

type PageInfo {
  hasNextPage: Boolean!
  hasPreviousPage: Boolean!
  startCursor: String
  endCursor: String
}
```

Arguments follow Relay conventions:
- `first` + `after` — forward pagination
- `last` + `before` — backward pagination
- Never mix `first` and `last` in one request

## Encoding cursors

Cursors must be opaque to clients — they encode position, not identity alone:

```javascript
function encodeCursor(row) {
  const payload = JSON.stringify({ t: row.created_at, i: row.id });
  return Buffer.from(payload).toString('base64url');
}

function decodeCursor(cursor) {
  return JSON.parse(Buffer.from(cursor, 'base64url').toString());
}
```

Use a composite sort key `(created_at, id)` even when sorting by one column — IDs break ties when timestamps collide.

The query becomes:

```sql
SELECT * FROM posts
WHERE (created_at, id) < ($t, $i)
ORDER BY created_at DESC, id DESC
LIMIT $first + 1
```

For ascending sorts, flip the comparison operator.

## Resolver implementation

```javascript
async function postsConnection(_, { first = 20, after }, { db }) {
  const limit = Math.min(first, 100); // cap page size
  let query = db('posts').orderBy([
    { column: 'created_at', order: 'desc' },
    { column: 'id', order: 'desc' },
  ]);

  if (after) {
    const { t, i } = decodeCursor(after);
    query = query.where(function () {
      this.where('created_at', '<', t)
        .orWhere(function () {
          this.where('created_at', '=', t).andWhere('id', '<', i);
        });
    });
  }

  const rows = await query.limit(limit + 1);
  const hasNextPage = rows.length > limit;
  const nodes = hasNextPage ? rows.slice(0, limit) : rows;

  const edges = nodes.map(node => ({
    node,
    cursor: encodeCursor(node),
  }));

  return {
    edges,
    pageInfo: {
      hasNextPage,
      hasPreviousPage: !!after,
      startCursor: edges[0]?.cursor ?? null,
      endCursor: edges[edges.length - 1]?.cursor ?? null,
    },
  };
}
```

## Index requirements

Cursor pagination is only fast with matching indexes. For `(created_at DESC, id DESC)`:

```sql
CREATE INDEX idx_posts_cursor ON posts (created_at DESC, id DESC);
```

Without this index, each page is a sequential scan. Explain-analyze your paginated queries before shipping.

## Client usage

Forward infinite scroll:

```javascript
const { data, fetchMore } = useQuery(POSTS_QUERY, { variables: { first: 20 } });

function loadMore() {
  fetchMore({
    variables: { after: data.posts.pageInfo.endCursor },
    updateQuery: (prev, { fetchMoreResult }) => ({
      posts: {
        ...fetchMoreResult.posts,
        edges: [...prev.posts.edges, ...fetchMoreResult.posts.edges],
      },
    }),
  });
}
```

Check `pageInfo.hasNextPage` before calling `fetchMore` — don't fire requests into an empty tail.

## Common mistakes

| Mistake | Fix |
|---------|-----|
| Cursor is just the row ID | Encode full sort position |
| No tiebreaker column | Add `id` to sort and cursor |
| Unbounded `first` | Cap at 50–100 server-side |
| COUNT(*) for hasNextPage | Fetch N+1 rows instead |
| Mutable sort keys | Sort by immutable columns only |

## Backward pagination

Relay supports `last` + `before` for reverse pagination (chat history, logs):

```graphql
query {
  messages(last: 20, before: "cursor_xyz") {
    edges { node { id body } cursor }
    pageInfo { hasPreviousPage startCursor }
  }
}
```

SQL for backward cursor requires reversing sort in query, then reversing results in application layer — easy to get wrong. Many APIs implement forward-only pagination and use separate "load older" endpoint with explicit timestamp cursor.

## Null handling in cursors

Nullable sort columns break cursor stability:

```sql
-- BAD: NULL created_at rows sort unpredictably
ORDER BY created_at DESC

-- GOOD: COALESCE with sentinel
ORDER BY COALESCE(created_at, '1970-01-01') DESC, id DESC
```

Encode null presence in cursor payload if sort column is nullable — decoding must reconstruct exact SQL sort semantics.

## GraphQL-specific performance

DataLoader batching still applies to Connection resolvers — N+1 on `edges.node.author` defeats cursor pagination performance gains. Use `@defer` sparingly on paginated lists; deferred fragments complicate cache keys for APQ.

Load test pagination deep into tail (page 100+) — missing composite index shows up only at depth, not on first page.

Pair with [persisted queries security](https://blog.michaelsam94.com/graphql-persisted-queries-security/) when paginated queries are your highest-traffic operations.

## Production checklist

- [ ] Composite index matches ORDER BY columns exactly
- [ ] Cursor encodes full sort position, not just row ID
- [ ] `first`/`last` capped server-side at 50–100
- [ ] N+1 prevented via DataLoader on edge resolvers
- [ ] Deep pagination load-tested (page 100+)

Offset pagination still appears in admin exports — keep cursor APIs for user-facing lists and document when internal tools may use unsafe OFFSET for one-off reports.

## Common production mistakes

Teams get pagination cursor relay wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

GraphQL APIs for pagination cursor relay melt down under nested queries without depth limits, N+1 resolvers hit the database per field, and schema deprecation has no usage telemetry.

## Resources

- [Relay Cursor Connections Specification](https://relay.dev/graphql/connections.htm) — canonical Connection/Edge/PageInfo definitions
- [GraphQL Pagination best practices (GraphQL.org)](https://graphql.org/learn/pagination/) — overview of offset vs cursor approaches
- [Apollo Pagination Guide](https://www.apollographql.com/docs/react/pagination/cursor-based/) — client-side fetchMore patterns
- [Use The Index, Luke — Pagination](https://use-the-index-luke.com/sql/partial-results/fetch-next-page) — SQL indexing for cursor queries
