---
title: "Postgres citext Case Insensitive"
slug: "postgres-citext-case-insensitive"
description: "Use the citext extension for case-insensitive text columns — semantics, indexing, and when to prefer lower() instead."
datePublished: "2026-02-23"
dateModified: "2026-07-17"
tags:
  - "PostgreSQL"
  - "Backend"
  - "Database"
keywords: "citext, case insensitive postgres, email lookup, functional index lower, collation"
faq:
  - q: "How does citext compare to applying lower() on insert and query?"
    a: "citext applies case folding at comparison time inside the type — SELECT works with plain equality operators without wrapping columns in lower(). The lower() approach stores normalized text explicitly and indexes with a functional index. citext is cleaner in application code; lower() gives more control over locale-specific folding rules and works without an extension."
  - q: "Can I create a unique index on a citext column for email addresses?"
    a: "Yes. CREATE UNIQUE INDEX ON users (email) where email is citext treats 'User@Example.com' and 'user@example.com' as duplicates. The unique constraint fires on case-insensitive match. Combine with a CHECK constraint for basic format validation if needed."
  - q: "Does citext affect sorting order?"
    a: "citext sorts using the underlying case-insensitive comparison, which may differ from what users expect for display sorting. For display, cast to text or use a separate display column. For lookup and uniqueness, citext sorting is usually fine."
---

Email login forms accept `User@Example.com` and `user@example.com` as the same address — but Postgres `text` columns treat them as different strings. Every query becomes `WHERE lower(email) = lower($1)`, every unique constraint needs a functional index, and ORMs fight the pattern. The **citext** extension adds a case-insensitive text type that makes equality comparisons fold case automatically.

This article covers citext semantics, indexing behavior, locale caveats, and when explicit `lower()` normalization is the better engineering choice.

## Installing and using citext

```sql
CREATE EXTENSION IF NOT EXISTS citext;

CREATE TABLE users (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email      citext NOT NULL,
  username   citext NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX users_email_idx ON users (email);
CREATE UNIQUE INDEX users_username_idx ON users (username);
```

Insert and query without case wrangling:

```sql
INSERT INTO users (email, username) VALUES ('Alice@Example.COM', 'Alice');

-- Both match
SELECT * FROM users WHERE email = 'alice@example.com';
SELECT * FROM users WHERE username = 'ALICE';
```

The unique index rejects:

```sql
INSERT INTO users (email, username) VALUES ('alice@example.com', 'alice');
-- ERROR: duplicate key value violates unique constraint "users_email_idx"
```

## How citext works internally

citext is a domain-like type over `text` that wraps comparison operators (`=`, `<`, `>`, `LIKE`) to call `lower()` on both operands before comparing. Storage is unchanged — the original casing is preserved in the column. Only comparisons fold case.

Implications:

- **Storage**: `'Alice@Example.COM'` stored as-is; display shows original casing
- **Comparison**: Case-insensitive for `=` and ordering operators
- **Pattern matching**: `LIKE` and `~` operate case-insensitively on citext operands
- **Concatenation**: `||` with text returns text, not citext — cast back if needed

## Indexing behavior

B-tree indexes on citext columns work correctly for equality lookups:

```sql
EXPLAIN SELECT * FROM users WHERE email = 'alice@example.com';
-- Index Scan using users_email_idx
```

For pattern matching, standard B-tree indexes do not help `LIKE '%example%'` regardless of type. Use trigram indexes if needed:

```sql
CREATE EXTENSION pg_trgm;
CREATE INDEX users_email_trgm ON users USING gin (email gin_trgm_ops);
```

citext GiST/GIN operator classes exist for advanced pattern queries — rarely needed for email/username lookups.

## citext vs explicit lower() normalization

**citext approach**:

```sql
email citext NOT NULL
-- Query: WHERE email = $1
```

**lower() approach**:

```sql
email text NOT NULL
-- Insert: lower(trim($1))
-- Query: WHERE email = lower($1)
-- Index: CREATE UNIQUE INDEX ON users (email);  -- stores pre-normalized
```

| Aspect | citext | lower() normalization |
| --- | --- | --- |
| Application code | Clean equality | Must normalize everywhere |
| Missed normalization bug | Impossible for = | Possible if one path forgets lower() |
| Display casing | Preserved in column | Lost unless separate display column |
| Locale control | Database locale only | Custom normalization logic |
| Extension dependency | Requires citext | None |
| Index type | Standard B-tree on citext | B-tree on text (already normalized) |

Choose citext when you want database-enforced case insensitivity without application discipline. Choose lower() when you need Turkish I/İ locale handling, custom normalization (Gmail-style dot ignoring), or extension-free portability.

## Locale and Unicode caveats

citext uses the database's default collation for case folding via `lower()`. Unicode locale-sensitive case mapping is **not** fully handled:

