---
title: "Self-Critique Loops for LLMs"
slug: "llm-reflection-self-critique"
description: "Improve LLM output quality with self-critique loops: generate-critique-revise patterns, when reflection helps, budget controls, and production architectures that don't triple your latency."
datePublished: "2025-01-02"
dateModified: "2025-01-02"
tags: ["AI", "LLM", "AI Agents", "Machine Learning"]
keywords: "LLM self-critique, reflection prompting, generate critique revise, Reflexion agent, LLM output improvement"
faq:
  - q: "Do self-critique loops always improve output quality?"
    a: "No. They help on complex reasoning, code generation, and multi-constraint tasks where first drafts often miss requirements. They often hurt simple tasks — the critique introduces errors or verbosity. Route to reflection only when a complexity classifier scores above threshold, not on every request."
  - q: "How many critique iterations should I run?"
    a: "One generate-critique-revise cycle catches most fixable errors. Two cycles show diminishing returns and 3x cost. Cap at 2 iterations with a quality gate — if the critic scores the draft above 4/5, skip revision. Never loop unbounded."
  - q: "Should the critic be the same model as the generator?"
    a: "Use the same or stronger model for critique. A weaker critic misses errors the generator made. Common pattern: strong model critiques, mid-tier model generates (or vice versa for cost — mid generates, strong critiques only when needed). Never use the exact same prompt for both roles."
---

The first draft SQL query ran but scanned 40 million rows. A second pass — asking the model to review its own output against the requirements — caught the missing WHERE clause. Self-critique loops (generate → critique → revise) exploit the fact that LLMs are often better at finding flaws in existing text than producing perfect text initially. The technique works, but blind application triples latency and cost on tasks that didn't need a second opinion.

## The Reflexion pattern

```
Draft → Critic evaluates → [pass? return draft] → Revise → [optional: re-critic] → Final
```

```python
async def generate_with_reflection(
    task: str,
    max_iterations: int = 2,
) -> str:
    draft = await llm.complete(GENERATE_PROMPT, task)

    for i in range(max_iterations):
        critique = await llm.complete(CRITIC_PROMPT, f"Task: {task}\n\nDraft: {draft}")
        score = parse_score(critique)

        if score >= PASS_THRESHOLD:
            break

        draft = await llm.complete(REVISE_PROMPT, f"""
            Task: {task}
            Previous draft: {draft}
            Critique: {critique}
            Produce an improved version addressing all critique points.
        """)

    return draft
```

Three prompts, up to three LLM calls. Budget accordingly.

## Writing effective critic prompts

Bad critic: "Review this and suggest improvements."

Good critic:

```
Evaluate the draft against these criteria:
1. Does the SQL query include a WHERE clause filtering by date?
2. Are all requested columns present?
3. Will this query use indexes (no full table scans)?
4. Is the output format valid JSON?

Score each criterion pass/fail. Overall score 1-5.
If any criterion fails, explain specifically what's wrong.
Do NOT rewrite — only critique.
```

Separate critique from revision. Combined "critique and fix" prompts produce shallow self-praise.

## When reflection helps

| Task type | Reflection value |
|-----------|-----------------|
| SQL/code generation | High — catches syntax and logic errors |
| Multi-constraint writing | High — checks requirements checklist |
| Factual Q&A with context | Low — critique can't fix retrieval gaps |
| Classification | Low — usually overthinking |
| Creative writing | Mixed — can homogenize voice |

Use a router:

```python
if complexity_score(task) >= 4 or task_type in REFLECTION_TASKS:
    return await generate_with_reflection(task)
return await llm.complete(DIRECT_PROMPT, task)
```

## Cost and latency control

Reflection multiplies cost. Mitigate:

- **Cheap critic** — GPT-4o-mini for critique, GPT-4o only for revision of failed drafts
- **Early exit** — critic passes → return immediately
- **Async reflection** — return draft to user, refine in background for next interaction (rare)
- **Token caps** — limit critique to 200 tokens, revision to same length as original

```python
REFLECTION_BUDGET = RunBudget(max_cost_usd=0.05, max_steps=3)
```

## Self-critique in agents

Agents naturally reflect when tool results contradict their plan:

```python
async def agent_step(state: AgentState) -> AgentState:
    action = await planner.decide(state)
    result = await execute_tool(action)

    if result contradicts state.plan:
        reflection = await llm.complete(
            "Why did this fail? What should we try next?",
            context=[state.plan, action, result],
        )
        state.add_reflection(reflection)

    return state
```

