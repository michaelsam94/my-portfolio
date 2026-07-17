---
title: "RAG: Expand Contract Migrations"
slug: "rag-expand-contract-migrations"
description: "Expand-contract migrations for RAG schema and index changes — zero-downtime corpus metadata updates, dual-write phases, and safe column renames."
datePublished: "2024-12-25"
dateModified: "2026-07-17"
tags: ["AI", "Rag", "Expand"]
keywords: "rag, expand, contract, migrations, ai, production, engineering, architecture"
faq:
  - q: "What is expand-contract in the context of RAG systems?"
    a: "Expand-contract is a multi-phase migration: expand adds new schema or index fields alongside old ones without breaking readers; migrate backfills data; contract removes deprecated fields after all consumers switch. It applies to Postgres metadata tables, vector index payload schemas, chunk metadata JSON, and API response shapes—not only relational databases."
  - q: "When must RAG deployments use expand-contract instead of big-bang migrations?"
    a: "Whenever ingestion workers, retrieval services, and admin UI deploy independently on rolling schedules. Renaming metadata filter fields, changing ACL encoding, or splitting chunk text from metadata requires phases so old pods read old fields while new pods write both."
  - q: "How long should the expand phase last for corpus metadata changes?"
    a: "Until all deployed service versions read the new field and backfill reaches 100% of active documents, plus one rollback window—typically 2–4 weeks for large corpora. Monitor dual-write error rates and lagging backfill jobs before contract deletes old columns or stops populating legacy fields."
---
A Friday deploy renamed chunk metadata field `tenant_id` to `organization_id` in the vector payload and Postgres filter table simultaneously. Saturday ingestion wrote `organization_id`; Friday's retrieval pods still filtered on `tenant_id`—multi-tenant isolation silently broke: users saw other organizations' documents in hybrid search results until rollback Monday. The fix was not "migrate faster" but **expand-contract**: add new field, dual-write, migrate readers, backfill, then remove old field—never rename in one cut.

**Expand-contract** (expand → migrate → contract) is the standard pattern for zero-downtime schema evolution. RAG platforms have multiple moving schemas—SQL metadata, vector payloads, OpenSearch mappings, API contracts— that rolling Kubernetes deploys desynchronize if you big-bang rename.

## Three phases defined

### Expand

Add new structure without removing old:

- Postgres: `ALTER TABLE chunks ADD COLUMN organization_id UUID;`
- Vector metadata: start writing both `tenant_id` and `organization_id`
- API: accept both query params; response includes both keys marked deprecated

Old code ignores new fields. New code writes both.

### Migrate

Backfill historical data:

```sql
UPDATE chunks SET organization_id = tenant_id WHERE organization_id IS NULL;
```

Vector index backfill via async job re-upserting metadata with dual keys—expensive; batch off-peak with rate limits.

Feature flag retrieval filters: `USE_ORG_ID_FILTER` false until backfill > 99.9%.

### Contract

Remove deprecated after all services upgraded:

- Drop column `tenant_id`
- Stop writing legacy metadata key
- Remove API field; major version bump if external

Verify no pod image older than N releases in prod via deployment inventory.

## RAG-specific expand examples

### Renaming ACL metadata for filtering

Vector query filter changes from `tenant_id` to `organization_id`:

| Phase | Ingestion writes | Retrieval reads |
|-------|------------------|-----------------|
| Expand | both keys | `tenant_id` (old) |
| Migrate | both keys | COALESCE org from either |
| Contract | `organization_id` only | `organization_id` only |

Retrieval code during migrate:

```python
def tenant_filter(ctx):
    org = ctx.organization_id or ctx.legacy_tenant_id  # transitional
    return {"organization_id": org}  # index must have field populated
```

### Adding required chunk field `locale`

Expand: add nullable `locale` with default inference from source.
Migrate: batch job sets locale from document headers.
Contract: reject chunks missing locale at ingest; non-null constraint.

### Splitting `text` from oversized metadata payloads

Some indexes store full chunk text in metadata—hits size limits.

Expand: write text to object storage pointer `text_ref`; keep inline `text` for old readers.
Migrate: backfill `text_ref`, verify fetch parity.
Contract: remove inline `text` from metadata; retrieval fetches blob.

## Dual-write implementation

Centralize in repository layer— not scattered handlers:

```python
def build_chunk_metadata(doc, chunk) -> dict:
    meta = {
        "tenant_id": doc.tenant_id,           # legacy
        "organization_id": doc.organization_id,  # new
        "locale": doc.locale,
    }
    return meta
```

Single function ensures every write path dual-populates during expand.

## Coordinating vector and SQL migrations

RAG state spans systems—order matters:

