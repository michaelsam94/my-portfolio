---
title: "Data Quality Expectations in Analytics Pipelines"
slug: "rag-data-quality-expectations"
description: "Expectations-as-code for agent pipelines—validating RAG chunks, tool schemas, eval datasets, and streaming ingestion with Great Expectations-style contracts that block bad data before it poisons retrieval."
datePublished: "2025-03-01"
dateModified: "2026-07-17"
tags: ["AI", "Rag", "Data"]
keywords: "data quality, expectations, great expectations, agent pipeline, rag validation, schema contracts, data tests, eval datasets"
faq:
  - q: "Why do agent systems need data quality expectations beyond API validation?"
    a: "API schemas validate shape at request time, but agent pipelines accumulate silent drift: empty chunks in vector indexes, mislabeled eval rows, stale tool definitions in caches, and partial JSON from streaming parsers. Expectations assert statistical and semantic properties on datasets over time—catching drift before users see wrong answers."
  - q: "Where should expectations run in an agent stack?"
    a: "At document ingest before embedding, after ETL into feature stores, on eval dataset publishes, and on nightly snapshots of production conversation analytics. Fail fast on ingest for hard constraints; warn on distribution drift for soft constraints."
  - q: "How is this different from LLM eval scores?"
    a: "Eval scores measure model behavior on prompts. Data quality expectations measure input data integrity—missing fields, duplicate IDs, toxic content ratios, token length outliers. Bad data can make a good model look broken; expectations separate data incidents from model regressions."
---
The retrieval quality dashboard looked healthy: p95 latency normal, zero 5xx. Yet answer accuracy dropped eighteen points over two weeks. Root cause was not the reranker—it was a document ingest job that started emitting **empty text chunks** when a upstream HTML parser changed. Null checks existed on the API, but nobody asserted `chunk_text.length > 50` on the embedding batch. Data quality expectations would have blocked the partition before vectors hit the index.

Agent platforms are data pipelines wearing a chat UI. RAG corpora, tool registries, session exports, labeling queues, and offline eval sets all need **contracts** that go beyond JSON Schema. This post covers expectations-as-code: declarative rules, where to enforce them, and how to wire failures into application-specific runbooks.

## From schema validation to expectations

| Layer | Validates | Example |
|-------|-----------|---------|
| JSON Schema | Structure | `tool.parameters.type == object` |
| Business rules | Domain logic | `effective_date <= expiry_date` |
| **Expectations** | Distribution & completeness | `null_rate(chunk_text) < 0.01` |
| Eval harness | Model output quality | `faithfulness > 0.8` |

Schemas fail a single bad row at the API. Expectations fail **batches** and **trends**—better suited to nightly ingest and analytics tables.

## Core expectation types for production data

**Completeness.** Required fields populated: `session_id`, `embedding`, `source_uri`, `tool_name`.

**Uniqueness.** No duplicate `(document_id, chunk_index)` in vector ingest batches.

**Range and length.** Token counts within bounds; `chunk_text` between 100 and 8192 characters for your embedding model.

**Referential integrity.** Every `tool_id` in conversation logs exists in `tool_registry` snapshot for that date.

**Distribution.** Language mix, toxicity score histogram, percentage of chunks tagged `legal` vs `support`—alert when KL divergence from baseline exceeds threshold.

**Freshness.** `max(updated_at)` in index metadata within 24 hours of source CMS.

```python
# expectations/rag_chunks.py
import great_expectations as gx

context = gx.get_context()

suite = context.add_expectation_suite("rag_chunks_v2")

suite.add_expectation(
    gx.expectations.ExpectColumnValuesToNotBeNull(column="chunk_text")
)
suite.add_expectation(
    gx.expectations.ExpectColumnValueLengthsToBeBetween(
        column="chunk_text", min_value=50, max_value=12000
    )
)
suite.add_expectation(
    gx.expectations.ExpectCompoundColumnsToBeUnique(
        column_list=["document_id", "chunk_index"]
    )
)
suite.add_expectation(
    gx.expectations.ExpectColumnValuesToBeInSet(
        column="content_type", value_set=["html", "pdf", "markdown", "slack"]
    )
)
```