Store reflections in agent memory — they prevent repeating failed approaches (see Reflexion paper).

## Evaluating reflection value

A/B test on your task set:

- Measure quality delta (human eval or LLM judge)
- Measure cost and latency increase
- Reflection is worth it when: `quality_gain × value_per_quality_point > additional_cost`

If quality improves 5% at 200% cost, route selectively.

## Failure modes

- **Self-reinforcing errors** — critic validates a wrong draft because both share the same blind spots
- **Verbosity inflation** — each revision adds length without adding substance
- **Infinite improvement** — model keeps "improving" without converging; hard cap iterations
- **Critique hallucination** — critic inventing requirements not in the original task

Ground the critic in explicit criteria from the original task, not open-ended evaluation.

## Reflexion pattern for agents

Store reflections in memory to prevent repeating failed approaches:

```python
class ReflexionAgent:
    def __init__(self, llm, memory: list[str] = []):
        self.llm = llm
        self.memory = memory  # accumulated reflections

    async def run(self, task: str, max_attempts: int = 3) -> str:
        for attempt in range(max_attempts):
            context = "\n".join(self.memory) if self.memory else ""
            action = await self.llm.generate(f"Task: {task}\n\nPast reflections:\n{context}")
            result = await self.execute(action)

            if result.success:
                return result.output

            reflection = await self.llm.generate(
                f"Task: {task}\nAction taken: {action}\nResult: {result.error}\n"
                f"What went wrong and what should be tried differently?"
            )
            self.memory.append(reflection)

        raise MaxAttemptsExceeded(task)
```

Each failed attempt generates a reflection stored in memory. Subsequent attempts explicitly avoid repeated mistakes.

## Self-critique with explicit rubric

Open-ended critique produces vague feedback — use structured rubrics:

```python
CRITIQUE_RUBRIC = """
Evaluate the draft response against these criteria (score 1-5 each):
1. Addresses the original question completely
2. Uses only information from provided context (no hallucination)
3. Appropriate length and tone
4. Correct format (JSON/markdown as specified)

Draft: {draft}
Original task: {task}
Context: {context}

Return JSON: {{"scores": {{...}}, "must_fix": ["..."], "revised": "..."}}
"""
```

Critic returns specific fixes, not generic "could be better." Revised output included in same call — one round-trip for critique + revision.

## Cost-benefit analysis for reflection

Reflection adds 2–3× token cost — route selectively:

```python
REFLECTION_ROUTING = {
    "high_stakes": True,   # legal, medical, financial — always reflect
    "complex_task": True,  # multi-step reasoning — reflect on failure
    "simple_faq": False,   # single-turn FAQ — skip reflection
    "creative": False,     # creative writing — reflection reduces quality
}

def should_reflect(task_type: str, first_attempt_quality: float) -> bool:
    if REFLECTION_ROUTING.get(task_type, False):
        return True
    return first_attempt_quality < 0.7  # reflect only if first attempt weak
```

Measure quality delta vs cost increase per task type before enabling reflection globally.

## Failure modes

- **Self-reinforcing errors** — critic and generator share blind spots; both miss same error
- **Infinite revision loop** — model keeps revising without converging; hard cap at 3 iterations
- **Critique hallucination** — critic inventing requirements not in original task
- **Reflection on every request** — 3× cost for simple tasks with no quality benefit
- **No rubric grounding** — vague critique produces vague revision

## Production checklist

- Reflection capped at 3 iterations maximum
- Critic grounded in explicit rubric from original task criteria
- Reflection routed selectively by task type and first-attempt quality
- Reflexion memory stored across attempts within session
- Quality delta vs cost measured per task type before global enable
- A/B test: reflection on vs off for each feature before production deploy

## Resources

- [Reflexion paper (Shinn et al.)](https://arxiv.org/abs/2303.11366)
- [Self-Refine: Iterative Refinement with Self-Feedback](https://arxiv.org/abs/2303.17651)
- [CRITIC: LLM self-correction with tool-interactive critiquing](https://arxiv.org/abs/2305.11738)
- [LangGraph reflection agent example](https://langchain-ai.github.io/langgraph/tutorials/reflection/reflection/)
- [DSPy assert-and-refine modules](https://dspy-docs.vercel.app/)
