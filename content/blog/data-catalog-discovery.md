---
title: "Data Catalogs and Discovery"
slug: "data-catalog-discovery"
description: "A data catalog is only useful if people can find trustworthy datasets. How discovery, lineage, ownership, and search design work in practice."
datePublished: "2025-07-08"
dateModified: "2025-07-08"
tags: ["Data Engineering", "Analytics"]
keywords: "data catalog, data discovery, metadata management, Amundsen, DataHub, data governance, dataset search"
faq:
  - q: "What is a data catalog used for?"
    a: "A data catalog indexes datasets, tables, dashboards, and pipelines with metadata — schema, owner, freshness, lineage, and documentation. It helps analysts and engineers discover existing data instead of rebuilding tables, and surfaces trust signals like SLA status and certification tags."
  - q: "How is a data catalog different from a data dictionary?"
    a: "A data dictionary documents column definitions for known schemas, often in a spreadsheet or wiki. A catalog adds search, automated harvesting from warehouses and BI tools, lineage graphs, ownership workflows, and integration with access requests. Dictionaries are static reference; catalogs are living systems."
  - q: "What makes catalog adoption fail?"
    a: "Stale metadata, missing owners, and search that returns junk. If descriptions are empty and lineage is broken, analysts revert to Slack asks. Successful catalogs automate ingestion, require owner assignment at table creation, and embed discovery in tools people already use — SQL clients, notebooks, BI platforms."
---

Every data team I've joined had the same hidden tax: an analyst spends two days rebuilding a metric that already exists under a name nobody remembers, in a schema nobody documents. Catalogs exist to kill that loop — not as governance theater, but as infrastructure for finding data you can trust without posting in `#data-help`.

## What a catalog actually indexes

Modern catalogs (DataHub, Amundsen, Atlan, Collibra, open-source alternatives) treat **assets** as first-class objects:

- Warehouse tables and views
- dbt models and sources
- Airflow/Dagster jobs
- Kafka topics and schemas
- Dashboards and saved queries
- ML features and training sets

Each asset carries **technical metadata** (schema, partition keys, row counts), **operational metadata** (last updated, job success rate), and **business metadata** (description, domain, certified flag, PII tags). Discovery is search over that graph, not a folder browse.

## Discovery UX that gets used

Search ranking matters more than feature count. Effective catalogs weight:

1. **Query popularity** — tables others actually SELECT from
2. **Certification** — `#certified` or `tier: gold` boosts
3. **Freshness** — stale tables sink unless explicitly historical
4. **Name and column match** — `revenue` hits `fct_daily_revenue`, not `tmp_rev_test_v3`

Faceted filters by domain (`marketing`, `finance`), environment (`prod` vs `dev`), and platform (`snowflake`, `bigquery`) cut noise. Showing **sample queries** and **downstream dashboards** on the dataset page answers "why would I use this?" faster than a paragraph of prose.

```yaml
# Example dataset metadata (DataHub-style)
entity:
  urn: urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.fct_orders,PROD)
  properties:
    description: "Order facts grain one row per order_id. Use for revenue reporting."
    customProperties:
      domain: commerce
      tier: gold
      pii: false
  ownership:
    owners:
      - team: data-platform
      - user: jchen@company.com
```

Automate this from dbt `meta` blocks and CI checks — hand-written YAML rots.

## Lineage powers trust

Discovery without lineage is a phone book without addresses. When an analyst lands on `mart_customer_ltv`, they need to see:

- Upstream: `stg_orders`, `dim_customers`, HubSpot export
- Transform: dbt model `models/marts/mart_customer_ltv.sql`
- Downstream: Looker explore "Customer 360", nightly ML feature job

Broken lineage erodes trust faster than missing descriptions. Instrument SQL parsers, dbt artifacts, and orchestrator metadata so lineage updates on every deploy. Manual lineage diagrams die in a week.

## Ownership and stewardship

Every production table needs a named owner — team or individual — with SLA accountability. Catalogs should enforce this at creation time (Terraform hook, dbt pre-commit, warehouse tag policy). Owners receive stale-metadata nags and breaking-change alerts.

Stewardship tiers help scale:

| Tier | Expectation |
|---|---|
| Gold / certified | Documented, tested, SLA, approved schema changes |
| Silver | Documented, best-effort freshness |
| Bronze / experimental | Use at own risk, may disappear |

Analysts filter to gold during discovery; engineers promote tables through tiers as maturity increases.

## Integration beats standalone portals

Adoption spikes when the catalog surfaces **where work happens**:

- dbt docs link back to catalog URNs
- IDE plugins show table descriptions on hover
- BI tools display owner and freshness on dataset pickers
- Slack bots resolve `#catalog/orders` to the asset page

A standalone portal nobody bookmarks becomes shelfware. Push metadata into existing flows.

## Building vs buying

Open-source stacks (DataHub, OpenMetadata, Amundsen) need ingestion pipelines, search tuning, and ongoing curation. Commercial tools add governance workflows and access integration at license cost. Either path fails without **curation discipline** — weekly owner reviews, deprecation tags, merged duplicate entries.

Start narrow: index production warehouse schemas and top 50 dashboards. Expand to pipelines once search quality is acceptable. Boiling the ocean on day one produces empty shells.

## Measuring success

Track metrics that reflect behavior change:

- Percentage of queries hitting catalog-linked tables vs unknown schemas
- Time-to-first-query for new hires (self-reported or instrumented)
- Duplicate table creation rate
- Metadata completeness score (% tables with owner + description + freshness)

If Slack `#data-help` volume doesn't drop, the catalog isn't working yet — fix search and ownership before adding features.

Automate catalog ingestion from dbt manifest and Airflow DAGs — manual catalog entries stale within weeks without pipeline integration.

## Data lineage integration

Catalog value multiplies with lineage graphs:

```yaml
# DataHub ingestion from dbt
source:
  type: dbt
  config:
    manifest_path: target/manifest.json
    catalog_path: target/catalog.json
```

Lineage answers "what breaks if I change this column?" — the question analysts ask daily and Slack threads answer poorly.

## Ownership and SLAs

Every catalog entry needs:

| Field | Purpose |
|-------|---------|
| Owner team | Escalation path |
| Freshness SLA | Expected update frequency |
| Tier (1-3) | Criticality for incident response |
| PII classification | Access control routing |

Automate freshness checks — compare `last_updated` metadata against SLA, open ticket when stale.

## Search quality tuning

Poor search kills adoption faster than missing features:

- Synonyms: "orders" → "purchases", "transactions"
- Boost exact table name matches over description text
- Deprecate renamed tables with redirect to replacement URN

Run quarterly "find the orders table" test with new hires — if it takes > 2 minutes, fix search before adding governance workflows.

Pair with [data lineage tracking](https://blog.michaelsam94.com/data-lineage-tracking/) for column-level impact analysis.

## Common production mistakes

Teams get catalog discovery wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Data pipelines for catalog discovery silently corrupt when schema evolution is backward-incompatible, late-arriving events are dropped, and warehouse costs spike because nobody partitions by query pattern.

## Resources

- [DataHub — LinkedIn open-source metadata platform](https://datahubproject.io/)
- [Amundsen — Lyft's data discovery tool](https://www.amundsen.io/)
- [OpenMetadata documentation](https://docs.open-metadata.org/)
- [dbt metadata and docs integration](https://docs.getdbt.com/docs/build/documentation)
- [Google Cloud — Data catalog best practices](https://cloud.google.com/data-catalog/docs)
