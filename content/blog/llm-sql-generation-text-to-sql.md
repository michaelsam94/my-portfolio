---
title: "Text-to-SQL That Actually Works"
slug: "llm-sql-generation-text-to-sql"
description: "Build reliable text-to-SQL pipelines with schema grounding, few-shot examples, execution feedback, and validation — not just prompt engineering."
datePublished: "2025-03-21"
dateModified: "2026-07-17"
tags:
keywords: "text to SQL LLM, natural language to SQL, SQL generation accuracy, schema grounding, Vanna AI, SQL validation LLM"
faq:
  - q: "Why do LLMs hallucinate columns and tables in SQL generation?"
    a: "Models trained on public SQL corpora guess schema elements from pattern matching rather than your actual database. Without explicit schema context in the prompt, the model invents plausible-sounding column names. Schema grounding — injecting your real DDL into the prompt — is the single highest-impact fix."
  - q: "Should I fine-tune a model or use prompt engineering for text-to-SQL?"
    a: "Start with prompt engineering plus schema grounding and few-shot examples. Fine-tuning on your specific schema and query patterns helps when you have 500+ validated question-SQL pairs and need sub-second latency without large prompts. Most teams never need fine-tuning if schema context is good."
  - q: "How do I prevent the LLM from running destructive SQL?"
    a: "Never execute LLM-generated SQL directly against production. Use a read-only database role, parse and validate the AST before execution (allow only SELECT), set query timeouts, and require human approval for anything that modifies data."
---
Every text-to-SQL demo works perfectly on the conference stage. Then you deploy it against your actual database — with 47 tables, abbreviated column names, and three schemas merged from acquisitions — and accuracy drops from 90% to 40%. The model confidently joins `orders` to `customers` on a column that does not exist and selects `total_amount` when the field is called `order_total_cents`.

Text-to-SQL that works in production is not a prompt trick. It is a pipeline: schema grounding, example selection, generation, validation, execution, and error recovery.

## Schema grounding: show the model your actual database

The model cannot generate correct SQL for tables it has never seen. Inject schema context into every request:

```python
schema_context = """
CREATE TABLE orders (
    order_id UUID PRIMARY KEY,
    customer_id UUID REFERENCES customers(customer_id),
    order_total_cents INTEGER NOT NULL,
    status VARCHAR(20) CHECK (status IN ('pending', 'shipped', 'delivered', 'cancelled')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE customers (
    customer_id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(100),
    signup_date DATE
);
"""

prompt = f"""Given this schema:
{schema_context}

Write a PostgreSQL query to answer: {user_question}
Return only the SQL, no explanation."""
```

For large schemas (100+ tables), retrieve only relevant tables rather than dumping the entire DDL:

```python
# Embed table/column descriptions, retrieve top-k relevant tables
relevant_tables = schema_retriever.search(user_question, top_k=5)
schema_context = format_ddl(relevant_tables)
```

Tools like Vanna.ai automate this retrieval step by embedding your schema and past successful queries.

## Few-shot examples from your query history

Generic few-shot examples help format. Domain-specific examples help semantics:

```python
examples = """
Q: How many orders were placed last month?
SQL: SELECT COUNT(*) FROM orders WHERE created_at >= date_trunc('month', CURRENT_DATE - INTERVAL '1 month') AND created_at < date_trunc('month', CURRENT_DATE);

Q: Top 5 customers by total spend?
SQL: SELECT c.name, SUM(o.order_total_cents) AS total FROM customers c JOIN orders o ON c.customer_id = o.customer_id WHERE o.status != 'cancelled' GROUP BY c.customer_id, c.name ORDER BY total DESC LIMIT 5;
"""
```

Select examples dynamically based on similarity to the current question. A question about "revenue by month" should retrieve examples involving date truncation and aggregation, not examples about user counts.

## Generation with constrained output

Use grammar-constrained decoding to guarantee syntactically valid SQL:

```python
import outlines

sql_grammar = """
?start: select_stmt
select_stmt: "SELECT" column_list "FROM" table_name where_clause? group_clause? order_clause? limit_clause?
...
"""

generator = outlines.generate.cfg(model, sql_grammar)
sql = generator(f"Schema: {schema_context}\nQuestion: {user_question}")
```

Even without grammar constraints, instruct the model to return only SQL with clear delimiters and parse the response strictly.

## Validation before execution

Never trust raw LLM output. Validate in layers:

```python
import sqlparse
from sqlglot import parse_one, exp

def validate_sql(sql: str, allowed_tables: set[str]) -> str:
    parsed = parse_one(sql, dialect="postgres")

    # Reject anything that is not a SELECT
    if not isinstance(parsed, exp.Select):
        raise ValueError("Only SELECT queries allowed")

    # Check all referenced tables exist
    for table in parsed.find_all(exp.Table):
        if table.name not in allowed_tables:
            raise ValueError(f"Unknown table: {table.name}")

    return sql
```

Additional safeguards:

- **Read-only role:** connect with a DB user that has SELECT-only grants.
- **Query timeout:** `SET statement_timeout = '5s'` prevents runaway queries.
- **Row limit:** append `LIMIT 1000` if the query lacks one.
- **Cost estimation:** run `EXPLAIN` before `EXECUTE` for expensive-looking queries.

## Execution feedback loop

When SQL fails, feed the error back to the model:

```python
MAX_RETRIES = 3

for attempt in range(MAX_RETRIES):
    sql = generate_sql(schema_context, question, previous_errors)
    try:
        validate_sql(sql, allowed_tables)
        result = db.execute(sql)
        return result
    except Exception as e:
        previous_errors.append({"sql": sql, "error": str(e)})

raise SQLGenerationError("Failed after 3 attempts")
```

This self-correction loop fixes 60–70% of first-attempt failures. The model sees `ERROR: column "total_amount" does not exist` and adjusts to `order_total_cents`.

## Measuring accuracy on your schema

Build a golden eval set from real analyst questions:

```python
eval_set = [
    {"question": "Revenue last quarter", "expected_sql": "SELECT SUM(...)", "expected_result_hash": "abc123"},
    {"question": "Active users this week", "expected_sql": "SELECT COUNT(DISTINCT ...)", "expected_result_hash": "def456"},
]

def evaluate(pipeline, eval_set):
    correct = 0
    for item in eval_set:
        sql = pipeline.generate(item["question"])
        result = execute(sql)
        if hash_result(result) == item["expected_result_hash"]:
            correct += 1
    return correct / len(eval_set)
```

Track execution accuracy (does the query run and return correct results), not just exact SQL match. Two syntactically different queries that return the same result both pass.

## Common production mistakes

Teams get sql generation text to sql wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

LLM features around sql generation text to sql break in production when prompts assume deterministic output, context windows are sized for dev datasets, or token costs are never budgeted per user session. Always log prompt hash, model version, and latency—not raw prompts with PII.

## Debugging and triage workflow

When sql generation text to sql misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Vanna.ai — RAG-based text-to-SQL](https://vanna.ai/)
- [Spider benchmark for text-to-SQL](https://yale-lily.github.io/spider)
- [SQLGlot SQL parser and transpiler](https://github.com/tobymao/sqlglot)
- [DIN-SQL: Decomposed In-Context Learning (paper)](https://arxiv.org/abs/2304.03111)
- [Defog SQLCoder model](https://github.com/defog-ai/sqlcoder)
