---
title: "Summarizing Long Documents"
slug: "llm-summarization-long-documents"
description: "Summarize documents that exceed LLM context windows with map-reduce, hierarchical, and refine strategies — plus evaluation methods that catch quality regressions."
datePublished: "2025-03-29"
dateModified: "2026-07-17"
tags:
keywords: "long document summarization LLM, map reduce summarization, hierarchical summary, document chunking LLM, abstractive summarization production"
faq:
  - q: "What is the best strategy for summarizing a 200-page document?"
    a: "Hierarchical summarization works best for very long documents: chunk into sections, summarize each section, then summarize the section summaries. Map-reduce (summarize all chunks independently, then combine) is simpler but loses cross-chunk context. For documents under 50 pages, a single pass with a long-context model may suffice if quality is acceptable."
  - q: "How do I prevent summaries from losing critical details?"
    a: "Use extractive pre-selection to identify key sentences before abstractive summarization. Instruct the model to preserve numbers, dates, names, and decisions explicitly. Evaluate with entity recall — check whether named entities from the source appear in the summary."
  - q: "Should I use the same model for chunk summaries and final synthesis?"
    a: "Not necessarily. A smaller, faster model works fine for chunk-level summaries where the task is compression. Use a larger model for the final synthesis step where coherence and prioritization matter. This saves cost without sacrificing final quality."
---
Legal teams need a two-page brief from a 300-page contract. Support agents need the key facts from a customer's 40-message email thread. Research analysts need takeaways from a 60-page report. All of these exceed what you can stuff into a single prompt — even with 128K context windows, quality degrades on very long inputs and you pay for every token.

Long document summarization is an orchestration problem. You chunk the source, summarize each piece, combine the pieces, and evaluate whether the result actually captured what mattered.

## Map-reduce summarization

The simplest multi-step approach:

1. **Map:** split the document into chunks, summarize each independently.
2. **Reduce:** combine chunk summaries into a final summary.

```python
def map_reduce_summarize(text: str, chunk_size: int = 4000) -> str:
    chunks = split_text(text, max_tokens=chunk_size, overlap=200)
    chunk_summaries = [
        llm.generate(f"Summarize this section concisely:\n\n{chunk}")
        for chunk in chunks
    ]
    combined = "\n\n".join(f"Section {i+1}: {s}" for i, s in enumerate(chunk_summaries))
    final = llm.generate(
        f"Synthesize these section summaries into a cohesive executive summary:\n\n{combined}"
    )
    return final
```

**Pros:** simple, parallelizable, works with any context window size.
**Cons:** cross-chunk references get lost. If page 10 introduces a term that page 80 resolves, the map step never connects them.

Use map-reduce when sections are relatively independent — quarterly reports by division, meeting notes by agenda item.

## Hierarchical summarization

For documents with nested structure, mirror the hierarchy:

```python
def hierarchical_summarize(sections: list[Section]) -> str:
    # Level 1: summarize each section
    section_summaries = [summarize(section.text) for section in sections]

    # Level 2: group sections into chapters, summarize groups
    chapters = group_sections(sections, group_size=5)
    chapter_summaries = [
        llm.generate(f"Summarize these related sections:\n{format_summaries(group)}")
        for group in chapters
    ]

    # Level 3: final executive summary
    return llm.generate(
        f"Write an executive summary from these chapter summaries:\n"
        f"{format_summaries(chapter_summaries)}"
    )
```

Each level compresses further. A 300-page document might go: 60 sections → 12 chapter summaries → 1 executive summary. The hierarchy preserves more structural context than flat map-reduce.

## Refine strategy for narrative coherence

The refine approach processes chunks sequentially, updating a running summary:

```python
def refine_summarize(text: str, chunk_size: int = 4000) -> str:
    chunks = split_text(text, max_tokens=chunk_size)
    running_summary = ""

    for chunk in chunks:
        running_summary = llm.generate(f"""
            Current summary: {running_summary}

            New section to incorporate:
            {chunk}

            Update the summary to include relevant information from the new section.
            Keep the summary concise. Preserve all key facts, dates, and names.
        """)
    return running_summary
```

Refine maintains a single evolving summary, so later chunks can correct or extend earlier content. Trade-off: sequential processing, no parallelism, and error accumulation — a bad update in chunk 5 propagates through chunks 6–20.

## Prompt design for faithful summaries

Generic "summarize this" prompts produce generic summaries. Be specific:

```python
SUMMARIZATION_PROMPT = """
Summarize the following document for a {audience} audience.

Requirements:
- Maximum {max_words} words
- Preserve all dollar amounts, dates, and proper nouns exactly
- Highlight decisions made and action items assigned
- Note any conditions, exceptions, or caveats
- Use bullet points for lists of 3+ items

Document:
{text}
"""
```

For legal and financial documents, add:

```
- Do not paraphrase numerical values
- Flag any ambiguous language verbatim with [AMBIGUOUS: "..."]
- Include section references for key claims
```

## Handling context window limits smartly

Even with 128K+ models, very long documents benefit from chunking:

| Document size | Recommended approach |
|--------------|---------------------|
| < 8K tokens | Single-pass summarization |
| 8K–32K tokens | Map-reduce with 4K chunks |
| 32K–128K tokens | Hierarchical with section detection |
| > 128K tokens | Hierarchical + extractive pre-selection |

Extractive pre-selection reduces input before abstractive summarization:

```python
def extractive_filter(text: str, top_k: int = 50) -> str:
    sentences = split_sentences(text)
    scores = rank_sentences(sentences, query="key facts decisions outcomes")
    top_sentences = sorted(scores, key=lambda x: x.score, reverse=True)[:top_k]
    return " ".join(s.content for s in sorted(top_sentences, key=lambda x: x.position))
```

This sends only the most salient sentences to the LLM, reducing cost and noise.

## Evaluating summary quality

Automated metrics catch regressions when you change models or prompts:

```python
def evaluate_summary(source: str, summary: str, reference: str = None) -> dict:
    metrics = {}

    # Entity recall: are key entities preserved?
    source_entities = extract_entities(source)
    summary_entities = extract_entities(summary)
    metrics["entity_recall"] = len(source_entities & summary_entities) / len(source_entities)

    # Compression ratio
    metrics["compression_ratio"] = len(source.split()) / len(summary.split())

    # ROUGE against reference (if available)
    if reference:
        metrics["rouge_l"] = rouge_score(reference, summary)["rougeL"].fmeasure

    return metrics
```

Entity recall below 0.7 usually means the summary dropped important names, dates, or numbers. Pair automated metrics with periodic human review on a sample.

## Common production mistakes

Teams get summarization long documents wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

LLM features around summarization long documents break in production when prompts assume deterministic output, context windows are sized for dev datasets, or token costs are never budgeted per user session. Always log prompt hash, model version, and latency—not raw prompts with PII.

## Debugging and triage workflow

When summarization long documents misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [LangChain summarization strategies](https://python.langchain.com/docs/how_to/summarize/)
- [Map-reduce for LLM chains (original concept)](https://www.anthropic.com/research)
- [ROUGE evaluation metric paper](https://aclanthology.org/W04-1013/)
- [LongBench benchmark for long-context tasks](https://arxiv.org/abs/2308.14508)
- [Anthropic long context prompting guide](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/long-context-tips)
