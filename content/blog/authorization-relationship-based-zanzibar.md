---
title: "Zanzibar-Style Authorization"
slug: "authorization-relationship-based-zanzibar"
description: "Relationship-based access control the Zanzibar way: tuples, namespaces, computed usersets, and when ReBAC beats roles and ACLs."
datePublished: "2024-11-05"
dateModified: "2024-11-05"
tags: ["Security", "Backend", "Architecture"]
keywords: "Zanzibar, ReBAC, relationship-based access control, Google Zanzibar, OpenFGA, SpiceDB, authorization tuples"
faq:
  - q: "What is ReBAC / Zanzibar-style authorization?"
    a: "Instead of attaching a flat role to a user, you store relationships as tuples like `doc:readme#viewer@user:alice` or `doc:readme#viewer@group:eng#member`. Authorization checks walk those relationships — including inherited ones through groups and parent folders — to decide if a subject can perform a relation on an object."
  - q: "When is Zanzibar a better fit than RBAC?"
    a: "When permissions follow graphs: shared documents, folder trees, org hierarchies, or 'users who can view this because they're in a team that owns the parent project.' Classic RBAC struggles when the same role means different object sets per tenant. ReBAC models that naturally."
  - q: "What are the hard parts in production?"
    a: "Consistent, low-latency checks at high QPS; cache invalidation when tuples change; and modeling mistakes that grant broader access than intended. You also need a clear story for listing objects a user can access — checks are easier than reverse indexes."
---

Role-based access control collapses when the question isn't "is Alice an admin?" but "can Alice view *this* document because she's a member of a group that was granted viewer on a parent folder?" Google's Zanzibar paper describes a relationship graph that answers those questions at planetary scale. You don't need Google's scale to steal the model — you need shared docs, multi-tenant object graphs, or nested ownership.

## Tuples are the API

A relationship tuple has the shape:

```
<object>#<relation>@<subject>
```

Examples:

```
doc:budget-2026#owner@user:alice
doc:budget-2026#viewer@group:finance#member
folder:finance#viewer@user:bob
doc:budget-2026#parent@folder:finance
```

A check asks: is `user:alice` in the computed userset for `doc:budget-2026#viewer`? The namespace config defines how relations expand — e.g. `viewer` includes `owner`, and includes viewers of the parent folder.

```python
# Conceptual namespace (OpenFGA-style)
type doc
  relations
    define owner: [user]
    define parent: [folder]
    define viewer: [user, group#member] or owner or viewer from parent
```

## Check vs list

**Check** (`allowed = check(user, relation, object)`) is the hot path — cache aggressively with careful invalidation.

**List** (`objects = list(user, relation, type)`) powers "show my documents" UIs and is harder: you need reverse indexes or carefully designed queries. Budget for list early; bolting it on later is painful.

## Consistency

Zanzibar exposes a consistency token so a read-after-write (share doc → immediately open as viewer) doesn't race a cache. SpiceDB and OpenFGA offer similar levers (`fully_consistent` vs minimize latency). For share flows, prefer tighter consistency; for passive reads of public objects, prefer cached checks.

## Modeling pitfalls

- **Over-broad `viewer from parent`** — a public parent folder silently opens every child
- **Missing relation aliases** — product says "commenter" but you only modeled viewer/editor
- **Subjects as users only** — forget service accounts and API keys as subjects
- **Embedding authz in every service differently** — centralize the tuple store; services call check

## When not to use it

Simple apps with three global roles and no object sharing don't need ReBAC — a `role` column is fine. Zanzibar-style systems earn their keep when the permission graph *is* the product (collaboration, ACL-heavy SaaS).

I've migrated a document product from "ACL array on each row" to tuples when folder inheritance requests started producing SQL only the original author understood. The graph was clearer, and checks became one API.

## OpenFGA and SpiceDB in practice

Production ReBAC systems need a store, not hand-rolled SQL. OpenFGA and SpiceDB (both Zanzibar-inspired) provide:

- **Tuple write API** — `write(user:alice, viewer, doc:readme)`
- **Check API** — `check(user:alice, viewer, doc:readme)` → true/false
- **Expand API** — debug why a check passed (which path granted access)
- **Schema language** — define types, relations, and inheritance rules

```yaml
# OpenFGA authorization model
model
  schema 1.1

type user

type document
  relations
    define owner: [user]
    define editor: [user] or owner
    define viewer: [user] or editor
    define parent: [folder]
    define viewer: viewer from parent

type folder
  relations
    define owner: [user]
    define viewer: [user] or owner
```

Deploy as a sidecar or centralized service. Application services call check before every sensitive operation — never embed permission logic in SQL WHERE clauses.

## Tuple lifecycle and cache invalidation

Tuples change when users share, revoke, join groups, or move objects:

```
Share doc → write tuple (doc#viewer@user:bob)
Revoke → delete tuple
Move doc to folder → update parent tuple
User leaves group → delete (group#member@user:alice), re-evaluate all group grants
```

Every tuple mutation must invalidate cached check results for affected subjects and objects. Zanzibar's **zookie** (consistency token) pattern:

1. Write tuples, receive token T
2. Subsequent checks include "at least as fresh as T"
3. Store guarantees read-after-write consistency for that token

Without this, Alice shares a doc with Bob and Bob immediately gets "access denied" because the check hit a stale cache.

## Reverse lookup: listing accessible objects

Check is O(graph walk from subject). List is harder — "show all docs Alice can view":

**Option 1: Reverse index** — maintain `user:alice → [doc:1, doc:2, ...]` updated on every tuple write. Fast list, expensive writes.

**Option 2: Search-time filter** — query all docs, filter each through check API. Simple, slow at scale.

**Option 3: Materialized view** — periodic batch job computes accessible objects per user. Stale but fast.

Most products start with Option 2, hit scale limits, migrate to Option 1 for hot paths. Plan for this transition before launch.

## Migration from RBAC/ACL

Typical migration from row-level ACL arrays:

1. Export existing permissions: `(user_id, object_id, role)` tuples
2. Map roles to relations: `role=read` → `viewer`, `role=write` → `editor`
3. Write tuples to ReBAC store
4. Dual-read: check both old ACL and new tuples during transition
5. Switch checks to ReBAC-only
6. Drop ACL column after validation period

Don't try to model RBAC roles as ReBAC relations 1:1 — rethink the permission graph during migration.

## Failure modes

- **Over-broad inheritance** — `viewer from parent` on a public folder opens all children
- **Missing service account subjects** — API keys and bots need tuple entries too
- **Stale cache after share** — user sees "access denied" immediately after being shared
- **List without reverse index** — "my documents" page times out checking every doc
- **Inconsistent checks across services** — each service implements different logic; centralize

## Production checklist

- Authorization model defined in schema language (OpenFGA/SpiceDB)
- Check API called at every sensitive operation boundary
- Consistency tokens used for read-after-write on share flows
- Reverse index or materialized view for list operations
- Tuple write/delete audited with actor and timestamp
- Migration plan from existing RBAC/ACL documented
- Expand API used for debugging access decisions in support tools

## Resources

- [Google Zanzibar paper](https://research.google/pubs/pub48190/)
- [OpenFGA documentation](https://openfga.dev/docs)
- [SpiceDB documentation](https://authzed.com/docs)
- [Auth0 — Introduction to ReBAC](https://auth0.com/blog/what-is-rebac/)
---