Run the suite in a checkpoint against each Parquet partition landing in `s3://agent-corpus/staging/`.

## Checkpoint actions and agent ingest gates

```python
# pipelines/ingest_gate.py
from great_expectations.checkpoint import Checkpoint

checkpoint = Checkpoint(
    name="rag_staging_gate",
    run_name_template="rag_%Y%m%d",
    data_asset_name="staging_chunks",
    expectation_suite_name="rag_chunks_v2",
    action_list=[
        {"name": "store_validation_result"},
        {
            "name": "update_data_docs",
            "site_names": ["team_site"],
        },
    ],
)

result = checkpoint.run(batch_request=batch)

if not result.success:
    metrics.emit("ingest.blocked", tags={"suite": "rag_chunks_v2"})
    notify_slack("#agent-data", f"Ingest blocked: {result.statistics}")
    raise IngestBlockedError(result.run_id)

embed_and_promote(batch)
```

Blocked ingest should **not** silently leave stale index—either continue serving previous partition with a banner in admin UI or route to keyword fallback if business rules allow.

## Tool registry and eval dataset expectations

Tool definitions are data products. Broken schemas surface as runtime tool-call errors—expensive and user-visible.

```yaml
# expectations/tool_registry.yaml
expectation_suite_name: tool_registry_daily
expectations:
  - type: expect_column_values_to_not_be_null
    kwargs: { column: name }
  - type: expect_column_values_to_be_unique
    kwargs: { column: tool_id }
  - type: expect_column_values_to_match_json_schema
    kwargs:
      column: parameters_json
      json_schema:
        type: object
        required: [type, properties]
  - type: expect_table_row_count_to_be_between
    kwargs: { min_value: 1, max_value: 500 }
```

Eval datasets need stricter rules—wrong labels poison regression decisions:

```python
def validate_eval_row(row: dict) -> list[str]:
    errors = []
    if not row.get("expected_tools"):
        errors.append("missing expected_tools for tool-use eval")
    if row.get("label") not in ALLOWED_LABELS:
        errors.append(f"invalid label {row.get('label')}")
    if len(row.get("prompt", "")) < 10:
        errors.append("prompt too short")
    return errors
```

Publish eval sets only after batch expectation checkpoint passes; version with git tag `eval-v2025.03.02`.

## Custom expectations for application-specific semantics

Generic null checks miss domain failures. Implement custom expectations:

```python
# expectations/custom/valid_markdown_links.py
from great_expectations.expectations.expectation import ColumnMapExpectation
from great_expectations.execution_engine import PandasExecutionEngine
import re

class ExpectChunkMarkdownLinksResolvable(ColumnMapExpectation):
    """Flag markdown links that are clearly malformed before embed."""

    map_metric = "column_values.chunk_links_valid"
    success_keys = ("mostly",)

    @staticmethod
    def _validate_link(value: str) -> bool:
        if not value:
            return True
        links = re.findall(r"\]\(([^)]+)\)", value)
        return all(link.startswith(("http://", "https://", "/")) for link in links)
```

Register with Great Expectations or your internal validator; share across ingest and CMS export jobs.

## Observability: data quality as metrics

Emit validation results to Prometheus/Datadog:

```python
for result in validation_results:
    tags = [f"expectation:{result.expectation_type}", f"suite:{suite_name}"]
    metrics.gauge("data_quality.expectation.success", 1 if result.success else 0, tags)
    if not result.success:
        metrics.increment("data_quality.expectation.failure", tags)
```

Dashboard panels:

- Pass rate by suite over 7 days
- Top failing expectations
- Rows quarantined vs promoted
- Correlation between ingest failures and answer-quality eval drops

Separate **data incident** alerts from **model regression** alerts—on-call runbooks differ.

## Streaming and micro-batch validation

Conversation analytics often stream through Kafka. Full GE checkpoints on unbounded streams need windowing:

