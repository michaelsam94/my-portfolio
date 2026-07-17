---
title: "Temperature and Sampling, Demystified"
slug: "llm-temperature-sampling-explained"
description: "Understand LLM temperature, top-p, top-k, and frequency penalty: what each parameter actually does to token probabilities and when to use which setting."
datePublished: "2025-04-02"
dateModified: "2026-07-17"
tags:
keywords: "LLM temperature explained, top-p nucleus sampling, top-k sampling, frequency penalty, LLM sampling parameters, temperature 0 vs 1"
faq:
  - q: "Should I always use temperature 0 for deterministic output?"
    a: "Temperature 0 (greedy decoding) picks the highest-probability token at each step. Use it for extraction, classification, code generation, and any task where consistency matters. It can produce repetitive text in open-ended generation because the model never explores alternative phrasings."
  - q: "What is the difference between top-p and top-k?"
    a: "Top-k limits sampling to the K highest-probability tokens (e.g., top 40). Top-p (nucleus sampling) dynamically selects the smallest set of tokens whose cumulative probability exceeds P (e.g., 0.9). Top-p adapts to the distribution shape — narrow when the model is confident, wide when uncertain."
  - q: "Why does my output change between identical requests at temperature 0?"
    a: "True greedy decoding at temperature 0 should be deterministic on the same hardware and software version. Non-determinism usually comes from floating-point operation ordering in batched inference, different CUDA kernels, or the provider not actually using temperature 0 internally. Set a fixed seed where supported for reproducibility."
---
You set temperature to 0.7 because the blog post said to. Your chatbot gives different answers to the same question. Your extraction pipeline occasionally returns malformed JSON. Your creative writing feature produces the same three opening sentences repeatedly.

Temperature and sampling parameters control how the model chooses the next token from its probability distribution. They are not magic knobs — they are precise mathematical operations on logits. Understanding what they do lets you pick the right settings per task instead of copying defaults.

## From logits to tokens

At each generation step, the model outputs a logit vector — one score per token in the vocabulary (50,000–128,000 entries). Sampling converts logits to a token:

```
logits → softmax(temperature) → filter (top-k/top-p) → sample → next token
```

Every parameter in that pipeline changes which tokens are eligible and how likely each is.

## Temperature: sharpening or flattening the distribution

Temperature divides logits before softmax:

```python
import torch
import torch.nn.functional as F

logits = model_output  # shape: [vocab_size]

def sample_with_temperature(logits, temperature=1.0):
    scaled = logits / temperature
    probs = F.softmax(scaled, dim=-1)
    return torch.multinomial(probs, num_samples=1)

# temperature = 0.01 ≈ greedy (always picks highest)
# temperature = 1.0  = model's natural distribution
# temperature = 2.0  = flatter, more random
```

| Temperature | Effect | Use case |
|------------|--------|----------|
| 0.0 | Greedy — always highest probability token | Extraction, SQL, classification, code |
| 0.1–0.3 | Low randomness, mostly deterministic | Factual Q&A, summarization |
| 0.5–0.7 | Moderate creativity | Chatbots, general assistants |
| 0.8–1.0 | High diversity | Creative writing, brainstorming |
| > 1.0 | Very flat distribution, often incoherent | Rarely useful in production |

At temperature 0, `"The capital of France is"` almost always produces `" Paris"`. At temperature 1.5, it might produce `" Lyon"`, `" a city"`, or `" located"`.

## Top-k: hard cap on candidates

Top-k keeps only the K highest-probability tokens and zeroes the rest:

```python
def top_k_filter(logits, k=40):
    top_k_values, top_k_indices = torch.topk(logits, k)
    filtered = torch.full_like(logits, float('-inf'))
    filtered.scatter_(0, top_k_indices, top_k_values)
    return filtered
```

With k=40, the model samples only from the 40 most likely tokens. This prevents low-probability tail tokens (which cause hallucinations and incoherence) from being selected.

Typical values: k=40–50 for general use, k=1 equivalent to greedy.

## Top-p (nucleus sampling): adaptive filtering

Top-p selects the smallest token set whose cumulative probability exceeds p:

