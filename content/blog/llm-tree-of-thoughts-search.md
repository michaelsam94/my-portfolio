---
title: "Tree-of-Thoughts Reasoning"
slug: "llm-tree-of-thoughts-search"
description: "Improve LLM reasoning on complex problems with Tree-of-Thoughts: branching exploration, evaluation, and search strategies beyond linear chain-of-thought."
datePublished: "2025-04-14"
dateModified: "2025-04-14"
tags: ["AI", "LLM", "Reasoning", "Prompting"]
keywords: "Tree of Thoughts LLM, ToT reasoning, chain of thought vs tree of thought, LLM search reasoning, branching reasoning prompts"
faq:
  - q: "When does Tree-of-Thoughts outperform chain-of-thought?"
    a: "ToT helps on problems where early reasoning steps determine the final answer and wrong early steps cannot be recovered — math word problems, logic puzzles, planning tasks, and multi-step decision problems. For straightforward Q&A or tasks where any reasonable reasoning path reaches the correct answer, chain-of-thought is simpler and cheaper."
  - q: "How much more expensive is Tree-of-Thoughts compared to a single CoT pass?"
    a: "Cost depends on branching factor and search depth. With 3 branches per step and 4 reasoning steps, you generate 3 + 9 + 27 + 27 = 66 partial thoughts plus evaluations — roughly 10–30× a single CoT call. Use ToT selectively on hard problems, not as a default for every request."
  - q: "Can I implement ToT without custom search code?"
    a: "Simple ToT with generate-and-evaluate loops works in 50 lines of Python with any LLM API. Full tree search with backtracking requires more code but libraries like LangGraph can model the search as a state graph. Start with a flat generate-evaluate-select loop before building a full tree."
---

Chain-of-thought prompting asks the model to reason step by step in a single linear pass. That works when the first reasonable approach happens to be correct. It fails when the problem requires exploring alternatives — a math puzzle where step two can branch three ways, a planning task where an early decision closes off better paths, or a code debugging scenario where the obvious hypothesis is wrong.

Tree-of-Thoughts (ToT) treats reasoning as search. The model generates multiple candidate thoughts at each step, evaluates them, and explores the most promising branches — backtracking when a path dead-ends.

## Chain-of-thought vs. tree-of-thoughts

**Chain-of-thought (CoT):**
```
Question → Thought 1 → Thought 2 → Thought 3 → Answer
           (single path, no backtracking)
```

**Tree-of-thoughts (ToT):**
```
Question → [Thought 1a, 1b, 1c] → evaluate → select 1b
         → [Thought 2a, 2b]       → evaluate → select 2a
         → [Thought 3a, 3b, 3c]   → evaluate → select 3c
         → Answer
```

CoT is one path. ToT explores a tree and picks the best leaf.

## The ToT algorithm

1. **Generate:** produce k candidate next thoughts from the current state.
2. **Evaluate:** score each candidate (self-evaluation by the LLM or heuristic).
3. **Search:** select the best candidate(s) to expand using BFS, DFS, or beam search.
4. **Repeat** until a terminal state (answer found or max depth reached).

```python
def tree_of_thoughts(problem: str, max_depth: int = 4, branches: int = 3) -> str:
    root = ThoughtState(problem=problem, path=[])

    for depth in range(max_depth):
        candidates = []
        for state in current_states:
            thoughts = generate_thoughts(state, k=branches)
            for thought in thoughts:
                score = evaluate_thought(state, thought)
                candidates.append(ThoughtState(
                    problem=problem,
                    path=state.path + [thought],
                    score=score,
                ))

        # Keep top candidates for next depth
        current_states = sorted(candidates, key=lambda s: s.score, reverse=True)[:branches]

        # Check for terminal states
        for state in current_states:
            if is_solution(state):
                return state.path[-1]

    return best_state(current_states).path[-1]
```

## Generating candidate thoughts

Prompt the model to produce diverse reasoning steps:

```python
GENERATE_PROMPT = """
Problem: {problem}
Current reasoning path:
{path}

Generate {k} distinct next reasoning steps. Each step should explore
a different approach. Format as numbered list.
"""

def generate_thoughts(state: ThoughtState, k: int = 3) -> list[str]:
    response = llm.generate(GENERATE_PROMPT.format(
        problem=state.problem,
        path=format_path(state.path),
        k=k,
    ), temperature=0.7)
    return parse_numbered_list(response)
```