- Turkish `I` vs `İ` — citext may not match user expectations
- German eszett `ß` vs `ss` — not equivalent in citext
- Unicode normalization (NFC vs NFD) — visually identical characters with different codepoints remain distinct

For internationalized username systems, consider:

```sql
-- Normalize on insert with explicit function
CREATE FUNCTION normalize_username(raw text) RETURNS text AS $$
  SELECT lower(unaccent(trim(raw)));
$$ LANGUAGE sql IMMUTABLE;
```

And store normalized text with a unique index on the normalized form, keeping display text separate.

## citext in ORMs

**Rails (ActiveRecord)**:

```ruby
# migration
enable_extension 'citext'
add_column :users, :email, :citext

# model — standard equality works
User.find_by(email: params[:email])
```

**SQLAlchemy**:

```python
from sqlalchemy import TypeDecorator, Text
from sqlalchemy.dialects.postgresql import CITEXT

class User(Base):
    email = Column(CITEXT, unique=True, nullable=False)
```

**Prisma**: No native citext support — use `Unsupported("citext")` or stick with lower() normalization.

ORM caveat: case-insensitive `IN` queries and JOIN conditions work; ORDER BY may sort differently than application-level sort with locale-aware collations.

## Partial unique constraints with citext

Enforce case-insensitive uniqueness only for active records:

```sql
CREATE UNIQUE INDEX users_active_email_idx
ON users (email)
WHERE deleted_at IS NULL;
```

citext applies within the partial index predicate the same as full indexes.

## Migration from text to citext

Existing table with duplicate emails differing only by case must be deduplicated first:

```sql
-- Find case-insensitive duplicates
SELECT lower(email), count(*)
FROM users
GROUP BY lower(email)
HAVING count(*) > 1;

-- Resolve duplicates, then:
ALTER TABLE users
  ALTER COLUMN email TYPE citext USING email::citext;
```

The cast preserves data; the unique index creation may fail if duplicates exist — fix data before adding constraints.

Online migration on large tables: use concurrent index creation after type change:

```sql
ALTER TABLE users ALTER COLUMN email TYPE citext USING email::citext;
CREATE UNIQUE INDEX CONCURRENTLY users_email_citext_idx ON users (email);
```

## When NOT to use citext

- **Case-sensitive identifiers**: API keys, session tokens, base64-encoded values
- **Filesystem paths on case-sensitive systems**: `/Home` vs `/home` are different paths
- **Hash inputs**: Case sensitivity matters for checksums
- **Performance-critical bulk comparisons** where lower() IMMUTABLE functional indexes with pre-computed values outperform runtime folding — benchmark at your scale

## Performance considerations

citext comparison calls `lower()` on both operands at runtime. For a functional index approach with pre-normalized storage, comparison is a direct byte match — potentially faster at billions of rows.

At typical application scale (millions of users), citext index scan performance is indistinguishable from text equality on normalized columns. Benchmark before optimizing.

Connection poolers (PgBouncer transaction mode) cache prepared statements referencing citext — no special handling needed.

## Testing checklist

- Insert mixed-case email, query with different case → found
- Unique constraint rejects case-variant duplicate
- Original casing preserved in SELECT without transformation
- JOIN on citext columns matches case-insensitively
- ORM find_by / WHERE equality works without lower() wrapper

## Real-world deployment notes

Teams migrating from `lower(email)` patterns should plan a phased rollout:

1. Add citext column alongside existing text column in staging
2. Run parallel queries comparing citext equality vs lower() results — investigate any mismatches (usually whitespace or Unicode normalization edge cases)
3. Swap application queries to use citext column
4. Drop functional index on lower(email) after traffic validates
5. Alter original column type in maintenance window for large tables

For multi-tenant SaaS with email-as-identity, citext unique constraints prevent the embarrassing duplicate account bug where `founder@startup.com` and `Founder@Startup.com` coexist as separate tenants. The fix after the fact requires painful account merges — citext at schema design time is cheaper.

When exporting data to systems that do not understand citext, cast explicitly:

```sql
COPY (SELECT id, email::text FROM users) TO '/tmp/users.csv' CSV HEADER;
```

Drivers return citext as text automatically in most cases, but ETL pipelines with strict type validation may need explicit casts documented in the data contract.

## Summary

citext removes an entire class of case-normalization bugs from email, username, and slug lookups by making equality comparisons case-insensitive at the type level. It preserves original casing for display, works with standard B-tree unique indexes, and integrates cleanly with most ORMs. For locale-sensitive case folding or extension-free portability, explicit lower() normalization with pre-normalized storage remains the stronger choice. For the common case of ASCII email login, citext is the simplest correct answer.


citext solves case, not whitespace: always trim emails in application code or with a CHECK constraint before relying on the unique index.

On Postgres 15+, ICU nondeterministic collations can approximate case-insensitive uniqueness without citext when extensions are restricted — test LIKE and index usage before switching.
