---
title: "Data Vault Modeling"
slug: "data-vault-modeling"
description: "Data Vault 2.0 separates hubs, links, and satellites for agile warehouse modeling. Auditability, parallel loading, and when Vault beats star schema."
datePublished: "2025-08-13"
dateModified: "2025-08-13"
tags: ["Data Engineering", "Analytics"]
keywords: "Data Vault, hub link satellite, DV2, warehouse modeling, agile data warehouse, raw vault"
faq:
  - q: "What is Data Vault modeling?"
    a: "Data Vault is a warehouse modeling methodology using Hubs (business keys), Links (relationships), and Satellites (descriptive attributes and history). It decouples structural integration from descriptive attributes, enabling parallel loads and late-binding history without destructive overwrites."
  - q: "When should I use Data Vault instead of star schema?"
    a: "Use Data Vault for complex, many-source environments with frequent schema change, strong audit requirements, and separate ingestion vs consumption teams. Star schema suits stable domains where Kimball conformed dimensions deliver simpler analyst UX and faster time-to-dashboard."
  - q: "What is the difference between raw vault and business vault?"
    a: "Raw vault stores source-aligned integrations with minimal business rules — audit trail close to landing zone. Business vault applies domain rules, deduplication, and conformance on top of raw vault. Information marts (star schemas) consume business vault for reporting."
---

Kimball star schemas are pleasant to query until twelve source systems feed `dim_customer` with conflicting definitions and every schema change requires a weekend migration. Data Vault trades some query simplicity for **integration resilience** — structure changes without rewiring the entire warehouse.

## Hubs, links, satellites

**Hub** — unique business key, load metadata, hash surrogate:

```sql
CREATE TABLE hub_customer (
  customer_hk CHAR(32) PRIMARY KEY,  -- hash of business key
  customer_id VARCHAR NOT NULL,
  load_dts TIMESTAMP NOT NULL,
  record_source VARCHAR NOT NULL
);
```

**Link** — many-to-many or associative relationships:

```sql
CREATE TABLE link_customer_order (
  customer_order_hk CHAR(32) PRIMARY KEY,
  customer_hk CHAR(32) REFERENCES hub_customer,
  order_hk CHAR(32) REFERENCES hub_order,
  load_dts TIMESTAMP NOT NULL,
  record_source VARCHAR NOT NULL
);
```

**Satellite** — descriptive attributes, Type 2 history by load date:

```sql
CREATE TABLE sat_customer_details (
  customer_hk CHAR(32),
  load_dts TIMESTAMP,
  hash_diff CHAR(32),  -- change detection
  email VARCHAR,
  country_code VARCHAR,
  PRIMARY KEY (customer_hk, load_dts)
);
```

New attribute values append rows; nothing overwritten. Full audit trail preserved.

## Hash keys and change detection

Business keys hash to fixed-width surrogates (`MD5` or `SHA256` truncated — pick one standard). Satellites compare `hash_diff` of payload columns; insert only when diff changes — avoids noise from identical reloads.

```sql
-- Pseudoload pattern
INSERT INTO sat_customer_details
SELECT
  customer_hk,
  current_timestamp AS load_dts,
  md5(concat(email, '|', country_code)) AS hash_diff,
  email,
  country_code
FROM staging_customers s
JOIN hub_customer h ON s.customer_id = h.customer_id
WHERE NOT EXISTS (
  SELECT 1 FROM sat_customer_details sat
  WHERE sat.customer_hk = h.customer_hk
    AND sat.hash_diff = md5(concat(s.email, '|', s.country_code))
  ORDER BY load_dts DESC LIMIT 1
);
```

Tools like dbtvault automate this boilerplate.

## Loading parallelism

Hubs and links load independently per source — no giant `dim_customer` merge blocking nightly batch. Source A and Source B ingest in parallel; conflicts surface in satellites with `record_source` lineage instead of silent overwrites.

Late-arriving facts link to hubs even if satellite history arrives later — store unknown keys in ghost records or staging per policy.

## Raw vault → business vault → marts

Three-layer stack:

1. **Raw vault** — source-faithful integration
2. **Business vault** — survivorship rules, conformed customer, status logic
3. **Information marts** — star schemas for BI

Analysts query marts, not raw vault. Data engineers refactor marts without re-ingesting sources when vault history is intact.

## Vault vs Kimball tradeoffs