Higher temperature during generation encourages diverse branches. Lower temperature during evaluation keeps scoring consistent.

## Evaluating thoughts

The model evaluates its own partial solutions:

```python
EVALUATE_PROMPT = """
Problem: {problem}
Reasoning so far: {path}
Proposed next step: {thought}

Rate this reasoning step on a scale of 1-10 for:
- Progress toward the solution
- Logical correctness
- Likelihood of leading to the correct answer

Return only the integer score.
"""

def evaluate_thought(state: ThoughtState, thought: str) -> float:
    response = llm.generate(EVALUATE_PROMPT.format(
        problem=state.problem,
        path=format_path(state.path),
        thought=thought,
    ), temperature=0.0)
    return float(response.strip())
```

Self-evaluation is imperfect but correlates with actual quality on structured problems. For math, you can add programmatic checks — does the partial calculation produce valid intermediate numbers?

## Search strategies

**Breadth-first search (BFS):** expand all candidates at each depth, keep top-k. Best for problems where the correct path is not obvious early.

**Depth-first search (DFS):** commit to one branch, backtrack on failure. Cheaper (fewer evaluations) but can miss better paths.

**Beam search:** keep the top-b branches at each step. Practical default for most applications.

```python
def beam_search_tot(problem: str, beam_width: int = 3, max_depth: int = 4) -> str:
    beam = [ThoughtState(problem=problem, path=[], score=0.0)]

    for depth in range(max_depth):
        all_candidates = []
        for state in beam:
            if is_solution(state):
                return extract_answer(state)
            thoughts = generate_thoughts(state, k=beam_width)
            for thought in thoughts:
                score = evaluate_thought(state, thought)
                all_candidates.append(ThoughtState(
                    problem=problem,
                    path=state.path + [thought],
                    score=score,
                ))
        beam = sorted(all_candidates, key=lambda s: s.score, reverse=True)[:beam_width]

    return extract_answer(beam[0])
```

## When ToT is worth the cost

| Problem type | CoT sufficient? | ToT recommended? |
|-------------|----------------|-----------------|
| Factual Q&A | Yes | No |
| Simple arithmetic | Yes | No |
| Multi-step math word problems | Sometimes | Yes |
| Logic puzzles / riddles | No | Yes |
| Planning and scheduling | No | Yes |
| Code debugging (multiple hypotheses) | Sometimes | Yes |
| Creative writing | Yes | No |

Use ToT as a routing decision: attempt CoT first, fall back to ToT when confidence is low or the problem matches known hard categories.

## Practical cost control

ToT can consume 10–30× the tokens of a single CoT call. Mitigate:

- **Limit branches:** 2–3 candidates per step, not 5–10.
- **Limit depth:** 3–4 reasoning steps covers most problems.
- **Early termination:** stop when any branch reaches high confidence.
- **Cache evaluations:** identical partial paths should not be re-evaluated.
- **Route selectively:** only invoke ToT for classified hard problems.

```python
def adaptive_reasoning(problem: str) -> str:
    difficulty = classify_difficulty(problem)
    if difficulty == "easy":
        return chain_of_thought(problem)
    elif difficulty == "medium":
        return chain_of_thought(problem, self_consistency=3)
    else:
        return beam_search_tot(problem, beam_width=3, max_depth=4)
```

## Common production mistakes

Teams get tree of thoughts search wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

LLM features around tree of thoughts search break in production when prompts assume deterministic output, context windows are sized for dev datasets, or token costs are never budgeted per user session. Always log prompt hash, model version, and latency—not raw prompts with PII.

## Resources

- [Tree of Thoughts paper (Yao et al., 2023)](https://arxiv.org/abs/2305.10601)
- [LangGraph for stateful reasoning workflows](https://langchain-ai.github.io/langgraph/)
- [Chain-of-thought prompting (Wei et al., 2022)](https://arxiv.org/abs/2201.11903)
- [Self-consistency improves chain of thought (Wang et al., 2022)](https://arxiv.org/abs/2203.11171)
- [Guidance library for structured generation in reasoning loops](https://github.com/guidance-ai/guidance)
