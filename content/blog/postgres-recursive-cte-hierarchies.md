---
title: "Postgres Recursive CTEs for Hierarchies"
slug: "postgres-recursive-cte-hierarchies"
description: "Model org charts, category trees, and bill-of-materials with recursive CTEs, cycle detection, and when to migrate to ltree or closure tables."
datePublished: "2026-03-01"
dateModified: "2026-07-17"
tags:
  - "PostgreSQL"
  - "Backend"
  - "Database"
keywords: "recursive CTE, postgres hierarchy, org chart query, adjacency list, cycle detection"
faq:
  - q: "When should I use a recursive CTE versus storing a materialized path?"
    a: "Recursive CTEs on adjacency lists are simplest for read-mostly trees under a few thousand nodes per query and moderate depth. Materialized paths or closure tables win when you need constant-time subtree checks, frequent ancestor lookups, or depth limits without recursive planning cost."
  - q: "How do I prevent infinite loops in cyclic graphs?"
    a: "Track visited node IDs in an array column in the recursive term and filter with WHERE NOT (id = ANY(path)). Postgres 14+ also offers CYCLE clause in WITH RECURSIVE for automatic cycle detection."
  - q: "Are recursive CTEs efficient for deep org charts?"
    a: "Each depth level is another iteration; depth 50 means 50 recursive steps. Index parent_id, consider ltree extension, or precompute paths. EXPLAIN shows Recursive Union nodes—watch work_mem and row counts on wide trees."
  - q: "Can I use recursive CTEs for bill-of-materials quantity explosion?"
    a: "Yes. Carry cumulative quantity in the recursive term: child_qty = parent_qty * edge_qty. Use numeric types, not float. Cap depth or detect cycles; BOM graphs are prone to cycles from data entry errors."
---

Hierarchies appear everywhere: reporting lines, product categories, nested comments, multi-level BOMs. Relational tables are flat; trees are a graph constraint you enforce with `parent_id` foreign keys and query with **recursive common table expressions (CTEs)**.

The hard parts are **cycle safety**, **performance on wide/deep trees**, **aggregating up and down the tree**, and knowing when adjacency list + recursive CTE stops scaling and **ltree** or **closure tables** deserve a migration.

## Adjacency list baseline

```sql
CREATE TABLE org_unit (
  id         int PRIMARY KEY,
  name       text NOT NULL,
  parent_id  int REFERENCES org_unit(id)
);

CREATE INDEX org_unit_parent_idx ON org_unit (parent_id);
```

Roots have `parent_id IS NULL`. Inserts are O(1).

## Walking down: all descendants

```sql
WITH RECURSIVE subtree AS (
  SELECT id, name, parent_id, 1 AS depth,
         ARRAY[id] AS path
  FROM org_unit
  WHERE id = 4

  UNION ALL

  SELECT c.id, c.name, c.parent_id, s.depth + 1,
         s.path || c.id
  FROM org_unit c
  JOIN subtree s ON c.parent_id = s.id
  WHERE NOT c.id = ANY(s.path)
)
SELECT * FROM subtree ORDER BY depth, name;
```

**Anchor member** (non-recursive): starting node(s). **Recursive member**: joins working set to base table.

**`path` array:** prevents revisiting nodes if a cycle exists.

Postgres 14+ **CYCLE** syntax:

```sql
WITH RECURSIVE subtree AS (
  ...
  CYCLE id SET is_cycle TO 'yes' DEFAULT 'no' USING path
)
SELECT * FROM subtree WHERE is_cycle = 'no';
```

## Walking up: ancestors to root

```sql
WITH RECURSIVE ancestors AS (
  SELECT id, name, parent_id, 0 AS depth
  FROM org_unit WHERE id = 42

  UNION ALL

  SELECT p.id, p.name, p.parent_id, a.depth + 1
  FROM org_unit p
  JOIN ancestors a ON p.id = a.parent_id
)
SELECT * FROM ancestors ORDER BY depth DESC;
```

## Aggregates roll-up

Each node has `headcount`; executive wants total including reports—propagate leaf metrics upward via join direction carefully. Test on small hand-drawn trees first.

For **BOM quantity explosion**:

```sql
WITH RECURSIVE explode AS (
  SELECT parent_part_id AS root_id, child_part_id, qty::numeric AS cumulative_qty
  FROM bom_edge WHERE parent_part_id = $1

  UNION ALL

  SELECT e.root_id, b.child_part_id, e.cumulative_qty * b.qty
  FROM explode e
  JOIN bom_edge b ON b.parent_part_id = e.child_part_id
  WHERE e.cumulative_qty * b.qty < 1000000
)
SELECT root_id, child_part_id, cumulative_qty FROM explode;
```

## Depth limits and pagination

"Only direct reports" is depth = 1—skip recursion. "Up to 3 levels" adds `WHERE s.depth < 3` in recursive term.

Paginating recursive results is awkward—materialized path or closure table for "page 2 of subtree."

## Indexing and EXPLAIN

Critical index: **`(parent_id)`** for downward walks.

Wide tree (CEO → 500 direct reports) explodes row count—**breadth kills** more than depth.

Mitigations: materialized view refreshed nightly, closure table, or **ltree**:

```sql
CREATE EXTENSION ltree;
ALTER TABLE org_unit ADD path ltree;
CREATE INDEX path_gist ON org_unit USING gist (path);
SELECT * FROM org_unit WHERE path <@ '1.4';
```

## Closure table pattern