| Data Vault | Star schema |
|---|---|
| Schema agility | Query simplicity |
| Audit and lineage by design | Faster analyst onboarding |
| More tables, joins | Fewer tables |
| Parallel source onboarding | Conformed dimensions upfront |

Vault shines in banking, healthcare, telecom — regulated, multi-source chaos. A single-product SaaS with one Postgres may not justify the ceremony.

## Pitfalls

**PIT and bridge tables** needed for point-in-time queries — vault isn't analyst-ready raw.

**Over-hubbing** — not every column deserves a hub.

**Skipping business vault** — exposing raw vault to BI recreates chaos with extra joins.

**Hash algorithm changes** — migration nightmare; standardize day one.

## Tooling

- dbtvault (automate DDL and load SQL)
- WhereScape, VaultSpeed (commercial)
- Custom dbt macros with discipline

Measure success: source onboarding time, reprocessing scope after logic bugs (should shrink), not raw table count.

## Hub-link-satellite loading patterns

Standard load order for Data Vault 2.0:

```
1. Stage raw source → staging tables (truncate/reload each run)
2. Load Hubs — insert new business keys only (idempotent)
3. Load Links — insert new relationships only
4. Load Satellites — insert new rows when hashdiff changes
5. Business Vault — apply rules, PIT tables, bridge tables
6. Information Mart — dimensional models for BI
```

```sql
-- Satellite load: insert only when attributes changed
INSERT INTO sat_customer_details
SELECT h.hub_customer_hash_key, s.load_date, s.hashdiff, s.name, s.email
FROM staging_customer s
JOIN hub_customer h ON h.customer_id = s.customer_id
LEFT JOIN sat_customer_details existing
  ON existing.hub_customer_hash_key = h.hub_customer_hash_key
  AND existing.hashdiff = MD5(CONCAT(s.name, s.email))
WHERE existing.hub_customer_hash_key IS NULL;  -- new or changed only
```

Never UPDATE satellites — append only. History is the audit trail.

## Point-in-Time (PIT) tables

PIT tables flatten satellite history for BI consumption:

```sql
-- PIT table: one row per hub key per snapshot date
CREATE TABLE pit_customer AS
SELECT
  h.hub_customer_hash_key,
  pit.snapshot_date,
  sat_name.name,
  sat_email.email,
  sat_address.city
FROM hub_customer h
CROSS JOIN snapshot_dates pit
LEFT JOIN sat_customer_name sat_name
  ON sat_name.hub_customer_hash_key = h.hub_customer_hash_key
  AND sat_name.load_date = (SELECT MAX(load_date) FROM sat_customer_name
    WHERE hub_customer_hash_key = h.hub_customer_hash_key
    AND load_date <= pit.snapshot_date)
-- repeat for each satellite
```

PIT tables are rebuilt periodically — they're in the Business Vault layer, not raw vault.

## When Data Vault is overkill

- Single source, stable schema, no audit requirement → Kimball star schema is faster to deliver
- Team <3 engineers without dedicated data modeling discipline → vault structure won't be maintained
- Real-time analytics primary use case → vault's insert-only history adds latency
- Source systems already provide reliable audit trails → vault duplicates existing capability

Data Vault shines when integrating 10+ source systems with changing schemas and regulatory audit requirements.

## Failure modes

- **Hub for every column** — over-normalization; hubs only for true business keys
- **Satellite updates instead of inserts** — destroys history; append-only violated
- **Raw vault exposed to BI** — analysts drown in joins; business vault layer skipped
- **Hash algorithm change mid-project** — all keys invalid; standardize SHA-256 day one
- **No PIT tables** — BI queries scan full satellite history every time

## Production checklist

- Hash algorithm standardized (SHA-256) before first load
- Satellites append-only — no UPDATE statements
- Business vault layer between raw vault and BI
- PIT tables rebuilt on schedule for common snapshot dates
- Source onboarding documented with hub/link/satellite mapping template
- dbtvault or AutomateDV for repeatable DDL generation

## Resources

- [Data Vault Alliance — official methodology](https://www.datavaultalliance.com/)
- [dbtvault documentation](https://dbtvault.readthedocs.io/)
- [Building a Scalable Data Warehouse with Data Vault 2.0 (Linstedt & Olschimke)](https://www.datavaultalliance.com/books/)
- [AutomateDV (formerly dbtvault) GitHub](https://github.com/Datavault-UK/automate-dv)
- [Kimball vs Data Vault comparison (Scalefree)](https://www.scalefree.com/blog/data-vault/)