```python
def top_p_filter(logits, p=0.9):
    sorted_logits, sorted_indices = torch.sort(logits, descending=True)
    cumulative_probs = torch.cumsum(F.softmax(sorted_logits, dim=-1), dim=-1)

    # Remove tokens beyond the nucleus
    sorted_indices_to_remove = cumulative_probs > p
    sorted_indices_to_remove[1:] = sorted_indices_to_remove[:-1].clone()
    sorted_indices_to_remove[0] = False

    filtered = logits.clone()
    filtered[sorted_indices[sorted_indices_to_remove]] = float('-inf')
    return filtered
```

When the model is confident (one token at 95%), top-p=0.9 might keep only 2–3 tokens. When uncertain (flat distribution), it might keep 500+. This adaptiveness is why top-p generally outperforms fixed top-k.

Most production configs use top-p=0.9 or top-p=0.95 combined with temperature.

## Frequency and presence penalties

These modify logits based on tokens already generated:

```python
# Conceptual: reduce logit of tokens that already appeared
for token_id in generated_tokens:
    if token_id in logits:
        count = generated_tokens.count(token_id)
        logits[token_id] -= frequency_penalty * count  # per occurrence
        logits[token_id] -= presence_penalty              # flat penalty if seen
```

- **Frequency penalty** (0.0–2.0): reduces probability proportional to how many times a token already appeared. Higher values discourage repetition.
- **Presence penalty** (0.0–2.0): flat reduction if the token appeared at all. Encourages topic diversity.

Use frequency penalty 0.3–0.6 when the model repeats phrases in long outputs. Avoid high penalties on extraction tasks — they can suppress valid repeated field names.

## Recommended settings by task

```python
TASK_CONFIGS = {
    "extraction": {"temperature": 0.0, "top_p": 1.0},
    "classification": {"temperature": 0.0, "top_p": 1.0},
    "code_generation": {"temperature": 0.2, "top_p": 0.95},
    "summarization": {"temperature": 0.3, "top_p": 0.9},
    "chatbot": {"temperature": 0.7, "top_p": 0.9},
    "creative_writing": {"temperature": 0.9, "top_p": 0.95, "frequency_penalty": 0.5},
}
```

Do not tune these in isolation. Temperature and top-p interact — low temperature with low top-p is nearly greedy; high temperature with high top-p produces chaos.

## Reproducibility in production

For deterministic pipelines:

```python
# OpenAI
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[...],
    temperature=0,
    seed=42,  # fixed seed for reproducibility
)

# vLLM
params = SamplingParams(temperature=0.0, seed=42)
```

Log the full sampling configuration with every request. When output quality shifts after a model update, you need to know exactly which parameters were used to isolate whether the model or the settings changed.

## Resources

- [The Curious Case of Neural Text Degeneration (top-p paper)](https://arxiv.org/abs/1904.09751)
- [OpenAI API sampling parameters](https://platform.openai.com/docs/api-reference/chat/create)
- [Hugging Face generation strategies guide](https://huggingface.co/docs/transformers/en/generation_strategies)
- [vLLM SamplingParams documentation](https://docs.vllm.ai/en/latest/dev/sampling_params.html)
- [Holtzman et al. on repetition in neural text generation](https://arxiv.org/abs/1904.09751)

## Production notes for LLM stacks

When `llm-temperature-sampling-explained` sits on an inference or RAG path, treat user prompts and retrieved chunks as untrusted input. Log correlation IDs and policy decisions—not raw prompts—in production telemetry. Gate risky operations behind explicit authorization at the gateway, not inside ad-hoc tool handlers.

Roll out changes with shadow mode first: record what **would** have happened under the new rule without blocking traffic. Compare deny rates, latency impact, and false positives for at least one business week before enforcing. Pair enforcement with a runbook entry: symptom, dashboard, rollback (feature flag or config), and owner.

Load-test with production-shaped concurrency. LLM workloads burst differently from CRUD APIs—tail latency and token throttling dominate. If `temperature and sampling, demystified` protects an invariant (security, billing, data residency), prove the invariant with an automated test that fails CI when someone removes the check.

## What teams get wrong

Teams copy a reference architecture without matching their compliance tier, then discover in audit that logs, backups, or support exports reintroduced the data they thought they had eliminated. Another pattern: shipping the demo integration without idempotency, then fighting duplicate side effects when clients retry on model timeouts.

Document the tradeoff you chose—strictness vs recall, cost vs quality, sync vs async—and the metric that tells you if the choice still holds six months later.