```python
# micro_batch every 5 minutes
def validate_window(df_window):
    result = suite.run(batch_data=df_window, result_format="SUMMARY")
    if result.statistics["unsuccessful_expectations"] > 0:
        dead_letter.publish(df_window.filter(failed_mask))
    else:
        warehouse.merge(df_window)
```

For tool-call JSON parsed from streaming LLM output, validate **after** repair heuristics but **before** persistence—malformed tool args should not enter training exports.

## Testing expectations themselves

Meta-tests prevent silent suite rot:

```python
def test_suite_catches_empty_chunks():
    bad_batch = pd.DataFrame({"chunk_text": ["", "ok " * 30], "document_id": ["a", "b"], "chunk_index": [0, 0]})
    result = checkpoint.run(batch_request=make_batch(bad_batch))
    assert not result.success
    assert any("ExpectColumnValuesToNotBeNull" in str(f) for f in result.run_results)
```

When changing embedding models, update length expectations and re-baseline distribution tests—document in migration checklist.

## Organizational patterns

**Data contracts between teams.** CMS team owns `rag_chunks_v2` suite; agent team owns `tool_registry_daily`. Producers fix upstream; consumers do not patch bad rows locally without audit.

**Versioned suites.** `rag_chunks_v2` → `v3` when adding `tenant_id` column—never mutate expectations in place without version bump.

**Documentation site.** GE Data Docs or internal MkDocs render latest validation results for PM and compliance—not just engineers.

## Failure modes and honest tradeoffs

**Over-blocking.** Too-strict expectations halt ingest during benign CMS experiments. Use warning severity for distribution drift; blocking only for integrity (null IDs, duplicates).

**Under-sampling.** Validating 1% of rows misses rare PII column swaps. Stratified sampling by `content_type` and full validation on new sources for first 30 days.

**Latency.** Synchronous GE on large Parquet files slows ingest—run lightweight critical expectations inline, full suite async before promote.

## Conversation analytics expectations

Production traffic generates tables engineers query for product decisions—`daily_tool_usage`, `session_outcomes`, `retrieval_miss_rate`. These tables inherit the same drift problems as RAG ingest. Add expectations that mirror how PMs actually slice data:

```python
suite.add_expectation(
    gx.expectations.ExpectColumnValuesToBeBetween(
        column="tool_success_rate",
        min_value=0.0,
        max_value=1.0,
    )
)
suite.add_expectation(
    gx.expectations.ExpectColumnPairValuesAToBeGreaterThanB(
        column_A="ended_at", column_B="started_at"
    )
)
```

Alert when `retrieval_miss_rate` jumps more than three standard deviations from a fourteen-day rolling baseline—often the first signal that corpus quality degraded before eval harness runs. Tie checkpoint failures to agent feature flags: disable auto-ingest for a source CMS when its partition fails twice in twenty-four hours while keeping read path on last-good snapshot.

Document every expectation in plain language for non-engineers: "No chunk may be shorter than fifty characters" is auditable; `ExpectColumnValueLengthsToBeBetween(min_value=50)` is not. Link Data Docs to the on-call runbook entry for ingest blocked so whoever gets paged knows whether to rollback CMS, pause embed jobs, or widen a threshold with approval. Review suite pass rates in weekly data standups the same way you review model eval regressions.

## Closing

Data quality expectations turn pipelines from hope-and-monitor into contract-driven systems: empty chunks never embed, broken tool schemas never reach production registries, and eval datasets cannot ship with mislabeled rows. Pair API validation with batch checkpoints at ingest gates, emit validation metrics beside model evals, and block promotion when integrity fails. When answer quality moves, check data expectations first—often the model is fine and the corpus is not.

## Resources

- [Great Expectations documentation](https://docs.greatexpectations.io/)
- [dbt tests vs custom data quality](https://docs.getdbt.com/docs/build/data-tests)
- [Monte Carlo: Data observability patterns](https://www.montecarlodata.com/blog-what-is-data-observability/)
- [Google PAIR: Data Cards for datasets](https://pair.withgoogle.com/guidebook/chapters/data-collection/data-cards/)
- [OpenLineage for pipeline metadata](https://openlineage.io/)