```sql
CREATE TABLE org_closure (
  ancestor_id   int NOT NULL,
  descendant_id int NOT NULL,
  depth         int NOT NULL,
  PRIMARY KEY (ancestor_id, descendant_id)
);
```

Subtree query without recursion:

```sql
SELECT o.* FROM org_unit o
JOIN org_closure c ON o.id = c.descendant_id
WHERE c.ancestor_id = 4;
```

## Mutations: moving subtrees

Verify no cycle before reparent: ensure new parent is not in node's subtree. ltree/closure require bulk path or closure row updates.

## Materialized hierarchy cache

When recursive CTE latency crosses SLO:

```sql
CREATE MATERIALIZED VIEW org_unit_enriched AS
WITH RECURSIVE tree AS ( ... ) SELECT * FROM tree;
REFRESH MATERIALIZED VIEW CONCURRENTLY org_unit_enriched;
```

Refresh after bulk HR imports—not every row update.

## Graphs with multiple parents

BOM and dependency graphs are DAGs—model **`edge (from_id, to_id)`** with cycle guard, not single `parent_id`.

## Common data quality failures

- Orphan nodes—FK or periodic audit
- Multiple roots when business expects one
- Cycles from manual SQL fixes

```sql
SELECT id FROM org_unit o
WHERE parent_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM org_unit p WHERE p.id = o.parent_id);
```

## When to stop using recursive CTEs

Signals: P95 subtree query > 50ms at your scale, depth > 20, frequent ancestor/d descendant checks, or graph is DAG not tree.

Recursive CTEs are the right default for org charts and category trees—until measurement says otherwise.



## work_mem and spilling on deep trees

Recursive CTEs materialize working tables; wide trees exceed **`work_mem`** and spill to disk—**`EXPLAIN ANALYZE`** shows **`workfile`** usage. Raise **`work_mem`** session-local for reporting queries only, not globally. Alternative: limit depth, paginate roots, or precompute closure. **`max_recursive_iterations`** (PG 14+) caps runaway graphs—set on APIs exposed to user-supplied graph traversal to prevent DoS.

## Serializable isolation and hierarchy updates

Reparenting under **`SERIALIZABLE`** may abort when concurrent reads traverse old and new structure—retry logic required. For HR org changes during business hours, short transactions on metadata tables plus **`READ COMMITTED`** default often suffice; use **`SELECT ... FOR UPDATE`** on moved subtree root during reparent.

## Comparing ltree operators

Beyond **`@>`** (ancestor) and **`<@`** (descendant), **`~`** matches lquery patterns—useful for "all units matching `*.engineering.*`" without recursive CTE. **`?`** checks label at level. Migration from adjacency to ltree: bulk **`UPDATE path FROM recursive compute`**, validate with **`nlevel(path)`** vs recursive depth, add GiST index before cutover.

## Comment threading and visibility

Comment trees add **`visible`** and **`deleted_at`** predicates in recursive term—apply in anchor and recursive members identically or hidden replies reappear as orphan paths. Soft-delete patterns: stop recursion at deleted node but keep subtree counts for moderation dashboards via separate **`moderation_walk`** CTE.




## Recursive CTE in writable CTEs (DML)

Postgres allows **`WITH RECURSIVE ... UPDATE/DELETE`** patterns for hierarchical bulk operations—use carefully with row locks. Example: deactivate entire subtree by recursive selection then update—prefer single **`UPDATE ... WHERE id IN (SELECT id FROM recursive_cte)`** for clarity and lock ordering.

## Performance comparison table

| Approach | Query complexity | Write complexity | Best for |
| --- | --- | --- | --- |
| Adjacency + recursive CTE | Low | Low | Small/medium trees |
| ltree | Medium | Medium (path recompute) | Frequent subtree queries |
| Closure table | Low reads | High writes | Read-heavy, moderate writes |
| Materialized view | Lowest reads | Refresh lag | Analytics snapshots |

Choose based on read/write ratio measured in production, not architecture blog preferences.



## API design for hierarchy endpoints

Expose three endpoints—ancestors, descendants, subtree aggregate—backed by different SQL plans rather than one mega-recursive query with optional flags. Cache subtree roots with TTL for catalog trees changing hourly not per second. Return cycle_detected boolean in API when using CYCLE clause so clients can surface data quality errors to admins instead of silent truncation.

## Debugging recursive performance in production

Log recursive depth and row count from application after EXPLAIN ANALYZE in staging derived templates. When production latency spikes, compare current depth distribution to baseline—org reorg flattening tree should reduce depth but reorg bugs often create temporary deep chains before cleanup jobs run.


## Data import validation for hierarchies

After bulk CSV import of parent_id relationships, run cycle detection and orphan queries before enabling user traffic. One bad row creating cycle can DoS admin tree views—validate in transaction, reject file on failure.



## Serializable subtree deletion

Deleting subtree root with recursive CTE selection then DELETE must lock rows in consistent order to avoid deadlock with concurrent inserts under parent—delete deepest nodes first via recursive ordering by depth DESC or use closure table batch delete pattern.

## Export for downstream systems

Graph analytics tools prefer edge list CSV—export `(parent_id, child_id)` pairs rather than recursive query at export time; recursion stays for online API, batch export uses simple join.

## Resources

- [PostgreSQL WITH queries (recursive)](https://www.postgresql.org/docs/current/queries-with.html)
- [ltree module](https://www.postgresql.org/docs/current/ltree.html)