1. Expand SQL + vector metadata (dual keys)
2. Deploy retrieval reading new key with fallback
3. Backfill both stores
4. Deploy ingestion writing new key only (still dual read)
5. Contract SQL column drop
6. Contract vector metadata key removal via reindex or metadata patch API

Skipping vector backfill while SQL migrates causes filter mismatches—track **schema version** in health endpoints.

## Feature flags and version skew

```yaml
flags:
  read_organization_id: true   # retrieval
  write_dual_metadata: true   # ingestion
```

Flag service defaults safe for oldest deployed version during rollouts.

## Testing expand-contract

Integration test matrix:

- Old reader + new writer data → old reader works
- New reader + old writer data → fallback works
- New reader + new writer → primary path

Staging runs three pod versions simultaneously before prod.

## Rollback during expand

If new field logic bugs, rollback deploy without contract phase—old field still populated via dual-write. Contract phase burns rollback bridge—delay until confidence high.

## Documentation and runbooks

Migration ticket template:

- Expand PR number, deploy date
- Backfill job dashboard link
- Criteria for contract (version list, backfill %)
- Contract PR scheduled date

Communicate to ML ops: reindex jobs may double write amplification during dual metadata phase—budget cost.

Expand-contract migrations are how RAG teams rename fields and evolve metadata without weekend isolation breaches. Add before remove, dual-write across SQL and vector payloads, backfill with measurable progress, flip readers before writers contract, and treat simultaneous rename deploys as incident invitations—not migration strategy.

## Automated contract phase gates

CI job queries production deployment API: list running image tags for ingestion and retrieval services. Contract phase PR merges only when all tags ≥ minimum version from expand runbook. Script fails if canary pod still runs N-2 release.

Database migrations use expand-contract in Flyway/Liquibase with explicit `/* expand */` and `/* contract */` comment markers—reviewers see phase at glance.

## Communication with data science and eval teams

Metadata field renames break offline eval sets filtering on old keys—notify DS team at expand start with field mapping CSV. Eval pipelines dual-read filters during migrate phase; stale notebooks are silent eval skew source.

Schedule contract phase outside major product launches and holiday freezes—rollback without old column after contract is expensive full reindex.

## Roll-forward-only contract mistakes

If contract phase drops column still read by forgotten cron job on old VM, silent failures occur. **Service inventory** scan before contract: grep all repos for deprecated field name; ArgoCD application list must show zero old image tags. Infrastructure outside k8s (legacy cron on VM) often missed—include in expand runbook checklist.

Maintain **rollback migration** SQL scripts during contract window for 14 days—even if rarely used, legal-us isolation incident recovery time drops from days to hours.

## Tooling for metadata backfill progress

Grafana panel: `expand_migration_backfill_percent` per field, per corpus. Stakeholders see contract phase blocked until bar hits 100%—removes subjective "looks done enough" debates. Automated Slack reminder daily when backfill <95% and contract PR scheduled within 7 days.

Vector metadata patch APIs vs full re-upsert: patch cheaper for adding field; re-upsert required when removing inline text in contract phase. Cost estimate in migration ticket prevents finance surprise on Pinecone write units.

## Training engineers on expand-contract rhythm

Expand-contract feels slow to engineers accustomed to ORM auto-migrations. Lunch-and-learn with before/after outage story—tenant isolation breach from rename—builds patience. Template PR descriptions with expand/migrate/contract checkboxes; reviewers reject combined phases in single deploy.

Include expand-contract in **architecture decision record** template for any metadata schema change affecting retrieval filters. ADR links migration ticket, backfill job, and contract scheduled date—onboarding engineers trace history without archaeology in Slack.

Expand-contract migrations belong in definition of done for any retrieval metadata change—same checkbox as unit tests. Skipping phases to meet sprint deadline trades hours saved now for isolation breach or silent filter failure later; incident cost exceeds migration discipline every time in regulated RAG deployments.

Pair expand-contract with feature flags on read paths before contract removes legacy fields—flags off means old code path still works during rollback window even after contract SQL migration merged, giving 24h safety net if undiscovered consumer still parsed deprecated JSON key from cached API responses at edge.

Contract phase deserves its own deploy ticket template separate from expand—reviewers explicitly confirm zero consumers on deprecated field via telemetry and inventory scans, not developer assertion alone in PR description footnote.

Maintain a living inventory of every field deprecated via expand-contract with target contract date—program management visibility prevents migrations stalling in expand phase for quarters because no owner tracked contract deadline on calendar. Review the inventory in weekly platform sync until contract merges.

## What to watch after shipping expand contract migrations

The first week after rollout is when silent misconfigurations show up. Watch p95 latency and error rate for the new path, compare against the previous baseline, and sample logs for unexpected status codes. Keep a feature flag or config kill switch until the metrics stabilize. Document the owner of the dashboard and the expected "green" ranges so the next on-call engineer is not reverse-engineering intent from a blank Grafana folder.
